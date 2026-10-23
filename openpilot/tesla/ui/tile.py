"""Tile base and the shared Windows Phone tile look (UI v4). Format (TileSpec) and layout live in tiles.py.
The host keeps one texture per tile and redraws it only when state() returns something new (or the size changes)."""
from typing import ClassVar

import pyray as rl

from openpilot.system.ui.lib.application import FontWeight, gui_app
from openpilot.tesla.ui.tiles import ACCENT, TileSpec

DIM = rl.Color(255, 255, 255, 170)
TITLE, UNIT, SUB = 30, 40, 36  # font sizes, px


def text_w(weight: FontWeight, text: str, size: int) -> float:
  return rl.measure_text_ex(gui_app.font(weight), text, size, 0).x


def text(weight: FontWeight, s: str, x: float, y: float, size: int, color=rl.WHITE) -> None:
  rl.draw_text_ex(gui_app.font(weight), s, rl.Vector2(x, y), size, 0, color)


class Tile:
  """Subclass in openpilot/tesla/ui/slots/ or in a plugin's ui.py (hidden while the plugin is off); must construct with no
  arguments. Tiles draw only; a tap offroad opens PAGE (a native page from tesla/ui/pages, or a mici layout when MICI)."""
  SPEC: ClassVar[TileSpec]
  PAGE: ClassVar[type | None] = None
  MICI: ClassVar[bool] = False
  COLOR: ClassVar[tuple[int, int, int]] = ACCENT  # the chosen tiles.THEMES color, set on Tile by the host

  def state(self, sm):
    """What the face shows, as a comparable value; polled at most SPEC.hz times per second. sm has ui_state services plus
    SPEC.services. The face is redrawn only when this changes."""
    return None

  def draw(self, rect: rl.Rectangle, size: str, state) -> None:
    """Draw the face into rect (texture px, origin 0,0); size is the placed size name."""
    self.face(rect)

  def face(self, rect: rl.Rectangle, icon: str | None = None) -> None:
    """Square tile in COLOR with the title at the bottom left and an optional centered icon (assets path)."""
    rl.draw_rectangle_rec(rect, rl.Color(*self.COLOR, 255))
    if icon is not None:
      side = int(min(rect.width, rect.height) * 0.36)
      tex = gui_app.texture(icon, side, side)
      rl.draw_texture(tex, int(rect.x + (rect.width - tex.width) / 2), int(rect.y + (rect.height - tex.height) / 2 - 16), rl.WHITE)
    text(FontWeight.MEDIUM, self.SPEC.title, rect.x + 16, rect.y + rect.height - TITLE - 14, TITLE)

  def draw_value(self, rect: rl.Rectangle, value: str, unit: str = "", sub: str = "") -> None:
    """Face, then one big value (with an optional unit after it) centered above the title, and an optional line below it."""
    self.face(rect)
    bottom = rect.height - TITLE - 28
    size = int(max(40, min(150, bottom - (SUB + 8 if sub else 0) - 24, rect.width * 0.42)))
    unit_w = text_w(FontWeight.MEDIUM, unit, UNIT) + 8 if unit else 0
    value_w = text_w(FontWeight.BOLD, value, size)
    y = rect.y + (bottom - size - (SUB + 8 if sub else 0)) / 2
    x = rect.x + (rect.width - value_w - unit_w) / 2
    text(FontWeight.BOLD, value, x, y, size)
    if unit:
      text(FontWeight.MEDIUM, unit, x + value_w + 8, y + size - UNIT - size * 0.12, UNIT, DIM)
    if sub:
      text(FontWeight.MEDIUM, sub, rect.x + (rect.width - text_w(FontWeight.MEDIUM, sub, SUB)) / 2, y + size + 8, SUB, DIM)

  def draw_lines(self, rect: rl.Rectangle, lines: list[str], size: int = 40) -> None:
    """Face, then one left-aligned line per entry from the top."""
    self.face(rect)
    for i, line in enumerate(lines):
      text(FontWeight.SEMI_BOLD, line, rect.x + 16, rect.y + 16 + i * (size + 6), size)
