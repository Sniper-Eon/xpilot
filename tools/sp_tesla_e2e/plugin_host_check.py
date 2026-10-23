#!/usr/bin/env python3
"""Plugin host check: fault isolation, enable switch and plugin metadata (runs without a device).

Failure cases listed before implementation:
- P1 a plugin hook raises and card's host raises with it (card dies, openpilot drops out while driving)
- P2 a faulted plugin keeps sending CAN or getting hooks
- P3 a plugin whose __init__ raises takes the other plugins down with it
- P4 a fault is not recorded for the UI (plugin name + where)
- P5 a disabled plugin is still built in card, its process still runs, or its plan filter is still used
- P6 a plan filter raises and the longitudinal plan is not published (controlsd would see a stale plan)
- P7 a faulted plan filter keeps being called every cycle
- P8 a non-Tesla car loads plugins
- P9 a real plugin lacks TITLE/ENABLE_PARAM, or names a setting key not declared in params_keys.h,
       or two settings share a key, or ENABLE_PARAM is not a BOOL key
- P10 a plugin ui.py does not parse, or the plugin page is missing a plugin
- P11 common/plugin_params.inc is out of date with the plugins' plugin.json params (device would miss a key)
- P12 a key is declared both in params_keys.h and a plugin.json, or in two plugins
- P13 a lower plugin speed target does not win over cruise (cannot tighten)
- P14 a higher plugin target does not raise the cruise target while engaged (cannot accelerate)
- P15 a raise applies while disengaged, during gas override, or while pressing the brake
- P16 a raise goes above V_CRUISE_MAX
- P17 a raise overrides SP's other limiters (speed limit assist, SCC) instead of only the driver set speed
- P18 two raising plugins: the higher one wins (should be the lower, more conservative one)
- P19 a long target that raises takes plannerd down or keeps running; None changes nothing
- P20 a disabled plugin still contributes a long target
- R1 card does not use the active plugin's radar_interface (source:radar)
- R2 no, a disabled, or a non-Tesla radar plugin: card gets anything but the port radar
- R3 a radar returned without a source:radar claim, or by the loser of a source:radar conflict, is used
- R4 radar_interface raises at creation: card raises, no fault recorded, or the port radar is not used
- R5 the plugin radar raises in update: card raises, or the plugin keeps being called instead of the port radar

Run from the repo root with the openpilot python env. Native-only modules (Params) are stubbed if missing.
"""
import ast
import json
from pathlib import Path
import re
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "opendbc_repo")]
try:
  import openpilot.common.params  # noqa: F401
except Exception:
  stub = types.ModuleType("openpilot.common.params")
  stub.Params = object
  stub.UnknownKeyName = KeyError
  sys.modules["openpilot.common.params"] = stub

from openpilot.tesla import plugins  # noqa: E402
from openpilot.tesla.plugin import Plugin  # noqa: E402

KEY_RE = r'\{"(\w+)", \{[^,]+, (\w+)'
CORE_KEYS = dict(re.findall(KEY_RE, (ROOT / "openpilot/common/params_keys.h").read_text()))
INC = ROOT / "openpilot/common/plugin_params.inc"
PLUGIN_KEYS = dict(re.findall(KEY_RE, INC.read_text())) if INC.exists() else {}
KEYS = {**CORE_KEYS, **PLUGIN_KEYS}


class FakeParams:
  def __init__(self, values=None):
    self.values = dict(values or {})

  def get_bool(self, key):
    return bool(self.values.get(key, False))

  def get(self, key, return_default=False):
    return self.values.get(key)


class CP:
  brand = "tesla"


calls = []


made = []


def make(name, fail_in=None, enable=None):
  made.append(name)
  addr = 0x100 + len(made)  # each fake owns its own exclusive CAN claim
  class P(Plugin):
    NAME, TITLE, ENABLE_PARAM = name, name, enable
    CLAIMS = (f"can.tx:0x{addr:X}:0", "plan.filter", f"process:{name}d")

    def __init__(self, CP, params):
      super().__init__(CP, params)
      if fail_in == "__init__":
        raise RuntimeError("init")

    def observe_can(self, can_list, now_ns):
      calls.append((name, "observe_can"))
      if fail_in == "observe_can":
        raise RuntimeError("observe")
      return [(addr, f"{name}-now".encode(), 0)]

    def control_sends(self, CS, CC, now_ns):
      calls.append((name, "control_sends"))
      if fail_in == "control_sends":
        raise RuntimeError("control")
      return [(addr, f"{name}-ctl".encode(), 0)]

    @classmethod
    def processes(cls):
      return [types.SimpleNamespace(name=f"{name}d", should_run=lambda started, params, CP: started)]

    @classmethod
    def plan_filter(cls, CP, params):
      return Filter(name, fail_in == "plan")
  P.__name__ = name
  return P


class Filter:
  def __init__(self, name, fail):
    self.name, self.fail, self.calls = name, fail, 0

  def publisher(self, pm, sm):
    outer = self

    class Sink:
      def send(self, service, msg):
        outer.calls += 1
        if outer.fail:
          raise RuntimeError("filter")
        pm.send(service, msg + [outer.name])
    return Sink()


class PM:
  def __init__(self):
    self.sent = []

  def send(self, service, msg):
    self.sent.append((service, msg))


def main() -> int:
  errors = []
  faults = []
  plugins.record_fault = lambda name, where, exc: faults.append((name, where))

  plugins.PLUGINS = (make("good"), make("bad_obs", "observe_can"), make("bad_init", "__init__"), make("off", enable="OffKey"))
  host = plugins.CarPlugins(CP, FakeParams())
  names = [p.NAME for p in host.plugins]
  if "bad_init" in names:
    errors.append("P3 plugin with failing __init__ kept")
  if "good" not in names:
    errors.append("P3 good plugin dropped")
  if "off" in names:
    errors.append("P5 disabled plugin built in card")
  try:
    out1 = host.observe_can([])
    out2 = host.observe_can([])
  except Exception as e:
    errors.append(f"P1 host raised {e!r}")
    out1 = out2 = []
  if b"good-now" not in [s[1] for s in out1] or b"good-now" not in [s[1] for s in out2]:
    errors.append("P1 good plugin output lost after a fault")
  if any(c == ("bad_obs", "observe_can") for c in calls[2:]):
    errors.append("P2 faulted plugin still called")
  if b"bad_obs-ctl" in [s[1] for s in host.control_sends(None, None, 0)]:
    errors.append("P2 faulted plugin still sends")
  if ("bad_obs", "card.observe_can") not in faults or ("bad_init", "card.__init__") not in faults:
    errors.append(f"P4 faults not recorded: {faults}")

  procs = plugins.processes()
  off = [p for p in procs if p.name == "offd"]
  if not off or off[0].should_run(True, FakeParams(), None):
    errors.append("P5 disabled plugin process still runs")
  if not [p for p in procs if p.name == "goodd"][0].should_run(True, FakeParams(), None):
    errors.append("P5 enabled plugin process blocked")
  if not off[0].should_run(True, FakeParams({"OffKey": True}), None):
    errors.append("P5 plugin process ignores its enable param")

  plugins.PLUGINS = (make("bad_plan", "plan"), make("good"), make("off", enable="OffKey"))
  filters = plugins.plan_filters(CP, FakeParams())
  if any(f.name == "off" for f in filters):
    errors.append("P5 disabled plugin plan filter used")
  pm = PM()
  bad = next(f for f in filters if f.name == "bad_plan")
  for _ in range(3):
    try:
      plugins.plan_sink(filters, pm, None).send("longitudinalPlan", [])
    except Exception as e:
      errors.append(f"P6 plan_sink raised {e!r}")
      break
  if len(pm.sent) != 3:
    errors.append(f"P6 plan published {len(pm.sent)}/3 times")
  if bad.calls > 1:
    errors.append(f"P7 faulted filter called {bad.calls} times")

  class Other:
    brand = "toyota"
  if plugins.CarPlugins(Other, FakeParams()).plugins or plugins.plan_filters(Other, FakeParams()):
    errors.append("P8 non-Tesla car loads plugins")

  import importlib
  plugins_mod = importlib.reload(plugins)
  real = plugins_mod.PLUGINS
  seen = set()
  for cls in real:
    if not cls.TITLE or not cls.ENABLE_PARAM:
      errors.append(f"P9 {cls.NAME} lacks TITLE or ENABLE_PARAM")
    if KEYS.get(cls.ENABLE_PARAM) != "BOOL":
      errors.append(f"P9 {cls.NAME} ENABLE_PARAM {cls.ENABLE_PARAM} not a declared BOOL")
    for s in cls.SETTINGS:
      if s.key not in KEYS:
        errors.append(f"P9 {cls.NAME} setting {s.key} not in params_keys.h")
      if s.key in seen:
        errors.append(f"P9 duplicate setting {s.key}")
      seen.add(s.key)
    ui = ROOT / "openpilot/tesla/plugins" / cls.NAME / "ui.py"
    if ui.exists():
      try:
        ast.parse(ui.read_text())
      except SyntaxError as e:
        errors.append(f"P10 {ui} {e}")
  if KEYS.get("XpilotPluginFaults") != "JSON":
    errors.append("P4 XpilotPluginFaults not declared as JSON")
  page = (ROOT / "openpilot/tesla/ui/plugins_page.py")
  if not page.exists() or "PLUGINS" not in page.read_text():
    errors.append("P10 plugin page missing or not driven by PLUGINS")

  import subprocess
  gen = subprocess.run([sys.executable, str(ROOT / "openpilot/tesla/plugins/gen_params.py"), "--check"], capture_output=True, text=True)
  if gen.returncode != 0:
    errors.append(f"P11 {gen.stdout.strip() or gen.stderr.strip()[-200:]}")
  if not INC.exists() or '#include "common/plugin_params.inc"' not in (ROOT / "openpilot/common/params_keys.h").read_text():
    errors.append("P11 params_keys.h does not include common/plugin_params.inc")
  errors += [f"P12 {k} in params_keys.h and a plugin.json" for k in CORE_KEYS.keys() & PLUGIN_KEYS.keys()]
  owners = {}
  for f in sorted((ROOT / "openpilot/tesla/plugins").glob("*/plugin.json")):
    for k in json.loads(f.read_text()).get("params", {}):
      if k in owners:
        errors.append(f"P12 {k} in {owners[k]} and {f.parent.name}")
      owners[k] = f.parent.name
  errors += long_target_checks(plugins_mod)
  errors += radar_checks(plugins_mod)

  print(json.dumps({"plugins": [c.NAME for c in real], "errors": errors}, indent=1))
  return 1 if errors else 0


def long_target_checks(plugins) -> list[str]:
  from openpilot.cereal import custom
  from openpilot.common.constants import CV
  from openpilot.selfdrive.car.cruise import V_CRUISE_MAX
  Source = custom.LongitudinalPlanSP.LongitudinalPlanSource
  errors = []

  def sm(enabled=True, override=False, gas=False, brake=False):
    cc = types.SimpleNamespace(enabled=enabled, cruiseControl=types.SimpleNamespace(override=override))
    return {"carControl": cc, "carState": types.SimpleNamespace(gasPressed=gas, brakePressed=brake)}

  class T:
    def __init__(self, v, fail=False):
      self.v, self.fail, self.calls = v, fail, 0

    def update(self, sm, v_ego, v_cruise):
      self.calls += 1
      if self.fail:
        raise RuntimeError("target")
      return self.v

  def run(targets, s, cruise=20.0, sla=40.0):
    base = {Source.cruise: (cruise, 0.0), Source.speedLimitAssist: (sla, 0.0)}
    out = plugins.apply_long_targets(targets, s, dict(base), 0.0, 0.0, cruise)
    return min(out.values(), key=lambda t: t[0])[0], out

  if run([T(15.0)], sm())[0] != 15.0:
    errors.append("P13 lower plugin target ignored")
  if run([T(25.0)], sm())[0] != 25.0:
    errors.append("P14 raise ignored while engaged")
  for label, s in (("disengaged", sm(enabled=False)), ("override", sm(override=True)), ("gas", sm(gas=True)), ("brake", sm(brake=True))):
    if run([T(25.0)], s)[0] != 20.0:
      errors.append(f"P15 raise applied while {label}")
  if run([T(500.0)], sm(), sla=1000.0)[0] > V_CRUISE_MAX * CV.KPH_TO_MS + 1e-6:
    errors.append("P16 raise above V_CRUISE_MAX")
  if run([T(50.0)], sm(), sla=30.0)[0] != 30.0:
    errors.append("P17 raise beat speed limit assist")
  if run([T(25.0), T(28.0)], sm())[0] != 25.0:
    errors.append("P18 higher of two raises won")
  bad = T(25.0, fail=True)
  faults = []
  plugins.record_fault = lambda name, where, exc: faults.append(where)
  targets = [bad, T(None)]
  try:
    for _ in range(2):
      v, _ = run(targets, sm())
      if v != 20.0:
        errors.append(f"P19 failing/None target changed speed to {v}")
  except Exception as e:
    errors.append(f"P19 apply_long_targets raised {e!r}")
  if bad.calls != 1 or not faults:
    errors.append(f"P19 failing target called {bad.calls}x, faults {faults}")

  class Off(Plugin):
    NAME, ENABLE_PARAM, CLAIMS = "off", "OffKey", ("long.target",)

    @classmethod
    def long_target(cls, CP, params):
      return T(1.0)
  plugins.PLUGINS = (Off,)
  if plugins.long_targets(CP, FakeParams()):
    errors.append("P20 disabled plugin contributes a long target")
  return errors


def radar_checks(plugins) -> list[str]:
  errors, faults = [], []
  plugins.record_fault = lambda name, where, exc: faults.append((name, where))

  class Radar:
    def __init__(self, name, fail=False):
      self.name, self.fail, self.calls = name, fail, 0

    def update(self, can_packets):
      self.calls += 1
      if self.fail:
        raise RuntimeError("radar update")
      return self.name

  def make_radar(name, claims=("source:radar",), enable=None, priority=100, fail_init=False, fail_update=False):
    class R(Plugin):
      NAME, ENABLE_PARAM, CLAIMS, PRIORITY = name, enable, claims, priority

      @classmethod
      def radar_interface(cls, CP, CP_SP):
        if fail_init:
          raise RuntimeError("radar init")
        return Radar(name, fail_update)
    return R

  def got(*classes, brand=CP, params=None):
    plugins.PLUGINS = classes
    return plugins.radar_interface(brand, None, params or FakeParams(), Radar("port")).update([])

  if got(make_radar("ext")) != "ext":
    errors.append("R1 active radar plugin not used")
  if got() != "port" or got(make_radar("off", enable="OffKey")) != "port":
    errors.append("R2 no or disabled radar plugin: port radar not used")

  class Other:
    brand = "toyota"
  if got(make_radar("ext"), brand=Other) != "port":
    errors.append("R2 non-Tesla car uses a radar plugin")
  if got(make_radar("noclaim", claims=())) != "port":
    errors.append("R3 radar used without a source:radar claim")
  if got(make_radar("b", priority=50), make_radar("a")) != "b":
    errors.append("R3 source:radar conflict not won by the lower priority")
  faults.clear()
  try:
    if got(make_radar("boom", fail_init=True)) != "port" or ("boom", "card.radar_interface") not in faults:
      errors.append(f"R4 creation fault: port radar not used or not recorded {faults}")
  except Exception as e:
    errors.append(f"R4 host raised {e!r}")
  plugins.PLUGINS = (make_radar("flaky", fail_update=True),)
  ri = plugins.radar_interface(CP, None, FakeParams(), Radar("port"))
  try:
    out = [ri.update([]) for _ in range(3)]
    if out != ["port"] * 3 or ri.plugin.calls != 1 or ("flaky", "card.radar_interface.update") not in faults:
      errors.append(f"R5 update fault: {out}, plugin calls {ri.plugin.calls}, faults {faults}")
  except Exception as e:
    errors.append(f"R5 host raised {e!r}")
  return errors


if __name__ == "__main__":
  sys.exit(main())
