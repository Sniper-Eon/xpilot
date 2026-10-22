"""Plugin manifests (plugin.json), categories, claims and conflict resolution. Stdlib only: the UI, gen_params.py and
the checks read manifests without importing plugin code. Format and rules: XPILOT.md "插件清单".

plugin.json:
  id           directory name                     name, description, author, version   shown on the Plugins page
  api          API_VERSION this plugin targets    category  one of CATEGORIES
  entry        "module:Class" inside the plugin package (e.g. "plugin:AutoSpeed")
  priority     lower wins an exclusive claim (then id); also orders plugins in a category. Default 100
  enable_param BOOL param that switches the plugin; null = always on
  claims       resources the plugin uses (see CLAIM_PATTERNS); the host refuses anything unclaimed
  settings     [{"key", "label", "range": [min, max, step, unit, divisor]} | {"key", "label", "choices": [[label, value]]}
                | {"key", "label"} (toggle)]
  params       {"Key": {"type", "default", "flags", "note"}} rendered into common/plugin_params.inc by gen_params.py
"""
from dataclasses import dataclass, field
import json
from pathlib import Path
import re

API_VERSION = 1
PLUGINS_DIR = Path(__file__).resolve().parent / "plugins"

# id -> title, in pipeline order. The first 12 sit on the control path.
CATEGORIES = {
  "perception_model": "Perception Models",
  "object_fusion": "Lead & Object Fusion",
  "vehicle_params": "Calibration & Vehicle Params",
  "engagement": "Engagement",
  "driver_monitoring": "Driver Monitoring",
  "lateral_planning": "Lateral Planning",
  "longitudinal_planning": "Longitudinal Planning",
  "lane_change": "Lane Change",
  "navigation": "Navigate on xpilot",
  "controller": "Controllers",
  "actuation": "Actuation & Car Messages",
  "safety_fallback": "Safety Fallback & Autopilot Handoff",
  "data_source": "Data Sources & External Compute",
  "alerts": "Alerts",
  "body_comfort": "Body & Comfort",
  "ui": "UI",
  "tools": "Tools & Diagnostics",
}

# Exclusive unless listed in SHARED_CLAIMS: only one active plugin may hold it.
CLAIM_PATTERNS = (
  r"can\.tx:0x[0-9A-Fa-f]{1,8}:[0-7]",  # send this CAN address on this bus (needs a panda safety plugin)
  r"process:[a-z][a-z0-9_]*",           # run this manager process
  r"source:[a-z][a-z0-9_.]*",           # be the provider of this data, e.g. source:radar, source:lanes
  r"role:[a-z][a-z0-9_.]*",             # own a replaceable stage, e.g. role:lateral.controller
  r"long\.target",                      # long_target hook (shared, merged by the host)
  r"plan\.filter",                      # plan_filter hook (shared, chained in priority order)
)
SHARED_CLAIMS = {"long.target", "plan.filter"}
_CLAIM_RE = re.compile("|".join(f"(?:{p})" for p in CLAIM_PATTERNS))


@dataclass(frozen=True)
class Setting:
  """One row on a plugin's settings page. No range/choices: toggle. range=(min, max, step, unit, divisor)."""
  key: str
  label: str
  range: tuple[int, int, int, str, int] | None = None
  choices: tuple[tuple[str, int], ...] | None = None


@dataclass(frozen=True)
class Manifest:
  id: str
  name: str
  version: str
  api: int
  category: str
  entry: str
  description: str = ""
  author: str = ""
  priority: int = 100
  enable_param: str | None = None
  claims: tuple[str, ...] = ()
  settings: tuple[Setting, ...] = ()
  params: dict = field(default_factory=dict)


def _setting(d: dict) -> Setting:
  rng = d.get("range")
  return Setting(d["key"], d["label"], tuple(rng) if rng else None,
                 tuple((str(label), int(v)) for label, v in d["choices"]) if d.get("choices") else None)


def parse(path: Path) -> Manifest:
  """Read and validate one plugin.json; raises ValueError with the reason."""
  try:
    d = json.loads(path.read_text())
  except (OSError, ValueError) as e:
    raise ValueError(f"unreadable: {e}") from None
  if not isinstance(d, dict):
    raise ValueError("not an object")
  if d.get("id") != path.parent.name:
    raise ValueError(f"id {d.get('id')!r} != directory {path.parent.name!r}")
  if d.get("api") != API_VERSION:
    raise ValueError(f"api {d.get('api')!r}, host supports {API_VERSION}")
  if d.get("category") not in CATEGORIES:
    raise ValueError(f"unknown category {d.get('category')!r}")
  if not isinstance(d.get("entry"), str) or not re.fullmatch(r"[a-z_][a-z0-9_]*:[A-Za-z_]\w*", d["entry"]):
    raise ValueError(f"bad entry {d.get('entry')!r}")
  claims = d.get("claims", [])
  if not isinstance(claims, list) or not all(isinstance(c, str) and _CLAIM_RE.fullmatch(c) for c in claims):
    raise ValueError(f"bad claims {claims!r}")
  try:
    return Manifest(id=d["id"], name=str(d.get("name") or d["id"]), version=str(d.get("version", "0")), api=d["api"],
                    category=d["category"], entry=d["entry"], description=str(d.get("description", "")),
                    author=str(d.get("author", "")), priority=int(d.get("priority", 100)), enable_param=d.get("enable_param"),
                    claims=tuple(claims), settings=tuple(_setting(s) for s in d.get("settings", [])), params=dict(d.get("params", {})))
  except (KeyError, TypeError, ValueError) as e:
    raise ValueError(f"bad field: {e!r}") from None


def load_all(root: Path = PLUGINS_DIR) -> tuple[list[Manifest], dict[str, str]]:
  """Valid manifests in (category, priority, id) order, and {directory: error} for the rejected ones."""
  found, errors = [], {}
  for path in sorted(root.glob("*/plugin.json")):
    try:
      found.append(parse(path))
    except ValueError as e:
      errors[path.parent.name] = str(e)
  order = list(CATEGORIES)
  found.sort(key=lambda m: (order.index(m.category), m.priority, m.id))
  return found, errors


def resolve(items, enabled: set[str]) -> tuple[set[str], dict[str, str]]:
  """items: (id, priority, claims). Returns (active ids, {losing id: winning id}) among the enabled ones.
  Each exclusive claim goes to the lowest (priority, id); a plugin that loses any claim is not active."""
  active, conflicts, owner = set(), {}, {}
  for name, _, claims in sorted((i for i in items if i[0] in enabled), key=lambda i: (i[1], i[0])):
    taken = [owner[c] for c in claims if c not in SHARED_CLAIMS and c in owner]
    if taken:
      conflicts[name] = taken[0]
      continue
    active.add(name)
    owner.update({c: name for c in claims if c not in SHARED_CLAIMS})
  return active, conflicts


def conflicting(name: str, items) -> list[str]:
  """Ids sharing an exclusive claim with name: switch these off when name is switched on."""
  mine = {c for i, _, claims in items if i == name for c in claims if c not in SHARED_CLAIMS}
  return [i for i, _, claims in items if i != name and mine & set(claims)]


def can_tx(claims) -> set[tuple[int, int]]:
  """(address, bus) pairs from can.tx claims."""
  return {(int(a, 16), int(b)) for c in claims if c.startswith("can.tx:") for a, b in [c[7:].split(":")]}
