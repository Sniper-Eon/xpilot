"""Slot format and placement for the big-screen host. No pyray here, so it is checkable anywhere
(tools/sp_tesla_e2e/slot_layout_check.py).

Slot format: a module in openpilot/tesla/ui/slots/ defines a subclass of openpilot.tesla.ui.slot.Slot with
  SPEC = SlotSpec(id, title, cells=(cols, rows), services=(...), show="always"|"onroad"|"offroad", hz=5.0, order=100)
The host finds it at startup and places it around the video window; nothing else needs registering.
"""
from dataclasses import dataclass
import itertools
from typing import Literal

CELL = 180  # px; the 2160x1080 screen is a 12 x 6 grid
COLS, ROWS = 12, 6


@dataclass(frozen=True)
class SlotSpec:
  id: str                          # unique
  title: str
  cells: tuple[int, int] = (2, 1)  # size in grid cells (cols, rows)
  services: tuple[str, ...] = ()   # every service update() reads; empty means it reads ui_state.sm
  show: Literal["always", "onroad", "offroad"] = "always"
  hz: float = 5.0                  # max redraw rate; other frames reuse the cached texture
  order: int = 100                 # placement priority, lower first


def _overlap(a, b) -> bool:
  return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def place(window: tuple[float, float, float, float], specs: list[SlotSpec], started: bool) -> dict[str, tuple[int, int, int, int]]:
  """First-fit, row-major placement of visible slots in cells the window (x, y, w, h px) does not touch.
  Returns slot id -> (x, y, w, h) px. Slots without room are left out."""
  taken = [[_overlap((c * CELL, r * CELL, CELL, CELL), window) for c in range(COLS)] for r in range(ROWS)]
  out = {}
  for spec in sorted(specs, key=lambda s: (s.order, s.id)):
    if spec.show != "always" and (spec.show == "onroad") != started:
      continue
    cols, rows = spec.cells
    for r, c in itertools.product(range(ROWS - rows + 1), range(COLS - cols + 1)):
      cells = [(rr, cc) for rr in range(r, r + rows) for cc in range(c, c + cols)]
      if not any(taken[rr][cc] for rr, cc in cells):
        for rr, cc in cells:
          taken[rr][cc] = True
        out[spec.id] = (c * CELL, r * CELL, cols * CELL, rows * CELL)
        break
  return out
