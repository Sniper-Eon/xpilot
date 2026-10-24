#!/usr/bin/env python3
"""Plugin manifest, claims and conflict check (runs without a device).

Failure cases listed before implementation:
- M1 an invalid manifest (id != directory, unknown category, wrong api, bad claim, bad JSON) crashes discovery
     or loads anyway, instead of being skipped with an error while the other plugins load
- M2 discovery order is not deterministic (category order, then priority, then id)
- M3 two enabled plugins with the same exclusive claim both become active (two senders on one CAN address)
- M4 a conflict is won by load order instead of priority (then id)
- M5 a plugin uses something it did not claim and keeps running: sends an unclaimed CAN address/bus,
     returns a long target or plan filter without claiming it, or starts an unclaimed process
- M6 shared claims (long.target, plan.filter, msg:<kind>) are treated as exclusive, or msg:<kind> is refused
- M7 switching a plugin on leaves its conflicting plugins switched on
- M8 a built-in plugin's manifest is invalid, or its claims do not cover the hooks it overrides
- M9 an unknown claim kind is accepted
- M10 a disabled plugin still takes an exclusive claim from an enabled one
- M11 a plugin's code is not split by role (XPILOT.md 5.3): a file over MAX_LINES, a fat entry module, or pyray imported
     outside ui.py passes; or a built-in plugin breaks the rules beyond the files listed in LAYOUT_DEBT
"""
import json
from pathlib import Path
import sys
import tempfile
import types

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "opendbc_repo")]
try:
  import openpilot.common.params  # noqa: F401
except Exception:
  sys.modules["openpilot.common.params"] = types.SimpleNamespace(Params=object, UnknownKeyName=KeyError)

from openpilot.tesla import manifest as mf  # noqa: E402
from openpilot.common.swaglog import cloudlog  # noqa: E402
for _level in ("error", "exception", "warning", "info"):  # the check only needs results, not logs (host has no log sink)
  setattr(cloudlog, _level, lambda *a, **k: None)
from openpilot.tesla.plugin import Plugin  # noqa: E402

# ponytail: built-in files over MAX_LINES from before the rule; split them when next changed, never add to this list
LAYOUT_DEBT = {"traffic_light": {"controller.py", "final_plan_arbitrator.py"}}


def write(root: Path, d: str, **over) -> None:
  m = {"id": d, "name": d, "version": "1.0.0", "api": mf.API_VERSION, "category": "body_comfort", "entry": "plugin:X",
       "enable_param": f"{d}On", "claims": [], "priority": 100}
  m.update(over)
  (root / d).mkdir()
  (root / d / "plugin.json").write_text(json.dumps(m))


class FakeParams:
  def __init__(self, values=None):
    self.values = dict(values or {})

  def get_bool(self, key):
    return bool(self.values.get(key, False))


def main() -> int:
  errors = []
  with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    write(root, "good_b", priority=50)
    write(root, "good_a", priority=50)
    write(root, "early", category="engagement", priority=900)
    write(root, "wrong_id", id="other")
    write(root, "bad_cat", category="nope")
    write(root, "bad_api", api=mf.API_VERSION + 1)
    write(root, "bad_claim", claims=["can.tx:hello"])
    write(root, "unknown_kind", claims=["teleport:now"])
    (root / "bad_json").mkdir()
    (root / "bad_json" / "plugin.json").write_text("{nope")
    try:
      found, errs = mf.load_all(root)
    except Exception as e:
      errors.append(f"M1 load_all raised {e!r}")
      found, errs = [], {}
    ids = [m.id for m in found]
    for bad in ("wrong_id", "bad_cat", "bad_api", "bad_claim", "bad_json"):
      if bad in ids or bad not in errs:
        errors.append(f"M1 {bad} not rejected with an error")
    if "unknown_kind" in ids or "unknown_kind" not in errs:
      errors.append("M9 unknown claim kind accepted")
    if ids != ["early", "good_a", "good_b"]:
      errors.append(f"M2 order {ids}")

  X = "can.tx:0x3C2:1"
  items = [("b", 10, (X, "long.target")), ("a", 10, (X,)), ("c", 5, (X,)), ("d", 1, ("long.target", "plan.filter"))]
  active, conflicts = mf.resolve(items, {"a", "b", "c", "d"})
  if active != {"c", "d"}:
    errors.append(f"M3/M4/M6 active {active}")
  if conflicts.get("a") != "c" or conflicts.get("b") != "c":
    errors.append(f"M4 conflicts {conflicts}")
  active, _ = mf.resolve(items, {"a", "b"})
  if active != {"a"}:
    errors.append(f"M4 tie not broken by id: {active}")
  active, _ = mf.resolve(items, {"a", "d"})
  if active != {"a", "d"}:
    errors.append(f"M10 disabled plugin took a claim: {active}")
  if not mf._CLAIM_RE.fullmatch("msg:x.y") or mf.resolve([("e", 1, ("msg:x.y",)), ("f", 2, ("msg:x.y",))], {"e", "f"})[0] != {"e", "f"}:
    errors.append("M6 msg:<kind> refused or exclusive")
  if set(mf.conflicting("c", items)) != {"a", "b"} or mf.conflicting("d", items):
    errors.append(f"M7 conflicting('c') = {mf.conflicting('c', items)}")

  from openpilot.tesla import plugins
  faults = []
  plugins.record_fault = lambda name, where, exc: faults.append((name, where))

  class CP:
    brand = "tesla"

  def make(name, claims, send=None, target=False, proc=None):
    class P(Plugin):
      NAME, CLAIMS, ENABLE_PARAM, PRIORITY = name, tuple(claims), None, 100

      def control_sends(self, CS, CC, now_ns):
        return [send] if send else []

      @classmethod
      def long_target(cls, CP, params):
        return types.SimpleNamespace(update=lambda sm, v, c: 1.0) if target else None

      @classmethod
      def processes(cls):
        return [types.SimpleNamespace(name=proc, should_run=lambda s, p, c: True)] if proc else []
    return P

  plugins.PLUGINS = (make("ok", [X], send=(0x3C2, b"", 1)), make("wrong_bus", ["can.tx:0x3C3:1"], send=(0x3C3, b"", 0)),
                     make("unclaimed", [], send=(0x679, b"", 1)))
  host = plugins.CarPlugins(CP, FakeParams())
  try:
    sent = host.control_sends(None, None, 0)
  except Exception as e:
    errors.append(f"M5 host raised {e!r}")
    sent = []
  if [tuple(s) for s in sent] != [(0x3C2, b"", 1)]:
    errors.append(f"M5 sends {sent}")
  if {p.NAME for p in host.plugins} != {"ok"} or {n for n, _ in faults} != {"wrong_bus", "unclaimed"}:
    errors.append(f"M5 plugins {[p.NAME for p in host.plugins]} faults {faults}")
  plugins.PLUGINS = (make("t_no", [], target=True), make("t_yes", ["long.target"], target=True))
  if [t.plugin_name for t in plugins.long_targets(CP, FakeParams())] != ["t_yes"]:
    errors.append("M5 unclaimed long target used")
  plugins.PLUGINS = (make("p_no", [], proc="rogued"), make("p_yes", ["process:goodd"], proc="goodd"))
  if [p.name for p in plugins.processes()] != ["goodd"]:
    errors.append("M5 unclaimed process started")
  plugins.PLUGINS = (make("x1", [X], send=(0x3C2, b"", 1)), make("x2", [X], send=(0x3C2, b"", 1)))
  if [p.NAME for p in plugins.CarPlugins(CP, FakeParams()).plugins] != ["x1"]:
    errors.append("M3 both claimants built in card")

  import importlib
  plugins = importlib.reload(plugins)
  found, errs = mf.load_all()
  if errs:
    errors.append(f"M8 built-in manifest errors {errs}")
  for cls in plugins.PLUGINS:
    claims = set(cls.CLAIMS)
    if cls.control_sends is not Plugin.control_sends and not any(c.startswith("can.tx:") for c in claims):
      errors.append(f"M8 {cls.NAME} sends CAN without a can.tx claim")
    if cls.long_target.__func__ is not Plugin.long_target.__func__ and "long.target" not in claims:
      errors.append(f"M8 {cls.NAME} long_target unclaimed")
    if cls.plan_filter.__func__ is not Plugin.plan_filter.__func__ and "plan.filter" not in claims:
      errors.append(f"M8 {cls.NAME} plan_filter unclaimed")
    for proc in cls.processes():
      if f"process:{proc.name}" not in claims:
        errors.append(f"M8 {cls.NAME} process {proc.name} unclaimed")
  builtin = [c for c in plugins.PLUGINS if not c.__module__.startswith("xpilot_ext.")]  # store plugins are not in mf.load_all()
  if len(builtin) != len(found):
    errors.append(f"M8 {len(found)} manifests but {len(builtin)} built-in plugin classes")

  for m in found:
    debt = LAYOUT_DEBT.get(m.id, set())
    for problem in mf.layout_problems(mf.PLUGINS_DIR / m.id, m.entry.split(":")[0]):
      if not (problem.split(":")[0] in debt and "lines" in problem):
        errors.append(f"M11 {m.id}/{problem}")
  with tempfile.TemporaryDirectory() as tmp:
    d = Path(tmp)
    (d / "plugin.py").write_text("x = 1\n" * (mf.MAX_ENTRY_LINES + 1))
    (d / "logic.py").write_text("import pyray as rl\n" + "x = 1\n" * mf.MAX_LINES)
    (d / "ui.py").write_text("import pyray as rl\n")
    (d / "tests").mkdir()
    (d / "tests" / "big.py").write_text("x = 1\n" * (mf.MAX_LINES + 1))
    got = sorted(p.split(":")[0] + ":" + p.split(": ")[1].split()[0] for p in mf.layout_problems(d))
    if got != ["logic.py:401", "logic.py:imports", "plugin.py:151"]:
      errors.append(f"M11 layout problems {got}")

  print(json.dumps({"plugins": [c.NAME for c in plugins.PLUGINS], "errors": errors}, indent=1))
  return 1 if errors else 0


if __name__ == "__main__":
  sys.exit(main())
