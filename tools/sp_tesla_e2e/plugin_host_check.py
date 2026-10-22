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

KEYS = dict(re.findall(r'\{"(\w+)", \{[^,]+, (\w+)', (ROOT / "openpilot/common/params_keys.h").read_text()))


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


def make(name, fail_in=None, enable=None):
  class P(Plugin):
    NAME, TITLE, ENABLE_PARAM = name, name, enable

    def __init__(self, CP, params):
      super().__init__(CP, params)
      if fail_in == "__init__":
        raise RuntimeError("init")

    def observe_can(self, can_list, now_ns):
      calls.append((name, "observe_can"))
      if fail_in == "observe_can":
        raise RuntimeError("observe")
      return [f"{name}-now"]

    def control_sends(self, CS, CC, now_ns):
      calls.append((name, "control_sends"))
      if fail_in == "control_sends":
        raise RuntimeError("control")
      return [f"{name}-ctl"]

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
  if "good-now" not in out1 or "good-now" not in out2:
    errors.append("P1 good plugin output lost after a fault")
  if any(c == ("bad_obs", "observe_can") for c in calls[2:]):
    errors.append("P2 faulted plugin still called")
  if "bad_obs-ctl" in host.control_sends(None, None, 0):
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

  print(json.dumps({"plugins": [c.NAME for c in real], "errors": errors}, indent=1))
  return 1 if errors else 0


if __name__ == "__main__":
  sys.exit(main())
