"""Tile layout model of the big-screen UI v4 (XPILOT.md §9): grid, tile sizes, first-fit placement around the drive view,
the saved layout, edit operations, touch gestures and the redraw decision. No pyray here, so
tools/sp_tesla_e2e/tile_layout_check.py runs it on any host.

Grid: COLS x ROWS cells of CELL px with GAP px between them, centered on the 2160x1080 screen. A tile covers SIZES[size]
cells (cols, rows). Tiles go, in list order, to the first position that fits, scanning column by column (Win 8 landscape).
Onroad the cells under the mici driving view (DRIVE_CELLS) are blocked and a tile shrinks to a smaller supported size
when its saved size does not fit."""
from dataclasses import dataclass
from typing import Literal

SCREEN = (2160, 1080)
COLS, ROWS = 8, 4
CELL, GAP = 250, 12
PITCH = CELL + GAP
ORIGIN = ((SCREEN[0] - COLS * PITCH + GAP) // 2, (SCREEN[1] - ROWS * PITCH + GAP) // 2)
SIZES = {"small": (1, 1), "medium": (2, 2), "wide": (4, 2), "large": (4, 4)}
ACCENT = (0, 80, 239)  # WP cobalt
DARK = (22, 24, 30)

DRIVE_CELLS = (1, 0, 6, 3)  # col, row, cols, rows under the mici driving view
MICI = (536, 240)
LAYOUT_PARAM = "XpilotTileLayout"
LAYOUT_SPEC = {LAYOUT_PARAM: {"type": "JSON"}}  # kept by plugin_params.ParamsView as a file, not a compiled param

LONG_PRESS = 0.6  # s held without moving: enters edit mode
SLOP = 24         # px a press may move and still tap / long-press


def area(size: str) -> int:
  w, h = SIZES[size]
  return w * h


def size_rect(col: int, row: int, cells: tuple[int, int]) -> tuple[int, int, int, int]:
  """Screen px (x, y, w, h) of a block of cells (cols, rows) anchored at (col, row)."""
  return ORIGIN[0] + col * PITCH, ORIGIN[1] + row * PITCH, cells[0] * PITCH - GAP, cells[1] * PITCH - GAP


def cell_rect(col: int, row: int) -> tuple[int, int, int, int]:
  return size_rect(col, row, (1, 1))


def tile_rect(placed: tuple[int, int, str]) -> tuple[int, int, int, int]:
  col, row, size = placed
  return size_rect(col, row, SIZES[size])


def _view() -> tuple[int, int, int, int]:
  x, y, w, h = size_rect(DRIVE_CELLS[0], DRIVE_CELLS[1], DRIVE_CELLS[2:])
  scale = min(w / MICI[0], h / MICI[1])
  vw, vh = round(MICI[0] * scale), round(MICI[1] * scale)
  return x + (w - vw) // 2, y + (h - vh) // 2, vw, vh


VIEW = _view()  # mici onroad view, 536:240 centered in DRIVE_CELLS


def blocked(started: bool) -> set[tuple[int, int]]:
  if not started:
    return set()
  c, r, w, h = DRIVE_CELLS
  return {(col, row) for col in range(c, c + w) for row in range(r, r + h)}


@dataclass(frozen=True)
class TileSpec:
  id: str                                   # unique
  title: str                                # drawn at the bottom left of the tile
  sizes: tuple[str, ...] = ("small", "medium")  # supported sizes, the first is the default; onroad needs "small"
  services: tuple[str, ...] = ()            # every service state() reads; empty means it reads ui_state.sm
  show: Literal["always", "onroad", "offroad"] = "always"
  hz: float = 10.0                          # max state() polls per second; the face is redrawn only when state changes
  order: int = 100                          # default position, lower first
  color: tuple[int, int, int] = ACCENT      # background

  def __post_init__(self):
    if not self.sizes or any(s not in SIZES for s in self.sizes):
      raise ValueError(f"tile {self.id}: sizes {self.sizes} not in {tuple(SIZES)}")
    if self.show not in ("always", "onroad", "offroad"):
      raise ValueError(f"tile {self.id}: unknown show {self.show}")
    if not self.hz > 0:
      raise ValueError(f"tile {self.id}: hz must be > 0")


def shows(spec: TileSpec, started: bool) -> bool:
  return spec.show == "always" or (spec.show == "onroad") == started


def place(items: list[tuple[str, str, tuple[str, ...]]], started: bool) -> dict[str, tuple[int, int, str]]:
  """items: (id, saved size, supported sizes) in list order. Returns id -> (col, row, size) for every tile that fits;
  onroad a tile tries its saved size, then each smaller supported size, largest first."""
  taken = set(blocked(started))
  out = {}
  for tid, saved, sizes in items:
    tries = [saved] if not started else sorted((s for s in sizes if area(s) <= area(saved)), key=lambda s: -area(s))
    for size in tries:
      w, h = SIZES[size]
      pos = next(((c, r) for c in range(COLS - w + 1) for r in range(ROWS - h + 1)
                  if not any((c + i, r + j) in taken for i in range(w) for j in range(h))), None)
      if pos is not None:
        taken |= {(pos[0] + i, pos[1] + j) for i in range(w) for j in range(h)}
        out[tid] = (*pos, size)
        break
  return out


def cell_at(x: float, y: float) -> tuple[int, int] | None:
  """Grid cell under a screen point; a gap belongs to the cell left of / above it."""
  col, row = int((x - ORIGIN[0]) // PITCH), int((y - ORIGIN[1]) // PITCH)
  return (col, row) if 0 <= col < COLS and 0 <= row < ROWS else None


def hit(placed: dict[str, tuple[int, int, str]], x: float, y: float) -> str | None:
  for tid, p in placed.items():
    rx, ry, rw, rh = tile_rect(p)
    if rx <= x < rx + rw and ry <= y < ry + rh:
      return tid
  return None


def corner_buttons(rect) -> dict[str, tuple[float, float, float]]:
  """Edit mode circles (cx, cy, r) on the selected tile: unpin top right, resize bottom right."""
  x, y, w, h = rect
  r = 30
  return {"unpin": (x + w - r - 8, y + r + 8, r), "resize": (x + w - r - 8, y + h - r - 8, r)}


def add_cell(placed: dict[str, tuple[int, int, str]], started: bool) -> tuple[int, int] | None:
  """First free cell (column-major): edit mode draws the "+" (add tiles) there."""
  taken = set(blocked(started))
  for col, row, size in placed.values():
    w, h = SIZES[size]
    taken |= {(col + i, row + j) for i in range(w) for j in range(h)}
  return next(((c, r) for c in range(COLS) for r in range(ROWS) if (c, r) not in taken), None)


# saved layout: {"tiles": [[id, size], ...], "hidden": [id, ...]}

def arrange(specs: list[TileSpec], saved) -> tuple[list[tuple[str, str]], list[str]]:
  """(pinned [(id, size)] in order, hidden ids) from the saved layout. Unknown ids, unsupported sizes, duplicates and
  malformed entries are dropped; tiles in neither list are appended in (order, id) order at their default size."""
  by_id = {s.id: s for s in specs}
  saved = saved if isinstance(saved, dict) else {}
  tiles = saved.get("tiles") if isinstance(saved.get("tiles"), list) else []
  hidden_in = saved.get("hidden") if isinstance(saved.get("hidden"), list) else []
  pinned, seen = [], set()
  for entry in tiles:
    if not (isinstance(entry, list) and len(entry) == 2 and entry[0] in by_id) or entry[0] in seen:
      continue
    tid, size = entry
    seen.add(tid)
    pinned.append((tid, size if size in by_id[tid].sizes else by_id[tid].sizes[0]))
  hidden = []
  for tid in hidden_in:
    if isinstance(tid, str) and tid in by_id and tid not in seen:
      seen.add(tid)
      hidden.append(tid)
  pinned += [(s.id, s.sizes[0]) for s in sorted(specs, key=lambda s: (s.order, s.id)) if s.id not in seen]
  return pinned, hidden


def saved(pinned: list[tuple[str, str]], hidden: list[str]) -> dict:
  return {"tiles": [[tid, size] for tid, size in pinned], "hidden": list(hidden)}


def resize(pinned, tid: str, sizes: tuple[str, ...]):
  """Next size in the tile's sizes, wrapping."""
  return [(i, sizes[(sizes.index(s) + 1) % len(sizes)] if s in sizes else sizes[0]) if i == tid else (i, s) for i, s in pinned]


def unpin(pinned, hidden, tid: str):
  return [(i, s) for i, s in pinned if i != tid], [*hidden, tid]


def pin(pinned, hidden, tid: str, sizes: tuple[str, ...]):
  """Hidden or left-out tile to the end of the list at its smallest size, so it fits wherever a cell is free."""
  smallest = min(sizes, key=area)
  return [(i, s) for i, s in pinned if i != tid] + [(tid, smallest)], [i for i in hidden if i != tid]


def move(pinned, placed: dict[str, tuple[int, int, str]], tid: str, cell: tuple[int, int]):
  """Drop tid on cell: it goes before the first other placed tile anchored at or after the cell (column-major), else to
  the end. Dropping inside its own cells changes nothing."""
  if tid in placed:
    col, row, size = placed[tid]
    w, h = SIZES[size]
    if col <= cell[0] < col + w and row <= cell[1] < row + h:
      return list(pinned)
  key = (cell[0], cell[1])
  before = next((i for i, _ in pinned if i != tid and i in placed and placed[i][:2] >= key), None)
  entry = next(e for e in pinned if e[0] == tid)
  rest = [e for e in pinned if e[0] != tid]
  index = next((n for n, e in enumerate(rest) if e[0] == before), len(rest))
  return rest[:index] + [entry] + rest[index:]


def addable(pinned, hidden, placed) -> list[str]:
  """The "Add tiles" list: hidden tiles, then visible pinned tiles left out for lack of room."""
  return list(hidden) + [i for i, _ in pinned if i not in placed]


class Gesture:
  """One finger on the tile screen: press/move/release feed it screen points; tick(now) runs every frame.
  Events: "tap" (released before LONG_PRESS, moved < SLOP), "long" (held LONG_PRESS without moving, once),
  "drag" (moved >= SLOP, once), "drop" (released after a drag)."""

  def __init__(self):
    self.start = None  # (x, y, t) of the press
    self.pos = None
    self.long = self.drag = False

  def press(self, x, y, t):
    self.start, self.pos, self.long, self.drag = (x, y, t), (x, y), False, False

  def move(self, x, y, t):
    if self.start is None:
      return None
    self.pos = (x, y)
    if not self.drag and (x - self.start[0]) ** 2 + (y - self.start[1]) ** 2 >= SLOP ** 2:
      self.drag = True
      return "drag"
    return None

  def tick(self, now):
    if self.start is None or self.long or self.drag or now - self.start[2] < LONG_PRESS:
      return None
    self.long = True
    return "long"

  def release(self, x, y, t):
    if self.start is None:
      return None
    event = self.move(x, y, t)
    self.start = None
    if self.drag or event:
      return "drop"
    return None if self.long else "tap"


class Poll:
  """Per-tile redraw decision: state() is polled at most hz times a second, the face redrawn only when the polled state
  or the size key differs from what the cached texture shows."""
  _UNSET = object()

  def __init__(self, hz: float):
    self.period, self.next = 1.0 / hz, float("-inf")
    self.shown = self._UNSET

  def due(self, now: float) -> bool:
    if now < self.next - 1e-3 * self.period:
      return False
    self.next = now + self.period
    return True

  def changed(self, state, key) -> bool:
    if self.shown is not self._UNSET and self.shown == (state, key):
      return False
    self.shown = (state, key)
    return True

  def invalidate(self) -> None:
    self.shown = self._UNSET
