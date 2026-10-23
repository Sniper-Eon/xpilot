"""Driver camera page (native): the cabin camera preview of mici CabinCameraDialog (BaseCabinCameraDialog: camera view, face box,
awareness) in the content rect. Opened from Device offroad only; closes itself when the device sleeps, like mici. While it is open
IsDriverViewEnabled is set, which also keeps hardwared from going onroad."""
from __future__ import annotations

import pyray as rl

from openpilot.selfdrive.ui.mici.onroad.cabin_camera_dialog import BaseCabinCameraDialog
from openpilot.selfdrive.ui.ui_state import device, ui_state
from openpilot.system.ui.widgets import Widget
from openpilot.tesla.ui.pages.base import back


class DriverCameraPage(Widget):
  def __init__(self):
    super().__init__()
    self._dialog = BaseCabinCameraDialog()
    self._active = False

    def on_timeout():
      if self._active:
        self.hide_event()  # rendering stops while asleep, so stop driver view now
        back()

    device.add_interactive_timeout_callback(on_timeout)

  def show_event(self):
    super().show_event()
    if ui_state.is_offroad():
      self._active = True
      self._dialog.show_event()

  def hide_event(self):
    super().hide_event()
    if self._active:
      self._active = False
      self._dialog.hide_event()

  def _render(self, rect: rl.Rectangle):
    if not self._active:
      back()
      return
    self._dialog.render(rect)
