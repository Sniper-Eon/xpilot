"""Slot base widget and the shared card look. The format (SlotSpec) and placement live in grid.py."""
from typing import ClassVar

import pyray as rl

from openpilot.system.ui.lib.application import FontWeight, gui_app
from openpilot.system.ui.widgets import Widget
from openpilot.tesla.ui.grid import SlotSpec

BG = rl.Color(22, 24, 30, 235)
DIM = rl.Color(150, 152, 162, 255)
TITLE, VALUE, UNIT, SUB = 34, 110, 40, 40  # font sizes, px


def _text_w(weight: FontWeight, text: str, size: int) -> float:
  return rl.measure_text_ex(gui_app.font(weight), text, size, 0).x


class Slot(Widget):
  """Subclass in openpilot/tesla/ui/slots/ or in a plugin's ui.py (hidden while the plugin is off), set SPEC, read data in update(), draw in _render(rect).
  Slots draw only: touches on cards are not forwarded to anything."""
  SPEC: ClassVar[SlotSpec]

  def update(self, sm) -> None:
    """Called at most SPEC.hz times per second before drawing; sm has ui_state services plus SPEC.services."""

  def _card(self, rect: rl.Rectangle) -> None:
    """Rounded dark card with the slot title at the top left."""
    rl.draw_rectangle_rounded(rect, 0.12, 10, BG)
    rl.draw_text_ex(gui_app.font(FontWeight.MEDIUM), self.SPEC.title, rl.Vector2(rect.x + 22, rect.y + 16), TITLE, 0, DIM)

  def draw_value(self, rect: rl.Rectangle, value: str, unit: str = "", sub: str = "") -> None:
    """One big value (with an optional unit after it) centered under the title, and an optional gray line below."""
    self._card(rect)
    top = rect.y + 16 + TITLE
    size = int(max(40, min(VALUE, rect.height - (top - rect.y) - (SUB + 8 if sub else 0) - 16)))
    unit_w = _text_w(FontWeight.MEDIUM, unit, UNIT) + 10 if unit else 0
    value_w = _text_w(FontWeight.BOLD, value, size)
    block_h = size + (SUB + 8 if sub else 0)
    y = top + (rect.y + rect.height - top - block_h) / 2
    x = rect.x + (rect.width - value_w - unit_w) / 2
    rl.draw_text_ex(gui_app.font(FontWeight.BOLD), value, rl.Vector2(x, y), size, 0, rl.WHITE)
    if unit:
      rl.draw_text_ex(gui_app.font(FontWeight.MEDIUM), unit, rl.Vector2(x + value_w + 10, y + size - UNIT - size * 0.12), UNIT, 0, DIM)
    if sub:
      sub_w = _text_w(FontWeight.MEDIUM, sub, SUB)
      rl.draw_text_ex(gui_app.font(FontWeight.MEDIUM), sub, rl.Vector2(rect.x + (rect.width - sub_w) / 2, y + size + 8), SUB, 0, DIM)

  def draw_lines(self, rect: rl.Rectangle, lines: list[str], size: int = 48) -> None:
    """Card with the title, then one left-aligned line per entry (for multi-value cards)."""
    self._card(rect)
    for i, line in enumerate(lines):
      rl.draw_text_ex(gui_app.font(FontWeight.SEMI_BOLD), line, rl.Vector2(rect.x + 22, rect.y + 24 + TITLE + i * (size + 6)), size, 0, rl.WHITE)
