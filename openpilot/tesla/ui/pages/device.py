"""Device page (native): the actions of mici DeviceLayoutMici. Reset calibration, reboot and power off ask in a tici ConfirmDialog
and are blocked while engaged. Training guide, driver camera, terms and regulatory info open the mici widgets (host draws them
as a mici fallback page)."""
import os

from openpilot.common.basedir import BASEDIR
from openpilot.selfdrive.ui.mici.layouts.settings.device.device_layout import MiciFccModal, ReviewTermsPage, ReviewTrainingGuide
from openpilot.selfdrive.ui.mici.onroad.cabin_camera_dialog import CabinCameraDialog
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.widgets.list_view import button_item, text_item
from openpilot.tesla.ui.pages.base import ListPage, confirm

CALIB_DESC = "openpilot calibrates continuously; resetting is rarely needed. Mount within 4° left/right and 5° up/9° down."


def _reset_calibration() -> None:
  for key in ("CalibrationParams", "LiveTorqueParameters", "LiveParametersV2", "LiveDelay"):
    ui_state.params.remove(key)
  ui_state.params.put_bool("OnroadCycleRequested", True, block=True)


class DevicePage(ListPage):
  def __init__(self):
    super().__init__()
    self.main = None  # set by the host: the training guide returns to it
    offroad = ui_state.is_offroad
    params = ui_state.params
    fcc = os.path.join(BASEDIR, "openpilot/selfdrive/assets/offroad/mici_fcc.html")
    power_off = button_item("Power off", "POWER OFF", callback=lambda: confirm("Are you sure you want to power off?", "power off",
                                                                               lambda: params.put_bool("DoShutdown", True, block=True)))
    power_off.set_visible(lambda: not ui_state.ignition)
    self.add(
      text_item("Dongle ID", lambda: params.get("DongleId") or "N/A"),
      text_item("Serial", lambda: params.get("HardwareSerial") or "N/A"),
      button_item("Review training guide", "REVIEW", callback=lambda: gui_app.push_widget(
        ReviewTrainingGuide(completed_callback=lambda: gui_app.pop_widgets_to(self.main))), enabled=offroad),
      button_item("Driver camera preview", "PREVIEW", "Preview the cabin camera to check driver monitoring visibility. The vehicle must be off.",
                  callback=lambda: gui_app.push_widget(CabinCameraDialog()), enabled=offroad),
      button_item("Terms & conditions", "VIEW", callback=lambda: gui_app.push_widget(ReviewTermsPage())),
      button_item("Regulatory info", "VIEW", callback=lambda: gui_app.push_widget(MiciFccModal(fcc))),
      button_item("Reset calibration", "RESET", CALIB_DESC,
                  callback=lambda: confirm("Are you sure you want to reset calibration?", "reset", _reset_calibration)),
      button_item("Reboot", "REBOOT", callback=lambda: confirm("Are you sure you want to reboot?", "reboot",
                                                               lambda: params.put_bool("DoReboot", True, block=True))),
      power_off,
    )

  def show_event(self):
    super().show_event()
