#!/usr/bin/env python3
"""DS compatibility failures: vehicle-model curvature replaces commanded curvature;
a straight-road prediction transient starts braking; confirmation survives a gap,
disengagement, override or low speed; sustained turns lose braking. Exercise the
shared SCCV class used by both SP and TN; never publish synthetic device messages.
"""
from types import SimpleNamespace as N
from unittest.mock import patch
import unittest
import numpy as np
from openpilot.sunnypilot.selfdrive.controls.lib.smart_cruise_control import vision_controller as v


class FakeParams:
  def get_bool(self, key):
    return True


class SccvCompatibility(unittest.TestCase):
  def setUp(self):
    with patch.object(v, 'Params', FakeParams):
      self.c = v.SmartCruiseControlVision()
    self.c._update_params = lambda: None
    self.sm = {'controlsState': N(curvature=0.001, desiredCurvature=0.02),
               'modelV2': N(orientationRate=N(z=[0.08] * 33), velocity=N(x=[20.] * 33))}

  def tick(self, n=1, enabled=True, override=False, speed=20.):
    for _ in range(n):
      self.c.update(self.sm, enabled, override, speed, 0., 30.)

  def test_commanded_curvature_drives_turn_phase(self):
    self.tick()
    self.assertAlmostEqual(self.c.current_lat_acc, 8.)

  def test_short_prediction_spike_does_not_brake(self):
    self.tick()  # disabled -> enabled
    self.tick(4)
    self.assertEqual(self.c.state, v.VisionState.enabled)
    self.assertFalse(self.c.is_active)
    self.sm['modelV2'].orientationRate.z = [0.005] * 33
    self.tick()
    self.assertEqual(self.c.state, v.VisionState.enabled)

  def test_persistent_curve_enters_and_brakes(self):
    self.tick(6)
    self.assertEqual(self.c.state, v.VisionState.entering)
    self.assertLess(self.c.output_a_target, 0.)
    self.tick()
    self.assertEqual(self.c.state, v.VisionState.turning)

  def test_continuity_resets_after_gap_override_disable_or_low_speed(self):
    for cause in ('gap', 'override', 'disable', 'lowSpeed'):
      with self.subTest(cause=cause):
        self.setUp(); self.tick(4)
        if cause == 'gap':
          self.sm['modelV2'].orientationRate.z = [0.005] * 33
          self.tick()
          self.sm['modelV2'].orientationRate.z = [0.08] * 33
        elif cause == 'override':
          self.tick(override=True); self.tick()
        elif cause == 'disable':
          self.tick(enabled=False); self.tick()
        else:
          self.tick(speed=1.)
        self.tick(4)
        self.assertEqual(self.c.state, v.VisionState.enabled)
        self.tick()
        self.assertEqual(self.c.state, v.VisionState.entering)

  def test_active_disable_and_driver_override_win(self):
    self.tick(6); self.tick(override=True)
    self.assertEqual(self.c.state, v.VisionState.overriding)
    self.assertFalse(self.c.is_active)
    self.tick(enabled=False)
    self.assertEqual(self.c.state, v.VisionState.disabled)
    self.assertFalse(self.c.is_active)

  def test_feature_switch_off_stays_inactive(self):
    self.c.enabled = False
    self.tick(10)
    self.assertEqual(self.c.state, v.VisionState.disabled)
    self.assertFalse(self.c.is_active)


if __name__ == '__main__':
  unittest.main()
