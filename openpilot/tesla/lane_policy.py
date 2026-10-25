"""One-way plugin limits applied after SP's lane state update, before desire output.

A plugin cannot start a change here. It can keep a lamp in preparation, veto
continuation, or distinguish a route-turn lamp from a lane-position lamp.
"""
from dataclasses import dataclass, fields


@dataclass(frozen=True)
class LaneChangeLimits:
  allow_start: bool = True
  allow_continue: bool = True
  turn_only: bool = False
  suppress_turn: bool = False


def apply_context(helper, carstate, lateral_active, call, fault):
  from openpilot.cereal import log, custom
  states = log.LaneChangeState
  was_changing = getattr(helper, '_xpilot_previous_lane_state', states.off) == states.laneChangeStarting
  limits = []
  for policy in list(helper.lane_change_policy):
    try:
      context = getattr(policy, 'constraints', None)
    except Exception as exc:
      helper.lane_change_policy.remove(policy)
      fault(getattr(policy, 'plugin_name', '?'), 'modeld.lane_context', exc)
      helper._xpilot_lane_context_fault = True
      continue
    if not callable(context):
      continue
    ok, value = call(helper.lane_change_policy, policy, 'constraints', 'modeld.lane_context',
                     carstate, helper.lane_change_direction)
    if ok and value is not None:
      if not isinstance(value, LaneChangeLimits) or any(type(getattr(value, f.name)) is not bool for f in fields(value)):
        helper.lane_change_policy.remove(policy)
        fault(getattr(policy, 'plugin_name', '?'), 'modeld.lane_context', ValueError('invalid lane limits'))
        ok = False
      else:
        limits.append(value)
    if not ok:
      helper._xpilot_lane_context_fault = True
  turn_only = any(v.turn_only for v in limits)
  blocked = bool(getattr(helper, '_xpilot_lane_context_fault', False)) or any(
    not (v.allow_continue if was_changing else v.allow_start) for v in limits)
  if turn_only:
    helper.lane_change_state = states.off
    helper.lane_change_direction = log.LaneChangeDirection.none
    helper.lane_change_timer = 0.
  elif blocked and helper.lane_change_state == states.laneChangeStarting:
    if lateral_active and carstate.leftBlinker != carstate.rightBlinker:
      helper.lane_change_state = states.preLaneChange
      helper.lane_change_direction = helper.get_lane_change_direction(carstate)
    else:
      helper.lane_change_state = states.off
      helper.lane_change_direction = log.LaneChangeDirection.none
    helper.lane_change_timer = 0.
  if getattr(helper, '_xpilot_lane_context_fault', False) or any(v.suppress_turn for v in limits):
    helper.lane_turn_direction = custom.ModelDataV2SP.TurnDirection.none
  helper._xpilot_previous_lane_state = helper.lane_change_state
