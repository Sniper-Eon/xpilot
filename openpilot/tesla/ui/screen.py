"""Big-screen host (C3/C3X/C3XL, 2160x1080), UI v4: Windows Phone / Win 8 style tiles (XPILOT.md §9, layout in tiles.py).
Onroad: the mici view fixed at tiles.VIEW, tiles in the cells around it, then plugin ScreenOverlays; no touches.
Alerts are drawn once, by mici inside the view.
Offroad: the tile screen (tap opens a tile's page, long press enters edit mode), or a full-screen detail page: back
button, parent name, title, and a native page (tesla/ui/pages) drawn here in screen pixels. The mici texture is not
drawn (viewport() -> None) except during onboarding and for mici pages pushed above main (Models, training guide, terms,
regulatory, cabin camera), which show at 3x in FALLBACK_VIEW. Without a viewport every touch maps far outside the mici
screen, so the mici widgets running underneath never react. tici dialogs (ConfirmDialog, Keyboard) the native pages
push onto the nav stack are hidden in the mici pass and drawn full-screen here."""
from __future__ import annotations  # pyray types are functions: rl.Rectangle | None fails at import

from contextlib import contextmanager
import math
import time

import pyray as rl

from openpilot.cereal import messaging
from openpilot.common.hardware import HARDWARE
from openpilot.common.params import Params
from openpilot.common.swaglog import cloudlog
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.sunnypilot.hardware.profile import HardwareProfile, get_hardware_profile
from openpilot.system.ui.lib.application import MousePos, gui_app, FontWeight
from openpilot.system.ui.widgets.list_view import button_item, text_item
from openpilot.tesla.plugin_params import ParamsView
from openpilot.tesla.ui import offroad, tiles
from openpilot.tesla.ui.offroad import BACK, CONTENT, TITLE_H
from openpilot.tesla.ui.pages.base import ListPage
from openpilot.tesla.ui.pages.device import DevicePage
from openpilot.tesla.ui.pages.onboarding import OnboardingPage
from openpilot.tesla.ui.plugin_ui import MAX_FAILURES, EnabledPlugins, Overlays, ScreenOverlay, load
from openpilot.tesla.ui.tile import Tile
from openpilot.tesla.ui.tiles import LAYOUT_PARAM, LAYOUT_SPEC, SCREEN, VIEW

DIM = rl.Color(150, 152, 162, 255)
SHADE = rl.Color(0, 0, 0, 120)      # over unselected tiles in edit mode
PRESSED = rl.Color(0, 0, 0, 60)
ACCENT = rl.Color(*tiles.ACCENT, 255)


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


def _zones() -> dict:
  """ScreenOverlay zones: the strips around VIEW and VIEW itself."""
  x, y, w, h = VIEW
  return {"left": rl.Rectangle(0, 0, x, SCREEN[1]), "right": rl.Rectangle(x + w, 0, SCREEN[0] - x - w, SCREEN[1]),
          "top": rl.Rectangle(x, 0, w, y), "bottom": rl.Rectangle(x, y + h, w, SCREEN[1] - y - h), "view": rl.Rectangle(*VIEW)}


class _Entry:
  def __init__(self, plugin: str | None, tile: Tile):
    self.plugin, self.tile, self.spec = plugin, tile, tile.SPEC
    self.poll, self.texture, self.state, self.failures = tiles.Poll(tile.SPEC.hz), None, None, 0


class AddTilesPage(ListPage):
  """Edit mode "+": one row per hidden or left-out tile; tapping one pins it."""

  def __init__(self, entries, pin):
    super().__init__()
    if not entries:
      self.add(text_item("No tiles to add", "", "Every tile is on the screen."))
    for e in entries:
      self.add(button_item(e.spec.title, "ADD", callback=lambda tid=e.spec.id: pin(tid)))

  def show_event(self):
    super().show_event()


class BigScreenHost:
  size = SCREEN

  def __init__(self):
    self._params = Params()
    self._layout_params = ParamsView(self._params, LAYOUT_SPEC)
    self._entries: dict[str, _Entry] = {}
    for name, tile in load(Tile):  # core slots/ and each plugin's ui.py
      if tile.SPEC.id in self._entries:
        cloudlog.error(f"tile id {tile.SPEC.id} used twice, keeping the first")
        continue
      self._entries[tile.SPEC.id] = _Entry(name, tile)
    self._overlays = Overlays(ScreenOverlay, self._params)
    self._enabled = EnabledPlugins(self._params)
    services = sorted({svc for e in self._entries.values() for svc in e.spec.services})
    self._sm = messaging.SubMaster(services) if services else None
    self._zones = _zones()
    try:
      saved = self._layout_params.get(LAYOUT_PARAM)
    except Exception:
      saved = None
    specs = [e.spec for e in self._entries.values()]
    self._layouts = {mode: tiles.arrange([s for s in specs if tiles.shows(s, mode == "drive")], saved, mode) for mode in ("park", "drive")}
    self._layout = "park"  # the layout the tile screen shows and edit mode edits; onroad always shows "drive"
    self._placed_key = None
    self._placed: dict[str, tuple[int, int, str]] = {}
    self._main = None
    self._pages: dict[str, object] = {}
    self._stack: list[tuple[str, object | None]] = []  # open detail pages (title, native page or None for a mici page)
    self._shown = None  # the native page that last got show_event
    self._gesture = tiles.Gesture()
    self._edit = False
    self._selected: str | None = None
    self._drag: str | None = None
    self._back_pressed = False
    self._view: tuple | None = None  # set each frame by viewport(); to_logical runs on the touch thread
    self._mode = "native"
    self._host_pass = False
    self._onboarding = OnboardingPage(self._onboarding_done)

  def bind_settings(self, main, _settings) -> None:
    self._main = main

  def open_settings(self) -> None:
    self.open_tile("toggles")

  # layout

  def _visible(self, mode: str) -> list[tuple[str, str, tuple[str, ...], tuple[int, int] | None]]:
    enabled = self._enabled.get()
    out = []
    for tid, size, fixed in self._layouts[mode][0]:
      e = self._entries[tid]
      if e.failures < MAX_FAILURES and (e.plugin is None or e.plugin in enabled):
        out.append((tid, size, e.spec.sizes, fixed))
    return out

  def _place(self, mode: str) -> dict[str, tuple[int, int, str]]:
    items = self._visible(mode)
    key = (mode, tuple(items))
    if key != self._placed_key:
      self._placed_key, self._placed = key, tiles.place(items, mode == "drive")
    return self._placed

  def _save(self, pinned, hidden=None) -> None:
    """Replace the edited layout and write both."""
    self._layouts[self._layout] = (pinned, self._layouts[self._layout][1] if hidden is None else hidden)
    try:
      self._layout_params.put(LAYOUT_PARAM, {mode: tiles.saved(*layout) for mode, layout in self._layouts.items()})
    except Exception:
      cloudlog.exception("tile layout not saved")

  def _pin(self, tid: str) -> None:
    self._save(*tiles.pin(*self._layouts[self._layout], tid, self._entries[tid].spec.sizes))
    self._back()

  # pages

  def open_tile(self, tid: str) -> None:
    e = self._entries.get(tid)
    if e is None or e.tile.PAGE is None:
      return
    gui_app.pop_widgets_to(self._main, instant=True)  # never grow the nav stack
    self._stack = []
    if tid not in self._pages:
      try:
        page = e.tile.PAGE()
      except Exception:
        cloudlog.exception(f"tile {tid}: page failed to build")  # a broken page must not take the UI down
        return
      page.open = self._open
      if isinstance(page, DevicePage):
        page.main = self._main
      self._pages[tid] = page
    if e.tile.MICI:
      gui_app.push_widget(self._pages[tid])
      self._stack.append((e.spec.title, None))  # shown by mici in FALLBACK_VIEW
    else:
      self._open(e.spec.title, self._pages[tid])

  def _open(self, title, page) -> None:
    """Push a detail page; ListPage.open(title, sub) of the open page lands here too. page None: back one level."""
    if page is not None:
      self._stack.append((title, page))
    elif self._stack:
      self._stack.pop()

  def _onboarding_done(self) -> None:
    gui_app.pop_widgets_to(self._main, instant=True)  # what mici's OnboardingWindow callback does

  def back(self) -> None:
    """Close the open detail page (pages.base.back)."""
    self._back()

  def _back(self) -> None:
    if self._mode == "mici":
      gui_app.pop_widgets_to(self._main, instant=True)
      if self._stack and self._stack[-1][1] is not None:
        return  # a mici dialog opened by a native page (Device): back to that page
    if self._stack:
      self._stack.pop()

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

  # drawing

  def render(self) -> None:
    if self._mode == "onroad":
      self._edit, self._drag, self._selected, self._layout = False, None, None, "park"
      self._draw_tiles(self._place("drive"))
      self._draw_overlays()
    elif self._mode == "onboarding":
      events = [e._replace(pos=MousePos(*offroad.to_screen(None, e.pos.x, e.pos.y))) for e in gui_app.mouse_events]
      self._show(self._onboarding if self._main is not None else None)
      if self._main is not None:
        with self._native(events):
          self._onboarding.render(rl.Rectangle(0, 0, *SCREEN))
    else:
      self._draw_offroad()

  def _face(self, e: _Entry, size: str, now: float) -> bool:
    """Bring the tile's cached texture up to date; True if there is one to draw."""
    w, h = tiles.SIZES[size]
    w, h = w * tiles.PITCH - tiles.GAP, h * tiles.PITCH - tiles.GAP
    if e.texture is None or e.texture.texture.width != w or e.texture.texture.height != h:
      if e.texture is not None:
        rl.unload_render_texture(e.texture)
      e.texture = rl.load_render_texture(w, h)
      e.poll.invalidate()
    try:
      if e.poll.due(now):
        e.state = e.tile.state(self._sm if self._sm is not None and e.spec.services else ui_state.sm)
      if e.poll.changed(e.state, size):
        rl.begin_texture_mode(e.texture)
        rl.clear_background(rl.BLANK)
        try:
          with scaled(1):
            e.tile.draw(rl.Rectangle(0, 0, w, h), size, e.state)
        finally:
          rl.end_texture_mode()
      e.failures = 0
    except Exception:
      e.failures += 1  # a broken tile must never take the UI (and engagement) down
      e.poll.invalidate()
      cloudlog.exception(f"tile {e.spec.id} failed")
      return False
    return True

  def _draw_tiles(self, placed, now: float | None = None) -> None:
    if self._sm is not None:
      self._sm.update(0)
    now = time.monotonic() if now is None else now
    for tid, p in placed.items():
      e = self._entries[tid]
      if tid == self._drag or not self._face(e, p[2], now):
        continue
      x, y, w, h = tiles.tile_rect(p)
      grow = 0.03 * w if self._edit and tid == self._selected else 0.0
      self._blit(e, rl.Rectangle(x - grow, y - grow * h / w, w + 2 * grow, h + 2 * grow * h / w))
      if self._edit and tid != self._selected:
        rl.draw_rectangle(x, y, w, h, SHADE)
      elif not self._edit and self._gesture.start is not None and tiles.hit({tid: p}, *self._gesture.start[:2]) and not self._gesture.long:
        rl.draw_rectangle(x, y, w, h, PRESSED)

  @staticmethod
  def _blit(e: _Entry, dest: rl.Rectangle) -> None:
    t = e.texture.texture
    rl.draw_texture_pro(t, rl.Rectangle(0, 0, t.width, -t.height), dest, rl.Vector2(0, 0), 0.0, rl.WHITE)

  def _draw_overlays(self) -> None:
    self._overlays.each(lambda o: (o.update(ui_state.sm), o.draw(self._zones)))

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

  def _draw_offroad(self) -> None:
    events = [e._replace(pos=MousePos(*offroad.to_screen(self._view, e.pos.x, e.pos.y))) for e in gui_app.mouse_events]
    top = gui_app.get_active_widget()
    if top is self._main and self._stack and self._stack[-1][1] is None:
      self._stack.pop()  # left the Models page with the mici back gesture
    modal = self._mode == "modal"
    if not self._stack and self._mode != "mici":
      self._show(None)
      self._draw_start(events if not modal else [])
    else:
      self._draw_detail(top, events if not modal else [])
    self._hook_modal()
    if modal:
      with self._native(events):
        top.render(rl.Rectangle(0, 0, *SCREEN))

  def _show(self, page) -> None:
    if page is not self._shown:
      if self._shown is not None:
        self._shown.hide_event()
      if page is not None:
        page.show_event()
      self._shown = page

  # tile screen and edit mode

  def _draw_start(self, events) -> None:
    now = time.monotonic()
    placed = self._place(self._layout)
    for ev in events:
      if ev.slot != 0:
        continue
      x, y = ev.pos.x, ev.pos.y
      if ev.left_pressed:
        self._gesture.press(x, y, ev.t)
      elif ev.left_released:
        self._on_gesture(self._gesture.start, self._gesture.release(x, y, ev.t), x, y, placed)
      elif ev.left_down:
        self._on_gesture(self._gesture.start, self._gesture.move(x, y, ev.t), x, y, placed)
    if self._gesture.start is not None:
      self._on_gesture(self._gesture.start, self._gesture.tick(now), *self._gesture.pos, placed)
    placed = self._place(self._layout)
    drive = self._layout == "drive"
    if drive:
      rl.draw_rectangle_rec(rl.Rectangle(*VIEW), rl.Color(40, 42, 50, 255))
      label = "Driving view"
      width = rl.measure_text_ex(gui_app.font(FontWeight.MEDIUM), label, 48, 0).x
      rl.draw_text_ex(gui_app.font(FontWeight.MEDIUM), label, rl.Vector2(VIEW[0] + (VIEW[2] - width) / 2, VIEW[1] + VIEW[3] / 2 - 24), 48, 0, DIM)
    self._draw_tiles(placed, now)
    if not self._edit:
      return
    cell = tiles.add_cell(placed, drive)
    if cell is not None:
      x, y, w, h = tiles.cell_rect(*cell)
      rl.draw_rectangle_lines_ex(rl.Rectangle(x, y, w, h), 3, DIM)
      rl.draw_line_ex(rl.Vector2(x + w / 2 - 40, y + h / 2), rl.Vector2(x + w / 2 + 40, y + h / 2), 6, DIM)
      rl.draw_line_ex(rl.Vector2(x + w / 2, y + h / 2 - 40), rl.Vector2(x + w / 2, y + h / 2 + 40), 6, DIM)
    if self._selected in placed and self._drag is None:
      self._draw_corner_buttons(tiles.tile_rect(placed[self._selected]))
    if self._drag is not None and self._drag in placed and self._gesture.start is not None:
      e = self._entries[self._drag]
      x, y, w, h = tiles.tile_rect(placed[self._drag])
      dx, dy = self._gesture.pos[0] - self._gesture.start[0], self._gesture.pos[1] - self._gesture.start[1]
      if self._face(e, placed[self._drag][2], now):
        self._blit(e, rl.Rectangle(x + dx, y + dy, w, h))
    self._draw_bar(placed)

  def _draw_bar(self, placed) -> None:
    medium = gui_app.font(FontWeight.MEDIUM)
    for name, (x, y, w, h) in tiles.bar_buttons(placed, self._layout == "drive").items():
      active = name == self._layout
      rl.draw_rectangle(x, y, w, h, ACCENT if active else rl.Color(72, 75, 88, 255))
      label = name.capitalize()
      width = rl.measure_text_ex(medium, label, 40, 0).x
      rl.draw_text_ex(medium, label, rl.Vector2(x + (w - width) / 2, y + (h - 40) / 2), 40, 0, rl.WHITE)

  @staticmethod
  def _draw_corner_buttons(rect) -> None:
    buttons = tiles.corner_buttons(rect)
    for name, (cx, cy, r) in buttons.items():
      rl.draw_circle(int(cx), int(cy), r, rl.WHITE)
      d = r * 0.45
      dark = rl.Color(20, 20, 24, 255)
      if name == "unpin":  # x
        rl.draw_line_ex(rl.Vector2(cx - d, cy - d), rl.Vector2(cx + d, cy + d), 5, dark)
        rl.draw_line_ex(rl.Vector2(cx - d, cy + d), rl.Vector2(cx + d, cy - d), 5, dark)
      else:  # diagonal double arrow
        rl.draw_line_ex(rl.Vector2(cx - d, cy + d), rl.Vector2(cx + d, cy - d), 5, dark)
        for sx, sy in ((cx + d, cy - d), (cx - d, cy + d)):
          k = 1 if sx > cx else -1
          rl.draw_line_ex(rl.Vector2(sx, sy), rl.Vector2(sx - k * d * 0.9, sy), 5, dark)
          rl.draw_line_ex(rl.Vector2(sx, sy), rl.Vector2(sx, sy + k * d * 0.9), 5, dark)

  def _on_gesture(self, start, event, x, y, placed) -> None:
    if event is None or start is None:
      return
    sx, sy = start[:2]
    bar = tiles.bar_buttons(placed, self._layout == "drive")
    if self._edit and any(x0 <= sx < x0 + w and y0 <= sy < y0 + h for x0, y0, w, h in bar.values()):
      if event == "tap":
        self._bar_tap(sx, sy, bar)
      return
    tid = tiles.hit(placed, sx, sy)
    if event == "long" and not self._edit:
      self._edit, self._selected = True, tid
    elif event == "drag" and self._edit and tid is not None:
      self._drag = self._selected = tid
    elif event == "drop" and self._drag is not None:
      cell = tiles.cell_at(x, y)
      if cell is not None:
        self._save(tiles.move(self._layouts[self._layout][0], placed, self._drag, cell, self._layout == "drive"))
      self._drag = None
    elif event == "tap" and not self._edit:
      if tid is not None:
        self.open_tile(tid)
    elif event == "tap":
      self._edit_tap(sx, sy, tid, placed)

  def _bar_tap(self, x, y, bar) -> None:
    for name, (x0, y0, w, h) in bar.items():
      if x0 <= x < x0 + w and y0 <= y < y0 + h:
        self._selected = None
        if name == "done":
          self._edit, self._layout = False, "park"
        else:
          self._layout = name

  def _edit_tap(self, x, y, tid, placed) -> None:
    if self._selected in placed:
      for name, (cx, cy, r) in tiles.corner_buttons(tiles.tile_rect(placed[self._selected])).items():
        if (x - cx) ** 2 + (y - cy) ** 2 <= (r + 12) ** 2:
          if name == "unpin":
            self._save(*tiles.unpin(*self._layouts[self._layout], self._selected))
            self._selected = None
          else:
            self._save(tiles.resize(self._layouts[self._layout][0], self._selected, self._entries[self._selected].spec.sizes))
          return
    if tid is not None:
      self._selected = None if tid == self._selected else tid
      return
    drive = self._layout == "drive"
    if tiles.cell_at(x, y) is not None and tiles.cell_at(x, y) == tiles.add_cell(placed, drive):
      ids = tiles.addable(self._visible(self._layout), self._layouts[self._layout][1], placed)
      self._open("add tiles", AddTilesPage([self._entries[i] for i in ids], self._pin))
      return
    self._selected = None

  # detail pages

  def _draw_detail(self, top, events) -> None:
    title, page = self._stack[-1] if self._stack else ("", None)
    parent = self._stack[-2][0] if len(self._stack) > 1 else "xpilot"
    if self._mode == "mici" and page is not None:
      parent, title = title, type(top).__name__
    self._draw_title(parent, title, events)
    if self._mode == "mici":
      self._show(None)
      return  # the mici page is drawn in FALLBACK_VIEW
    self._show(page)
    if page is not None:
      with self._native(events):
        page.render(rl.Rectangle(*CONTENT))

  def _draw_title(self, parent: str, title: str, events) -> None:
    back = rl.Rectangle(*BACK)
    for ev in events:
      inside = rl.check_collision_point_rec(ev.pos, back)
      if ev.left_pressed and inside:
        self._back_pressed = True
      if ev.left_released and self._back_pressed:
        self._back_pressed = False
        if inside:
          self._back()
    cx, cy, r = 72, 84, 38
    color = DIM if self._back_pressed else rl.WHITE
    rl.draw_ring(rl.Vector2(cx, cy), r - 3, r, 0, 360, 48, color)
    rl.draw_line_ex(rl.Vector2(cx - 16, cy), rl.Vector2(cx + 16, cy), 4, color)
    rl.draw_line_ex(rl.Vector2(cx - 16, cy), rl.Vector2(cx - 2, cy - 14), 4, color)
    rl.draw_line_ex(rl.Vector2(cx - 16, cy), rl.Vector2(cx - 2, cy + 14), 4, color)
    rl.draw_text_ex(gui_app.font(FontWeight.SEMI_BOLD), parent.upper(), rl.Vector2(CONTENT[0], 50), 34, 2, DIM)
    rl.draw_text_ex(gui_app.font(FontWeight.NORMAL), title.lower(), rl.Vector2(CONTENT[0] - 6, 88), 110, 0, rl.WHITE)
    rl.draw_line_ex(rl.Vector2(CONTENT[0], TITLE_H - 2), rl.Vector2(CONTENT[0] + CONTENT[2], TITLE_H - 2), 2, rl.Color(255, 255, 255, 30))
