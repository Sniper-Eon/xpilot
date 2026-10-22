"""Network page (native): the tici NetworkUI (Wi-Fi list, advanced settings) with its own WifiManager, built on first show.
mici NetworkLayoutMici (built by the mici settings layout) keeps a second WifiManager; sharing one would also trigger mici's
password dialogs, so they stay apart (XPILOT.md §9)."""
import pyray as rl

from openpilot.system.ui.lib.wifi_manager import WifiManager
from openpilot.system.ui.widgets import Widget
from openpilot.system.ui.widgets.network import NetworkUI


class NetworkPage(Widget):
  def __init__(self):
    super().__init__()
    self.ui = None

  def show_event(self):
    super().show_event()
    if self.ui is None:
      self.ui = NetworkUI(WifiManager())
    self.ui.show_event()

  def hide_event(self):
    super().hide_event()
    if self.ui is not None:
      self.ui.hide_event()

  def _render(self, rect: rl.Rectangle):
    if self.ui is not None:
      self.ui.render(rect)
