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
- B1 an accel boost without role:long.accel_boost is used, or without a plugin the planner loses openpilot's AccelBoost object
- B2 a boost plugin lowers the model (e2e) acceleration, or raises it by more than ACCEL_BOOST_CAP
- B3 a boost that raises or returns NaN/inf keeps running or changes the e2e candidate (openpilot's AccelBoost must take over)
- B4 openpilot's AccelBoost stops updating while a plugin boosts (a fallback would start from stale state)
- B5 total_boost (published as longitudinalPlan.accelBoost) differs from the boost actually applied
- B6 plannerd does not hand the planner's AccelBoost to the plugin hook
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

  # ---- accel boost ----
  class SpBoost:
    def __init__(self):
      self.calls, self.total_boost = 0, 0.05

    def update(self, sm, a_e2e, a_mpc, a_cruise):
      self.calls += 1
      return a_e2e + self.total_boost

  class Boost:
    def __init__(self, out=None, fail=False):
      self.out, self.fail, self.calls = out, fail, 0

    def update(self, sm, a_e2e, a_mpc, a_cruise):
      self.calls += 1
      if self.fail:
        raise RuntimeError("boom")
      return self.out(a_e2e)

  plugins.PLUGINS = (make("ab_no", [], accel_boost=Boost(lambda a: a + 0.2)),)
  sp_b = SpBoost()
  if plugins.accel_boost(CP, None, FakeParams(), sp_b) is not sp_b:
    errors.append("B1 unclaimed accel boost used or openpilot's AccelBoost replaced")
  plugins.PLUGINS = ()
  if plugins.accel_boost(CP, None, FakeParams(), sp_b) is not sp_b:
    errors.append("B1 no plugin: openpilot's AccelBoost not kept")
  for label, fn, want in (("ok", lambda a: a + 0.2, 0.2), ("cap", lambda a: a + 3.0, plugins.ACCEL_BOOST_CAP)):
    sp_b = SpBoost()
    plugins.PLUGINS = (make("ab", ["role:long.accel_boost"], accel_boost=Boost(fn)),)
    g = plugins.accel_boost(CP, None, FakeParams(), sp_b)
    out = g.update({}, 0.3, 1.0, 1.0)
    if abs(out - (0.3 + want)) > 1e-9:
      errors.append(f"B2 {label}: e2e 0.3 became {out}, expected {0.3 + want}")
    if abs(g.total_boost - want) > 1e-9:
      errors.append(f"B5 {label}: total_boost {g.total_boost} != applied {want}")
    if sp_b.calls != 1:
      errors.append(f"B4 {label}: openpilot's AccelBoost updated {sp_b.calls}x")
  for label, b in (("lower", Boost(lambda a: a - 0.2)), ("nan", Boost(lambda a: math.nan)), ("raise", Boost(fail=True))):
    sp_b = SpBoost()
    plugins.PLUGINS = (make("ab_" + label, ["role:long.accel_boost"], accel_boost=b),)
    g = plugins.accel_boost(CP, None, FakeParams(), sp_b)
    try:
      outs = [g.update({}, 0.3, 1.0, 1.0) for _ in range(2)]
    except Exception as e:
      errors.append(f"B3 {label}: raised {e!r}")
      continue
    if outs != [0.35, 0.35] or b.calls != 1 or g.total_boost != 0.05:
      errors.append(f"B{'2' if label == 'lower' else '3'} {label}: outputs {outs}, plugin calls {b.calls}, total_boost {g.total_boost}")
  src = (ROOT / "openpilot/selfdrive/controls/plannerd.py").read_text()
  if "longitudinal_planner.accel_boost = plugins.accel_boost(CP, CP_SP, params, longitudinal_planner.accel_boost)" not in src:
    errors.append("B6 plannerd does not wire the accel_boost hook")

  print(json.dumps({"errors": errors}, indent=1))
  return 1 if errors else 0


if __name__ == "__main__":
  sys.exit(main())
