"""Plugins page (native): plugins that failed to load, then one section per manifest category with a switch per plugin
(value "fault"/"conflict") and a row per Setting. Switching a plugin on switches off its conflicts (offroad.switch_plugin).
"Plugin Store ›" opens the Store sub-page."""
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.widgets.list_view import ListItem, TextAction, button_item, toggle_item
from openpilot.tesla.plugins import FAULTS_PARAM, LOAD_ERRORS, is_enabled, resolve
from openpilot.tesla.ui.offroad import plugin_sections, plugin_status, switch_plugin
from openpilot.tesla.ui.pages.base import Header, ListPage, SettingRow, params
from openpilot.tesla.ui.pages.store import StorePage


def _details(plugin) -> str:
  m = plugin.MANIFEST
  return (f"{plugin.DESCRIPTION} — {m.author or 'unknown'}, v{m.version}, priority {plugin.PRIORITY}, claims: {', '.join(plugin.CLAIMS) or 'none'}")


class PluginsPage(ListPage):
  def __init__(self):
    super().__init__()
    self.store = None
    self.add(button_item("Plugin Store ›", "OPEN", "Install third-party plugins (reviewed, not signed). Restart to apply.",
                         callback=self._open_store))
    if LOAD_ERRORS:
      self.add(Header("Failed to load"))
      for name, error in LOAD_ERRORS.items():
        self.add(ListItem(name, description=error, action_item=TextAction("failed")))
    self.switches = []
    self.rows = []
    for title, plugins in plugin_sections():
      self.add(Header(title))
      for p in plugins:
        status = {"": ""}
        switch = toggle_item(lambda p=p, s=status: f"{p.TITLE}  [{s['']}]" if s[''] else p.TITLE, _details(p), is_enabled(p, ui_state.params),
                             lambda value, p=p: self._switch(p, value), enabled=lambda p=p: ui_state.is_offroad() and p.ENABLE_PARAM is not None)
        self.switches.append((p, switch, status))
        self.add(switch)
        for s in p.SETTINGS:
          row = SettingRow(s, f"{p.TITLE}: {s.label}")
          self.rows.append(row)
          self.add(row.item)

  def _open_store(self) -> None:
    if self.store is None:
      self.store = StorePage()
    self.open("Store", self.store)

  def _switch(self, plugin, value: bool) -> None:
    if ui_state.is_offroad():
      switch_plugin(plugin, value, params())
    self.refresh()

  def refresh(self) -> None:
    faults = ui_state.params.get(FAULTS_PARAM) or {}
    _, conflicts = resolve(ui_state.params)
    for p, switch, status in self.switches:
      switch.action_item.set_state(is_enabled(p, ui_state.params))
      status[""] = plugin_status(p, faults, conflicts)
    for row in self.rows:
      row.refresh()

  def show_event(self):
    super().show_event()
