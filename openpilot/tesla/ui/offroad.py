"""Pyray-free logic of the offroad pages (UI v3): nav entries, view modes, touch mapping, plugin rows and store jobs.
Kept apart from drawing so tools/sp_tesla_e2e/offroad_pages_check.py can test it on a host without raylib."""
import json
import os
import threading

from openpilot.common.basedir import BASEDIR
from openpilot.tesla import store
from openpilot.tesla.manifest import CATEGORIES, conflicting
from openpilot.tesla.plugins import FAULTS_PARAM, LOAD_ERRORS, PLUGINS, resolve

NAV = ("Home", "Toggles", "Models", "Plugins", "Tesla", "Network", "Device", "Software", "Developer")
MICI = (536, 240)
NAV_W, TITLE_H = 360, 150
CONTENT = (360, 150, 1800, 930)  # x, y, w, h right of the nav column and below the title band
MAX_W = 1500  # content rows are at most this wide, centered in CONTENT
ONBOARDING_VIEW = (456, 180, 1608, 720)  # onboarding: mici at 3x, as in v2
FALLBACK_VIEW = (456, 255, 1608, 720)  # mici pages without a native page (Models, mici dialogs): 3x centered in CONTENT
FAR = 100000.0
NATIVE_VIEW = (FAR, FAR, MICI[0], MICI[1])  # nothing drawn; touches map far outside every mici widget


def view_mode(onboarding: bool, top_is_main: bool, top_is_modal: bool) -> tuple[str, tuple | None]:
  """Offroad (mode, viewport): the mici texture is drawn only for onboarding and for mici pages pushed above main."""
  if onboarding:
    return "onboarding", ONBOARDING_VIEW
  if top_is_main or top_is_modal:
    return ("modal" if top_is_modal else "native"), None
  return "mici", FALLBACK_VIEW


def to_logical(view, x: float, y: float) -> tuple[float, float]:
  vx, vy, vw, vh = view or NATIVE_VIEW
  return (x - vx) * MICI[0] / vw, (y - vy) * MICI[1] / vh


def to_screen(view, x: float, y: float) -> tuple[float, float]:
  vx, vy, vw, vh = view or NATIVE_VIEW
  return vx + x * vw / MICI[0], vy + y * vh / MICI[1]


def content_rect(width: float = CONTENT[2]) -> tuple[float, float, float, float]:
  w = min(MAX_W, width)
  return CONTENT[0] + (CONTENT[2] - w) / 2, CONTENT[1], w, CONTENT[3]


with open(os.path.join(BASEDIR, "openpilot/selfdrive/selfdrived/alerts_offroad.json")) as f:
  OFFROAD_ALERT_KEYS = tuple(json.load(f))


def offroad_alerts(params) -> list[tuple[int, str]]:
  """(severity, text) of the active offroad alerts (alertmanager.set_offroad_alert), most severe first."""
  alerts = []
  for key in OFFROAD_ALERT_KEYS:
    alert = params.get(key)
    if alert:
      alerts.append((alert.get("severity", 0), alert.get("text", key).replace("%1", alert.get("extra", ""))))
  return sorted(alerts, key=lambda a: -a[0])


def plugin_status(plugin, faults, conflicts) -> str:
  """"fault" = dropped this boot (FAULTS_PARAM), "conflict" = switched on but lost an exclusive claim."""
  if plugin.NAME in faults:
    return "fault"
  if plugin.NAME in conflicts:
    return "conflict"
  return ""


def plugin_sections():
  """(category title, plugins) for each manifest category that has plugins, in CATEGORIES order."""
  return [(title, [p for p in PLUGINS if p.CATEGORY == c]) for c, title in CATEGORIES.items() if any(p.CATEGORY == c for p in PLUGINS)]


def plugin_rows(params) -> list[tuple[str, str, str]]:
  """Rows of the Plugins page: ("failed", name, error), ("plugin", name, status), ("setting", plugin, key)."""
  faults = params.get(FAULTS_PARAM) or {}
  _, conflicts = resolve(params)
  rows = [("failed", name, error) for name, error in LOAD_ERRORS.items()]
  for _, plugins in plugin_sections():
    for p in plugins:
      rows.append(("plugin", p.NAME, plugin_status(p, faults, conflicts)))
      rows += [("setting", p.NAME, s.key) for s in p.SETTINGS]
  return rows


def switch_plugin(plugin, value: bool, params) -> None:
  """Switch a plugin; switching on switches off every plugin sharing an exclusive claim. Clears its fault mark.
  params = plugins.view(...); callers check offroad."""
  if plugin.ENABLE_PARAM is None:
    return
  if value:
    by_name = {p.NAME: p for p in PLUGINS}
    for name in conflicting(plugin.NAME, [(p.NAME, p.PRIORITY, p.CLAIMS) for p in PLUGINS]):
      if by_name[name].ENABLE_PARAM is not None:
        params.put_bool(by_name[name].ENABLE_PARAM, False, block=True)
  params.put_bool(plugin.ENABLE_PARAM, value, block=True)
  faults = params.get(FAULTS_PARAM) or {}
  if faults.pop(plugin.NAME, None) is not None:
    params.put(FAULTS_PARAM, faults, block=True)


def setting_kind(setting) -> str:
  """toggle (no range/choices), buttons (≤5 values) or cycle (a button stepping to the next value)."""
  if setting.range is None and setting.choices is None:
    return "toggle"
  from openpilot.tesla.ui.settings_meta import setting_choices
  return "buttons" if len(setting_choices(setting)) <= 5 else "cycle"


def next_choice(choices: list[tuple[str, int]], value) -> int:
  values = [v for _, v in choices]
  return values[(values.index(value) + 1) % len(values)] if value in values else values[0]


class StoreJobs:
  """Plugin store state for the Store page: network and disk work in one background thread at a time.
  offroad: callable; install/remove only while it returns True."""

  def __init__(self, offroad):
    self.offroad = offroad
    self.busy = False
    self.status = "tap Refresh"
    self.entries: list[store.IndexEntry] = []
    self.installed: dict[str, str] = store.installed_versions()
    self.dirty = False  # set after a fetch; the UI thread rebuilds its rows and clears it

  def run(self, job, wait: bool = False) -> None:
    if self.busy:
      return
    self.busy = True
    t = threading.Thread(target=self._job, args=(job,), daemon=True)
    t.start()
    if wait:
      t.join()

  def _job(self, job) -> None:
    try:
      job()
    except Exception as e:
      self.status = f"error: {e}"[:60]
    finally:
      self.installed = store.installed_versions()
      self.busy = False

  def fetch(self) -> None:
    self.status = "loading..."
    entries, error = store.fetch_index()
    self.entries, self.status, self.dirty = entries, error or f"{len(entries)} plugins", True

  def current(self, pid: str) -> store.IndexEntry | None:
    """The entry from the latest fetch (rows outlive refreshes; a dropped entry gives None)."""
    return next((e for e in self.entries if e.id == pid), None)

  def act(self, pid: str) -> None:
    entry = self.current(pid)
    if entry is None:
      return
    if not self.offroad():
      self.status = "park first"
      return
    have = self.installed.get(entry.id)
    if have is not None and (have == entry.version or not entry.installable):
      store.uninstall(entry.id)
      self.status = f"removed {entry.id}: restart to apply"
    elif entry.installable:
      self.status = f"installing {entry.id}..."
      error = store.install(entry)
      self.status = f"{entry.id}: {error}"[:60] if error else f"installed {entry.id}: restart to apply"

  def can_act(self, pid: str) -> bool:
    return not self.busy and self.offroad() and (pid in self.installed or getattr(self.current(pid), "installable", False))

  def action(self, entry: store.IndexEntry) -> str:
    """Button text of an entry row."""
    have = self.installed.get(entry.id)
    if have is not None and (have == entry.version or not entry.installable):
      return "REMOVE"
    if not entry.installable:
      return "N/A"
    return "UPDATE" if have else "INSTALL"

  def row_value(self, entry: store.IndexEntry) -> str:
    have = self.installed.get(entry.id)
    if not entry.installable:
      return f"needs api {entry.api}" if have is None else f"v{have} installed"
    if have == entry.version:
      return f"v{have} installed"
    return f"v{have} -> v{entry.version}" if have else f"v{entry.version}"
