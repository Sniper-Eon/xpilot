"""Home page (native): status block (version, branch, commit, network, car), update banner, and the active offroad alerts
(alertmanager.set_offroad_alert params), most severe first, re-read every 2 s."""
import time

import pyray as rl

from openpilot.common.version import get_build_metadata
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.widgets.list_view import ListItem, TextAction, text_item
from openpilot.tesla.ui.offroad import offroad_alerts
from openpilot.tesla.ui.pages.base import Header, ListPage

MAX_ALERTS = 8
SEVERITY = {0: ("NOTICE", rl.Color(255, 170, 40, 255)), 1: ("ALERT", rl.Color(230, 60, 60, 255))}


def _build() -> tuple[str, str, str]:
  try:
    b = get_build_metadata()
    return b.openpilot.version, b.channel, b.openpilot.git_commit[:8]
  except Exception:
    return "N/A", "N/A", "N/A"


def _network() -> str:
  try:
    return str(ui_state.sm["deviceState"].networkType).replace("NetworkType.", "")
  except Exception:
    return "unknown"


def _car() -> str:
  return ui_state.CP.carFingerprint if ui_state.CP is not None else "not detected yet"


class HomePage(ListPage):
  def __init__(self):
    super().__init__()
    version, branch, commit = _build()
    self.alerts: list[tuple[int, str]] = []
    self.read_t = 0.0
    update = ListItem("Update available: install it from Software", action_item=TextAction("UPDATE", color=rl.Color(54, 140, 255, 255)))
    update.set_visible(lambda: ui_state.params.get_bool("UpdateAvailable"))
    self.add(Header("Status"), text_item("Version", version), text_item("Branch", branch), text_item("Commit", commit),
             text_item("Network", _network), text_item("Car", _car), update, Header("Alerts"))
    none = text_item("No alerts", "")
    none.set_visible(lambda: not self.alerts)
    self.add(none)
    self.rows = []
    for i in range(MAX_ALERTS):
      row = ListItem(lambda i=i: self._alert(i)[1], action_item=TextAction(lambda i=i: SEVERITY[min(1, self._alert(i)[0])][0]))
      row.set_visible(lambda i=i: i < len(self.alerts))
      self.rows.append(row)
      self.add(row)

  def _alert(self, i: int) -> tuple[int, str]:
    return self.alerts[i] if i < len(self.alerts) else (0, "")

  def refresh(self) -> None:
    self.alerts = offroad_alerts(ui_state.params)[:MAX_ALERTS]
    self.read_t = time.monotonic()

  def _update_state(self):
    super()._update_state()
    if time.monotonic() - self.read_t > 2.0:
      self.refresh()
    for i, row in enumerate(self.rows):
      row.action_item.color = SEVERITY[min(1, self._alert(i)[0])][1]

  def show_event(self):
    super().show_event()
