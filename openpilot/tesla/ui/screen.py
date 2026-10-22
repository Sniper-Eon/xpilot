"""Big-screen host (C3/C3X/C3XL, 2160x1080) around the mici UI.
Onroad: the mici view in grid.VIEW, plugin cards in the zones around it (grid.py), then plugin ScreenOverlays.
Alerts are drawn once, by mici inside the view.
Offroad (UI v3): a nav column, a title band and native list pages (tesla/ui/pages/) drawn here in screen pixels. The mici
texture is not drawn (viewport() -> None) except during onboarding and for mici pages pushed above main (Models, training
guide, terms, regulatory, cabin camera), which show at 3x in the content area. Without a viewport every touch maps far
outside the mici screen, so the mici widgets running underneath never react. tici dialogs (ConfirmDialog, Keyboard) the
native pages push onto the nav stack are hidden in the mici pass and drawn full-screen here."""
from contextlib import contextmanager
import math
import time

import pyray as rl

from openpilot.cereal import messaging
from openpilot.common.hardware import HARDWARE
from openpilot.common.params import Params
from openpilot.common.swaglog import cloudlog
from openpilot.selfdrive.ui.sunnypilot.mici.layouts.models import ModelsLayoutMici
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.sunnypilot.hardware.profile import HardwareProfile, get_hardware_profile
from openpilot.system.ui.lib.application import MousePos, gui_app, FontWeight
from openpilot.tesla.ui import offroad
from openpilot.tesla.ui.grid import SCREEN, VIEW, ZONES, place
from openpilot.tesla.ui.offroad import NAV, NAV_W, TITLE_H
from openpilot.tesla.ui.pages.developer import DeveloperPage
from openpilot.tesla.ui.pages.device import DevicePage
from openpilot.tesla.ui.pages.home import HomePage
from openpilot.tesla.ui.pages.network import NetworkPage
from openpilot.tesla.ui.pages.plugins import PluginsPage
from openpilot.tesla.ui.pages.software import SoftwarePage
from openpilot.tesla.ui.pages.tesla import TeslaPage
from openpilot.tesla.ui.pages.toggles import TogglesPage
from openpilot.tesla.ui.plugin_ui import MAX_FAILURES, EnabledPlugins, ScreenOverlay, load
from openpilot.tesla.ui.slot import DIM, Slot

NAV_TOP, ROW_H = 180, 96
# Native page per nav label, built on first use. Models has none: it shows the mici page (FALLBACK_VIEW).
NATIVE = {"Home": HomePage, "Toggles": TogglesPage, "Plugins": PluginsPage, "Tesla": TeslaPage, "Network": NetworkPage,
          "Device": DevicePage, "Software": SoftwarePage, "Developer": DeveloperPage}
FALLBACK_TITLES = {"ReviewTrainingGuide": "Training guide", "CabinCameraDialog": "Cabin camera", "ReviewTermsPage": "Terms",
                   "MiciFccModal": "Regulatory"}
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
    self._pages: dict[str, object] = {}
    self._models = None
    self._selected = 0
    self._sub: tuple[str, object] | None = None  # (title, page) opened by the selected page
    self._shown = None  # the native page that last got show_event
    self._pressed = None
    self._view: tuple | None = None  # set each frame by viewport(); to_logical runs on the touch thread
    self._mode = "native"
    self._host_pass = False

  def bind_settings(self, main, _settings) -> None:
    self._main = main

  def open_settings(self) -> None:
    self._select(1)

  def _select(self, index: int) -> None:
    gui_app.pop_widgets_to(self._main, instant=True)  # never grow the nav stack
    self._selected, self._sub = index, None
    if NAV[index] not in NATIVE:
      self._models = self._models or ModelsLayoutMici()
      gui_app.push_widget(self._models)

  def _page(self):
    """The native page in the content area: the open sub-page, else the selected nav page (None for Models)."""
    if self._sub is not None:
      return self._sub[1]
    label = NAV[self._selected]
    if label not in NATIVE:
      return None
    if label not in self._pages:
      page = self._pages[label] = NATIVE[label]()
      page.open = lambda title, sub: self._open(title, sub)
      if isinstance(page, DevicePage):
        page.main = self._main
    return self._pages[label]

  def _open(self, title, page) -> None:
    self._sub = None if page is None else (title, page)

  @staticmethod
  def _is_modal(widget) -> bool:
    """tici dialogs (system/ui/widgets: ConfirmDialog, alert_dialog, Keyboard) pushed by the native pages."""
    return type(widget).__module__.startswith("openpilot.system.ui.widgets")

  def _hook_modal(self) -> None:
    top = gui_app.get_active_widget()
    if top is not self._main and self._is_modal(top):
      top.set_visible(lambda: self._host_pass)  # hidden in the mici texture pass, drawn by _draw_offroad

  def viewport(self) -> rl.Rectangle | None:
    if ui_state.started:
      self._mode, self._view = "onroad", VIEW
    else:
      onboarding = self._main is None or gui_app.widget_in_stack(self._main._onboarding_window)
      top = gui_app.get_active_widget()
      self._mode, self._view = offroad.view_mode(onboarding, top is self._main, self._is_modal(top))
    return rl.Rectangle(*self._view) if self._view is not None else None

  def to_logical(self, x: float, y: float) -> tuple[float, float]:
    return offroad.to_logical(self._view, x, y)

  def render(self) -> None:
    if self._mode != "onroad":
      if self._mode != "onboarding":
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

  @contextmanager
  def _native(self, events):
    """Run tici widgets in screen pixels: screen-space touches, full-screen gui_app size, unscaled scissor."""
    saved = gui_app._mouse_events, gui_app._width, gui_app._height
    gui_app._mouse_events, (gui_app._width, gui_app._height) = events, SCREEN
    self._host_pass = True
    try:
      with scaled(1):
        yield
    finally:
      self._host_pass = False
      gui_app._mouse_events, gui_app._width, gui_app._height = saved

  def _tapped(self, key, rect: rl.Rectangle, events) -> bool:
    tapped = False
    for event in events:
      inside = rl.check_collision_point_rec(event.pos, rect)
      if event.left_pressed and inside:
        self._pressed = key
      if event.left_released and self._pressed == key:
        self._pressed = None
        tapped = inside
    return tapped

  def _draw_offroad(self) -> None:
    events = [e._replace(pos=MousePos(*offroad.to_screen(self._view, e.pos.x, e.pos.y))) for e in gui_app.mouse_events]
    top = gui_app.get_active_widget()
    if top is self._main and NAV[self._selected] not in NATIVE:
      self._selected = 0  # left the Models page with the mici back gesture
    modal = self._mode == "modal"
    page_events = [] if modal else events

    rl.draw_rectangle(0, 0, NAV_W, SCREEN[1], NAV_BG)
    rl.draw_text_ex(gui_app.font(FontWeight.BOLD), "xpilot", rl.Vector2(48, 52), 76, 0, rl.WHITE)
    medium = gui_app.font(FontWeight.MEDIUM)
    for index, label in enumerate(NAV):
      rect = rl.Rectangle(0, NAV_TOP + index * ROW_H, NAV_W, ROW_H)
      if self._tapped(index, rect, page_events):
        self._select(index)
      selected = index == self._selected
      if selected or self._pressed == index:
        rl.draw_rectangle_rec(rect, NAV_SEL if selected else NAV_PRESSED)
      if selected:
        rl.draw_rectangle_rec(rl.Rectangle(0, rect.y, 8, ROW_H), ACCENT)
      rl.draw_text_ex(medium, label, rl.Vector2(48, rect.y + (ROW_H - 44) / 2), 44, 0, rl.WHITE if selected else DIM)

    # title band: the page title, or a breadcrumb and Back for a sub-page / a mici page pushed above main
    x, y, w, h = offroad.content_rect()
    label = NAV[self._selected]
    sub = self._sub[0] if self._sub is not None else None
    if self._mode == "mici" and label in NATIVE:
      sub = FALLBACK_TITLES.get(type(top).__name__, "")
    bold = gui_app.font(FontWeight.BOLD)
    if sub is None:
      rl.draw_text_ex(bold, label, rl.Vector2(x, (TITLE_H - 72) / 2), 72, 0, rl.WHITE)
    else:
      back = rl.Rectangle(x - 24, 0, 260, 76)
      if self._tapped("back", back, page_events):
        if self._mode == "mici":
          gui_app.pop_widgets_to(self._main, instant=True)
        else:
          self._sub = None
      rl.draw_text_ex(medium, "\u2039 Back", rl.Vector2(x, 22), 40, 0, ACCENT if self._pressed != "back" else DIM)
      rl.draw_text_ex(bold, f"{label} \u203a {sub}" if sub else label, rl.Vector2(x, 72), 60, 0, rl.WHITE)

    if self._mode == "mici":
      return  # the mici page is drawn in FALLBACK_VIEW
    page = self._page()
    if page is not self._shown:
      if self._shown is not None:
        self._shown.hide_event()
      if page is not None:
        page.show_event()
      self._shown = page
    if page is not None:
      with self._native(page_events):
        page.render(rl.Rectangle(x, y, w, h))
    self._hook_modal()
    if modal:
      with self._native(events):
        top.render(rl.Rectangle(0, 0, *SCREEN))
