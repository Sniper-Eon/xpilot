"""Big-screen mici content with direct settings navigation in the side slots."""
from contextlib import contextmanager
import math
import time

import pyray as rl

from openpilot.cereal import messaging
from openpilot.common.hardware import HARDWARE
from openpilot.common.params import Params
from openpilot.common.swaglog import cloudlog
from openpilot.selfdrive.ui.mici.layouts.settings.settings import SettingsBigButton
from openpilot.system.ui.lib.application import gui_app, FontWeight
from openpilot.selfdrive.ui.mici.onroad.alert_renderer import AlertRenderer
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.sunnypilot.hardware.profile import HardwareProfile, get_hardware_profile
from openpilot.tesla.ui.grid import place
from openpilot.tesla.ui.plugin_ui import MAX_FAILURES, EnabledPlugins, load
from openpilot.tesla.ui.slot import Slot

SCREEN = (2160, 1080)
MICI = (536, 240)
BANNER_SCALE = 2  # the mici alert layout at 2x: 1080x160 logical, full width and 320 px tall on screen


def is_big_screen() -> bool:
  return HARDWARE.get_device_type() in ("tici", "tizi") or get_hardware_profile() == HardwareProfile.C3XL


@contextmanager
def scaled(s: float):
  """Draw logical coordinates at s times size. gui_app patched scissor for its own texture scale, so swap it."""
  prev = rl.begin_scissor_mode
  rl.begin_scissor_mode = lambda x, y, w, h: rl._orig_begin_scissor_mode(int(x * s), int(y * s), int(math.ceil(w * s)), int(math.ceil(h * s)))
  rl.rl_push_matrix()
  rl.rl_scalef(s, s, 1.0)
  try:
    yield
  finally:
    rl.rl_pop_matrix()
    rl.begin_scissor_mode = prev


class _Tile:
  def __init__(self, plugin: str | None, slot: Slot):
    self.plugin, self.slot, self.rect, self.texture, self.last, self.failures = plugin, slot, None, None, 0.0, 0


class BigScreenHost:
  size = SCREEN

  def __init__(self):
    self._params = Params()
    self._s = 3.0
    self._x, self._y = (SCREEN[0] - MICI[0] * self._s) / 2, (SCREEN[1] - MICI[1] * self._s) / 2
    self._banner = AlertRenderer()
    self._tiles = [_Tile(name, s) for name, s in load(Slot)]  # core slots/ and each plugin's ui.py
    self._enabled = EnabledPlugins(self._params)
    services = sorted({svc for t in self._tiles for svc in t.slot.SPEC.services})
    self._sm = messaging.SubMaster(services) if services else None
    self._layout_key = None
    self._menu = []
    self._selected = 0
    self._menu_pressed = None

  def bind_settings(self, main, settings) -> None:
    self._main = main
    self._menu = [("Home", None)] + [(button.text, button._click_callback) for button in settings._scroller.items
                                   if isinstance(button, SettingsBigButton)]

  def open_settings(self) -> None:
    self._select_menu(1)

  def _select_menu(self, index: int) -> None:
    gui_app.pop_widgets_to(self._main, instant=True)
    self._selected = index
    if index:
      self._menu[index][1]()

  def viewport(self) -> rl.Rectangle:
    return rl.Rectangle(self._x, self._y, MICI[0] * self._s, MICI[1] * self._s)

  def to_logical(self, x: float, y: float) -> tuple[float, float]:
    return (x - self._x) / self._s, (y - self._y) / self._s

  def render(self) -> None:
    if not ui_state.started:
      if not gui_app.widget_in_stack(self._main._onboarding_window):
        self._draw_menu()
      return
    enabled = self._enabled.get()
    key = (self._x, self._y, self._s, ui_state.started, frozenset(enabled))
    if key != self._layout_key:
      self._layout_key = key
      shown = [t.slot.SPEC for t in self._tiles if t.plugin is None or t.plugin in enabled]
      rects = place((self._x, self._y, MICI[0] * self._s, MICI[1] * self._s), shown, ui_state.started)
      for t in self._tiles:
        t.rect = rects.get(t.slot.SPEC.id)
    self._draw_tiles()
    # Alerts never shrink with the window: same renderer and timeout logic as mici, drawn across the top.
    with scaled(BANNER_SCALE):
      self._banner.render(rl.Rectangle(0, 0, SCREEN[0] / BANNER_SCALE, 160))

  def _draw_tiles(self) -> None:
    if self._sm is not None:
      self._sm.update(0)
    now = time.monotonic()
    for t in self._tiles:
      if t.rect is None or t.failures >= MAX_FAILURES:
        continue
      x, y, w, h = t.rect
      if t.texture is None or t.texture.texture.width != w or t.texture.texture.height != h:
        t.texture, t.last = rl.load_render_texture(w, h), 0.0
      if now - t.last >= 1.0 / t.slot.SPEC.hz:
        t.last = now
        rl.begin_texture_mode(t.texture)
        rl.clear_background(rl.BLANK)
        try:
          t.slot.update(self._sm if self._sm is not None and t.slot.SPEC.services else ui_state.sm)
          rect = rl.Rectangle(0, 0, w, h)
          t.slot.set_rect(rect)
          with scaled(1):
            t.slot._update_state()
            t.slot._render(rect)
          t.failures = 0
        except Exception:
          t.failures += 1  # a broken slot must never take the UI (and engagement) down
          cloudlog.exception(f"slot {t.slot.SPEC.id} failed")
        rl.end_texture_mode()
      rl.draw_texture_pro(t.texture.texture, rl.Rectangle(0, 0, w, -h), rl.Rectangle(x, y, w, h), rl.Vector2(0, 0), 0.0, rl.WHITE)

  def _draw_menu(self) -> None:
    if gui_app.get_active_widget() is self._main:
      self._selected = 0
    for index, (label, _) in enumerate(self._menu):
      rect = rl.Rectangle(18 if index < 5 else SCREEN[0] - 258, 90 + (index % 5) * 180, 240, 144)
      for event in gui_app.mouse_events:
        pos = rl.Vector2(event.pos.x * self._s + self._x, event.pos.y * self._s + self._y)
        inside = rl.check_collision_point_rec(pos, rect)
        if event.left_pressed and inside:
          self._menu_pressed = index
        if event.left_released and self._menu_pressed == index:
          self._menu_pressed = None
          if inside:
            self._select_menu(index)
      rl.draw_rectangle_rounded(rect, 0.15, 8, rl.Color(36, 100, 180, 255) if index == self._selected else rl.Color(24, 24, 28, 255))
      font = gui_app.font(FontWeight.BOLD)
      width = rl.measure_text_ex(font, label, 36, 0).x
      rl.draw_text_ex(font, label, rl.Vector2(rect.x + (rect.width - width) / 2, rect.y + 48), 36, 0, rl.WHITE)
