#!/usr/bin/env python3
"""RX failure cases:
RX1 exempt UI_status2 at 2 Hz keeps safety_rx_checks_invalid true.
RX2 a non-exempt message configured below 10 Hz leaves RX checks valid.
Stock AP (xpilot EAP plugin) failure cases:
SA1 with TeslaSafetyFlagsSP.STOCK_AP a stock 0x488/0x2B9/0x27D frame from the AP ECU is not forwarded
    (stock Autosteer, TACC or EAC would stop), with or without openpilot longitudinal.
SA2 with STOCK_AP openpilot can still send 0x488/0x2B9/0x27D while controls are allowed.
SA3 without STOCK_AP stock 0x488 is forwarded while stock LKAS is off and openpilot is engaged
    (the flag leaks into the default mode).
Stock maneuver passthrough failure cases:
M1 while disengaged, a non-NONE 0x488 or 0x27D from bus 2 is dropped.
M2 while disengaged, openpilot TX of 0x488 NONE or 0x2B9 acc=4 is accepted.
M3 longitudinal mode starts in SP, or a disengaged 0x2B9 is not forwarded.
M4 DI_autoparkState STANDBY plus ANGLE_CONTROL does not enter a maneuver, or engage is accepted before type returns to NONE.
M5 a summon state in {2, 5, 7} does not block openpilot, or summon is ignored only because stock cruise is already on while openpilot lateral is inactive.
M6 mid-maneuver engage or a switch to SP is accepted.
M7 DI_cruiseState STANDSTILL then ENABLED about 70ms after a disengaged stock 0x488
   ANGLE rise (gear D or R, speed 0) clears the maneuver latch. openpilot then engages
   and its 0x488 overrides stock Autopark. Cruise cannot tell Autopark from Autosteer.
M7b the latch releases before stock 0x488 has been NONE for the 200ms hold, or it stays
   set after that hold so openpilot cannot engage once the maneuver is over.
M7c a steer rise while openpilot is disengaged is ignored because stock cruise is already on.
M8 engaged openpilot that is not transmitting 0x488 still blocks stock 0x488/0x27D, starving
   EPAS (car log 2026-11-27 12:18:51.87-54.19, EAC_INHIBITED / EAC_ERROR_TMP_FAULT latched).
M9 a second Autopark after a cancelled one does not latch again, or any latch is left over
   after the cancel (steer latch, maneuver hold, long owner).
M10 MADS three-finger lateral engage rejects openpilot 0x488, or the 0x2B9 owner handshake
   fails after Autopark was entered and cancelled.
"""
import random
import unittest
import numpy as np

from opendbc.car.lateral import get_max_angle_delta_vm, get_max_angle_vm
from opendbc.car.tesla.teslacan import get_steer_ctrl_type
from opendbc.car.tesla.values import CarControllerParams, TeslaSafetyFlags, TeslaFlags, CANBUS
from opendbc.car.tesla.carcontroller import get_safety_CP
from opendbc.car.structs import CarParams
from opendbc.car.vehicle_model import VehicleModel
from opendbc.can import CANDefine
import opendbc.safety.tests.common as common
from opendbc.safety.tests.libsafety import libsafety_py
from opendbc.safety.tests.common import CANPackerSafety, MAX_SPEED_DELTA, MAX_WRONG_COUNTERS, away_round, round_speed

from opendbc.sunnypilot.car.tesla.values import TeslaSafetyFlagsSP


MSG_DAS_steeringControl = 0x488
MSG_APS_eacMonitor = 0x27d
MSG_DAS_Control = 0x2b9
def round_angle(apply_angle, can_offset=0):
  apply_angle_can = (apply_angle + 1638.35) / 0.1 + can_offset
  # 0.49999_ == 0.5
  rnd_offset = 1e-5 if apply_angle >= 0 else -1e-5
  return away_round(apply_angle_can + rnd_offset) * 0.1 - 1638.35
class TestTeslaSafetyBase(common.CarSafetyTest, common.AngleSteeringSafetyTest, common.LongitudinalAccelSafetyTest):

  DBC = "tesla_model3_party"
  SAFETY_MODEL = CarParams.SafetyModel.tesla

  RELAY_MALFUNCTION_ADDRS = {0: (MSG_DAS_steeringControl, MSG_APS_eacMonitor)}
  # Disengaged openpilot forwards stock 0x488 and 0x27D, so they are not blacklisted.
  FWD_BLACKLISTED_ADDRS = {2: []}
  TX_MSGS = [[MSG_DAS_steeringControl, 0], [MSG_APS_eacMonitor, 0], [MSG_DAS_Control, 0]]

  STANDSTILL_THRESHOLD = 0.1
  GAS_PRESSED_THRESHOLD = 3

  # Angle control limits
  STEER_ANGLE_MAX = 360  # deg
  DEG_TO_CAN = 10

  # Tesla uses get_max_angle_delta_vm and get_max_angle_vm for real lateral accel and jerk limits
  # TODO: integrate this into AngleSteeringSafetyTest
  ANGLE_RATE_BP = None
  ANGLE_RATE_UP = None
  ANGLE_RATE_DOWN = None

  # Real time limits
  LATERAL_FREQUENCY = 50  # Hz

  # Long control limits
  MAX_ACCEL = 2.0
  MIN_ACCEL = -3.48
  INACTIVE_ACCEL = 0.0

  cnt_angle_cmd = 0

  def _get_steer_cmd_angle_max(self, speed):
    return get_max_angle_vm(max(speed, 1), self.VM, CarControllerParams)

  def setUp(self):
    super().setUp()
    self.VM = VehicleModel(get_safety_CP())
    self.define = CANDefine(self.DBC)
    self.acc_states = {d: v for v, d in self.define.dv["DAS_control"]["DAS_accState"].items()}
    self.autopark_states = {d: v for v, d in self.define.dv["DI_state"]["DI_autoparkState"].items()}
    self.active_autopark_states = [self.autopark_states[s] for s in (
      'STARTED', 'ACTIVE', 'COMPLETE', 'PAUSED', 'RESUMED', 'SELFPARK_STARTED')]
    self._maneuver_t = 0

    self.steer_control_types = {d: v for v, d in self.define.dv["DAS_steeringControl"]["DAS_steeringControlType"].items()}

  def _angle_cmd_msg(self, angle: float, state: bool | int, increment_timer: bool = True, bus: int = 0):
    # If FSD 14, translate steer control type to new flipped definition
    if self.safety.get_current_safety_param() & TeslaSafetyFlags.FSD_14:
      state = get_steer_ctrl_type(TeslaFlags.FSD_14, int(state))

    values = {"DAS_steeringAngleRequest": angle, "DAS_steeringControlType": int(state)}
    if increment_timer:
      self.safety.set_timer(self.cnt_angle_cmd * int(1e6 / self.LATERAL_FREQUENCY))
      self.__class__.cnt_angle_cmd += 1
    return self.packer.make_can_msg_safety("DAS_steeringControl", bus, values)

  def _angle_meas_msg(self, angle: float, hands_on_level: int = 0, eac_status: int = 1, eac_error_code: int = 0):
    values = {"EPAS3S_internalSAS": angle, "EPAS3S_handsOnLevel": hands_on_level,
              "EPAS3S_eacStatus": eac_status, "EPAS3S_eacErrorCode": eac_error_code}
    return self.packer.make_can_msg_safety("EPAS3S_sysStatus", 0, values)

  def _user_brake_msg(self, brake, quality_flag: bool = True):
    values = {"ESP_driverBrakeApply": 2 if brake else 1}
    if not quality_flag:
      values["ESP_driverBrakeApply"] = random.choice((0, 3))  # NotInit_orOff, Faulty_SNA
    return self.packer.make_can_msg_safety("ESP_status", 0, values)

  def _speed_msg(self, speed):
    values = {"DI_vehicleSpeed": speed * 3.6}
    return self.packer.make_can_msg_safety("DI_speed", 0, values)

  def _speed_msg_2(self, speed, quality_flag=True):
    values = {"ESP_vehicleSpeed": speed * 3.6, "ESP_wheelSpeedsQF": quality_flag}
    return self.packer.make_can_msg_safety("ESP_B", 0, values)

  def _vehicle_moving_msg(self, speed: float, quality_flag=True):
    values = {"ESP_vehicleStandstillSts": 1 if speed <= self.STANDSTILL_THRESHOLD else 0,
              "ESP_wheelSpeedsQF": quality_flag}
    return self.packer.make_can_msg_safety("ESP_B", 0, values)

  def _user_gas_msg(self, gas):
    values = {"DI_accelPedalPos": gas}
    return self.packer.make_can_msg_safety("DI_systemStatus", 0, values)

  def _pcm_status_msg(self, enable, autopark_state=0, cruise_state=None):
    if cruise_state is None:
      cruise_state = 2 if enable else 0
    values = {
      "DI_cruiseState": cruise_state,
      "DI_autoparkState": autopark_state,
    }
    return self.packer.make_can_msg_safety("DI_state", 0, values)

  def _gear_msg(self, gear):
    values = {"DI_gear": gear, "DI_accelPedalPos": 0}
    return self.packer.make_can_msg_safety("DI_systemStatus", 0, values)

  def _eac_msg(self, allow=1):
    values = {"APS_eacAllow": allow}
    return self.packer.make_can_msg_safety("APS_eacMonitor", 0, values)

  def _long_control_msg(self, set_speed, acc_state=0, jerk_limits=(0, 0), accel_limits=(0, 0), aeb_event=0, bus=0):
    values = {
      "DAS_setSpeed": set_speed,
      "DAS_accState": acc_state,
      "DAS_aebEvent": aeb_event,
      "DAS_jerkMin": jerk_limits[0],
      "DAS_jerkMax": jerk_limits[1],
      "DAS_accelMin": accel_limits[0],
      "DAS_accelMax": accel_limits[1],
    }
    return self.packer.make_can_msg_safety("DAS_control", bus, values)

  def _accel_msg(self, accel: float):
    # For common.LongitudinalAccelSafetyTest
    return self._long_control_msg(10, accel_limits=(accel, max(accel, 0)))

  def test_rx_hook(self):
    # counter check
    for msg_type in ("angle", "long", "speed", "speed_2"):
      # send multiple times to verify counter checks
      for i in range(10):
        if msg_type == "angle":
          msg = self._angle_cmd_msg(0, True, bus=2)
        elif msg_type == "long":
          msg = self._long_control_msg(0, bus=2)
        elif msg_type == "speed":
          msg = self._speed_msg(0)
        elif msg_type == "speed_2":
          msg = self._speed_msg_2(0)

        should_rx = i >= 5
        if not should_rx:
          # mess with checksums
          if msg_type == "angle":
            msg[0].data[3] = 0
          elif msg_type == "long":
            msg[0].data[7] = 0
          elif msg_type == "speed":
            msg[0].data[0] = 0
          elif msg_type == "speed_2":
            msg[0].data[7] = 0

        self.safety.set_controls_allowed(True)
        self.assertEqual(should_rx, self._rx(msg))
        self.assertEqual(should_rx, self.safety.get_controls_allowed())

      # Send static counters
      for i in range(MAX_WRONG_COUNTERS + 1):
        should_rx = i + 1 < MAX_WRONG_COUNTERS
        self.assertEqual(should_rx, self._rx(msg))
        self.assertEqual(should_rx, self.safety.get_controls_allowed())

  def test_vehicle_speed_measurements(self):
    # OVERRIDDEN: 79.1667 is the max speed in m/s
    self._common_measurement_test(self._speed_msg, 0, 285 / 3.6, 1,
                                  self.safety.get_vehicle_speed_min, self.safety.get_vehicle_speed_max)

  def test_rx_hook_speed_mismatch(self):
    # TODO: overridden because of custom rounding
    # Tesla relies on speed for lateral limits close to ISO 11270, so it checks two sources
    for speed in np.arange(0, 40, 0.5):
      # match signal rounding on CAN
      speed = away_round(speed / 0.08 * 3.6) * 0.08 / 3.6
      for speed_delta in np.arange(-5, 5, 0.1):
        speed_2 = max(speed + speed_delta, 0)
        speed_2 = away_round(speed_2 * 2 * 3.6) / 2 / 3.6

        # Set controls allowed in between rx since first message can reset it
        self.assertTrue(self._rx(self._speed_msg(speed)))
        self.safety.set_controls_allowed(True)
        self.assertTrue(self._rx(self._speed_msg_2(speed_2)))

        within_delta = abs(speed - speed_2) <= MAX_SPEED_DELTA
        self.assertEqual(self.safety.get_controls_allowed(), within_delta)

    # Test ESP_B quality flag
    for quality_flag in (True, False):
      self.safety.set_controls_allowed(True)
      self.assertTrue(self._rx(self._speed_msg(0)))
      self.assertEqual(quality_flag, self._rx(self._speed_msg_2(0, quality_flag=quality_flag)))
      self.assertEqual(quality_flag, self.safety.get_controls_allowed())

  def test_user_brake_quality_flag(self):
    for quality_flag in (True, False):
      msg = self._user_brake_msg(True, quality_flag=quality_flag)
      self.assertEqual(quality_flag, self._rx(msg))

  def test_steering_wheel_disengage(self):
    # Tesla disengages when the user forcibly overrides the locked-in angle steering control
    # Either when the hands on level is high, or if there is a high angle rate fault
    for hands_on_level in range(4):
      for eac_status in range(8):
        for eac_error_code in range(16):
          self.safety.set_controls_allowed(True)

          should_disengage = hands_on_level >= 3 or (eac_status == 0 and eac_error_code == 9)
          self.assertTrue(self._rx(self._angle_meas_msg(0, hands_on_level=hands_on_level, eac_status=eac_status,
                                                        eac_error_code=eac_error_code)))
          self.assertNotEqual(should_disengage, self.safety.get_controls_allowed())
          self.assertEqual(should_disengage, self.safety.get_steering_disengage_prev())

          # Should not recover
          self.assertTrue(self._rx(self._angle_meas_msg(0, hands_on_level=0, eac_status=1, eac_error_code=0)))
          self.assertNotEqual(should_disengage, self.safety.get_controls_allowed())
          self.assertFalse(self.safety.get_steering_disengage_prev())

  def _release_stock_maneuver(self):
    # 0x488 NONE and DI out of the summon states, then 200ms, before engage is accepted.
    self.safety.set_timer(self._maneuver_t)
    self._rx(self._angle_cmd_msg(0, False, bus=2, increment_timer=False))
    self._rx(self._pcm_status_msg(True, 0))
    self._maneuver_t += 200000
    self.safety.set_timer(self._maneuver_t)
    self._rx(self._angle_cmd_msg(0, False, bus=2, increment_timer=False))
    self._rx(self._pcm_status_msg(True, 0))
    step = int(1e6 / self.LATERAL_FREQUENCY)
    self.__class__.cnt_angle_cmd = max(self.cnt_angle_cmd, self._maneuver_t // step)

  def _confirm_autopark(self):
    # Move the safety timer forward so a later 200ms hold is not counted from t=0.
    step = int(1e6 / self.LATERAL_FREQUENCY)
    self.__class__.cnt_angle_cmd += 30
    t = self.cnt_angle_cmd * step
    self.safety.set_timer(t)
    self._maneuver_t = max(self._maneuver_t, t)

  def _now(self):
    # _angle_cmd_msg sets the timer to cnt * step and then increments cnt.
    step = int(1e6 / self.LATERAL_FREQUENCY)
    return max(self._maneuver_t, (self.cnt_angle_cmd - 1) * step)

  def _advance(self, us):
    t = self._now() + us
    self.safety.set_timer(t)
    self._maneuver_t = t
    step = int(1e6 / self.LATERAL_FREQUENCY)
    self.__class__.cnt_angle_cmd = max(self.cnt_angle_cmd, t // step + 1)

  def _start_vision_autopark(self):
    self._rx(self._pcm_status_msg(False, self.autopark_states["STANDBY"]))
    self._rx(self._angle_cmd_msg(0, state=self.steer_control_types["ANGLE_CONTROL"], bus=2))
    self._confirm_autopark()
    self._rx(self._angle_cmd_msg(0, state=self.steer_control_types["ANGLE_CONTROL"], bus=2, increment_timer=False))

  def _cancel_vision_autopark(self):
    # Driver cancel: DAS returns to NONE, DI stays STANDBY with cruise off, then the 200ms hold.
    self._advance(20000)
    self._rx(self._angle_cmd_msg(0, False, bus=2, increment_timer=False))
    self._rx(self._pcm_status_msg(False, self.autopark_states["STANDBY"]))
    self._advance(210000)
    self._rx(self._angle_cmd_msg(0, False, bus=2, increment_timer=False))
    self._rx(self._pcm_status_msg(False, self.autopark_states["STANDBY"]))

  def _assert_maneuver_owns_bus(self):
    self.assertEqual(0, self.safety.safety_fwd_hook(2, MSG_DAS_steeringControl))
    self.assertEqual(0, self.safety.safety_fwd_hook(2, MSG_APS_eacMonitor))
    self.assertEqual(0, self.safety.safety_fwd_hook(2, MSG_DAS_Control))
    self.assertFalse(self.safety.safety_tx_hook(self._angle_cmd_msg(0, False, increment_timer=False)))
    self.assertFalse(self.safety.safety_tx_hook(self._long_control_msg(0, acc_state=self.acc_states["ACC_ON"])))
    # Engage taps are refused for the whole maneuver.
    self._rx(self._pcm_status_msg(True, self.autopark_states["STANDBY"]))
    self.assertFalse(self.safety.get_controls_allowed())
    self._rx(self._pcm_status_msg(False, self.autopark_states["STANDBY"]))

  def test_autopark_reenter_after_cancel(self):
    # M9: Autopark, cancel, Autopark again. The second attempt must latch exactly like the first.
    for attempt in range(3):
      with self.subTest(attempt=attempt):
        self._start_vision_autopark()
        self._assert_maneuver_owns_bus()
        self._cancel_vision_autopark()
        # Cancelled and openpilot idle: stock frames still pass, openpilot still silent.
        self.assertFalse(self.safety.get_controls_allowed())
        self.assertEqual(0, self.safety.safety_fwd_hook(2, MSG_DAS_steeringControl))
        self.assertEqual(0, self.safety.safety_fwd_hook(2, MSG_APS_eacMonitor))
        self.assertFalse(self.safety.safety_tx_hook(self._angle_cmd_msg(0, False, increment_timer=False)))

    # After the last cancel nothing is left latched: engage works and openpilot owns lateral.
    self._rx(self._pcm_status_msg(True, self.autopark_states["STANDBY"]))
    self.assertTrue(self.safety.get_controls_allowed())
    self.assertTrue(self._tx(self._angle_cmd_msg(0, True)))
    self.assertEqual(-1, self.safety.safety_fwd_hook(2, MSG_DAS_steeringControl))
    self.assertEqual(-1, self.safety.safety_fwd_hook(2, MSG_APS_eacMonitor))

  def test_autopark_reenter_after_openpilot_engaged_between(self):
    # M9: Autopark, cancel, engage openpilot, disengage, then Autopark again.
    self._start_vision_autopark()
    self._cancel_vision_autopark()
    self._rx(self._pcm_status_msg(True, self.autopark_states["STANDBY"]))
    self.assertTrue(self.safety.get_controls_allowed())
    self.assertTrue(self._tx(self._angle_cmd_msg(0, True)))
    self._rx(self._pcm_status_msg(False, self.autopark_states["STANDBY"]))
    self.assertFalse(self.safety.get_controls_allowed())
    self._advance(20000)
    self._start_vision_autopark()
    self._assert_maneuver_owns_bus()

  def test_autopark_cruise_rise_stays_latched(self):
    # M7/M7b: gear D and R, speed 0, openpilot disengaged. Stock 0x488 rises to
    # ANGLE_CONTROL, then 70ms later DI_cruiseState goes STANDSTILL (3) then ENABLED (2).
    # That is Autopark on this car. The latch stays, engage is refused, openpilot
    # 0x488/0x27D stay off the bus even if controls_allowed is forced, and stock frames
    # are forwarded. After steer returns to NONE for the 200ms hold, engage works.
    gears = {d: v for v, d in self.define.dv["DI_systemStatus"]["DI_gear"].items()}
    angle = self.steer_control_types["ANGLE_CONTROL"]
    standby = self.autopark_states["STANDBY"]
    for gear_name in ("DI_GEAR_D", "DI_GEAR_R"):
      with self.subTest(gear=gear_name):
        self.setUp()
        self.__class__.cnt_angle_cmd = 0
        self.assertEqual(1, self._rx(self._speed_msg(0)))
        self.assertEqual(1, self._rx(self._speed_msg_2(0)))
        self.assertEqual(1, self._rx(self._vehicle_moving_msg(0)))
        self.assertEqual(1, self._rx(self._gear_msg(gears[gear_name])))
        self.assertEqual(1, self._rx(self._pcm_status_msg(False, standby)))
        self.assertFalse(self.safety.get_controls_allowed())

        self.assertEqual(1, self._rx(self._angle_cmd_msg(0, state=angle, bus=2)))
        self._advance(70000)
        self.assertEqual(1, self._rx(self._angle_cmd_msg(0, state=angle, bus=2, increment_timer=False)))
        self.assertEqual(1, self._rx(self._pcm_status_msg(False, standby, cruise_state=3)))
        self.assertFalse(self.safety.get_controls_allowed())
        self.assertFalse(self.safety.get_controls_allowed_lateral())
        self.assertEqual(1, self._rx(self._pcm_status_msg(False, standby, cruise_state=2)))
        self.assertFalse(self.safety.get_controls_allowed())

        self.safety.set_controls_allowed(True)
        self.safety.set_controls_allowed_lateral(True)
        self.assertFalse(self._tx(self._angle_cmd_msg(0, False, increment_timer=False)))
        self.assertFalse(self._tx(self._angle_cmd_msg(0, True, increment_timer=False)))
        self.assertFalse(self._tx(self._angle_cmd_msg(20, True, increment_timer=False)))
        self.assertFalse(self._tx(self._eac_msg()))
        self.assertEqual(0, self.safety.safety_fwd_hook(2, MSG_DAS_steeringControl))
        self.assertEqual(0, self.safety.safety_fwd_hook(2, MSG_APS_eacMonitor))

        self.assertEqual(1, self._rx(self._pcm_status_msg(False, standby, cruise_state=2)))
        self.assertFalse(self.safety.get_controls_allowed())
        self.assertFalse(self.safety.get_controls_allowed_lateral())

        # NONE starts the hold. 100ms later the latch is still set.
        self._advance(20000)
        self.assertEqual(1, self._rx(self._angle_cmd_msg(0, False, bus=2, increment_timer=False)))
        self.assertEqual(1, self._rx(self._pcm_status_msg(False, standby, cruise_state=2)))
        self.assertFalse(self.safety.get_controls_allowed())
        self._advance(100000)
        self.assertEqual(1, self._rx(self._angle_cmd_msg(0, False, bus=2, increment_timer=False)))
        self.assertEqual(1, self._rx(self._pcm_status_msg(False, standby, cruise_state=2)))
        self.assertFalse(self.safety.get_controls_allowed())
        self.assertFalse(self._tx(self._angle_cmd_msg(0, True, increment_timer=False)))

        # Past 200ms of NONE, ENABLED engages and openpilot owns lateral again.
        self._advance(120000)
        self.assertEqual(1, self._rx(self._angle_cmd_msg(0, False, bus=2, increment_timer=False)))
        self.assertEqual(1, self._rx(self._pcm_status_msg(False, standby, cruise_state=2)))
        self.assertTrue(self.safety.get_controls_allowed())
        self.assertTrue(self._tx(self._angle_cmd_msg(0, True)))
        self.assertTrue(self._tx(self._eac_msg()))
        self.assertEqual(-1, self.safety.safety_fwd_hook(2, MSG_DAS_steeringControl))
        self.assertEqual(-1, self.safety.safety_fwd_hook(2, MSG_APS_eacMonitor))

  def test_disengaged_steer_rise_latches_with_cruise_already_on(self):
    # M7c: stock cruise already ENABLED does not make a disengaged steer rise into Autosteer.
    standby = self.autopark_states["STANDBY"]
    self._rx(self._pcm_status_msg(True, standby))
    self.assertTrue(self.safety.get_controls_allowed())
    self.safety.set_controls_allowed(False)
    self._rx(self._angle_cmd_msg(0, state=self.steer_control_types["ANGLE_CONTROL"], bus=2))
    self._rx(self._pcm_status_msg(False, standby))
    self._rx(self._pcm_status_msg(True, standby))
    self.assertFalse(self.safety.get_controls_allowed())
    self.assertFalse(self._tx(self._angle_cmd_msg(0, True, increment_timer=False)))
    self.assertEqual(0, self.safety.safety_fwd_hook(2, MSG_DAS_steeringControl))
    self.assertEqual(0, self.safety.safety_fwd_hook(2, MSG_APS_eacMonitor))

  def test_engaged_without_openpilot_steer_tx_forwards_stock(self):
    # M8: engaged but openpilot has not sent 0x488 yet (or stopped): stock frames keep EPAS fed.
    for lateral_only in (False, True):
      with self.subTest(lateral_only=lateral_only):
        self.setUp()
        if lateral_only:
          self.safety.set_mads_params(True, False, False)
          self.safety.set_controls_allowed_lateral(True)
        else:
          self.safety.set_controls_allowed(True)
        self.assertEqual(0, self.safety.safety_fwd_hook(2, MSG_DAS_steeringControl))
        self.assertEqual(0, self.safety.safety_fwd_hook(2, MSG_APS_eacMonitor))
        self.assertTrue(self._tx(self._angle_cmd_msg(0, False)))
        self.assertEqual(-1, self.safety.safety_fwd_hook(2, MSG_DAS_steeringControl))
        self.assertEqual(-1, self.safety.safety_fwd_hook(2, MSG_APS_eacMonitor))
        # 40ms without a frame is jitter; 60ms means openpilot stopped.
        self._advance(40000)
        self.assertEqual(-1, self.safety.safety_fwd_hook(2, MSG_DAS_steeringControl))
        self._advance(30000)
        self.assertEqual(0, self.safety.safety_fwd_hook(2, MSG_DAS_steeringControl))
        self.assertEqual(0, self.safety.safety_fwd_hook(2, MSG_APS_eacMonitor))
        # Resuming openpilot TX takes the bus back.
        self.assertTrue(self._tx(self._angle_cmd_msg(0, False)))
        self.assertEqual(-1, self.safety.safety_fwd_hook(2, MSG_DAS_steeringControl))

  def test_mads_three_finger_lateral_tx_allowed(self):
    # M10: three-finger MADS sets only controls_allowed_lateral. openpilot steering must be accepted
    # and must own 0x488/0x27D while it transmits.
    self.safety.set_mads_params(True, False, False)
    self.safety.set_controls_allowed_lateral(True)
    self.assertFalse(self.safety.get_controls_allowed())
    self.assertTrue(self._tx(self._angle_cmd_msg(0, False)))
    self.assertTrue(self._tx(self._angle_cmd_msg(0, True)))
    self.assertEqual(-1, self.safety.safety_fwd_hook(2, MSG_DAS_steeringControl))
    self.assertEqual(-1, self.safety.safety_fwd_hook(2, MSG_APS_eacMonitor))
    # Lateral released: openpilot is idle again and stock passes.
    self.safety.set_controls_allowed_lateral(False)
    self.assertFalse(self._tx(self._angle_cmd_msg(0, False)))
    self.assertEqual(0, self.safety.safety_fwd_hook(2, MSG_DAS_steeringControl))

  def test_autopark_summon_while_enabled(self):
    # Summon that rises while openpilot lateral is already active is ignored.
    self._rx(self._pcm_status_msg(True, 0))

    self._rx(self._pcm_status_msg(True, self.autopark_states["SELFPARK_STARTED"]))
    self.assertTrue(self.safety.get_controls_allowed())
    self.assertTrue(self._tx(self._angle_cmd_msg(0, True)))
    self.assertTrue(self._tx(self._long_control_msg(0, acc_state=self.acc_states["ACC_CANCEL_GENERIC_SILENT"])))

    # Disengaging does not latch that earlier summon, but idle openpilot TX stays blocked.
    self._rx(self._pcm_status_msg(False, self.autopark_states["SELFPARK_STARTED"]))
    self.assertFalse(self.safety.get_controls_allowed())
    self.assertFalse(self._tx(self._angle_cmd_msg(0, False)))
    self.assertFalse(self._tx(self._long_control_msg(0, acc_state=self.acc_states["ACC_ON"])))

  def test_summon_not_ignored_when_only_stock_cruise_is_on(self):
    # MADS: longitudinal can be on while lateral is not. Summon must still latch.
    self.safety.set_mads_params(True, False, False)
    self._rx(self._pcm_status_msg(True, 0))
    self.assertTrue(self.safety.get_controls_allowed())
    self.safety.set_controls_allowed_lateral(False)
    self._rx(self._pcm_status_msg(True, self.autopark_states["ACTIVE"]))
    self.assertFalse(self.safety.get_controls_allowed())
    self.assertFalse(self._tx(self._angle_cmd_msg(0, True)))

  def test_autopark_summon_behavior(self):
    for autopark_state in range(16):
      self._release_stock_maneuver()
      self._rx(self._pcm_status_msg(False, 0))

      # We shouldn't allow controls if Autopark/Summon is an active state, including 2/5/7.
      autopark_active = autopark_state in self.active_autopark_states
      self._rx(self._pcm_status_msg(False, autopark_state))
      self._rx(self._pcm_status_msg(True, autopark_state))
      self.assertNotEqual(autopark_active, self.safety.get_controls_allowed())

      # We should also start blocking all inactive/active openpilot msgs
      self.assertNotEqual(autopark_active, self._tx(self._angle_cmd_msg(0, False)))
      self.assertNotEqual(autopark_active, self._tx(self._angle_cmd_msg(0, True)))
      self.assertNotEqual(autopark_active, self._tx(self._long_control_msg(0, acc_state=self.acc_states["ACC_CANCEL_GENERIC_SILENT"])))
      self.assertNotEqual(autopark_active or not self.LONGITUDINAL, self._tx(self._long_control_msg(0, acc_state=self.acc_states["ACC_ON"])))

      # Regain controls only after the steer type is NONE and the hold elapses
      self._release_stock_maneuver()
      self.assertTrue(self.safety.get_controls_allowed())
      self.assertTrue(self._tx(self._angle_cmd_msg(0, False)))
      self.assertTrue(self._tx(self._angle_cmd_msg(0, True)))
      self.assertTrue(self._tx(self._long_control_msg(0, acc_state=self.acc_states["ACC_CANCEL_GENERIC_SILENT"])))
      self.assertEqual(self.LONGITUDINAL, self._tx(self._long_control_msg(0, acc_state=self.acc_states["ACC_ON"])))

  def test_steering_control_type(self):
    # Only angle control is allowed (no LANE_KEEP_ASSIST, EMERGENCY_LANE_KEEP, or FSD)
    self.safety.set_controls_allowed(True)
    for steer_control_type in range(8):
      should_tx = steer_control_type in (self.steer_control_types["NONE"],
                                         self.steer_control_types["ANGLE_CONTROL"],
                                         self.steer_control_types["LANE_KEEP_ASSIST"])
      self.assertEqual(should_tx, self._tx(self._angle_cmd_msg(0, state=steer_control_type)))

  def test_stock_lkas_passthrough(self):
    # Disengaged: ANGLE_CONTROL and any other non-NONE type are forwarded, as is 0x27D.
    # Openpilot must not transmit its idle NONE / acc=4 frames onto that bus.
    for name in ("ANGLE_CONTROL", "LANE_KEEP_ASSIST", "EMERGENCY_LANE_KEEP"):
      with self.subTest(steer=name):
        self.setUp()
        msg = self._angle_cmd_msg(0, state=self.steer_control_types[name], bus=2)
        self.assertEqual(1, self._rx(msg))
        self.assertEqual(0, self.safety.safety_fwd_hook(2, MSG_DAS_steeringControl))
        self.assertEqual(0, self.safety.safety_fwd_hook(2, MSG_APS_eacMonitor))
        self.assertFalse(self._tx(self._angle_cmd_msg(0, state=False)))
        self.assertFalse(self._tx(self._long_control_msg(0, acc_state=self.acc_states["ACC_ON"])))

    # Engaged, and not in a stock maneuver: 0x488 is blocked once openpilot transmits it.
    self.setUp()
    self.safety.set_controls_allowed(True)
    self.assertEqual(0, self.safety.safety_fwd_hook(2, MSG_DAS_steeringControl))
    self.assertTrue(self._tx(self._angle_cmd_msg(0, state=False)))
    self.assertEqual(-1, self.safety.safety_fwd_hook(2, MSG_DAS_steeringControl))

    # Stock LKAS that rose while disengaged is still forwarded after engage, and openpilot stays off that bus.
    self.safety.set_controls_allowed(False)
    lkas_msg_cam = self._angle_cmd_msg(0, state=self.steer_control_types['LANE_KEEP_ASSIST'], bus=2)
    self.assertEqual(1, self._rx(lkas_msg_cam))
    self.safety.set_controls_allowed(True)
    self.assertEqual(0, self.safety.safety_fwd_hook(2, lkas_msg_cam.addr))
    self.assertFalse(self._tx(self._angle_cmd_msg(0, state=False)))

  def test_angle_cmd_when_disabled(self):
    # Disengaged openpilot does not send 0x488 at all, including NONE.
    self.safety.set_controls_allowed(False)
    self.assertFalse(self._tx(self._angle_cmd_msg(0, False)))
    self.assertFalse(self._tx(self._angle_cmd_msg(0, True)))

    # Engaged with the actuation bit off: the request must stay on the measured angle.
    self.safety.set_controls_allowed(True)
    for steer_control_enabled in (True, False):
      for angle_meas in np.arange(-90, 91, 10):
        self._reset_angle_measurement(angle_meas)
        for angle_cmd in np.arange(-90, 91, 10):
          self._set_prev_desired_angle(angle_cmd)
          should_tx = True if steer_control_enabled else angle_cmd == angle_meas
          self.assertEqual(should_tx, self._tx(self._angle_cmd_msg(angle_cmd, steer_control_enabled)),
                           f"{steer_control_enabled=} {angle_meas=} {angle_cmd=}")

  def test_vision_autopark_angle_blocks_until_none(self):
    # This car's vision Autopark leaves DI_autoparkState at STANDBY and uses ANGLE_CONTROL.
    self._rx(self._pcm_status_msg(False, self.autopark_states["STANDBY"]))
    self._rx(self._angle_cmd_msg(0, state=self.steer_control_types["ANGLE_CONTROL"], bus=2))
    self.assertEqual(0, self.safety.safety_fwd_hook(2, MSG_DAS_steeringControl))
    self.assertEqual(0, self.safety.safety_fwd_hook(2, MSG_APS_eacMonitor))
    self.assertFalse(self._tx(self._angle_cmd_msg(0, False)))
    self.assertFalse(self._tx(self._long_control_msg(0, acc_state=self.acc_states["ACC_ON"])))

    # Tapping engage during the maneuver does not stick.
    self._confirm_autopark()
    self._rx(self._pcm_status_msg(True, self.autopark_states["STANDBY"]))
    self.assertFalse(self.safety.get_controls_allowed())

    # NONE alone is not enough until the hold elapses.
    self.safety.set_timer(self._maneuver_t)
    self._rx(self._angle_cmd_msg(0, False, bus=2, increment_timer=False))
    self._rx(self._pcm_status_msg(True, self.autopark_states["STANDBY"]))
    self.assertFalse(self.safety.get_controls_allowed())

    self._release_stock_maneuver()
    self.assertTrue(self.safety.get_controls_allowed())
    self.assertTrue(self._tx(self._angle_cmd_msg(0, True)))

  def test_angle_cmd_when_enabled(self):
    # We properly test lateral acceleration and jerk below
    pass

  def test_lateral_accel_limit(self):
    for speed in np.linspace(0, 40, 100):
      speed = max(speed, 1)
      # match DI_vehicleSpeed rounding on CAN
      speed = round_speed(away_round(speed / 0.08 * 3.6) * 0.08 / 3.6)
      for sign in (-1, 1):
        self.safety.set_controls_allowed(True)
        self._reset_speed_measurement(speed + 1)  # safety fudges the speed

        # angle signal can't represent 0, so it biases one unit down
        angle_unit_offset = -1 if sign == -1 else 0

        # at limit (safety tolerance adds 1)
        max_angle = round_angle(get_max_angle_vm(speed, self.VM, CarControllerParams), angle_unit_offset + 1) * sign
        max_angle = np.clip(max_angle, -self.STEER_ANGLE_MAX, self.STEER_ANGLE_MAX)
        self.safety.set_desired_angle_last(round(max_angle * self.DEG_TO_CAN))

        self.assertTrue(self._tx(self._angle_cmd_msg(max_angle, True)))

        # 1 unit above limit
        max_angle_raw = round_angle(get_max_angle_vm(speed, self.VM, CarControllerParams), angle_unit_offset + 2) * sign
        max_angle = np.clip(max_angle_raw, -self.STEER_ANGLE_MAX, self.STEER_ANGLE_MAX)
        self._tx(self._angle_cmd_msg(max_angle, True))

        # at low speeds max angle is above 360, so adding 1 has no effect
        should_tx = abs(max_angle_raw) >= self.STEER_ANGLE_MAX
        self.assertEqual(should_tx, self._tx(self._angle_cmd_msg(max_angle, True)))

  def test_lateral_jerk_limit(self):
    for speed in np.linspace(0, 40, 100):
      speed = max(speed, 1)
      # match DI_vehicleSpeed rounding on CAN
      speed = round_speed(away_round(speed / 0.08 * 3.6) * 0.08 / 3.6)
      for sign in (-1, 1):  # (-1, 1):
        self.safety.set_controls_allowed(True)
        self._reset_speed_measurement(speed + 1)  # safety fudges the speed
        self._tx(self._angle_cmd_msg(0, True))

        # angle signal can't represent 0, so it biases one unit down
        angle_unit_offset = 1 if sign == -1 else 0

        # Stay within limits
        # Up
        max_angle_delta = round_angle(get_max_angle_delta_vm(speed, self.VM, CarControllerParams), angle_unit_offset) * sign
        self.assertTrue(self._tx(self._angle_cmd_msg(max_angle_delta, True)))

        # Don't change
        self.assertTrue(self._tx(self._angle_cmd_msg(max_angle_delta, True)))

        # Down
        self.assertTrue(self._tx(self._angle_cmd_msg(0, True)))

        # Inject too high rates
        # Up
        max_angle_delta = round_angle(get_max_angle_delta_vm(speed, self.VM, CarControllerParams), angle_unit_offset + 1) * sign
        self.assertFalse(self._tx(self._angle_cmd_msg(max_angle_delta, True)))

        # Don't change
        self.safety.set_desired_angle_last(round(max_angle_delta * self.DEG_TO_CAN))
        self.assertTrue(self._tx(self._angle_cmd_msg(max_angle_delta, True)))

        # Down
        self.assertFalse(self._tx(self._angle_cmd_msg(0, True)))

        # Recover
        self.assertTrue(self._tx(self._angle_cmd_msg(0, True)))
class TestTeslaStockSafety(TestTeslaSafetyBase):

  LONGITUDINAL = False

  def test_cancel(self):
    for acc_state in range(16):
      self.safety.set_controls_allowed(True)
      should_tx = acc_state == self.acc_states["ACC_CANCEL_GENERIC_SILENT"]
      self.assertFalse(self._tx(self._long_control_msg(0, acc_state=acc_state, accel_limits=(self.MIN_ACCEL, self.MAX_ACCEL))))
      self.assertEqual(should_tx, self._tx(self._long_control_msg(0, acc_state=acc_state)))

  def test_no_aeb(self):
    self.safety.set_controls_allowed(True)
    for aeb_event in range(4):
      should_tx = aeb_event == 0
      ret = self._tx(self._long_control_msg(10, acc_state=self.acc_states["ACC_CANCEL_GENERIC_SILENT"], aeb_event=aeb_event))
      self.assertEqual(ret, should_tx)

  def test_stock_aeb_no_cancel(self):
    # No passthrough logic since we always forward DAS_control,
    # but ensure we can't send cancel cmd while stock AEB is active.
    # Cancel TX is only meaningful once openpilot is engaged.
    self.safety.set_controls_allowed(True)
    no_aeb_msg = self._long_control_msg(10, acc_state=self.acc_states["ACC_CANCEL_GENERIC_SILENT"], aeb_event=0)
    no_aeb_msg_cam = self._long_control_msg(10, aeb_event=0, bus=2)
    aeb_msg_cam = self._long_control_msg(10, aeb_event=1, bus=2)

    # stock system sends no AEB -> no forwarding, and OP is allowed to TX
    self.assertEqual(1, self._rx(no_aeb_msg_cam))
    self.assertEqual(0, self.safety.safety_fwd_hook(2, no_aeb_msg_cam.addr))
    self.assertTrue(self._tx(no_aeb_msg))

    # stock system sends AEB -> forwarding, and OP is not allowed to TX
    self.assertEqual(1, self._rx(aeb_msg_cam))
    self.assertEqual(0, self.safety.safety_fwd_hook(2, aeb_msg_cam.addr))
    self.assertFalse(self._tx(no_aeb_msg))


class TestTeslaFSD14StockSafety(TestTeslaStockSafety):
  SAFETY_PARAM = TeslaSafetyFlags.FSD_14


class TestTeslaLongitudinalSafety(TestTeslaSafetyBase):
  SAFETY_PARAM = TeslaSafetyFlags.LONG_CONTROL

  RELAY_MALFUNCTION_ADDRS = {0: (MSG_DAS_steeringControl, MSG_APS_eacMonitor, MSG_DAS_Control)}
  # Disengaged longitudinal starts STOCK, so 0x2B9 is forwarded until the handshake.
  FWD_BLACKLISTED_ADDRS = {2: []}

  def _tx(self, msg):
    # Inherited accel/angle limit tests engage with set_controls_allowed and then
    # transmit. Production reaches SP only through the handshake; give those
    # limit checks the post-handshake owner without skipping the dedicated test.
    if self.safety.get_controls_allowed() and msg.addr == MSG_DAS_Control:
      self.safety.test_long_fixture_sp()
    return super()._tx(msg)

  def _owner_byte(self):
    buf = libsafety_py.ffi.new("uint8_t[8]")
    self.safety.test_long_snapshot(buf)
    return bytes(buf)[1]

  def test_no_aeb(self):
    self.safety.set_controls_allowed(True)
    for aeb_event in range(4):
      self.assertEqual(self._tx(self._long_control_msg(10, aeb_event=aeb_event)), aeb_event == 0)

  def test_stock_aeb_passthrough(self):
    no_aeb_msg = self._long_control_msg(10, aeb_event=0)
    no_aeb_msg_cam = self._long_control_msg(10, aeb_event=0, bus=2)
    aeb_msg_cam = self._long_control_msg(10, aeb_event=1, bus=2)

    # Not engaged: owner is STOCK, so stock 0x2B9 is forwarded and openpilot must not TX.
    self.assertEqual(self._owner_byte(), 0)
    self.assertEqual(1, self._rx(no_aeb_msg_cam))
    self.assertEqual(0, self.safety.safety_fwd_hook(2, no_aeb_msg_cam.addr))
    self.assertFalse(self._tx(self._long_control_msg(0, acc_state=self.acc_states["ACC_ON"])))

    # Engaged, owner SP: non-AEB is intercepted and openpilot may TX; AEB is still forwarded.
    self.safety.set_controls_allowed(True)
    self.safety.test_long_fixture_sp()
    self.assertEqual(-1, self.safety.safety_fwd_hook(2, no_aeb_msg_cam.addr))
    self.assertTrue(self._tx(no_aeb_msg))
    self.assertEqual(1, self._rx(aeb_msg_cam))
    self.assertEqual(0, self.safety.safety_fwd_hook(2, aeb_msg_cam.addr))
    self.assertFalse(self._tx(no_aeb_msg))

  def test_disengaged_long_starts_stock_then_handshake(self):
    from opendbc.safety.tests.test_tesla_long_owner_contract import OwnerDrive, long_msg

    self.assertFalse(self.safety.get_controls_allowed())
    self.assertEqual(self._owner_byte(), 0)
    valid = libsafety_py.ffi.new("bool *")
    fwd = self.safety.safety_rx_fwd_hook(self._long_control_msg(0, acc_state=self.acc_states["ACC_ON"], bus=2), valid, True)
    self.assertEqual(fwd, 0)

    drive = OwnerDrive(safety=self.safety, stock=False)
    self.assertEqual(drive.owner, 0)
    self.assertEqual(drive.outputs[-1][1], 0)
    drive.takeover()
    self.assertEqual(drive.owner, 1)
    self.assertEqual(drive.rx(long_msg(2))[0], -1)

  def test_handshake_after_autopark_cancel(self):
    # M10: Autopark, cancel, then engage. The 0x2B9 owner must still go STOCK -> SP.
    from opendbc.safety.tests.test_tesla_long_owner_contract import OwnerDrive, long_msg

    drive = OwnerDrive(safety=self.safety, stock=False)
    self.safety.set_controls_allowed(False)
    t = drive.now
    for attempt in range(2):
      drive.peer('DI_state', {'DI_cruiseState': 0, 'DI_autoparkState': self.autopark_states["STANDBY"]})
      drive.peer('DAS_steeringControl', {'DAS_steeringControlType': self.steer_control_types["ANGLE_CONTROL"]})
      t += 600_000
      drive.set_time(t)
      drive.peer('DI_state', {'DI_cruiseState': 0, 'DI_autoparkState': self.autopark_states["STANDBY"]})
      self.assertEqual(drive.rx(long_msg(attempt + 1, bus=2))[0], 0, attempt)
      self.assertFalse(self.safety.get_controls_allowed())
      # cancel + 200ms hold
      drive.peer('DAS_steeringControl', {'DAS_steeringControlType': 0})
      drive.peer('DI_state', {'DI_cruiseState': 0, 'DI_autoparkState': self.autopark_states["STANDBY"]})
      t += 210_000
      drive.set_time(t)
      drive.peer('DAS_steeringControl', {'DAS_steeringControlType': 0})
      drive.peer('DI_state', {'DI_cruiseState': 0, 'DI_autoparkState': self.autopark_states["STANDBY"]})
      self.assertEqual(drive.owner, 0)

    t += 20_000
    drive.set_time(t)
    for counter in (3, 4, 5, 6, 7):
      t += 20_000
      drive.set_time(t)
      self.assertEqual(drive.rx(long_msg(counter, bus=2))[0], 0)
    t += 20_000
    drive.set_time(t)
    drive.peers()  # fresh RX, DI_cruiseState ENABLED engages openpilot
    self.assertEqual(drive.rx(long_msg(0, bus=2))[0], 0)
    self.assertTrue(self.safety.get_controls_allowed())
    drive.takeover()
    self.assertEqual(drive.owner, 1)
    self.assertEqual(drive.rx(long_msg(7, bus=2))[0], -1)

  def test_mid_maneuver_engage_and_sp_rejected(self):
    self._rx(self._pcm_status_msg(False, self.autopark_states["STANDBY"]))
    self._rx(self._angle_cmd_msg(0, state=self.steer_control_types["ANGLE_CONTROL"], bus=2))
    self._confirm_autopark()
    self._rx(self._pcm_status_msg(True, self.autopark_states["STANDBY"]))
    self.assertFalse(self.safety.get_controls_allowed())
    self.assertFalse(self.safety.safety_tx_hook(self._angle_cmd_msg(0, False)))
    self.assertFalse(self.safety.safety_tx_hook(self._long_control_msg(0, acc_state=self.acc_states["ACC_ON"])))
    buf = libsafety_py.ffi.new("uint8_t[8]")
    self.assertEqual(self.safety.test_long_request(1, 0, buf), 8)
    owner, pending = bytes(buf)[1], bytes(buf)[2]
    self.assertEqual(owner, 0)
    self.assertNotEqual(pending, 1)

  def test_accel_actuation_limits(self):
    # Disengaged: no 0x2B9 at all, including the inactive accel the common test allows.
    # Engaged: same limits, after _tx moves the owner to SP.
    from opendbc.safety import ALTERNATIVE_EXPERIENCE
    limits = ((self.MIN_ACCEL, self.MAX_ACCEL, ALTERNATIVE_EXPERIENCE.DEFAULT),
              (self.MIN_ACCEL, self.MAX_ACCEL, ALTERNATIVE_EXPERIENCE.RAISE_LONGITUDINAL_LIMITS_TO_ISO_MAX))
    for min_accel, max_accel, alternative_experience in limits:
      for accel in np.concatenate((np.arange(min_accel - 1, max_accel + 1, 0.05), [0, self.INACTIVE_ACCEL])):
        accel = round(accel, 2)
        for controls_allowed in (True, False):
          self.safety.set_controls_allowed(controls_allowed)
          self.safety.set_alternative_experience(alternative_experience)
          should_tx = controls_allowed and min_accel <= accel <= max_accel
          self.assertEqual(should_tx, self._tx(self._accel_msg(accel)))

  def test_prevent_reverse(self):
    # Note: Tesla can reverse while at a standstill if both accel_min and accel_max are negative.
    self.safety.set_controls_allowed(True)

    # accel_min and accel_max are positive
    self.assertTrue(self._tx(self._long_control_msg(set_speed=10, accel_limits=(1.1, 0.8))))
    self.assertTrue(self._tx(self._long_control_msg(set_speed=0, accel_limits=(1.1, 0.8))))

    # accel_min and accel_max are both zero
    self.assertTrue(self._tx(self._long_control_msg(set_speed=10, accel_limits=(0, 0))))
    self.assertTrue(self._tx(self._long_control_msg(set_speed=0, accel_limits=(0, 0))))

    # accel_min and accel_max have opposing signs
    self.assertTrue(self._tx(self._long_control_msg(set_speed=10, accel_limits=(-0.8, 1.3))))
    self.assertTrue(self._tx(self._long_control_msg(set_speed=0, accel_limits=(0.8, -1.3))))
    self.assertTrue(self._tx(self._long_control_msg(set_speed=0, accel_limits=(0, -1.3))))

    # accel_min and accel_max are negative
    self.assertFalse(self._tx(self._long_control_msg(set_speed=10, accel_limits=(-1.1, -0.6))))
    self.assertFalse(self._tx(self._long_control_msg(set_speed=0, accel_limits=(-0.6, -1.1))))
    self.assertFalse(self._tx(self._long_control_msg(set_speed=0, accel_limits=(-0.1, -0.1))))


class TestTeslaFSD14LongitudinalSafety(TestTeslaLongitudinalSafety):
  SAFETY_PARAM = TeslaSafetyFlags.LONG_CONTROL | TeslaSafetyFlags.FSD_14


class TestTeslaIgnition(common.SafetyTestBase):
  DBC = "tesla_model3_party"
  SAFETY_MODEL = None

  TX_MSGS: list = []

  def _msg(self, counter, state):
    return self.packer.make_can_msg_safety("VCFRONT_LVPowerState", 0,
                                           {"VCFRONT_LVPowerStateCounter": counter,
                                            "VCFRONT_vehiclePowerState": state})

  # VEHICLE_POWER_STATE_DRIVE=3 (counter-gated)
  def test_ignition_on(self):
    for i in range(16):
      self.safety.init_tests()
      self.safety.ignition_can_hook(self._msg(i, 3))
      self.assertFalse(self.safety.get_ignition_can())
      self.safety.ignition_can_hook(self._msg((i + 1) % 16, 3))
      self.assertTrue(self.safety.get_ignition_can())

  def test_ignition_off(self):
    self.safety.ignition_can_hook(self._msg(0, 3))
    self.safety.ignition_can_hook(self._msg(1, 3))
    self.assertTrue(self.safety.get_ignition_can())
    self.safety.ignition_can_hook(self._msg(2, 2))
    self.safety.ignition_can_hook(self._msg(3, 2))
    self.assertFalse(self.safety.get_ignition_can())
class TestTeslaVehicleBusSafety(TestTeslaSafetyBase):

  LONGITUDINAL = False

  def test_rx_minimum_frequency(self):
    values = {0x155: {"ESP_wheelSpeedsQF": 1}, 0x145: {"ESP_driverBrakeApply": 1}, 0x257: {"DI_vehicleSpeed": 0}}
    for ignore_frequency_check in (False, True):
      with self.subTest(ignore_frequency_check=ignore_frequency_check):
        self.setUp()
        cfg = self.safety.current_safety_config
        ui_status = cfg.rx_checks[cfg.rx_checks_len - 1].msg[0]
        self.assertEqual((ui_status.addr, ui_status.bus, ui_status.frequency), (0x3DF, 1, 2))
        ui_status.ignore_frequency_check = ignore_frequency_check
        for ts in range(0, 2_000_001, 10_000):
          self.safety.set_timer(ts)
          for i in range(cfg.rx_checks_len):
            msg = cfg.rx_checks[i].msg[0]
            if ts % (1_000_000 // msg.frequency) == 0:
              packer = self.packer_adas if msg.bus == CANBUS.vehicle else self.packer
              self.assertTrue(self._rx(packer.make_can_msg_safety(msg.addr, msg.bus, values.get(msg.addr, {}))))
          if ts and ts % 1_000_000 == 0:
            self.safety.set_controls_allowed(True)
            self.safety.safety_tick()
            self.assertTrue(self.safety.safety_config_valid())
            self.assertEqual(self.safety.safety_rx_checks_invalid, not ignore_frequency_check)
            self.assertEqual(self.safety.get_controls_allowed(), ignore_frequency_check)

  def setUp(self):
    super().setUp()
    self.safety = libsafety_py.libsafety
    self.packer_adas = CANPackerSafety("tesla_model3_vehicle")
    self.safety.set_current_safety_param_sp(TeslaSafetyFlagsSP.HAS_VEHICLE_BUS | TeslaSafetyFlagsSP.MADS_SCREEN_BUTTON_3_FINGER)
    self.safety.set_safety_hooks(CarParams.SafetyModel.tesla, 0)
    self.safety.init_tests()

  def _lkas_button_msg(self, enabled):
    values = {"UI_activeTouchPoints": 3 if enabled else 0}
    return self.packer_adas.make_can_msg_safety("UI_status2", CANBUS.vehicle, values)

  def _set_mads_screen_button_config(self, finger_flag):
    param_sp = TeslaSafetyFlagsSP.HAS_VEHICLE_BUS
    if finger_flag is not None:
      param_sp |= finger_flag
    self.safety.set_current_safety_param_sp(param_sp)
    self.safety.set_safety_hooks(CarParams.SafetyModel.tesla, 0)
    self.safety.init_tests()

  def _touch_points_msg(self, touch_points):
    return self.packer_adas.make_can_msg_safety("UI_status2", CANBUS.vehicle, {"UI_activeTouchPoints": touch_points})

  def test_mads_screen_button_finger_count_match(self):
    """Configured finger count must match received touch-point count to register a MADS button press."""
    configs = [
      (TeslaSafetyFlagsSP.MADS_SCREEN_BUTTON_3_FINGER, 3),
      (TeslaSafetyFlagsSP.MADS_SCREEN_BUTTON_4_FINGER, 4),
      (TeslaSafetyFlagsSP.MADS_SCREEN_BUTTON_5_FINGER, 5),
    ]
    for config_flag, config_count in configs:
      for actual in (0, 3, 4, 5):
        with self.subTest(configured=config_count, actual=actual):
          self._set_mads_screen_button_config(config_flag)
          self._rx(self._touch_points_msg(actual))
          expected = 1 if actual == config_count else 0  # PRESSED vs NOT_PRESSED
          self.assertEqual(expected, self.safety.get_mads_button_press())

  def test_mads_screen_button_disabled(self):
    """With no finger-count flag set, touch messages must not change the MADS button state from UNAVAILABLE."""
    self._set_mads_screen_button_config(None)
    for actual in (0, 3, 4, 5):
      with self.subTest(actual=actual):
        self._rx(self._touch_points_msg(actual))
        self.assertEqual(-1, self.safety.get_mads_button_press())  # UNAVAILABLE
class TestTeslaStockApSafety(unittest.TestCase):
  def setUp(self):
    self.safety = libsafety_py.libsafety
    self.packer = CANPackerSafety("tesla_model3_party")

  def _init(self, param, param_sp):
    self.safety.set_current_safety_param_sp(TeslaSafetyFlagsSP.HAS_VEHICLE_BUS | param_sp)
    self.safety.set_safety_hooks(CarParams.SafetyModel.tesla, param)
    self.safety.init_tests()
    self.safety.set_controls_allowed(True)

  def test_stock_ap(self):
    ops = (self.packer.make_can_msg_safety("DAS_steeringControl", 0, {"DAS_steeringAngleRequest": 0, "DAS_steeringControlType": 1}),
           self.packer.make_can_msg_safety("DAS_control", 0, {"DAS_setSpeed": 10, "DAS_accState": 4}),
           self.packer.make_can_msg_safety("APS_eacMonitor", 0, {}))
    for param in (0, TeslaSafetyFlags.LONG_CONTROL):
      with self.subTest(param=param):
        self._init(param, TeslaSafetyFlagsSP.STOCK_AP)
        for addr in (MSG_DAS_steeringControl, MSG_DAS_Control, MSG_APS_eacMonitor):
          self.assertEqual(0, self.safety.safety_fwd_hook(2, addr))  # SA1
        for msg in ops:
          self.assertFalse(self.safety.safety_tx_hook(msg))  # SA2
        self._init(param, 0)
        self.assertTrue(self.safety.safety_tx_hook(
          self.packer.make_can_msg_safety("DAS_steeringControl", 0, {"DAS_steeringAngleRequest": 0, "DAS_steeringControlType": 0})))
        self.assertEqual(-1, self.safety.safety_fwd_hook(2, MSG_DAS_steeringControl))  # SA3


if __name__ == "__main__":
  unittest.main()
