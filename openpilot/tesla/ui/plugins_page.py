"""Plugins page (mici): the one place to switch plugins on/off and open their settings, driven by PLUGINS.
A plugin that faulted this boot (Params XpilotPluginFaults) shows "fault"; long-press a row for its description.
Switching applies on the next drive (card/plannerd build plugins at start); UI slots and overlays follow within 1 s."""
from openpilot.selfdrive.ui.mici.widgets.button import BigButton, BigToggle
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import gui_app
from openpilot.tesla.plugins import FAULTS_PARAM, PLUGINS, is_enabled
from openpilot.tesla.ui.settings_page import SettingsList


class PluginsPage(SettingsList):
  def __init__(self):
    super().__init__()
    self.rows = []
    for plugin in PLUGINS:
      toggle = BigToggle(plugin.TITLE, initial_state=is_enabled(plugin, ui_state.params),
                         toggle_callback=lambda value, p=plugin: self._switch(p, value), description=plugin.DESCRIPTION)
      toggle.set_enabled(lambda p=plugin: ui_state.is_offroad() and p.ENABLE_PARAM is not None)
      self._scroller.add_widget(toggle)
      self.rows.append((plugin, toggle))
      if plugin.SETTINGS:
        page = SettingsList(plugin.SETTINGS)
        button = BigButton(f'{plugin.TITLE} Settings')
        button.set_click_callback(lambda pg=page: (pg.show_event(), gui_app.push_widget(pg)))
        self._scroller.add_widget(button)
    self.show_event()

  def _switch(self, plugin, value) -> None:
    if ui_state.is_offroad() and plugin.ENABLE_PARAM is not None:
      ui_state.params.put_bool(plugin.ENABLE_PARAM, value, block=True)
      faults = ui_state.params.get(FAULTS_PARAM) or {}
      if faults.pop(plugin.NAME, None) is not None:  # switching clears the fault mark
        ui_state.params.put(FAULTS_PARAM, faults, block=True)
    self.show_event()

  def show_event(self):
    super().show_event()
    faults = ui_state.params.get(FAULTS_PARAM) or {}
    for plugin, toggle in getattr(self, 'rows', ()):
      toggle.set_checked(is_enabled(plugin, ui_state.params))
      toggle.set_value('fault' if plugin.NAME in faults else '')
