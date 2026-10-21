"""Big-screen host for C3/C3X/C3XL: the mici UI in a movable window, slots around it, alerts on top.

Window: Params "TeslaVideoWindow" {"x", "y", "scale"} in screen px; default mici size (536x240) centered.
Edit: hold a finger 1 s outside the window, then drag the window to move it or its bottom-right corner to
resize it; tap outside to save. Slots: see grid.py for the format.
"""
from contextlib import contextmanager
import importlib
import inspect
import math
import pkgutil
import time

import pyray as rl

from openpilot.cereal import messaging
from openpilot.common.hardware import HARDWARE
from openpilot.common.params import Params
from openpilot.common.swaglog import cloudlog
from openpilot.selfdrive.ui.mici.onroad.alert_renderer import AlertRenderer
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.sunnypilot.hardware.profile import HardwareProfile, get_hardware_profile
from openpilot.tesla.ui import slots as slots_pkg
from openpilot.tesla.ui.grid import place
from openpilot.tesla.ui.slot import Slot

SCREEN = (2160, 1080)
MICI = (536, 240)
BANNER_SCALE = 2  # the mici alert layout at 2x: 1080x160 logical, full width and 320 px tall on screen
HOLD_S = 1.0
CORNER_PX = 90
MAX_FAILURES = 3
EDIT_COLOR = rl.Color(70, 160, 255, 255)


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


def load_slots() -> list[Slot]:
  """Every Slot subclass with a SPEC in openpilot/tesla/ui/slots/; a broken module is logged and skipped."""
  found = []
  for info in pkgutil.iter_modules(slots_pkg.__path__):
    try:
      mod = importlib.import_module(f"{slots_pkg.__name__}.{info.name}")
      found += [cls() for _, cls in inspect.getmembers(mod, inspect.isclass)
                if issubclass(cls, Slot) and cls.__module__ == mod.__name__ and hasattr(cls, "SPEC")]
    except Exception:
      cloudlog.exception(f"slot module {info.name} failed to load")
  return found


class _Tile:
  def __init__(self, slot: Slot):
    self.slot, self.rect, self.texture, self.last, self.failures = slot, None, None, 0.0, 0


class BigScreenHost:
  size = SCREEN

  def __init__(self):
    self._params = Params()
    w = self._params.get("TeslaVideoWindow") or {}
    self._max_scale = min(SCREEN[0] / MICI[0], SCREEN[1] / MICI[1])
    self._set_window(float(w.get("x", (SCREEN[0] - MICI[0]) / 2)), float(w.get("y", (SCREEN[1] - MICI[1]) / 2)), float(w.get("scale", 1.0)))
    self._banner = AlertRenderer()
    self._tiles = [_Tile(s) for s in load_slots()]
    services = sorted({svc for t in self._tiles for svc in t.slot.SPEC.services})
    self._sm = messaging.SubMaster(services) if services else None
    self._layout_key = None
    self._editing, self._drag, self._hold_start = False, None, 0.0

  def _set_window(self, x: float, y: float, s: float) -> None:
    self._s = min(max(s, 1.0), self._max_scale)
    self._x = min(max(x, 0.0), SCREEN[0] - MICI[0] * self._s)
    self._y = min(max(y, 0.0), SCREEN[1] - MICI[1] * self._s)

  def viewport(self) -> rl.Rectangle:
    return rl.Rectangle(self._x, self._y, MICI[0] * self._s, MICI[1] * self._s)

  def to_logical(self, x: float, y: float) -> tuple[float, float]:
    if self._editing:
      return -1e6, -1e6  # the mici UI ignores touches while the window is being edited
    return (x - self._x) / self._s, (y - self._y) / self._s

  def render(self) -> None:
    self._edit_input()
    key = (self._x, self._y, self._s, ui_state.started)
    if key != self._layout_key:
      self._layout_key = key
      rects = place((self._x, self._y, MICI[0] * self._s, MICI[1] * self._s), [t.slot.SPEC for t in self._tiles], ui_state.started)
      for t in self._tiles:
        t.rect = rects.get(t.slot.SPEC.id)
    self._draw_tiles()
    if self._editing:
      v = self.viewport()
      rl.draw_rectangle_lines_ex(v, 6, EDIT_COLOR)
      rl.draw_rectangle_rec(rl.Rectangle(v.x + v.width - CORNER_PX, v.y + v.height - CORNER_PX, CORNER_PX, CORNER_PX), EDIT_COLOR)
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

  def _edit_input(self) -> None:
    down, pos, now = rl.is_mouse_button_down(0), rl.get_touch_position(0), time.monotonic()
    inside = rl.check_collision_point_rec(pos, self.viewport())
    if not self._editing:
      if down and not inside:
        self._hold_start = self._hold_start or now
        if now - self._hold_start >= HOLD_S:
          self._editing, self._drag = True, "wait_release"
      else:
        self._hold_start = 0.0
      return
    if not down:
      if self._drag == "exit":
        self._editing = False
        self._params.put("TeslaVideoWindow", {"x": self._x, "y": self._y, "scale": self._s})
      self._drag = None
      return
    if self._drag is None:
      v = self.viewport()
      corner = inside and pos.x > v.x + v.width - CORNER_PX and pos.y > v.y + v.height - CORNER_PX
      self._drag = ("scale" if corner else "move", pos.x, pos.y, self._x, self._y, self._s) if inside else "exit"
    elif isinstance(self._drag, tuple):
      mode, px, py, x0, y0, s0 = self._drag
      if mode == "move":
        self._set_window(x0 + pos.x - px, y0 + pos.y - py, self._s)
      else:
        self._set_window(x0, y0, s0 + max(pos.x - px, (pos.y - py) * MICI[0] / MICI[1]) / MICI[0])
