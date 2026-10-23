"""Device page (native): the actions of mici DeviceLayoutMici. Reset calibration, reboot and power off ask in a tici ConfirmDialog
and are blocked while engaged. Training guide, driver camera, terms and regulatory info open native sub-pages (training.py,
driver_camera.py, terms.py, regulatory.py); the training guide and driver camera only offroad."""
from openpilot.common.hardware import HARDWARE
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.widgets.list_view import button_item, text_item
from openpilot.tesla.ui.pages.base import ListPage, back, confirm
from openpilot.tesla.ui.pages.driver_camera import DriverCameraPage
from openpilot.tesla.ui.pages.regulatory import RegulatoryPage
from openpilot.tesla.ui.pages.terms import TermsPage
from openpilot.tesla.ui.pages.training import TrainingGuidePage

CALIB_DESC = "openpilot calibrates continuously; resetting is rarely needed. Mount within 4 degrees left/right and 5 up/9 down."


def _reset_calibration() -> None:
  for key in ("CalibrationParams", "LiveTorqueParameters", "LiveParametersV2", "LiveDelay"):
    ui_state.params.remove(key)
  ui_state.params.put_bool("OnroadCycleRequested", True, block=True)


class DevicePage(ListPage):
  def __init__(self):
    super().__init__()
    self.main = None  # set by the host
    offroad = ui_state.is_offroad
    params = ui_state.params
    guide, camera, terms, regulatory = TrainingGuidePage(on_done=back), DriverCameraPage(), TermsPage(), RegulatoryPage()
    power_off = button_item("Power off", "POWER OFF", callback=lambda: confirm("Are you sure you want to power off?", "power off",
                                                                               lambda: params.put_bool("DoShutdown", True, block=True)))
    power_off.set_visible(lambda: not ui_state.ignition)
    regulatory_row = button_item("Regulatory info", "VIEW", callback=lambda: self.open("regulatory", regulatory))
    regulatory_row.set_visible(HARDWARE.get_device_type() == "mici")  # mici_fcc.html is the comma four label, wrong on C3/C3X/C3XL
    self.add(
      text_item("Dongle ID", lambda: params.get("DongleId") or "N/A"),
      text_item("Serial", lambda: params.get("HardwareSerial") or "N/A"),
      button_item("Review training guide", "REVIEW", callback=lambda: offroad() and self.open("training guide", guide), enabled=offroad),
      button_item("Driver camera preview", "PREVIEW", "Preview the cabin camera to check driver monitoring visibility. The vehicle must be off.",
                  callback=lambda: offroad() and self.open("driver camera", camera), enabled=offroad),
      button_item("Terms & conditions", "VIEW", callback=lambda: self.open("terms", terms)),
      regulatory_row,
      button_item("Reset calibration", "RESET", CALIB_DESC,
                  callback=lambda: confirm("Are you sure you want to reset calibration?", "reset", _reset_calibration)),
      button_item("Reboot", "REBOOT", callback=lambda: confirm("Are you sure you want to reboot?", "reboot",
                                                               lambda: params.put_bool("DoReboot", True, block=True))),
      power_off,
    )

  def show_event(self):
    super().show_event()
