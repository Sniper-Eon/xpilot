"""Tesla page (native): car model, driver monitoring and OSM map toggles and the VEHICLE_SETTINGS rows of mici TeslaSettingsMici."""
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.sunnypilot.hardware.driver_monitoring import driver_monitoring_configured
from openpilot.sunnypilot.hardware.profile import has_driver_camera
from openpilot.system.ui.widgets.list_view import ButtonAction, ListItem, button_item, toggle_item
from openpilot.tesla.ui.offroad import MODEL_PARAM, tesla_models
from openpilot.tesla.ui.pages.base import Header, ListPage, SettingRow, back
from openpilot.tesla.ui.settings_meta import VEHICLE_SETTINGS


MODEL_DESC = "Auto identifies the car when it starts. Pick a model only if it is not recognized. Applies on the next start."


def _model() -> str:
  return (ui_state.params.get(MODEL_PARAM) or {}).get("name") or "Auto"


class ModelPage(ListPage):
  """Auto, then one row per Tesla in the car list; picking one goes back."""

  def __init__(self):
    super().__init__()
    self.add(button_item("Auto", lambda: "SELECTED" if _model() == "Auto" else "SELECT", MODEL_DESC,
                         callback=lambda: self._pick(None), enabled=ui_state.is_offroad))
    for name, bundle in tesla_models():
      self.add(button_item(name, lambda name=name: "SELECTED" if _model() == name else "SELECT",
                           callback=lambda bundle=bundle: self._pick(bundle), enabled=ui_state.is_offroad))

  def _pick(self, bundle) -> None:
    if ui_state.is_offroad():
      if bundle is None:
        ui_state.params.remove(MODEL_PARAM)
      else:
        ui_state.params.put(MODEL_PARAM, bundle, block=True)
      back()


class TeslaPage(ListPage):
  def __init__(self):
    super().__init__()
    self.models = ModelPage()
    self.model = ListItem("Car model", description=MODEL_DESC, action_item=ButtonAction(_model, width=900, enabled=ui_state.is_offroad),
                          callback=lambda: self.open("car model", self.models))
    self.dm = toggle_item("Driver Monitoring", "When off, the DM processes do not start. Change only while parked; applies on the next drive.",
                          driver_monitoring_configured(ui_state.params), self._set_dm,
                          enabled=lambda: ui_state.is_offroad() and has_driver_camera())
    self.map = toggle_item("OSM Map Data", initial_state=self._osm(), callback=self._set_map, enabled=ui_state.is_offroad)
    self.rows = [SettingRow(s) for s in VEHICLE_SETTINGS]
    self.add(Header("Vehicle"), self.model, *(r.item for r in self.rows), Header("Device"), self.dm, self.map)

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
