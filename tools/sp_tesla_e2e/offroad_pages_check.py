#!/usr/bin/env python3
"""Offroad pages check (big-screen UI v3): the pyray-free logic behind the native offroad pages (openpilot/tesla/ui/offroad.py)
and the static shape of openpilot/tesla/ui/pages/. Drawing is not checked here (tools/sp_tesla_e2e/big_screen_e2e.py on the device).

Failure cases listed before implementation:
- O1 a nav entry (other than Models, which shows the mici page) or the Store sub-page has no pages/<name>.py with a Widget
     class defining show_event
- O2 a page reads or writes a param key (string literal in get/get_bool/put/put_bool/remove) the compiled Params does not know
- O3 the Plugins rows miss a PLUGINS entry or one of its settings, or a plugin that failed to load is not listed first
- O4 switching a plugin on leaves a plugin with a shared exclusive claim on, switches off one without a shared claim,
     or leaves its fault mark
- O5 a store row shows the wrong action/value for an index entry, a row acts while busy or onroad, or install/remove runs onroad
- O6 offroad the mici texture gets a viewport outside onboarding and mici pages pushed above main (Models, mici dialogs),
     or loses it in those cases
- O7 offroad without a viewport a screen touch maps inside the mici logical screen (a hidden mici widget would react)
- O8 offroad alerts are not most severe first, miss the %1 extra, or show inactive alerts
- O9 the v2 pieces (PAGES factories, _hide_back) remain in screen.py, or the application.py no-viewport hook is missing
- O10 the content rect is wider than MAX_W, not centered right of the nav column, or overlaps the title band
"""
import ast
import json
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "opendbc_repo")]
PKG = ROOT / "openpilot"


class FakeParams:
  def __init__(self, values=None):
    self.values = dict(values or {})

  def get(self, key, block=False, return_default=False):
    return self.values.get(key)

  def get_bool(self, key, block=False):
    return bool(self.values.get(key, False))

  def put(self, key, value, block=False):
    self.values[key] = value

  def put_bool(self, key, value, block=False):
    self.values[key] = bool(value)

  def remove(self, key):
    self.values.pop(key, None)


try:
  import openpilot.common.params  # noqa: F401
except Exception:
  sys.modules["openpilot.common.params"] = types.SimpleNamespace(Params=FakeParams, UnknownKeyName=KeyError)

from openpilot.tesla import manifest as mf, store
from openpilot.tesla.plugins import FAULTS_PARAM, LOAD_ERRORS, PLUGINS
from openpilot.tesla.ui import offroad

PAGE_MODULES = {"Home": "home", "Toggles": "toggles", "Plugins": "plugins", "Tesla": "tesla", "Network": "network",
                "Device": "device", "Software": "software", "Developer": "developer", "Store": "store"}
PARAM_CALLS = {"get", "get_bool", "put", "put_bool", "remove"}


def check_pages(errors: list) -> None:
  known = mf.compiled_param_keys()
  for label in offroad.NAV:
    if label != "Models" and label not in PAGE_MODULES:
      errors.append(f"O1 nav entry {label} has no page module")
  for label, module in PAGE_MODULES.items():
    path = PKG / "tesla/ui/pages" / f"{module}.py"
    if not path.exists():
      errors.append(f"O1 {label}: {path.relative_to(ROOT)} missing")
      continue
    tree = ast.parse(path.read_text())
    if not any(isinstance(n, ast.ClassDef) and any(isinstance(f, ast.FunctionDef) and f.name == "show_event" for f in n.body)
               for n in tree.body):
      errors.append(f"O1 {label}: no class with show_event in {path.name}")
    for node in ast.walk(tree):
      if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in PARAM_CALLS and node.args
          and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
        key = node.args[0].value
        if key[:1].isupper() and key not in known:
          errors.append(f"O2 {path.name}:{node.lineno} param {key} unknown to the compiled Params")


def check_plugins(errors: list) -> None:
  LOAD_ERRORS["broken_check_plugin"] = "SyntaxError"
  try:
    rows = offroad.plugin_rows(FakeParams())
  finally:
    LOAD_ERRORS.pop("broken_check_plugin")
  if not rows or rows[0][:2] != ("failed", "broken_check_plugin"):
    errors.append(f"O3 failed plugins not listed first: {rows[:1]}")
  kinds = [kind for kind, _, _ in rows]
  if "failed" in kinds[kinds.index("plugin") if "plugin" in kinds else 0:]:
    errors.append("O3 a failed plugin row after plugin rows")
  for p in PLUGINS:
    if ("plugin", p.NAME) not in {r[:2] for r in rows}:
      errors.append(f"O3 plugin {p.NAME} has no row")
    for s in p.SETTINGS:
      if ("setting", p.NAME, s.key) not in rows:
        errors.append(f"O3 setting {p.NAME}.{s.key} has no row")
  for p in PLUGINS:
    for s in p.SETTINGS:
      kind = offroad.setting_kind(s)
      if kind not in ("toggle", "buttons", "cycle") or (kind == "toggle") != (s.range is None and s.choices is None):
        errors.append(f"O3 setting {s.key} kind {kind}")
  if offroad.next_choice([("a", 1), ("b", 2)], 2) != 1 or offroad.next_choice([("a", 1), ("b", 2)], 9) != 1:
    errors.append("O3 next_choice does not wrap or recover from an unknown value")

  def fake(name, claims, param):
    return type(name, (), {"NAME": name, "PRIORITY": 0, "CLAIMS": claims, "ENABLE_PARAM": param})
  a, b, c, d = fake("a", ["x.claim"], "ExtAOn"), fake("b", ["x.claim"], "ExtBOn"), fake("c", ["y.claim"], "ExtCOn"), fake("d", ["x.claim"], None)
  saved = offroad.PLUGINS
  offroad.PLUGINS = (a, b, c, d)
  try:
    params = FakeParams({"ExtBOn": True, "ExtCOn": True, FAULTS_PARAM: {"a": "boom", "c": "old"}})
    offroad.switch_plugin(a, True, params)
  finally:
    offroad.PLUGINS = saved
  v = params.values
  if not v.get("ExtAOn") or v.get("ExtBOn") or not v.get("ExtCOn"):
    errors.append(f"O4 switching a on: {v}")
  if "a" in v[FAULTS_PARAM] or "c" not in v[FAULTS_PARAM]:
    errors.append(f"O4 fault marks after switching a on: {v[FAULTS_PARAM]}")


def check_store(errors: list) -> None:
  calls = []
  entry = lambda pid, version="1.0.0", installable=True: store.IndexEntry(pid, pid, version, mf.API_VERSION, "tools", "t", "d", "u",  # noqa: E731
                                                                          "0" * 64, None, installable)
  saved = store.installed_versions, store.install, store.uninstall
  store.installed_versions = lambda: {"same": "1.0.0", "old": "0.9.0", "gone": "1.0.0"}
  store.install = lambda e: calls.append(("install", e.id))
  store.uninstall = lambda pid: calls.append(("uninstall", pid))
  try:
    offroad_now = [True]
    jobs = offroad.StoreJobs(lambda: offroad_now[0])
    jobs.entries = [entry("new"), entry("same"), entry("old"), entry("api", installable=False), entry("gone", installable=False)]
    want = {"new": ("INSTALL", "v1.0.0", True), "same": ("REMOVE", "v1.0.0 installed", True), "old": ("UPDATE", "v0.9.0 -> v1.0.0", True),
            "api": ("N/A", f"needs api {mf.API_VERSION}", False), "gone": ("REMOVE", "v1.0.0 installed", True)}
    for e in jobs.entries:
      got = (jobs.action(e), jobs.row_value(e), jobs.can_act(e.id))
      if got != want[e.id]:
        errors.append(f"O5 store row {e.id}: {got} != {want[e.id]}")
    jobs.busy = True
    if jobs.can_act("new"):
      errors.append("O5 a row can act while a job runs")
    jobs.busy = False
    offroad_now[0] = False
    if jobs.can_act("new"):
      errors.append("O5 a row can act onroad")
    jobs.run(lambda: jobs.act("new"), wait=True)
    if calls:
      errors.append(f"O5 store work onroad: {calls}")
    offroad_now[0] = True
    jobs.run(lambda: jobs.act("new"), wait=True)
    jobs.run(lambda: jobs.act("same"), wait=True)
    jobs.run(lambda: jobs.act("old"), wait=True)
    jobs.run(lambda: jobs.act("api"), wait=True)
    if calls != [("install", "new"), ("uninstall", "same"), ("install", "old")]:
      errors.append(f"O5 store actions: {calls}")
  finally:
    store.installed_versions, store.install, store.uninstall = saved


def check_view(errors: list) -> None:
  for onboarding in (False, True):
    for main in (False, True):
      for modal in (False, True):
        mode, view = offroad.view_mode(onboarding, main, modal)
        drawn = onboarding or not (main or modal)
        if (view is not None) != drawn:
          errors.append(f"O6 view_mode(onboarding={onboarding}, main={main}, modal={modal}) = {mode}, {view}")
  for view in (offroad.ONBOARDING_VIEW, offroad.FALLBACK_VIEW):
    x, y = offroad.to_logical(view, *offroad.to_screen(view, 100, 50))
    if abs(x - 100) > 1e-6 or abs(y - 50) > 1e-6:
      errors.append(f"O6 to_logical/to_screen do not round trip for {view}")
  for sx in (0, 359, 360, 1080, 2159):
    for sy in (0, 149, 150, 540, 1079):
      x, y = offroad.to_logical(None, sx, sy)
      if 0 <= x <= offroad.MICI[0] and 0 <= y <= offroad.MICI[1]:
        errors.append(f"O7 screen ({sx}, {sy}) maps inside mici: ({x:.0f}, {y:.0f})")


def check_alerts(errors: list) -> None:
  keys = offroad.OFFROAD_ALERT_KEYS
  if len(keys) < 2:
    errors.append(f"O8 too few offroad alert keys: {keys}")
    return
  params = FakeParams({keys[0]: {"text": "low %1", "severity": 0, "extra": "X"}, keys[1]: {"text": "bad", "severity": 1}})
  if offroad.offroad_alerts(params) != [(1, "bad"), (0, "low X")]:
    errors.append(f"O8 offroad alerts: {offroad.offroad_alerts(params)}")
  if offroad.offroad_alerts(FakeParams()):
    errors.append("O8 alerts shown with no alert param set")


def check_sources(errors: list) -> None:
  screen = (PKG / "tesla/ui/screen.py").read_text()
  for name in ("PAGES", "_hide_back"):
    if name in screen:
      errors.append(f"O9 screen.py still has {name}")
  if "if texture and dst_rect is not None:" not in (PKG / "system/ui/lib/application.py").read_text():
    errors.append("O9 application.py no-viewport hook missing")
  x, y, w, h = offroad.content_rect()
  cx, cy, cw, ch = offroad.CONTENT
  if w > offroad.MAX_W or abs((x - cx) - (cx + cw - x - w)) > 1e-6 or x < offroad.NAV_W or y < offroad.TITLE_H or y + h > 1080:
    errors.append(f"O10 content rect {(x, y, w, h)}")


def main() -> int:
  errors: list[str] = []
  for check in (check_pages, check_plugins, check_store, check_view, check_alerts, check_sources):
    try:
      check(errors)
    except Exception as e:
      errors.append(f"{check.__name__} raised {e!r}")
  print(json.dumps({"errors": errors}, indent=1))
  return 1 if errors else 0


if __name__ == "__main__":
  sys.exit(main())
