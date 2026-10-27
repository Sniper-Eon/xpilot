"""xpilot panda safety plugin failure modes.

auto_speed (0x3C2, bus 1, 8 bytes):
- Inactive outside SAFETY_TESLA, without the 0x4000 safetyParamSP bit, or without the vehicle bus.
- Wrong address, bus, or length is not plugin-owned and remains blocked by stock Tesla safety.
- TX is blocked before an idle mux-1 template exists or after that template is stale.
- TX is blocked when any non-tick byte or the tick byte's non-tick bits differ from the template.
- Only tick values 1 and 0x3F are allowed.
- A second TX inside 250 ms is blocked and one at the boundary is allowed.
- controls_allowed false blocks TX.
- A safety-mode reset clears both the template and rate-limit state.
- Plugin RX does not change stock Tesla controls_allowed or relay-malfunction state.
- At most 50 ticks per session; a 3-second idle gap starts a new session.

ambient_light (0x679, bus 1, 7 bytes):
- Inactive outside SAFETY_TESLA, without the 0x2000 safetyParamSP bit, or without the vehicle bus.
- Wrong address, bus, or length is not plugin-owned and remains blocked by stock Tesla safety.
- TX is blocked before a template exists or after that template is stale.
- TX is blocked for a non-red color, excessive brightness, an invalid target, or a changed protected template bit.
- A second TX inside 80 ms is blocked and one at the boundary is allowed.
- controls_allowed false blocks TX.
- The 150-frame/15-second session cap blocks further TX until a one-second idle gap starts a new session.
- A safety-mode reset clears the template and rate-limit state.
- Plugin RX does not change stock Tesla controls_allowed or relay-malfunction state.

navassist (0x3E9, bus 1, 8 bytes):
- Inactive outside SAFETY_TESLA, without the 0x8000 safetyParamSP bit, or without the vehicle bus.
- TX clones a fresh idle template and only changes request/reason/counter.
- Active request 1/2 requires primary or enabled MADS lateral authority; cancel request 3 only
  releases the lamp, including before a disengage.
- Rate/session limits and the safety-mode reset apply to both active and cancel frames.
"""

import unittest

from opendbc.car.structs import CarParams
from opendbc.safety.tests import common
from opendbc.sunnypilot.car.tesla.values import TeslaSafetyFlagsSP


AUTO_SPEED_PARAM = 0x4000
AMBIENT_PARAM = 0x2000
AUTO_SPEED_TEMPLATE = bytes((0xA5, 0x12, 0x34, 0xC0, 0x9A, 0xBC, 0xDE, 0xF0))
AMBIENT_TEMPLATE = bytes((0x01, 0x12, 0x34, 0x56, 0xA8, 0x06, 0xA0))
AMBIENT_ALERT = bytes((0x03, 0xFF, 0x00, 0x00, 0x9E, 0xAE, 0xA0))


class XpilotPluginSafetyBase(common.SafetyTestBase):
  SAFETY_MODEL = None

  def _set_mode(self, mode, param=0, param_sp=0):
    self.safety.set_current_safety_param_sp(param_sp)
    self.assertEqual(0, self.safety.set_safety_hooks(mode, param))

  def _set_tesla(self, param_sp):
    self._set_mode(CarParams.SafetyModel.tesla, param_sp=param_sp)


class TestAutoSpeedPluginSafety(XpilotPluginSafetyBase):
  ACTIVE_PARAM_SP = TeslaSafetyFlagsSP.HAS_VEHICLE_BUS | AUTO_SPEED_PARAM

  def setUp(self):
    super().setUp()
    self._set_tesla(self.ACTIVE_PARAM_SP)

  @staticmethod
  def _template():
    return common.make_msg(1, 0x3C2, dat=AUTO_SPEED_TEMPLATE)

  @staticmethod
  def _tick(ticks=1, *, bus=1, addr=0x3C2, length=8):
    data = bytearray(AUTO_SPEED_TEMPLATE[:length])
    if length > 3:
      data[3] = (data[3] & 0xC0) | ticks
    return common.make_msg(bus, addr, length, data)

  def _prime(self, now=100):
    self.safety.set_timer(now)
    self.assertTrue(self._rx(self._template()))
    self.safety.set_controls_allowed(True)

  def test_activation_gates(self):
    for mode, param_sp in (
      (CarParams.SafetyModel.noOutput, self.ACTIVE_PARAM_SP),
      (CarParams.SafetyModel.tesla, TeslaSafetyFlagsSP.HAS_VEHICLE_BUS),
      (CarParams.SafetyModel.tesla, AUTO_SPEED_PARAM),
    ):
      with self.subTest(mode=mode, param_sp=param_sp):
        self._set_mode(mode, param_sp=param_sp)
        self.safety.set_controls_allowed(True)
        self.assertTrue(self._rx(self._template()))
        self.assertFalse(self._tx(self._tick()))

  def test_wrong_address_bus_or_length_not_owned(self):
    self._prime()
    for msg in (self._tick(addr=0x3C3), self._tick(bus=0), self._tick(length=7)):
      with self.subTest(addr=msg.addr, bus=msg.bus, length=msg.data_len_code):
        self.assertFalse(self._tx(msg))

  def test_no_template(self):
    self.safety.set_controls_allowed(True)
    self.assertFalse(self._tx(self._tick()))

  def test_stale_template(self):
    self._prime()
    self.safety.set_timer(1_500_101)
    self.assertFalse(self._tx(self._tick()))

  def test_non_tick_bytes_match_template(self):
    self._prime()
    for index in (0, 1, 2, 4, 5, 6, 7):
      with self.subTest(index=index):
        data = bytearray(AUTO_SPEED_TEMPLATE)
        data[3] |= 1
        data[index] ^= 1
        self.assertFalse(self._tx(common.make_msg(1, 0x3C2, dat=data)))

    data = bytearray(AUTO_SPEED_TEMPLATE)
    data[3] = (data[3] ^ 0x40) | 1
    self.assertFalse(self._tx(common.make_msg(1, 0x3C2, dat=data)))

  def test_tick_values(self):
    for ticks in range(64):
      with self.subTest(ticks=ticks):
        self._set_tesla(self.ACTIVE_PARAM_SP)
        self._prime()
        self.assertEqual(ticks in (1, 0x3F), self._tx(self._tick(ticks)))

  def test_rate_limit(self):
    self._prime()
    self.assertTrue(self._tx(self._tick()))
    self.safety.set_timer(250_099)
    self.assertFalse(self._tx(self._tick(0x3F)))
    self.safety.set_timer(250_100)
    self.assertTrue(self._tx(self._tick(0x3F)))

  def test_controls_allowed(self):
    self._prime()
    self.safety.set_controls_allowed(False)
    self.assertFalse(self._tx(self._tick()))

  def test_session_cap_and_idle_restart(self):
    now = 100
    for tick in range(50):
      now = 100 + tick * 500_000
      self.safety.set_timer(now)
      self.assertTrue(self._rx(self._template()))
      self.safety.set_controls_allowed(True)
      self.assertTrue(self._tx(self._tick()), tick)

    for gap in (500_000, 2_999_999):
      self.safety.set_timer(now + gap)
      self.assertTrue(self._rx(self._template()))
      self.assertFalse(self._tx(self._tick()), gap)
    self.safety.set_timer(now + 3_000_000)
    self.assertTrue(self._rx(self._template()))
    self.assertTrue(self._tx(self._tick()))

  def test_mode_reset_clears_template_and_rate_state(self):
    self._prime()
    self.assertTrue(self._tx(self._tick()))
    self._set_mode(CarParams.SafetyModel.noOutput)
    self._set_tesla(self.ACTIVE_PARAM_SP)
    self.safety.set_controls_allowed(True)
    self.assertFalse(self._tx(self._tick()))
    self._prime()
    self.assertTrue(self._tx(self._tick()))

  def test_inactive_message_remains_stock_blocked(self):
    self._set_tesla(TeslaSafetyFlagsSP.HAS_VEHICLE_BUS)
    self.safety.set_controls_allowed(True)
    self.assertFalse(self._tx(self._tick()))

  def test_rx_does_not_change_stock_state(self):
    self.safety.set_controls_allowed(True)
    self.assertFalse(self.safety.get_relay_malfunction())
    self.assertTrue(self._rx(self._template()))
    self.assertTrue(self.safety.get_controls_allowed())
    self.assertFalse(self.safety.get_relay_malfunction())


class TestAmbientLightPluginSafety(XpilotPluginSafetyBase):
  ACTIVE_PARAM_SP = TeslaSafetyFlagsSP.HAS_VEHICLE_BUS | AMBIENT_PARAM

  def setUp(self):
    super().setUp()
    self._set_tesla(self.ACTIVE_PARAM_SP)

  @staticmethod
  def _template():
    return common.make_msg(1, 0x679, length=7, dat=AMBIENT_TEMPLATE)

  @staticmethod
  def _alert(*, bus=1, addr=0x679, length=7, brightness=30):
    data = bytearray(AMBIENT_ALERT[:length])
    if length > 4:
      data[4] = (data[4] & 0x80) | brightness
    return common.make_msg(bus, addr, length, data)

  def _prime(self, now=100):
    self.safety.set_timer(now)
    self.assertTrue(self._rx(self._template()))
    self.safety.set_controls_allowed(True)

  def test_activation_gates(self):
    self._set_mode(CarParams.SafetyModel.noOutput, param=1, param_sp=self.ACTIVE_PARAM_SP)
    self.assertTrue(self._rx(self._template()))
    self.assertFalse(self._tx(self._alert(brightness=100)))

    for param_sp in (0, TeslaSafetyFlagsSP.HAS_VEHICLE_BUS, AMBIENT_PARAM):
      with self.subTest(param_sp=param_sp):
        self._set_tesla(param_sp)
        self.safety.set_controls_allowed(True)
        self.assertTrue(self._rx(self._template()))
        self.assertFalse(self._tx(self._alert()))

  def test_wrong_address_bus_or_length_not_owned(self):
    self._prime()
    for msg in (self._alert(addr=0x678), self._alert(bus=0), self._alert(length=6)):
      with self.subTest(addr=msg.addr, bus=msg.bus, length=msg.data_len_code):
        self.assertFalse(self._tx(msg))

  def test_no_template(self):
    self.safety.set_controls_allowed(True)
    self.assertFalse(self._tx(self._alert()))

  def test_stale_template(self):
    self._prime()
    self.safety.set_timer(1_000_101)
    self.assertFalse(self._tx(self._alert()))

  def test_color_brightness_target_and_template_bits(self):
    self._prime()
    invalid = []
    for index in (1, 2, 3):
      data = bytearray(AMBIENT_ALERT)
      data[index] ^= 1
      invalid.append((f"color byte {index}", data))
    data = bytearray(AMBIENT_ALERT)
    data[4] = (data[4] & 0x80) | 101
    invalid.append(("brightness", data))
    data = bytearray(AMBIENT_ALERT)
    data[5] = (data[5] & 0x07) | 0x20
    invalid.append(("target", data))
    for index, mask in ((0, 0x01), (4, 0x80), (5, 0x02), (6, 0x02)):
      data = bytearray(AMBIENT_ALERT)
      data[index] ^= mask
      invalid.append((f"template byte {index}", data))

    for name, data in invalid:
      with self.subTest(name=name):
        self.assertFalse(self._tx(common.make_msg(1, 0x679, length=7, dat=data)))

  def test_rate_limit(self):
    self._prime()
    self.assertTrue(self._tx(self._alert()))
    self.safety.set_timer(80_099)
    self.assertFalse(self._tx(self._alert()))
    self.safety.set_timer(80_100)
    self.assertTrue(self._tx(self._alert()))

  def test_controls_allowed(self):
    self._prime()
    self.safety.set_controls_allowed(False)
    self.assertFalse(self._tx(self._alert()))

  def test_session_cap_and_idle_restart(self):
    for frame in range(150):
      now = 100 + frame * 80_000
      self.safety.set_timer(now)
      self.assertTrue(self._rx(self._template()))
      self.safety.set_controls_allowed(True)
      self.assertTrue(self._tx(self._alert()), frame)

    self.safety.set_timer(100 + 150 * 80_000)
    self.assertTrue(self._rx(self._template()))
    self.assertFalse(self._tx(self._alert()))
    self.safety.set_timer(100 + 149 * 80_000 + 1_000_000)
    self.assertTrue(self._rx(self._template()))
    self.assertTrue(self._tx(self._alert()))

  def test_mode_reset_clears_template_and_rate_state(self):
    self._prime()
    self.assertTrue(self._tx(self._alert()))
    self._set_mode(CarParams.SafetyModel.noOutput)
    self._set_tesla(self.ACTIVE_PARAM_SP)
    self.safety.set_controls_allowed(True)
    self.assertFalse(self._tx(self._alert()))
    self._prime()
    self.assertTrue(self._tx(self._alert()))

  def test_inactive_message_remains_stock_blocked(self):
    self._set_tesla(TeslaSafetyFlagsSP.HAS_VEHICLE_BUS)
    self.safety.set_controls_allowed(True)
    self.assertFalse(self._tx(self._alert()))

  def test_rx_does_not_change_stock_state(self):
    self.safety.set_controls_allowed(True)
    self.assertFalse(self.safety.get_relay_malfunction())
    self.assertTrue(self._rx(self._template()))
    self.assertTrue(self.safety.get_controls_allowed())
    self.assertFalse(self.safety.get_relay_malfunction())


TURN_SIGNAL_PARAM = 0x8000


def _body_controls_checksum(data: bytearray) -> int:
  return (0xE9 + 0x03 + sum(data[:7])) & 0xFF


def _idle_template(counter=0) -> bytes:
  data = bytearray(8)
  data[2] = 8 << 1
  data[6] = (counter & 0x0F) << 4
  data[7] = _body_controls_checksum(data)
  return bytes(data)


def _turn_frame(request=1, counter=1, reason=None, template=None) -> bytes:
  data = bytearray(template or _idle_template())
  data[1] = (data[1] & 0xFC) | request
  if reason is None:
    reason = 4 if request == 3 else 8
  data[2] = (data[2] & 0xE1) | ((reason & 0x0F) << 1)
  data[6] = (data[6] & 0x0F) | ((counter & 0x0F) << 4)
  data[7] = _body_controls_checksum(data)
  return bytes(data)


class TestTurnSignalPluginSafety(XpilotPluginSafetyBase):
  ACTIVE_PARAM_SP = TeslaSafetyFlagsSP.HAS_VEHICLE_BUS | TURN_SIGNAL_PARAM

  def setUp(self):
    super().setUp()
    self._set_tesla(self.ACTIVE_PARAM_SP)

  @staticmethod
  def _template():
    return common.make_msg(1, 0x3E9, dat=_idle_template())

  @staticmethod
  def _frame(**kwargs):
    return common.make_msg(1, 0x3E9, dat=_turn_frame(**kwargs))

  def _prime(self, now=100):
    self.safety.set_timer(now)
    self.assertTrue(self._rx(self._template()))
    self.safety.set_controls_allowed(True)

  def test_activation_gates(self):
    for mode, param_sp in (
      (CarParams.SafetyModel.noOutput, self.ACTIVE_PARAM_SP),
      (CarParams.SafetyModel.tesla, TeslaSafetyFlagsSP.HAS_VEHICLE_BUS),
      (CarParams.SafetyModel.tesla, TURN_SIGNAL_PARAM),
    ):
      with self.subTest(mode=mode, param_sp=param_sp):
        self._set_mode(mode, param_sp=param_sp)
        self.safety.set_controls_allowed(True)
        self.assertTrue(self._rx(self._template()))
        self.assertFalse(self._tx(self._frame()))

  def test_wrong_address_bus_or_length_not_owned(self):
    self._prime()
    for msg in (
      common.make_msg(1, 0x3E8, dat=_turn_frame()),
      common.make_msg(0, 0x3E9, dat=_turn_frame()),
      common.make_msg(1, 0x3E9, length=7, dat=_turn_frame()[:7]),
    ):
      with self.subTest(addr=msg.addr, bus=msg.bus, length=msg.data_len_code):
        self.assertFalse(self._tx(msg))

  def test_no_template_or_stale(self):
    self.safety.set_controls_allowed(True)
    self.assertFalse(self._tx(self._frame()))
    self._prime()
    self.safety.set_timer(1_500_101)
    self.assertFalse(self._tx(self._frame()))

  def test_checksum_and_protected_bits(self):
    self._prime()
    bad_checksum = bytearray(_turn_frame())
    bad_checksum[7] ^= 1
    self.assertFalse(self._tx(common.make_msg(1, 0x3E9, dat=bytes(bad_checksum))))
    for index in (0, 3, 4, 5):
      with self.subTest(index=index):
        data = bytearray(_turn_frame())
        data[index] ^= 1
        data[7] = _body_controls_checksum(data)
        self.assertFalse(self._tx(common.make_msg(1, 0x3E9, dat=bytes(data))))
    for index, mask in ((1, 0x04), (2, 0x01), (6, 0x01)):
      with self.subTest(byte=index, mask=mask):
        data = bytearray(_turn_frame())
        data[index] ^= mask
        data[7] = _body_controls_checksum(data)
        self.assertFalse(self._tx(common.make_msg(1, 0x3E9, dat=bytes(data))))

  def test_request_reason_and_counter(self):
    self._prime()
    for request, reason in ((0, 8), (4, 8), (1, 4), (2, 4), (3, 8)):
      with self.subTest(request=request, reason=reason):
        self.assertFalse(self._tx(self._frame(request=request, reason=reason)))
    self.assertFalse(self._tx(self._frame(counter=2)))
    self.assertTrue(self._tx(self._frame(counter=1)))
    self.assertFalse(self._tx(self._frame(counter=1)))
    self.safety.set_timer(100 + 100_000)
    self.assertTrue(self._rx(common.make_msg(1, 0x3E9, dat=_idle_template(counter=3))))
    self.assertFalse(self._tx(self._frame(counter=1)))
    self.assertTrue(self._tx(self._frame(counter=4)))

  # Failure cases: a valid independent-lateral engagement cannot signal;
  # disabled MADS or a lost heartbeat grants authority; template/rate limits
  # disappear when only lateral authority is active.
  def _prime_lateral_only(self):
    self._prime()
    self.safety.set_mads_params(True, False, False)
    self.safety.set_controls_allowed(False)
    self.safety.set_controls_allowed_lateral(True)
    self.safety.set_heartbeat_engaged_mads(True)

  def test_independent_lateral_signal_authority(self):
    for enabled, lateral, primary in ((False, False, False), (False, True, False),
                                      (True, False, False), (True, True, False),
                                      (False, False, True), (True, True, True)):
      with self.subTest(enabled=enabled, lateral=lateral, primary=primary):
        self._set_tesla(self.ACTIVE_PARAM_SP)
        self._prime()
        self.safety.set_mads_params(enabled, False, False)
        self.safety.set_controls_allowed(primary)
        self.safety.set_controls_allowed_lateral(lateral)
        self.assertEqual(primary or (enabled and lateral), self._tx(self._frame(request=2)))

  def test_brake_held_blocks_new_signal_even_if_mads_keeps_lateral(self):
    self._prime_lateral_only()
    packer = common.CANPackerSafety("tesla_model3_party")
    brake = packer.make_can_msg_safety("ESP_status", 0, {"ESP_driverBrakeApply": 2})
    self.assertTrue(self._rx(brake))
    self.assertTrue(self.safety.get_controls_allowed_lateral())
    self.assertFalse(self._tx(self._frame(request=2)))
    self.assertTrue(self._tx(self._frame(request=3)))

  def test_lateral_heartbeat_loss_blocks_active_but_allows_release(self):
    self._prime_lateral_only()
    self.assertTrue(self._tx(self._frame(request=2)))
    self.safety.set_heartbeat_engaged_mads(False)
    for _ in range(3):
      self.safety.mads_heartbeat_engaged_check()
    self.assertFalse(self.safety.get_controls_allowed_lateral())
    self.safety.set_timer(100_100)
    self.assertFalse(self._tx(self._frame(request=2)))
    self.assertTrue(self._tx(self._frame(request=3)))

  def test_lateral_only_retains_template_checksum_rate_and_session_limits(self):
    self._prime_lateral_only()
    bad = bytearray(_turn_frame(request=2)); bad[7] ^= 1
    self.assertFalse(self._tx(common.make_msg(1, 0x3E9, dat=bytes(bad))))
    changed = bytearray(_turn_frame(request=2)); changed[0] ^= 1
    changed[7] = _body_controls_checksum(changed)
    self.assertFalse(self._tx(common.make_msg(1, 0x3E9, dat=bytes(changed))))
    self.assertTrue(self._tx(self._frame(request=2)))
    self.safety.set_timer(100_099)
    self.assertFalse(self._tx(self._frame(request=2)))
    self.safety.set_timer(1_500_101)
    self.assertFalse(self._tx(self._frame(request=2)))
    self._set_tesla(self.ACTIVE_PARAM_SP)
    self._prime_lateral_only()
    for index in range(200):
      self.safety.set_timer(100+index*100_000)
      self.assertTrue(self._rx(self._template()))
      self.assertTrue(self._tx(self._frame(request=2)), index)
    self.safety.set_timer(20_000_100)
    self.assertTrue(self._rx(self._template()))
    self.assertFalse(self._tx(self._frame(request=2)))

  def test_cancel_allowed_without_controls_allowed(self):
    """Cancel is accepted at any time because it only releases the lamp."""
    self._prime()
    self.safety.set_controls_allowed(False)
    self.assertFalse(self._tx(self._frame(request=1)))
    self.assertTrue(self._tx(self._frame(request=3, counter=1)))

  def test_rate_limit(self):
    self._prime()
    self.assertTrue(self._tx(self._frame()))
    self.safety.set_timer(100 + 99_999)
    self.assertFalse(self._tx(self._frame()))
    self.safety.set_timer(100 + 100_000)
    self.assertTrue(self._tx(self._frame()))

  def test_session_cap_and_restart(self):
    now = 100
    for frame in range(200):
      now = 100 + frame * 100_000
      self.safety.set_timer(now)
      self.assertTrue(self._rx(common.make_msg(1, 0x3E9, dat=_idle_template())))
      self.safety.set_controls_allowed(True)
      self.assertTrue(self._tx(self._frame()), frame)
    self.safety.set_timer(100 + 200 * 100_000)
    self.assertTrue(self._rx(common.make_msg(1, 0x3E9, dat=_idle_template())))
    self.assertFalse(self._tx(self._frame()))
    self.safety.set_timer(100 + 60_000_000)
    self.assertTrue(self._rx(common.make_msg(1, 0x3E9, dat=_idle_template())))
    self.assertTrue(self._tx(self._frame()))

  def test_mode_reset_clears_template_and_rate_state(self):
    self._prime()
    self.assertTrue(self._tx(self._frame()))
    self._set_mode(CarParams.SafetyModel.noOutput)
    self._set_tesla(self.ACTIVE_PARAM_SP)
    self.safety.set_controls_allowed(True)
    self.assertFalse(self._tx(self._frame()))
    self._prime()
    self.assertTrue(self._tx(self._frame()))

  def test_inactive_message_remains_stock_blocked(self):
    self._set_tesla(TeslaSafetyFlagsSP.HAS_VEHICLE_BUS)
    self.safety.set_controls_allowed(True)
    self.assertFalse(self._tx(self._frame()))

  def test_rx_does_not_change_stock_state(self):
    self.safety.set_controls_allowed(True)
    self.assertFalse(self.safety.get_relay_malfunction())
    self.assertTrue(self._rx(self._template()))
    self.assertTrue(self.safety.get_controls_allowed())
    self.assertFalse(self.safety.get_relay_malfunction())


@unittest.skip("TX inventory for common.SafetyTest's cross-mode scan")
class XpilotPluginTxInventory(common.SafetyTest):
  SAFETY_MODEL = None
  TX_MSGS = [[0x3C2, 1], [0x679, 1], [0x3E9, 1]]


if __name__ == "__main__":
  unittest.main()
