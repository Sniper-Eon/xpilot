"""Tesla settings page (mici). Rows come from settings_meta.py; device toggles (DM, map provider) live here too."""
from openpilot.selfdrive.ui.mici.widgets.button import BigButton, BigToggle
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.widgets.scroller import NavScroller
from openpilot.tesla.ui.settings_meta import BOOL_KEYS, CHOICES, LABELS, setting_label
from openpilot.sunnypilot.hardware.driver_monitoring import driver_monitoring_configured
from openpilot.sunnypilot.hardware.profile import has_driver_camera


def _page() -> NavScroller:
  page = NavScroller()
  back = BigButton('Back')
  back.set_click_callback(gui_app.pop_widget)
  page._scroller.add_widget(back)
  return page


class TeslaSettingsMici(NavScroller):
  def __init__(self):
    super().__init__()
    self.toggles = []
    self.choice_buttons = {}
    back = BigButton('Back')
    back.set_click_callback(gui_app.pop_widget)
    self._scroller.add_widget(back)
    self.dm_toggle = BigToggle('Driver Monitoring', initial_state=driver_monitoring_configured(ui_state.params),
                               toggle_callback=self._set_driver_monitoring,
                               description='When off, the DM processes do not start. Change only while parked; applies on the next drive.')
    self.dm_toggle.set_enabled(lambda: ui_state.is_offroad() and has_driver_camera())
    self._scroller.add_widget(self.dm_toggle)
    self.map_toggle = BigToggle('OSM Map Data', initial_state=ui_state.params.get('MapProvider', return_default=True) == 'osm',
                                toggle_callback=self._set_map_provider)
    self.map_toggle.set_enabled(ui_state.is_offroad)
    self._scroller.add_widget(self.map_toggle)
    for key in BOOL_KEYS:
      toggle = BigToggle(LABELS[key], initial_state=bool(ui_state.params.get(key, return_default=True)),
                         toggle_callback=lambda value, k=key: self._set_param(k, value))
      toggle.set_enabled(ui_state.is_offroad)
      self.toggles.append((key, toggle))
      self._scroller.add_widget(toggle)
    for key, choices in CHOICES.items():
      button = BigButton(LABELS[key])
      button.set_click_callback(lambda k=key, c=choices: self._choose_param(k, c))
      button.set_enabled(ui_state.is_offroad)
      self.choice_buttons[key] = button
      self._scroller.add_widget(button)
    self.show_event()

  def _set_driver_monitoring(self, value):
    if ui_state.is_offroad() and has_driver_camera():
      ui_state.params.put_bool('DriverMonitoringEnabled', value, block=True)
    self.dm_toggle.set_checked(driver_monitoring_configured(ui_state.params))

  def _set_map_provider(self, value):
    if ui_state.is_offroad():
      ui_state.params.put('MapProvider', 'osm' if value else 'none', block=True)
    self.map_toggle.set_checked(ui_state.params.get('MapProvider', return_default=True) == 'osm')

  def _set_param(self, key, value):
    if ui_state.is_offroad():
      ui_state.params.put(key, value, block=True)
    self.show_event()

  def _choose_param(self, key, choices):
    page = _page()
    for label, value in choices:
      button = BigButton(label)
      button.set_enabled(ui_state.is_offroad)
      button.set_click_callback(lambda v=value: (self._set_param(key, v), gui_app.pop_widget()))
      page._scroller.add_widget(button)
    gui_app.push_widget(page)

  def show_event(self):
    super().show_event()
    self.dm_toggle.set_checked(driver_monitoring_configured(ui_state.params))
    self.map_toggle.set_checked(ui_state.params.get('MapProvider', return_default=True) == 'osm')
    for key, toggle in self.toggles:
      toggle.set_checked(bool(ui_state.params.get(key, return_default=True)))
    for key, button in self.choice_buttons.items():
      button.set_value(setting_label(key, ui_state.params.get(key, return_default=True)))
