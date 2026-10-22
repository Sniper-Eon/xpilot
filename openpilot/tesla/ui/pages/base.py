"""Base of the native offroad pages (UI v3): a vertical list of tici-style rows (system/ui/widgets/list_view.py) in a
Scroller, drawn by the host in screen pixels inside offroad.content_rect(). Edits are offroad-only, as on the mici pages."""
import pyray as rl

from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import FontWeight, gui_app
from openpilot.system.ui.widgets import DialogResult, Widget
from openpilot.system.ui.widgets.confirm_dialog import ConfirmDialog, alert_dialog
from openpilot.system.ui.widgets.list_view import ListItem, MultipleButtonAction, ButtonAction, toggle_item
from openpilot.system.ui.widgets.scroller_tici import Scroller
from openpilot.tesla.plugins import view
from openpilot.tesla.ui.offroad import next_choice, setting_kind
from openpilot.tesla.ui.settings_meta import setting_choices, setting_label

HEADER_COLOR = rl.Color(140, 144, 156, 255)
HEADER_H = 110


class Header(Widget):
  """Section header: gray caps."""

  def __init__(self, text: str):
    super().__init__()
    self._text = text.upper()
    self._rect = rl.Rectangle(0, 0, 0, HEADER_H)

  def set_parent_rect(self, parent_rect: rl.Rectangle) -> None:
    super().set_parent_rect(parent_rect)
    self._rect.width = parent_rect.width

  def _render(self, rect: rl.Rectangle):
    rl.draw_text_ex(gui_app.font(FontWeight.MEDIUM), self._text, rl.Vector2(rect.x + 20, rect.y + rect.height - 56), 36, 2, HEADER_COLOR)


class ListPage(Widget):
  """Rows in a vertical scroller. refresh() reloads row state from params; called on show_event.
  open(title, page) is set by the host: shows a native sub-page with a breadcrumb and Back."""

  def __init__(self):
    super().__init__()
    self._scroller = Scroller([], spacing=0, line_separator=True)
    self.open = lambda title, page: None

  def add(self, *items: Widget) -> None:
    for item in items:
      self._scroller.add_widget(item)

  def refresh(self) -> None:
    pass

  def show_event(self):
    super().show_event()
    self.refresh()
    self._scroller.show_event()

  def hide_event(self):
    super().hide_event()
    self._scroller.hide_event()

  def _render(self, rect: rl.Rectangle):
    self._scroller.render(rect)


def confirm(text: str, action: str, callback) -> None:
  """tici ConfirmDialog for destructive actions; blocked while engaged, like the mici EngagedConfirmation buttons."""
  if ui_state.engaged:
    gui_app.push_widget(alert_dialog(f"Disengage to {action}"))
    return
  gui_app.push_widget(ConfirmDialog(text, action.capitalize(),
                                    callback=lambda result: result == DialogResult.CONFIRM and not ui_state.engaged and callback()))


def params():
  """ui_state.params with downloaded plugins' keys routed to their store."""
  return view(ui_state.params)


def set_param(key: str, value) -> None:
  if ui_state.is_offroad():
    params().put(key, value, block=True)


class SettingRow:
  """A row for one plugin/vehicle Setting: toggle, ≤5 buttons, or a button stepping to the next value. refresh() reloads it."""

  def __init__(self, setting, title: str | None = None):
    self.setting = setting
    self.kind = setting_kind(setting)
    title = title or setting.label
    if self.kind == "toggle":
      self.item = toggle_item(title, initial_state=bool(self._value()), callback=self._set, enabled=ui_state.is_offroad)
    elif self.kind == "buttons":
      self.choices = setting_choices(setting)
      self.item = ListItem(title=title, action_item=MultipleButtonAction([label for label, _ in self.choices], 250,
                                                                         callback=lambda i: self._set(self.choices[i][1])))
      self.item.action_item.set_enabled(ui_state.is_offroad)
    else:
      self.choices = setting_choices(setting)
      action = ButtonAction(lambda: setting_label(setting, self._value()), enabled=ui_state.is_offroad)
      self.item = ListItem(title=title, action_item=action, callback=lambda: self._set(next_choice(self.choices, self._value())))
    self.refresh()

  def _value(self):
    return params().get(self.setting.key, return_default=True)

  def _set(self, value) -> None:
    set_param(self.setting.key, value)
    self.refresh()

  def refresh(self) -> None:
    value = self._value()
    if self.kind == "toggle":
      self.item.action_item.set_state(bool(value))
    elif self.kind == "buttons":
      values = [v for _, v in self.choices]
      if value in values:
        self.item.action_item.set_selected_button(values.index(value))


class ParamToggle:
  """toggle_item bound to a bool param (like mici BigParamControl); after(value) runs once the param is written."""

  def __init__(self, title: str, key: str, description: str = "", enabled=True, after=None):
    self.key, self.after = key, after
    self.item = toggle_item(title, description, ui_state.params.get_bool(key), self._set, enabled=enabled)

  def _set(self, value: bool) -> None:
    ui_state.params.put_bool(self.key, value, block=True)
    if self.after is not None:
      self.after(value)

  def refresh(self) -> None:
    self.item.action_item.set_state(ui_state.params.get_bool(self.key))
