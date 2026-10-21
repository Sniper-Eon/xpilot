"""Slot base widget. The format (SlotSpec) and placement live in grid.py."""
from typing import ClassVar

import pyray as rl

from openpilot.system.ui.lib.application import FontWeight, gui_app
from openpilot.system.ui.widgets import Widget
from openpilot.tesla.ui.grid import SlotSpec

BG = rl.Color(24, 24, 28, 255)
DIM = rl.Color(150, 150, 160, 255)


class Slot(Widget):
  """Subclass in openpilot/tesla/ui/slots/, set SPEC, read data in update(), draw in _render(rect).
  Slots draw only: touches go to the mici window, not to slots."""
  SPEC: ClassVar[SlotSpec]

  def update(self, sm) -> None:
    """Called at most SPEC.hz times per second before drawing; sm has ui_state services plus SPEC.services."""

  def draw_lines(self, rect: rl.Rectangle, lines: list[str], size: int = 56) -> None:
    """Common tile look: title, then one value per line."""
    rl.draw_rectangle_rounded(rect, 0.08, 10, BG)
    rl.draw_text_ex(gui_app.font(FontWeight.MEDIUM), self.SPEC.title, rl.Vector2(rect.x + 24, rect.y + 16), 36, 0, DIM)
    for i, line in enumerate(lines):
      rl.draw_text_ex(gui_app.font(FontWeight.BOLD), line, rl.Vector2(rect.x + 24, rect.y + 64 + i * (size + 8)), size, 0, rl.WHITE)
