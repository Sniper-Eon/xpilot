"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import pyray as rl

from openpilot.selfdrive.ui.mici.onroad.hud_renderer import HudRenderer
from openpilot.tesla.ui.plugin_ui import HudOverlay, EnabledPlugins, MAX_FAILURES, load
from openpilot.selfdrive.ui.sunnypilot.onroad.blind_spot_indicators import BlindSpotIndicators
from openpilot.selfdrive.ui.ui_state import ui_state


class HudRendererSP(HudRenderer):
  def __init__(self):
    super().__init__()
    self.plugin_overlays = [[name, w, 0] for name, w in load(HudOverlay)]  # xpilot plugin HUD overlays
    self.enabled_plugins = EnabledPlugins(ui_state.params)
    self.blind_spot_indicators = BlindSpotIndicators()
    self._sp_engaged: bool = False

  def _update_state(self) -> None:
    super()._update_state()
    self.blind_spot_indicators.update()
    self._each_overlay(lambda w: w.update())

    sp_engaged = ui_state.engaged
    if sp_engaged != self._sp_engaged:
      self._chestnut_fade_time = rl.get_time() if sp_engaged else 0
    self._sp_engaged = sp_engaged

  def _render(self, rect: rl.Rectangle) -> None:
    super()._render(rect)
    self.blind_spot_indicators.render(rect)
    self._each_overlay(lambda w: w.render(rect))

  def _each_overlay(self, fn) -> None:
    for entry in self.plugin_overlays:
      name, widget, failures = entry
      if failures >= MAX_FAILURES or not self.enabled_plugins.shows(name):
        continue
      try:
        fn(widget)
        entry[2] = 0
      except Exception:
        entry[2] += 1  # a broken plugin overlay must never take the HUD down

  def _has_blind_spot_detected(self) -> bool:

    return self.blind_spot_indicators.detected
