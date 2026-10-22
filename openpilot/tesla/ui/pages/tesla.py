"""Tesla page (native): driver monitoring and OSM map toggles and the VEHICLE_SETTINGS rows of mici TeslaSettingsMici."""
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.sunnypilot.hardware.driver_monitoring import driver_monitoring_configured
from openpilot.sunnypilot.hardware.profile import has_driver_camera
from openpilot.system.ui.widgets.list_view import toggle_item
from openpilot.tesla.ui.pages.base import Header, ListPage, SettingRow
from openpilot.tesla.ui.settings_meta import VEHICLE_SETTINGS


class TeslaPage(ListPage):
  def __init__(self):
    super().__init__()
    self.dm = toggle_item("Driver Monitoring", "When off, the DM processes do not start. Change only while parked; applies on the next drive.",
                          driver_monitoring_configured(ui_state.params), self._set_dm,
                          enabled=lambda: ui_state.is_offroad() and has_driver_camera())
    self.map = toggle_item("OSM Map Data", initial_state=self._osm(), callback=self._set_map, enabled=ui_state.is_offroad)
    self.rows = [SettingRow(s) for s in VEHICLE_SETTINGS]
    self.add(Header("Device"), self.dm, self.map, Header("Vehicle"), *(r.item for r in self.rows))

  @staticmethod
  def _osm() -> bool:
    return ui_state.params.get("MapProvider", return_default=True) == "osm"

  def _set_dm(self, value: bool) -> None:
    if ui_state.is_offroad() and has_driver_camera():
      ui_state.params.put_bool("DriverMonitoringEnabled", value, block=True)
    self.refresh()

  def _set_map(self, value: bool) -> None:
    if ui_state.is_offroad():
      ui_state.params.put("MapProvider", "osm" if value else "none", block=True)
    self.refresh()

  def refresh(self) -> None:
    self.dm.action_item.set_state(driver_monitoring_configured(ui_state.params))
    self.map.action_item.set_state(self._osm())
    for row in self.rows:
      row.refresh()

  def show_event(self):
    super().show_event()
