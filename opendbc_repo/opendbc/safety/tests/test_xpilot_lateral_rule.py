"""Failure-first ABI 2 compatibility matrix: ABI 1 must keep primary-only
authority; only an explicit ABI 2/type 2 rule may use native enabled MADS lateral
authority. Missing authority, brake, invalid guard, stale template, relay fault,
wrong bus and forged primary-only v1 flags all fail. No real vehicle IO.
"""
import random
import struct
import unittest
from opendbc.safety.tests.common import CANPackerSafety
from opendbc.safety.tests.xpilot_rules_helpers import NAV, AUTO, configure, control, frames, harness, packet, table, upload


def lateral_table():
  row = bytearray(NAV); row[2] = 2; row[43] = 1
  blob = bytearray(table((row,))); struct.pack_into('<H', blob, 4, 2)
  return blob


class TestLateralRule(unittest.TestCase):
  def setUp(self): self.s = harness()

  def load(self, blob):
    self.s.set_safety_hooks(19, 0)
    self.s.set_timer(0)
    result = upload(self.s, blob)
    self.assertEqual(0, result[3])
    self.s.set_current_safety_param_sp(0x7001)
    self.s.set_safety_hooks(10, 0)
    self.s.init_tests()
    self.s.set_current_safety_param_sp(0x7001)

  def prime(self, mads=True, lateral=True):
    rx, tx = frames(2, random.Random(20261028))
    self.s.set_timer(100)
    self.s.safety_rx_hook(packet(0x3e9, rx))
    self.s.set_alternative_experience(1024 if mads else 0)
    self.s.set_controls_allowed(False)
    self.s.set_controls_allowed_lateral(lateral)
    return tx

  def test_v1_stays_primary_only(self):
    self.load(table((NAV,)))
    self.assertFalse(self.s.safety_tx_hook(packet(0x3e9, self.prime())))

  def test_explicit_v2_uses_only_enabled_native_lateral_authority(self):
    for mads, lateral in [(False,False),(False,True),(True,False),(True,True)]:
      with self.subTest(mads=mads,lateral=lateral):
        self.load(lateral_table());tx=self.prime(mads,lateral)
        self.assertEqual(mads and lateral, self.s.safety_tx_hook(packet(0x3e9,tx)))

  def test_brake_relay_wrong_bus_stale_still_block(self):
    for failure in ['brake','relay','bus','stale']:
      with self.subTest(failure=failure):
        self.load(lateral_table());tx=self.prime()
        if failure=='brake':
          brake=CANPackerSafety('tesla_model3_party').make_can_msg_safety('ESP_status',0,{'ESP_driverBrakeApply':2})
          self.s.safety_rx_hook(brake)
          self.assertTrue(self.s.get_brake_pressed_prev())
          self.s.set_controls_allowed_lateral(True)
        if failure=='relay':self.s.set_relay_malfunction(True)
        if failure=='stale':self.s.set_timer(1_500_101)
        self.assertFalse(self.s.safety_tx_hook(packet(0x3e9,tx,0 if failure=='bus' else 1)))

  def test_v1_cannot_smuggle_v2_and_unknown_guards_are_rejected(self):
    for pos,val in [(4,1),(59,2),(59,255),(18,1)]:
      self.s.set_safety_hooks(19,0)
      blob=lateral_table();blob[pos]=val
      self.assertNotEqual(0,upload(self.s,blob)[3])


if __name__=='__main__':unittest.main()
