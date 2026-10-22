"""Big-screen host (C3/C3X/C3XL, 2160x1080) around the mici UI.
Onroad: the mici view in grid.VIEW, plugin cards in the zones around it (grid.py), then plugin ScreenOverlays.
Alerts are drawn once, by mici inside the view.
Offroad: a nav column (Home and the settings pages), the page title above the mici content at 3x, a status footer.
The nav and the cards sit outside the mici viewport, so their touches map outside every mici widget and are ignored by mici."""
from contextlib import contextmanager
import math
import time

import pyray as rl

from openpilot.cereal import messaging
from openpilot.common.hardware import HARDWARE
from openpilot.common.params import Params
from openpilot.common.swaglog import cloudlog
from openpilot.common.version import get_build_metadata
from openpilot.selfdrive.ui.mici.layouts.settings.developer import DeveloperLayoutMici
from openpilot.selfdrive.ui.mici.layouts.settings.device.device_layout import DeviceLayoutMici
from openpilot.selfdrive.ui.mici.layouts.settings.network.network_layout import NetworkLayoutMici
from openpilot.selfdrive.ui.mici.layouts.settings.software import SoftwareLayoutMici
from openpilot.selfdrive.ui.mici.layouts.settings.toggles import TogglesLayoutMici
from openpilot.selfdrive.ui.mici.widgets.button import BigButton
from openpilot.selfdrive.ui.sunnypilot.mici.layouts.models import ModelsLayoutMici
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.sunnypilot.hardware.profile import HardwareProfile, get_hardware_profile
from openpilot.system.ui.lib.application import gui_app, FontWeight
from openpilot.tesla.ui.grid import SCREEN, VIEW, ZONES, place
from openpilot.tesla.ui.plugin_ui import MAX_FAILURES, EnabledPlugins, ScreenOverlay, load
from openpilot.tesla.ui.plugins_page import PluginsPage
from openpilot.tesla.ui.settings_page import TeslaSettingsMici
from openpilot.tesla.ui.slot import DIM, Slot

MICI = (536, 240)
OFFROAD_VIEW = (456, 180, 1608, 720)  # mici at 3x in the main area right of the nav column
NAV_W, NAV_TOP, ROW_H = 360, 180, 96
# Nav entries: (label, page class); pages are built on first use. Home is the mici main layout.
PAGES = (("Home", None), ("Toggles", TogglesLayoutMici), ("Models", ModelsLayoutMici), ("Plugins", PluginsPage), ("Tesla", TeslaSettingsMici),
         ("Network", NetworkLayoutMici), ("Device", DeviceLayoutMici), ("Software", SoftwareLayoutMici), ("Developer", DeveloperLayoutMici))
NAV_BG = rl.Color(14, 15, 19, 255)
NAV_SEL = rl.Color(34, 38, 48, 255)
NAV_PRESSED = rl.Color(26, 28, 36, 255)
ACCENT = rl.Color(54, 140, 255, 255)


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


def _hide_back(page) -> None:
  """Pages opened from the nav need no Back card: the nav stays visible. The tesla pages (SettingsList) start with one;
  hide it. This is the host's only reach into a page's internals (NavScroller._scroller)."""
  items = page._scroller.items
  if items and isinstance(items[0], BigButton) and items[0].text == "Back":
    items[0].set_visible(False)


class _Tile:
  def __init__(self, plugin: str | None, slot: Slot):
    self.plugin, self.slot, self.rect, self.texture, self.last, self.failures = plugin, slot, None, None, 0.0, 0


class BigScreenHost:
  size = SCREEN

  def __init__(self):
    self._params = Params()
    self._tiles = [_Tile(name, s) for name, s in load(Slot)]  # core slots/ and each plugin's ui.py
    self._overlays = [[name, o, 0] for name, o in load(ScreenOverlay)]
    self._enabled = EnabledPlugins(self._params)
    services = sorted({svc for t in self._tiles for svc in t.slot.SPEC.services})
    self._sm = messaging.SubMaster(services) if services else None
    self._zones = {**{k: rl.Rectangle(*z) for k, z in ZONES.items()}, "view": rl.Rectangle(*VIEW)}
    self._layout_key = None
    self._main = None
    self._pages: dict[int, object] = {}
    self._selected = 0
    self._pressed = None
    try:
      self._status = get_build_metadata().ui_description
    except Exception:
      self._status = ""

  def bind_settings(self, main, _settings) -> None:
    self._main = main

  def open_settings(self) -> None:
    self._select(1)

  def _select(self, index: int) -> None:
    gui_app.pop_widgets_to(self._main, instant=True)  # never grow the nav stack
    self._selected = index
    if index:
      if index not in self._pages:
        self._pages[index] = PAGES[index][1]()
        _hide_back(self._pages[index])
      gui_app.push_widget(self._pages[index])

  def _view(self) -> tuple[float, float, float, float]:
    return VIEW if ui_state.started else OFFROAD_VIEW

  def viewport(self) -> rl.Rectangle:
    return rl.Rectangle(*self._view())

  def to_logical(self, x: float, y: float) -> tuple[float, float]:
    vx, vy, vw, vh = self._view()
    return (x - vx) * MICI[0] / vw, (y - vy) * MICI[1] / vh

  def _to_screen(self, pos) -> rl.Vector2:
    vx, vy, vw, vh = self._view()
    return rl.Vector2(vx + pos.x * vw / MICI[0], vy + pos.y * vh / MICI[1])

  def render(self) -> None:
    if not ui_state.started:
      if not gui_app.widget_in_stack(self._main._onboarding_window):
        self._draw_offroad()
      return
    enabled = self._enabled.get()
    key = frozenset(enabled)
    if key != self._layout_key:
      self._layout_key = key
      rects = place([t.slot.SPEC for t in self._tiles if t.plugin is None or t.plugin in enabled], True)
      for t in self._tiles:
        t.rect = rects.get(t.slot.SPEC.id)
    self._draw_tiles()
    self._draw_overlays()

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

  def _draw_overlays(self) -> None:
    for entry in self._overlays:
      name, overlay, failures = entry
      if failures >= MAX_FAILURES or not self._enabled.shows(name):
        continue
      try:
        overlay.update(ui_state.sm)
        overlay.draw(self._zones)
        entry[2] = 0
      except Exception:
        entry[2] += 1  # same isolation as slots
        cloudlog.exception(f"screen overlay {type(overlay).__name__} failed")

  def _draw_offroad(self) -> None:
    if gui_app.get_active_widget() is self._main:
      self._selected = 0
    rl.draw_rectangle(0, 0, NAV_W, SCREEN[1], NAV_BG)
    rl.draw_text_ex(gui_app.font(FontWeight.BOLD), "xpilot", rl.Vector2(48, 52), 76, 0, rl.WHITE)
    medium = gui_app.font(FontWeight.MEDIUM)
    for index, (label, _) in enumerate(PAGES):
      rect = rl.Rectangle(0, NAV_TOP + index * ROW_H, NAV_W, ROW_H)
      for event in gui_app.mouse_events:
        inside = rl.check_collision_point_rec(self._to_screen(event.pos), rect)
        if event.left_pressed and inside:
          self._pressed = index
        if event.left_released and self._pressed == index:
          self._pressed = None
          if inside:
            self._select(index)
      selected = index == self._selected
      if selected or self._pressed == index:
        rl.draw_rectangle_rec(rect, NAV_SEL if selected else NAV_PRESSED)
      if selected:
        rl.draw_rectangle_rec(rl.Rectangle(0, rect.y, 8, ROW_H), ACCENT)
      rl.draw_text_ex(medium, label, rl.Vector2(48, rect.y + (ROW_H - 44) / 2), 44, 0, rl.WHITE if selected else DIM)
    x = OFFROAD_VIEW[0]
    rl.draw_text_ex(gui_app.font(FontWeight.BOLD), PAGES[self._selected][0], rl.Vector2(x, (OFFROAD_VIEW[1] - 80) / 2), 80, 0, rl.WHITE)
    footer = OFFROAD_VIEW[1] + OFFROAD_VIEW[3]
    rl.draw_text_ex(medium, self._status, rl.Vector2(x, footer + (SCREEN[1] - footer - 30) / 2), 30, 0, DIM)
