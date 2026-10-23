"""Toggles page (native): the params of mici TogglesLayoutMici with the same enable/visibility conditions."""
from openpilot.selfdrive.ui.mici.layouts.settings.common import restart_needed_callback
from openpilot.selfdrive.ui.mici.layouts.settings.initial_cruise_speed import get_speed_options, set_initial_cruise_speed
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.widgets.list_view import ButtonAction, ListItem, multiple_button_item
from openpilot.tesla.plugin_params import ParamsView
from openpilot.tesla.ui.pages.base import ListPage, ParamToggle
from openpilot.tesla.ui.tiles import LAYOUT_SPEC, THEME_PARAM, THEMES

PERSONALITY_DESC = "Standard is recommended. Aggressive follows closer with firmer gas and braking; relaxed leaves more space."

PERSONALITIES = ["aggressive", "standard", "relaxed"]


class TogglesPage(ListPage):
  def __init__(self):
    super().__init__()
    self.personality = multiple_button_item("Following distance", PERSONALITY_DESC,
                                            [p.capitalize() for p in PERSONALITIES], 0, button_width=250, callback=self._set_personality)
    self.personality.set_visible(lambda: ui_state.CP is not None and ui_state.has_longitudinal_control)
    self.cruise = ListItem("Initial cruise speed", description="Cruise speed set when cruise is engaged.",
                           action_item=ButtonAction(self._cruise_text), callback=self._next_cruise_speed)
    self.cruise.set_visible(lambda: ui_state.CP is not None and ui_state.has_longitudinal_control and not ui_state.CP.pcmCruise)
    not_engaged = lambda: not ui_state.engaged  # noqa: E731
    self.toggles = [
      ParamToggle("Use metric units", "IsMetric", after=lambda _: self.refresh()),
      ParamToggle("Lane departure warnings", "IsLdwEnabled",
                  "Warn when you drift across a detected lane line. Only above 31 mph (50 km/h), with no turn signal."),
      ParamToggle("Always-on driver monitor", "AlwaysOnDM", "Monitor the driver even when sunnypilot is not engaged."),
      ParamToggle("Record & upload cabin camera", "RecordFront", "Upload cabin camera data to help improve driver monitoring.",
                  enabled=False if ui_state.params.get_bool("RecordFrontLock") else not_engaged, after=restart_needed_callback),
      ParamToggle("Record & upload mic audio", "RecordAudio", "Record microphone audio while driving. Audio is included in dashcam videos.",
                  enabled=not_engaged, after=restart_needed_callback),
      ParamToggle("Enable sunnypilot", "OpenpilotEnabledToggle",
                  "Enable to use sunnypilot driver assistance. Disable to use your car's stock driver assistance.",
                  enabled=not_engaged, after=restart_needed_callback),
    ]
    self.theme_params = ParamsView(ui_state.params, LAYOUT_SPEC)
    self.theme = multiple_button_item("Tile color", "Color of every tile on the home screen.", list(THEMES), 0, button_width=200,
                                      callback=lambda i: self.theme_params.put(THEME_PARAM, list(THEMES)[i]))
    self.add(self.personality, self.cruise, *(t.item for t in self.toggles), self.theme)

  def _set_personality(self, index: int) -> None:
    ui_state.params.put("LongitudinalPersonality", index, block=True)

  def _cruise_text(self) -> str:
    options, idx = get_speed_options()
    return f"{options[idx]} {'km/h' if ui_state.is_metric else 'mph'}"

  def _next_cruise_speed(self) -> None:
    options, idx = get_speed_options()
    set_initial_cruise_speed(options[(idx + 1) % len(options)])
    ui_state.update_params()

  def refresh(self) -> None:
    ui_state.update_params()
    self.personality.action_item.set_selected_button(min(2, max(0, int(ui_state.params.get("LongitudinalPersonality", return_default=True) or 0))))
    for toggle in self.toggles:
      toggle.refresh()
    theme = self.theme_params.get(THEME_PARAM)
    self.theme.action_item.set_selected_button(list(THEMES).index(theme) if theme in THEMES else 0)

  def show_event(self):
    super().show_event()
