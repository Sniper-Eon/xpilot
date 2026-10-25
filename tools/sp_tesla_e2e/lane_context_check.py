#!/usr/bin/env python3
"""Actual DesireHelper -> generic plugin context end-to-end check.

Failures specified before implementation: preparation can start through a manual
nudge; a reliable veto cannot abort; a turn-only lamp enters the lane state
machine; a lane-position lamp generates an intersection turn desire; an invalid
constraint escapes isolation; a plugin grants a change that SP rejected.
"""
import json
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace as N

ROOT = Path(__file__).resolve().parents[2]
runpy.run_path(str(ROOT / 'tools/sp_tesla_e2e/phase2_check.py'))
from openpilot.tesla import plugins
from openpilot.cereal import log, custom
from openpilot.selfdrive.controls.lib.desire_helper import DesireHelper


class Policy:
  plugin_name = 'fixture'
  value = None
  broken = False

  def allow(self, *args):
    return True

  def constraints(self, carstate, direction):
    if self.broken:
      raise ValueError('fixture failure')
    return self.value


def cs(blinker=False, nudge=False, blind=False):
  return N(vEgo=20., leftBlinker=blinker, rightBlinker=False, leftBlindspot=blind,
           rightBlindspot=False, steeringPressed=nudge, steeringTorque=1. if nudge else 0., brakePressed=False)


def helper(policy):
  h = DesireHelper()
  h.lane_change_policy = [policy]
  h.alc.update_params = lambda: None
  h.lane_turn_controller.update_params = lambda: None
  return h


def main():
  errors = []
  if not hasattr(plugins, 'LaneChangeLimits') or not hasattr(plugins, 'apply_lane_change_context'):
    print(json.dumps({'errors': ['Missing generic lane preparation context API']}))
    return 1
  Limits = plugins.LaneChangeLimits
  p = Policy()
  p.value = Limits(allow_start=False)
  h = helper(p)
  for state in [cs(), cs(True), cs(True, True)]:
    h.update(state, True, 1.)
  if h.lane_change_state != log.LaneChangeState.preLaneChange:
    errors.append('Preparation was bypassed by torque/automatic policy')
  p.value = Limits()
  h.update(cs(True), True, 1.)
  if h.lane_change_state != log.LaneChangeState.laneChangeStarting:
    errors.append('A fresh unrestricted SP decision could not start')
  p.value = Limits(allow_continue=False)
  h.update(cs(True), True, 1.)
  if h.lane_change_state == log.LaneChangeState.laneChangeStarting or h.desire != log.Desire.none:
    errors.append('A new reliable veto did not abort the current change')
  p.value = Limits(turn_only=True)
  h = helper(p)
  for state in [cs(), cs(True), cs(True, True)]:
    h.update(state, True, 1.)
  if h.lane_change_state != log.LaneChangeState.off:
    errors.append('Turn-only physical lamp entered lane-change state machine')
  p.value = Limits(suppress_turn=True)
  h = helper(p)
  h.lane_turn_controller.get_turn_direction = lambda: custom.ModelDataV2SP.TurnDirection.turnLeft
  h.update(cs(True), True, 1.)
  if h.lane_turn_direction != custom.ModelDataV2SP.TurnDirection.none:
    errors.append('Lane-position lamp retained an intersection turn desire')
  p.value = Limits()
  for blinded in [True, False]:
    h = helper(p)
    for state in [cs(), cs(True, blind=blinded), cs(True, blind=blinded)]:
      h.update(state, not blinded, 1.)
    if blinded and h.lane_change_state == log.LaneChangeState.laneChangeStarting:
      errors.append('Plugin granted a change while lateral control was off / blind')
  p.broken = True
  h = helper(p)
  for state in [cs(), cs(True, True), cs(True, True)]:
    h.update(state, True, 1.)
  if h.lane_change_state == log.LaneChangeState.laneChangeStarting or h.lane_change_policy:
    errors.append('Faulting context did not isolate and inhibit a new change')
  if h.lane_turn_direction != custom.ModelDataV2SP.TurnDirection.none:
    errors.append('Faulting context left a turn desire active')
  class BrokenProperty(Policy):
    @property
    def constraints(self):
      raise ValueError('broken context accessor')
  h = helper(BrokenProperty())
  h.lane_turn_controller.get_turn_direction = lambda: custom.ModelDataV2SP.TurnDirection.turnLeft
  try:
    h.update(cs(True, True), True, 1.)
    if h.lane_change_policy or h.lane_turn_direction != custom.ModelDataV2SP.TurnDirection.none:
      errors.append('Broken context accessor was not isolated')
  except Exception:
    errors.append('Broken context accessor escaped into modeld')
  print(json.dumps({'errors': errors}, indent=2))
  return bool(errors)


if __name__ == '__main__':
  raise SystemExit(main())
