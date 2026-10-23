"""Failure modes (written before the safety changes; exercise the real compiled RX/TX hooks):
- Missing own safetyParam bit, wrong mode (including noOutput:param=1), or no vehicle bus allows TX.
- Auto speed sends while controls_allowed is false; ambient warning must still work disengaged.
- Wrong TX bus/length or missing, malformed, wrong-bus/address RX supplies a usable template.
- Non-tick fields, wheel magnitude/mux, ambient target/palette/brightness/reserved bits escape validation.
- Missing/stale templates pass; exact freshness and rate boundaries or uint32 timer wrap fail.
- Rejected frames consume rate budget, valid frames bypass the rate limit, or sessions exceed frame/time caps.
- RX refresh restarts a session; idle does not permit a new session; mode changes retain template/rate/cap state.
- Relay malfunction is bypassed, a valid frame is blocked, or enabling plugins changes upstream Tesla TX checks.

Auto session: <=60 frames in <30 seconds, >=2 seconds idle restarts it (host normally >=500 ms/frame).
Ambient session: <=150 frames in <15 seconds, >=1 second idle restarts it; no controls_allowed requirement.
Run: PYTHONPATH=opendbc_repo opendbc_repo/.venv/bin/python3 -m unittest opendbc.safety.tests.test_tesla_plugins
"""
import unittest

from opendbc.car.structs import CarParams
from opendbc.safety import DLC_TO_LEN
from opendbc.safety.tests import common, test_defaults, test_tesla


class TeslaPluginBase(common.SafetyTestBase):
  SAFETY_MODEL = CarParams.SafetyModel.tesla
  SAFETY_PARAM = 1

  def setUp(self):
    super().setUp()
    self._mode()

  def _mode(self, mode=CarParams.SafetyModel.tesla, param=1, bit=None, vehicle=True):
    self.safety.set_current_safety_param_sp((self.BIT if bit is None else bit) | int(vehicle))
    self.assertEqual(0, self.safety.set_safety_hooks(mode, param))
    self.safety.set_controls_allowed(True)

  def _msg(self, data, bus=1, addr=None):
    return common.make_msg(bus, self.ADDR if addr is None else addr, dat=bytes(data))

  def _template(self, now=0):
    self.safety.set_timer(now & 0xFFFFFFFF)
    self.assertTrue(self._rx(self._msg(self.TEMPLATE)))

  def test_valid_frame(self):
    self._template()
    self.assertTrue(self._tx(self._msg(self.FRAME)))

  def test_own_param_bit(self):
    for bit in (0, self.BIT ^ 0xC000):
      with self.subTest(bit=bit):
        self._mode(bit=bit)
        self._template()
        self.assertFalse(self._tx(self._msg(self.FRAME)))

  def test_mode_gate(self):
    for mode, param in ((CarParams.SafetyModel.noOutput, 0), (CarParams.SafetyModel.noOutput, 1),
                        (CarParams.SafetyModel.silent, 0)):
      with self.subTest(mode=mode, param=param):
        self._mode(mode, param)
        self._template()
        self.assertFalse(self._tx(self._msg(self.FRAME)))

  def test_vehicle_bus_gate(self):
    self._mode(vehicle=False)
    self._template()
    self.assertFalse(self._tx(self._msg(self.FRAME)))

  def test_controls_allowed(self):
    self._template()
    self.safety.set_controls_allowed(False)
    self.assertEqual(self.ADDR == 0x679, self._tx(self._msg(self.FRAME)))

  def test_tx_bus_and_length(self):
    for bus in range(8):
      for length in DLC_TO_LEN:
        if (bus, length) == (1, len(self.FRAME)):
          continue
        with self.subTest(bus=bus, length=length):
          self._mode()
          self._template()
          data = (self.FRAME + bytes(64))[:length]
          self.assertFalse(self._tx(self._msg(data, bus)))

  def test_rx_template_gate(self):
    bad = [(self.TEMPLATE, bus, self.ADDR) for bus in range(8) if bus != 1]
    bad += [(self.TEMPLATE, 1, self.ADDR + 1)]
    bad += [((self.TEMPLATE + bytes(64))[:n], 1, self.ADDR) for n in DLC_TO_LEN if n != len(self.TEMPLATE)]
    if self.ADDR == 0x3C2:
      bad += [(bytes([mux]) + self.TEMPLATE[1:], 1, self.ADDR) for mux in (0, 2, 3)]
      bad += [(self.TEMPLATE[:3] + bytes([0xC1]) + self.TEMPLATE[4:], 1, self.ADDR)]
    for data, bus, addr in bad:
      with self.subTest(data=data, bus=bus, addr=addr):
        self._mode()
        self.assertTrue(self._rx(self._msg(data, bus, addr)))
        frame = self.FRAME
        if self.ADDR == 0x3C2 and len(data) == 8:
          frame = data[:3] + bytes([(data[3] & 0xC0) | 1]) + data[4:]
        self.assertFalse(self._tx(self._msg(frame)))

  def test_template_freshness(self):
    self._template()
    self._mode()
    self.assertFalse(self._tx(self._msg(self.FRAME)))
    for age in (self.FRESH, self.FRESH + 1):
      self._mode()
      self._template()
      self.safety.set_timer(age)
      self.assertEqual(age == self.FRESH, self._tx(self._msg(self.FRAME)))

  def test_rate_limit(self):
    self._template()
    self.assertTrue(self._tx(self._msg(self.FRAME)))
    self.safety.set_timer(self.RATE - 1)
    self.assertFalse(self._tx(self._msg(self.FRAME)))
    self.safety.set_timer(self.RATE)
    self.assertTrue(self._tx(self._msg(self.FRAME)))

  def test_session_frame_cap(self):
    for i in range(self.CAP):
      self._template(i * self.RATE)
      self.assertTrue(self._tx(self._msg(self.FRAME)), i)
    self._template(self.CAP * self.RATE)
    self.assertFalse(self._tx(self._msg(self.FRAME)))
    self._template(self.CAP * self.RATE + self.IDLE)
    self.assertTrue(self._tx(self._msg(self.FRAME)))

  def test_session_time_cap(self):
    step = self.IDLE // 2
    for now in range(0, self.DURATION, step):
      self._template(now)
      self.assertTrue(self._tx(self._msg(self.FRAME)), now)
    self._template(self.DURATION)
    self.assertFalse(self._tx(self._msg(self.FRAME)))

  def test_mode_reset(self):
    for other in (CarParams.SafetyModel.tesla, CarParams.SafetyModel.noOutput):
      self._mode()
      self._template()
      self.assertTrue(self._tx(self._msg(self.FRAME)))
      self._mode(other)
      self._mode()
      self.safety.set_timer(self.RATE)
      self.assertFalse(self._tx(self._msg(self.FRAME)))
      self._template(self.RATE)
      self.assertTrue(self._tx(self._msg(self.FRAME)))
      self._mode()
      self._template(self.RATE)
      self.assertTrue(self._tx(self._msg(self.FRAME)))

  def test_timer_wrap(self):
    start = 0xFFFF0000
    self._template(start)
    self.assertTrue(self._tx(self._msg(self.FRAME)))
    self.safety.set_timer((start + self.RATE - 1) & 0xFFFFFFFF)
    self.assertFalse(self._tx(self._msg(self.FRAME)))
    self.safety.set_timer((start + self.RATE) & 0xFFFFFFFF)
    self.assertTrue(self._tx(self._msg(self.FRAME)))
    self.safety.set_timer((start + self.FRESH + 1) & 0xFFFFFFFF)
    self.assertFalse(self._tx(self._msg(self.FRAME)))

  def test_relay_malfunction(self):
    self._template()
    self.safety.set_relay_malfunction(True)
    self.assertFalse(self._tx(self._msg(self.FRAME)))


class TestTeslaAutoSpeed(TeslaPluginBase):
  BIT, ADDR = 0x4000, 0x3C2
  TEMPLATE = bytes.fromhex("a51234c056789abc")
  FRAME = bytes.fromhex("a51234c156789abc")
  FRESH, RATE, CAP, DURATION, IDLE = 1_500_000, 250_000, 60, 30_000_000, 2_000_000

  def test_content(self):
    for index in range(8):
      for bit in range(8):
        if index == 3 and bit < 6:
          continue
        self._mode()
        self._template()
        data = bytearray(self.FRAME)
        data[index] ^= 1 << bit
        self.assertFalse(self._tx(self._msg(data)), (index, bit))
    for tick in range(64):
      self._mode()
      self._template()
      data = bytearray(self.FRAME)
      data[3] = (data[3] & 0xC0) | tick
      self.assertEqual(tick in (1, 63), self._tx(self._msg(data)), tick)


class TestTeslaAmbientLight(TeslaPluginBase):
  BIT, ADDR = 0x8000, 0x679
  TEMPLATE = bytes.fromhex("d11234568006a4")
  FRAME = bytes.fromhex("03ff0000e4aea4")
  FRESH, RATE, CAP, DURATION, IDLE = 1_000_000, 80_000, 150, 15_000_000, 1_000_000

  def test_content(self):
    for index, mask in ((0, 255), (4, 128), (5, 7), (6, 254)):
      for bit in range(8):
        if not mask & (1 << bit):
          continue
        self._mode()
        self._template()
        data = bytearray(self.FRAME)
        data[index] ^= 1 << bit
        self.assertFalse(self._tx(self._msg(data)), (index, bit))
    for index in (1, 2, 3):
      for value in range(256):
        self._mode()
        self._template()
        data = bytearray(self.FRAME)
        data[index] = value
        self.assertEqual(value == self.FRAME[index], self._tx(self._msg(data)), (index, value))
    for brightness in range(128):
      self._mode()
      self._template()
      data = bytearray(self.FRAME)
      data[4] = 0x80 | brightness
      self.assertEqual(brightness <= 100, self._tx(self._msg(data)), brightness)
    for zone in range(0, 256, 8):
      for side in (0, 1):
        self._mode()
        self._template()
        data = bytearray(self.FRAME)
        data[5], data[6] = zone | 6, 0xA4 | side
        self.assertEqual((zone, side) in ((0xA8, 0), (0x50, 1), (0xF8, 1)), self._tx(self._msg(data)), (zone, side))


class TestTeslaStockWithPlugins(test_tesla.TestTeslaStockSafety):
  def setUp(self):
    super().setUp()
    self.safety.set_current_safety_param_sp(0xC001)
    self._reset_safety_hooks()
    self.safety.init_tests()
    self.safety.set_current_safety_param_sp(0xC001)


class TestTeslaLongWithPlugins(test_tesla.TestTeslaLongitudinalSafety):
  def setUp(self):
    super().setUp()
    self.safety.set_current_safety_param_sp(0xC001)
    self._reset_safety_hooks()
    self.safety.init_tests()
    self.safety.set_current_safety_param_sp(0xC001)


class TestNoOutputWithPluginBits(test_defaults.TestNoOutput):
  SAFETY_PARAM = 1

  def setUp(self):
    super().setUp()
    self.safety.set_current_safety_param_sp(0xC001)


if __name__ == "__main__":
  unittest.main()
