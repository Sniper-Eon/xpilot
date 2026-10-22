#!/usr/bin/env python3
"""Replaceable lateral controller and longitudinal planner check (runs without a device).

User floors (2026-10-22): the lateral controller output is not limited against SP's (car-side angle rate limits and
panda suffice); a longitudinal planner may bring its own lead-following logic. The host still guarantees:

Failure cases listed before implementation:
- R1 a lateral controller that raises takes controlsd down instead of falling back to SP's controller (and staying there)
- R2 a non-finite steering output reaches the car instead of SP's output
- R3 without a plugin, controlsd's controller is not SP's own object (behaviour change with nothing installed)
- R4 SP's controller stops updating while a plugin steers (a fallback would start from stale state)
- R5 a lateral controller without role:lateral.controller is used
- R6 reset() does not reach both controllers
- P1 a valid planner result does not replace SP's trajectories, aTarget and shouldStop, or aTarget escapes ACCEL_MIN/MAX
- P2 a result with wrong lengths, NaN/inf, or None changes SP's plan
- P3 a planner that raises keeps running or changes SP's plan
- P4 the planner can change FCW (SP's MPC keeps deciding forward collision warnings)
- P5 a planner without role:long.planner is used
- P6 the planner runs after the speed filter integrates aTarget, or before SP's own output is final
"""
import json
import math
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "opendbc_repo")]
try:
  import openpilot.common.params  # noqa: F401
except Exception:
  sys.modules["openpilot.common.params"] = types.SimpleNamespace(Params=object, UnknownKeyName=KeyError)
from openpilot.common.swaglog import cloudlog  # noqa: E402
for _level in ("error", "exception", "warning", "info"):
  setattr(cloudlog, _level, lambda *a, **k: None)

from openpilot.tesla import plugins  # noqa: E402
from openpilot.tesla.plugin import Plugin  # noqa: E402

N = 17


class CP:
  brand = "tesla"


class FakeParams:
  def get_bool(self, key):
    return False


def make(name, claims, **hooks):
  attrs = {"NAME": name, "CLAIMS": tuple(claims), "ENABLE_PARAM": None, "PRIORITY": 100}
  for hook, obj in hooks.items():
    attrs[hook] = classmethod(lambda cls, *a, _o=obj: _o)
  return type(name, (Plugin,), attrs)


class Ctl:
  def __init__(self, angle, fail=False):
    self.angle, self.fail, self.calls, self.resets = angle, fail, 0, 0

  def update(self, *args):
    self.calls += 1
    if self.fail:
      raise RuntimeError("ctl")
    return 0.0, self.angle, f"log{self.angle}"

  def reset(self):
    self.resets += 1


def sp_planner():
  return types.SimpleNamespace(v_desired_trajectory=[1.0] * N, a_desired_trajectory=[0.1] * N, j_desired_trajectory=[0.0] * N,
                               output_a_target=0.1, output_should_stop=False, fcw=True)


class Plan:
  def __init__(self, result=None, fail=False):
    self.result, self.fail, self.calls = result, fail, 0

  def update(self, sm, sp):
    self.calls += 1
    if self.fail:
      raise RuntimeError("plan")
    return self.result


def main() -> int:
  errors = []
  faults = []
  plugins.record_fault = lambda name, where, exc: faults.append((name, where))
  args = (True, None, None, None, False, 0.0, None, False, 0.2)

  # ---- lateral controller ----
  sp = Ctl(1.0)
  plugins.PLUGINS = ()
  if plugins.lateral_controller(CP, None, None, FakeParams(), sp) is not sp:
    errors.append("R3 SP controller wrapped with no plugin")
  plugins.PLUGINS = (make("no_claim", [], lat_controller=Ctl(9.0)),)
  if plugins.lateral_controller(CP, None, None, FakeParams(), sp) is not sp:
    errors.append("R5 unclaimed lateral controller used")

  good = Ctl(5.0)
  plugins.PLUGINS = (make("lat", ["role:lateral.controller"], lat_controller=good),)
  sp = Ctl(1.0)
  lac = plugins.lateral_controller(CP, None, None, FakeParams(), sp)
  out = lac.update(*args)
  if out[1] != 5.0:
    errors.append(f"R1 plugin output not used: {out}")
  if sp.calls != 1:
    errors.append(f"R4 SP controller not updated alongside ({sp.calls})")
  lac.reset()
  if good.resets != 1 or sp.resets != 1:
    errors.append("R6 reset not forwarded to both")

  for label, bad in (("raise", Ctl(5.0, fail=True)), ("nan", Ctl(float("nan"))), ("inf", Ctl(float("inf")))):
    plugins.PLUGINS = (make("lat", ["role:lateral.controller"], lat_controller=bad),)
    sp = Ctl(1.0)
    lac = plugins.lateral_controller(CP, None, None, FakeParams(), sp)
    try:
      o1, o2 = lac.update(*args), lac.update(*args)
    except Exception as e:
      errors.append(f"R1 {label}: raised {e!r}")
      continue
    if o1[1] != 1.0 or o2[1] != 1.0 or o1[2] != "log1.0":
      errors.append(f"R{'1' if label == 'raise' else '2'} {label}: outputs {o1} {o2}")
    if bad.calls != 1:
      errors.append(f"R1 {label}: faulted controller called {bad.calls}x")

  # ---- longitudinal planner ----
  from opendbc.car.interfaces import ACCEL_MAX
  ok_result = types.SimpleNamespace(speeds=[2.0] * N, accels=[0.5] * N, jerks=[0.1] * N, a_target=99.0, should_stop=True)
  plugins.PLUGINS = (make("lp_no", [], long_planner=Plan(ok_result)),)
  if plugins.long_planners(CP, None, FakeParams()):
    errors.append("P5 unclaimed long planner used")
  planner = Plan(ok_result)
  plugins.PLUGINS = (make("lp", ["role:long.planner"], long_planner=planner),)
  lps = plugins.long_planners(CP, None, FakeParams())
  p = sp_planner()
  plugins.apply_long_planner(lps, p, {})
  if list(p.v_desired_trajectory) != [2.0] * N or list(p.a_desired_trajectory) != [0.5] * N or not p.output_should_stop:
    errors.append(f"P1 plan not replaced: {p}")
  if p.output_a_target != ACCEL_MAX:
    errors.append(f"P1 aTarget {p.output_a_target} not clipped to {ACCEL_MAX}")
  if p.fcw is not True:
    errors.append("P4 fcw changed")

  bads = {"short": types.SimpleNamespace(speeds=[2.0] * 3, accels=[0.5] * N, jerks=[0.0] * N, a_target=0.2, should_stop=False),
          "nan": types.SimpleNamespace(speeds=[2.0] * N, accels=[math.nan] * N, jerks=[0.0] * N, a_target=0.2, should_stop=False),
          "inf_a": types.SimpleNamespace(speeds=[2.0] * N, accels=[0.5] * N, jerks=[0.0] * N, a_target=math.inf, should_stop=False),
          "none": None}
  for label, res in bads.items():
    lst = [Plan(res)]
    lst[0].plugin_name = label
    p = sp_planner()
    plugins.apply_long_planner(lst, p, {})
    if p.v_desired_trajectory != [1.0] * N or p.output_a_target != 0.1 or p.output_should_stop:
      errors.append(f"P2 {label} changed SP plan")
  boom = Plan(fail=True)
  boom.plugin_name = "boom"
  lst = [boom]
  p = sp_planner()
  try:
    plugins.apply_long_planner(lst, p, {})
    plugins.apply_long_planner(lst, p, {})
    if lst or boom.calls != 1 or p.output_a_target != 0.1:
      errors.append(f"P3 faulted planner kept={bool(lst)} calls={boom.calls}")
  except Exception as e:
    errors.append(f"P3 raised {e!r}")

  src = (ROOT / "openpilot/selfdrive/controls/lib/longitudinal_planner.py").read_text()
  i = src.find("plugins.apply_long_planner")
  j = src.find("self.output_a_target = np.clip(output_a_target")
  k = src.find("self.v_desired_filter.x = self.v_desired_filter.x + self.dt")
  if not (0 <= j < i < k):
    errors.append("P6 apply_long_planner not between SP's final output and the speed filter integration")

  print(json.dumps({"errors": errors}, indent=1))
  return 1 if errors else 0


if __name__ == "__main__":
  sys.exit(main())
