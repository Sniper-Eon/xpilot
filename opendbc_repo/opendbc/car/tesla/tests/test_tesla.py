"""CarState failure cases:
CS1 stock Autosteer enabled no longer raises invalidLkasSetting (except MISSING_DAS_SETTINGS).
CS2 the SP extension changes the source invalidLkasSetting or another CarState field.
CS3 a stock ANGLE_CONTROL rise followed by DI_cruiseState STANDSTILL/ENABLED (or cruise
    already on) clears stockManeuver, so the host takes over during Autopark.
CS3b stockManeuver drops before 200ms of NONE, or stays set after that hold.
CS5 DAS_status bit 26 (DAS_autoparkWaitingForBrake) does not keep stockManeuver set, or
    bit 24 (DAS_autoparkReady) alone sets it.
CS4 a second vision Autopark after a cancelled one does not set stockManeuver again.
CC1 MADS/engaged openpilot that is not actuating stops sending 0x488/0x27D, leaving EPAS without
    DAS_steeringControl.
"""
import re
import unittest
from unittest.mock import patch

from opendbc.can import CANPacker
from opendbc.car import Bus, gen_empty_fingerprint
from opendbc.car.structs import CarParams, CarParamsSP
from opendbc.car.tesla.carstate import CarState
from opendbc.car.tesla.interface import CarInterface
from opendbc.car.tesla.fingerprints import FW_VERSIONS
from opendbc.car.tesla.radar_interface import RADAR_START_ADDR
from opendbc.car.tesla.values import CAR, DBC, CANBUS, TeslaFlags
from opendbc.sunnypilot.car.tesla.carstate_ext import CarStateExt
from opendbc.sunnypilot.car.tesla.values import TeslaFlagsSP

Ecu = CarParams.Ecu

# Fields prefixed unknown_* we observe structurally but don't know the meaning of.
# Only `platform` has evidence-backed semantic meaning (matches car_model in FW_VERSIONS).
#
# unknown_prefix is everything before the comma; we don't split it because we don't know what its
# parts mean, but observed shape is: <family>_<package>_<triplet> (<build>), e.g.
#   TeMYG4 _ Main     _ 0.0.0 (78)     or     TeM3 _ SP_XP002p2 _ 0.0.0 (23)
#   family   package    triplet build           family  package    triplet build
#
# After the comma, the version string decomposes into:
#   platform             : E/Y/X = car model (Model 3 / Y / X). The only field with known meaning.
#   variant_code         : differentiator WITHIN a platform — hardware/trim/calibration bits packed
#                          into <digit?><letters?><3-digit series>, e.g. '4HP015', '4003', 'L014',
#                          'PR003'. We don't fully know what the parts mean individually, but the
#                          whole string identifies a specific variant within the car model.
#   software_major/minor : numeric components after the first '.' — conventional release numbers.
#                          minor is optional (e.g. 'E4S014.27' has no minor).
#
# Suspected (not confirmed): for M3/MY, `TeM3_*` outer + no-leading-digit variant_code == HW3, and
# `TeMYG4_*` outer + leading-'4' variant_code == HW4 (the 'G4' in TeMYG4 likely denotes Gen 4).
#
# Example full parse of 'TeMYG4_Main_0.0.0 (78),E4HP015.05.0':
#   unknown_prefix='TeMYG4_Main_0.0.0 (78)'
#   platform=E  variant_code=4HP015  software_major=05  software_minor=0
FW_RE = re.compile(
  rb'^(?P<unknown_prefix>.+),' +
  rb'(?P<platform>[EYX])' +
  rb'(?P<variant_code>\d?[A-Z]*\d{3})' +
  rb'\.(?P<software_major>\d+)' +
  rb'(?:\.(?P<software_minor>\d+))?$'
)

PLATFORM_TO_CAR = {
  b'E': CAR.TESLA_MODEL_3,
  b'Y': CAR.TESLA_MODEL_Y,
  b'X': CAR.TESLA_MODEL_X,
}


class TestTeslaCarState(unittest.TestCase):
  def test_stock_autosteer_setting(self):
    update_ext = CarStateExt.update
    for candidate in CAR:
      for flags in (0, TeslaFlags.MISSING_DAS_SETTINGS):
        for vehicle_bus in (False, True):
          for autosteer in (0, 1):
            with self.subTest(candidate=candidate, flags=flags, vehicle_bus=vehicle_bus, autosteer=autosteer):
              CP = CarParams(carFingerprint=candidate.value, flags=int(flags))
              CP_SP = CarParamsSP(flags=TeslaFlagsSP.HAS_VEHICLE_BUS if vehicle_bus else 0)
              cs = CarState(CP, CP_SP)
              parsers = cs.get_can_parsers(CP, CP_SP)
              self.assertIn("DAS_autosteerEnabled", parsers[Bus.ap_party].vl["DAS_settings"])
              packer = CANPacker(DBC[candidate][Bus.party])
              parsers[Bus.ap_party].update([(0, [packer.make_can_msg("DAS_settings", CANBUS.autopilot_party,
                                                                   {"DAS_autosteerEnabled": autosteer})])])
              self.assertEqual(parsers[Bus.ap_party].vl["DAS_settings"]["DAS_autosteerEnabled"], autosteer)

              def check_update(state, ret, ret_sp, can_parsers):
                before = ret.to_dict()
                update_ext(state, ret, ret_sp, can_parsers)
                after = ret.to_dict()
                self.assertEqual(after, before, "CS2: SP extension preserves CarState")

              with patch.object(CarStateExt, "update", check_update):
                ret, _ = cs.update(parsers)
              self.assertEqual(ret.invalidLkasSetting, bool(autosteer and not flags), "CS1: stock Autosteer signal")


class TestTeslaStockManeuver(unittest.TestCase):
  def _cs(self):
    return CarState(CarParams(carFingerprint=CAR.TESLA_MODEL_Y.value), CarParamsSP())

  def _run(self, cs, frames, autopark="STANDBY", steer=0, cruise=False):
    out = None
    for _ in range(frames):
      out = cs.update_stock_maneuver(autopark, steer, cruise)
    return out

  def test_autopark_cruise_rise_stays_latched(self):
    # CS3/CS3b: ANGLE_CONTROL, then cruise (STANDSTILL or ENABLED). Cruise must not clear it.
    # A rise while cruise is already on latches too. NONE holds ~200ms, then releases.
    cs = self._cs()
    self.assertFalse(self._run(cs, 10))
    self.assertTrue(self._run(cs, 1, steer=1))
    self.assertTrue(self._run(cs, 1, steer=1, cruise=True))
    self.assertTrue(self._run(cs, 50, steer=1, cruise=True))
    self.assertTrue(self._run(cs, 19, steer=0, cruise=True))
    self.assertFalse(self._run(cs, 1, steer=0, cruise=True))
    # Cruise already on, steer rises again: still a stock maneuver.
    self.assertTrue(self._run(cs, 1, steer=1, cruise=True))
    self.assertTrue(self._run(cs, 5, steer=1, cruise=True))

  def test_autopark_latches_and_reenters(self):
    # CS4: vision Autopark keeps cruise off; a late engage tap does not end it.
    cs = self._cs()
    for attempt in range(3):
      with self.subTest(attempt=attempt):
        self.assertTrue(self._run(cs, 100, steer=1))
        self.assertTrue(self._run(cs, 5, steer=1, cruise=True))
        self.assertTrue(self._run(cs, 1, steer=1))
        # cancel: NONE, then the 200ms hold
        self.assertTrue(self._run(cs, 10, steer=0))
        self.assertFalse(self._run(cs, 15, steer=0))

  def test_cruise_enabled_stays_off_while_latched(self):
    # Host must not report cruise enabled while it sees the stock maneuver, so
    # pcmEnable is not emitted. Gear D and R, speed 0, STANDSTILL then ENABLED.
    gears = {"D": 4, "R": 2}
    for gear_name, gear in gears.items():
      with self.subTest(gear=gear_name):
        cs = self._cs()
        parsers = cs.get_can_parsers(cs.CP, cs.CP_SP)
        packer = CANPacker(DBC[cs.CP.carFingerprint][Bus.party])

        def push(cruise, steer, hold_gear=gear):
          parsers[Bus.party].update([(0, [
            packer.make_can_msg("DI_state", CANBUS.party, {"DI_cruiseState": cruise, "DI_autoparkState": 1}),
            packer.make_can_msg("DI_systemStatus", CANBUS.party, {"DI_gear": hold_gear, "DI_accelPedalPos": 0}),
            packer.make_can_msg("DI_speed", CANBUS.party, {"DI_vehicleSpeed": 0}),
            packer.make_can_msg("ESP_B", CANBUS.party, {"ESP_vehicleSpeed": 0, "ESP_vehicleStandstillSts": 1}),
          ])])
          parsers[Bus.ap_party].update([(0, [
            packer.make_can_msg("DAS_steeringControl", CANBUS.autopilot_party, {"DAS_steeringControlType": steer}),
          ])])
          return cs.update(parsers)[0]

        idle = push(0, 0)
        self.assertFalse(idle.stockManeuver)
        self.assertFalse(idle.cruiseState.enabled)
        latched = push(0, 1)
        self.assertTrue(latched.stockManeuver)
        standstill = push(3, 1)
        self.assertTrue(standstill.stockManeuver)
        self.assertFalse(standstill.cruiseState.enabled)
        enabled = push(2, 1)
        self.assertTrue(enabled.stockManeuver)
        self.assertFalse(enabled.cruiseState.enabled)
        for _ in range(19):
          held = push(2, 0)
          self.assertTrue(held.stockManeuver)
          self.assertFalse(held.cruiseState.enabled)
        released = push(2, 0)
        self.assertFalse(released.stockManeuver)
        self.assertTrue(released.cruiseState.enabled)

  def test_das_autopark_bit_latches_and_releases(self):
    # CS5: bit 26 alone latches. Cruise does not clear it. Bit off and steer NONE
    # use the same 200ms hold. A false request does not latch by itself.
    cs = self._cs()
    self.assertFalse(cs.update_stock_maneuver("STANDBY", 0, True, False))
    self.assertTrue(cs.update_stock_maneuver("STANDBY", 0, True, True))
    self.assertTrue(cs.update_stock_maneuver("STANDBY", 0, True, True))
    for _ in range(19):
      self.assertTrue(cs.update_stock_maneuver("STANDBY", 0, True, False))
    self.assertFalse(cs.update_stock_maneuver("STANDBY", 0, True, False))

  def test_das_status_signal_from_dbc(self):
    # The party DBC bit, not a raw guess: bit 26 sets stockManeuver, bit 24 does not.
    cs = self._cs()
    parsers = cs.get_can_parsers(cs.CP, cs.CP_SP)
    packer = CANPacker(DBC[cs.CP.carFingerprint][Bus.party])

    def push(waiting, ready, steer=0, cruise=2):
      parsers[Bus.party].update([(0, [
        packer.make_can_msg("DI_state", CANBUS.party, {"DI_cruiseState": cruise, "DI_autoparkState": 1}),
      ])])
      parsers[Bus.ap_party].update([(0, [
        packer.make_can_msg("DAS_steeringControl", CANBUS.autopilot_party, {"DAS_steeringControlType": steer}),
        packer.make_can_msg("DAS_status", CANBUS.autopilot_party, {
          "DAS_autoparkWaitingForBrake": waiting,
          "DAS_autoparkReady": ready,
        }),
      ])])
      return cs.update(parsers)[0]

    # The first update only registers DBC messages. Frames before that are not parsed.
    cs.update(parsers)
    ready = push(0, 1, steer=0, cruise=2)
    self.assertFalse(ready.stockManeuver)
    self.assertTrue(ready.cruiseState.enabled)
    latched = push(1, 0, steer=0, cruise=2)
    self.assertTrue(latched.stockManeuver)
    self.assertFalse(latched.cruiseState.enabled)
    self.assertEqual(1, int(parsers[Bus.ap_party].vl["DAS_status"]["DAS_autoparkWaitingForBrake"]))
    for _ in range(19):
      self.assertTrue(push(0, 0, steer=0, cruise=2).stockManeuver)
    released = push(0, 0, steer=0, cruise=2)
    self.assertFalse(released.stockManeuver)
    self.assertTrue(released.cruiseState.enabled)

  def test_summon_states(self):
    cs = self._cs()
    for state in CarState.SUMMON_STATES:
      with self.subTest(state=state):
        self.assertTrue(self._run(cs, 1, autopark=state, cruise=True))
        self.assertFalse(self._run(cs, 25))


class TestTeslaCarControllerLateralFrames(unittest.TestCase):
  def _send(self, enabled, mads, lat_active, maneuver=False, frames=20):
    from opendbc.car import structs
    from opendbc.car.tesla.carcontroller import CarController
    CP = CarInterface.get_non_essential_params(CAR.TESLA_MODEL_Y.value)
    CP_SP = CarParamsSP()
    cc = CarController(DBC[CP.carFingerprint], CP, CP_SP)

    class CS:
      hands_on_level = 0
      stock_maneuver = maneuver
      das_control = {'DAS_controlCounter': 0}
      das_control_mono_time = 0
      out = structs.CarState()

    CC = structs.CarControl(enabled=enabled, latActive=lat_active).as_reader()
    CC_SP = structs.CarControlSP()
    CC_SP.mads.enabled = mads
    addrs = []
    for i in range(frames):
      _, sends = cc.update(CC, CC_SP, CS, i * 10_000_000)
      addrs += [m[0] for m in sends]
    return addrs

  def test_engaged_keeps_lateral_frames(self):
    # CC1: car log 2026-11-27 12:18:51.87 -> 54.19, no 0x488/0x27D for 2.3s, EPAS EAC_ERROR_TMP_FAULT.
    for enabled, mads in ((True, False), (False, True)):
      with self.subTest(enabled=enabled, mads=mads):
        addrs = self._send(enabled, mads, lat_active=False)
        self.assertEqual(addrs.count(0x488), 10)
        self.assertEqual(addrs.count(0x27D), 2)

  def test_disengaged_or_maneuver_sends_no_lateral_frames(self):
    self.assertNotIn(0x488, self._send(False, False, lat_active=False))
    addrs = self._send(True, True, lat_active=True, maneuver=True)
    self.assertNotIn(0x488, addrs)
    self.assertNotIn(0x27D, addrs)


class TestTeslaFingerprint(unittest.TestCase):
  def test_fw_platform_code(self):
    # Every EPS FW must parse and its platform letter must match the car it's filed under.
    for car_model, ecus in FW_VERSIONS.items():
      for fw in ecus.get((Ecu.eps, 0x730, None), []):
        m = FW_RE.match(fw)

        assert m is not None, f"Unparsable FW: {fw}"
        assert PLATFORM_TO_CAR[m['platform']] == car_model, f"Platform letter {m['platform']!r} != {car_model.value}: {fw}"

  def test_radar_detection(self):
    # Test radar availability detection for cars with radar DBC defined
    for radar in (True, False):
      fingerprint = gen_empty_fingerprint()
      if radar:
        fingerprint[1][RADAR_START_ADDR] = 8
      CP = CarInterface.get_params(CAR.TESLA_MODEL_3, fingerprint, [], False, False, False)
      assert CP.radarUnavailable != radar

  def test_no_radar_car(self):
    # Model X doesn't have radar DBC defined, should always be unavailable
    for radar in (True, False):
      fingerprint = gen_empty_fingerprint()
      if radar:
        fingerprint[1][RADAR_START_ADDR] = 8
      CP = CarInterface.get_params(CAR.TESLA_MODEL_X, fingerprint, [], False, False, False)
      assert CP.radarUnavailable  # Always unavailable since no radar DBC
