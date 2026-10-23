#!/usr/bin/env python3
"""Big-screen tile check (UI v4, XPILOT.md §9): the pyray-free layout model in openpilot/tesla/ui/tiles.py, plus the text the
tile UI draws. Rendering and real touches are checked on the device by tools/sp_tesla_e2e/big_screen_e2e.py.

Failure cases listed before implementation:
- T1  grid cells overlap, the gap is not GAP px, or the grid leaves the screen / is not centered
- T2  two placed tiles overlap
- T3  a tile is placed outside the grid or on a cell the drive view blocks
- T4  a tile is left out while a position (in column-major first-fit order) still fits it, or is placed after a free
      position that fits it (placement is not first-fit column-major, or depends on anything but the list)
- T5  offroad a tile is placed at another size than its saved size; onroad at a larger size than saved, or a size it does
      not support
- T6  the drive VIEW leaves the blocked cells, is not 536:240, is not centered in them, or onroad free cells are not 14
- T7  offroad-only tiles show onroad or onroad-only tiles show offroad
- T8  loading a saved layout: garbage gives no defaults, unknown ids or unsupported sizes survive, an id appears twice,
      new tiles are not appended in (order, id) order at their default size, hidden tiles show, or save/load does not
      round-trip
- T9  edit ops: resize does not cycle through the tile's sizes, unpin/pin do not move between pinned and hidden, move does
      not insert before the first tile placed after the drop cell (or at the end), or dropping a tile on itself reorders
- T10 hit tests: a gap hits a tile, a cell center does not map back to its cell, corner buttons leave their tile or
      overlap each other
- T11 gestures: a short press without movement is not a tap, a held press is not one long press, a moved press still
      taps or long-presses, or a drag does not end in one drop
- T12 TileSpec accepts no sizes, an unknown size, an unknown show value or hz <= 0
- T13 tile UI text (string constants in openpilot/tesla/ui and plugins' ui.py, plugin.json names, descriptions and setting
      labels) has non-ASCII characters (the device font lacks some, e.g. ‹ › · —, and draws "?")
- T14 edit mode: no "+" cell when tiles are hidden or left out and the grid has room, or the add list misses a hidden or
      left-out tile
- T15 a tile face is redrawn while its state and size are unchanged, not redrawn after either changes, or state() is
      polled more than hz times a second
"""
import ast
import itertools
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from openpilot.tesla.ui import tiles as T  # noqa: E402

ALL = tuple(T.SIZES)


def overlap(a, b) -> bool:
  return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def inside(r, z) -> bool:
  return r[0] >= z[0] and r[1] >= z[1] and r[0] + r[2] <= z[0] + z[2] and r[1] + r[3] <= z[1] + z[3]


def cells(col, row, size):
  w, h = T.SIZES[size]
  return {(c, r) for c in range(col, col + w) for r in range(row, row + h)}


def check_grid(errors):
  rects = [T.cell_rect(c, r) for c in range(T.COLS) for r in range(T.ROWS)]
  errors += [f"T1 cells overlap {a} {b}" for a, b in itertools.combinations(rects, 2) if overlap(a, b)]
  if T.cell_rect(1, 0)[0] - (T.cell_rect(0, 0)[0] + T.CELL) != T.GAP or T.cell_rect(0, 1)[1] - (T.cell_rect(0, 0)[1] + T.CELL) != T.GAP:
    errors.append("T1 gap")
  x, y, w, h = T.size_rect(0, 0, (T.COLS, T.ROWS))
  if not inside((x, y, w, h), (0, 0, *T.SCREEN)) or abs(x - (T.SCREEN[0] - x - w)) > 1 or abs(y - (T.SCREEN[1] - y - h)) > 1:
    errors.append(f"T1 grid {(x, y, w, h)} not centered on screen")
  for c, r in itertools.product(range(T.COLS), range(T.ROWS)):
    x, y, w, h = T.cell_rect(c, r)
    if T.cell_at(x + w / 2, y + h / 2) != (c, r):
      errors.append(f"T10 cell ({c},{r}) center maps to {T.cell_at(x + w / 2, y + h / 2)}")


def check_view(errors):
  bx, by, bw, bh = T.DRIVE_CELLS
  area = T.size_rect(bx, by, (bw, bh))
  vx, vy, vw, vh = T.VIEW
  if not inside(T.VIEW, area):
    errors.append(f"T6 VIEW {T.VIEW} outside drive cells {area}")
  if abs(vw / vh - 536 / 240) > 0.01 * 536 / 240:
    errors.append(f"T6 VIEW aspect {vw / vh:.3f}")
  if abs((vx - area[0]) - (area[0] + area[2] - vx - vw)) > 1 or abs((vy - area[1]) - (area[1] + area[3] - vy - vh)) > 1:
    errors.append("T6 VIEW not centered in its cells")
  for c, r in itertools.product(range(T.COLS), range(T.ROWS)):
    if overlap(T.cell_rect(c, r), T.VIEW) and (c, r) not in T.blocked(True):
      errors.append(f"T6 VIEW overlaps free cell ({c},{r})")
  free = T.COLS * T.ROWS - len(T.blocked(True))
  if free != 14 or T.blocked(False):
    errors.append(f"T6 onroad free cells {free}, offroad blocked {T.blocked(False)}")


def first_fit_ok(errors, items, out, started, tag):
  """Replays first-fit and compares; also checks overlaps, bounds and sizes."""
  taken = set(T.blocked(started))
  for tid, saved, sizes in items:
    tries = [saved] if not started else [s for s in sorted(sizes, key=lambda s: -T.area(s)) if T.area(s) <= T.area(saved)]
    want = None
    for size in tries:
      w, h = T.SIZES[size]
      pos = next(((c, r) for c in range(T.COLS - w + 1) for r in range(T.ROWS - h + 1) if not cells(c, r, size) & taken), None)
      if pos is not None:
        want = (*pos, size)
        break
    got = out.get(tid)
    if got != want:
      errors.append(f"T4 {tag} {tid}: placed {got}, first fit {want}")
      return
    if got is not None:
      if not cells(*got) <= {(c, r) for c in range(T.COLS) for r in range(T.ROWS)}:
        errors.append(f"T3 {tag} {tid} outside the grid {got}")
      if cells(*got) & T.blocked(started):
        errors.append(f"T3 {tag} {tid} on a drive view cell {got}")
      if cells(*got) & (taken - T.blocked(started)):
        errors.append(f"T2 {tag} {tid} overlaps {got}")
      if got[2] not in sizes or (not started and got[2] != saved) or T.area(got[2]) > T.area(saved):
        errors.append(f"T5 {tag} {tid} size {got[2]} saved {saved} sizes {sizes}")
      taken |= cells(*got)


def check_place(errors):
  rng = random.Random(4)
  for n in range(300):
    items = []
    for i in range(rng.randint(0, 20)):
      sizes = tuple(rng.sample(ALL, rng.randint(1, len(ALL))))
      items.append((f"t{i}", rng.choice(sizes), sizes))
    for started in (False, True):
      out = T.place(items, started)
      first_fit_ok(errors, items, out, started, f"n={n} started={started}")
      if T.place(list(items), started) != out:
        errors.append("T4 placement not deterministic")
  onroad = T.place([(f"s{i}", "small", ("small",)) for i in range(20)], True)
  if len(onroad) != 14:
    errors.append(f"T6 {len(onroad)} small tiles onroad, expected 14")


def check_show(errors):
  for show, started in itertools.product(("always", "onroad", "offroad"), (False, True)):
    spec = T.TileSpec("x", "X", show=show)
    if T.shows(spec, started) != (show == "always" or (show == "onroad") == started):
      errors.append(f"T7 show={show} started={started}")


def check_spec(errors):
  for bad in ({"sizes": ()}, {"sizes": ("huge",)}, {"show": "never"}, {"hz": 0}):
    try:
      T.TileSpec("bad", "Bad", **bad)
      errors.append(f"T12 accepted {bad}")
    except ValueError:
      pass


def specs():
  return [T.TileSpec("a", "A", sizes=("medium", "small"), order=1), T.TileSpec("b", "B", order=2),
          T.TileSpec("c", "C", sizes=("wide", "medium", "small"), order=2), T.TileSpec("d", "D", order=0)]


def check_layout(errors):
  sp = specs()
  default = T.arrange(sp, None)
  if default != ([("d", "small"), ("a", "medium"), ("b", "small"), ("c", "wide")], []):
    errors.append(f"T8 defaults {default}")
  for garbage in ("x", 5, [1], {"tiles": "x"}, {"tiles": [[1, 2], ["a"]], "hidden": 3}):
    if T.arrange(sp, garbage) != default:
      errors.append(f"T8 garbage {garbage!r} gives {T.arrange(sp, garbage)}")
  saved = {"tiles": [["c", "small"], ["zz", "small"], ["a", "large"], ["c", "wide"]], "hidden": ["b", "zz"]}
  pinned, hidden = T.arrange(sp, saved)
  if pinned != [("c", "small"), ("a", "medium"), ("d", "small")] or hidden != ["b"]:
    errors.append(f"T8 load {pinned} {hidden}")
  if T.arrange(sp, json.loads(json.dumps(T.saved(pinned, hidden)))) != (pinned, hidden):
    errors.append("T8 save/load does not round trip")


def check_edit(errors):
  sizes = {s.id: s.sizes for s in specs()}
  pinned, hidden = [("a", "medium"), ("b", "small"), ("c", "wide")], []
  seen = []
  p = pinned
  for _ in range(4):
    p = T.resize(p, "c", sizes["c"])
    seen.append(dict(p)["c"])
  if seen != ["medium", "small", "wide", "medium"] or [i for i, _ in p] != ["a", "b", "c"]:
    errors.append(f"T9 resize cycle {seen}")
  p, h = T.unpin(pinned, hidden, "b")
  if p != [("a", "medium"), ("c", "wide")] or h != ["b"]:
    errors.append(f"T9 unpin {p} {h}")
  p, h = T.pin(p, h, "b", sizes["b"])
  if p != [("a", "medium"), ("c", "wide"), ("b", "small")] or h:
    errors.append(f"T9 pin {p} {h}")
  items = [(i, s, sizes[i]) for i, s in pinned]
  placed = T.place(items, False)  # a (0,0) medium, b (0,2) small, c (1,2) wide
  if T.move(pinned, placed, "c", (0, 3)) != [("a", "medium"), ("b", "small"), ("c", "wide")]:
    errors.append(f"T9 move c to (0,3): {T.move(pinned, placed, 'c', (0, 3))}")
  if T.move(pinned, placed, "c", (0, 0)) != [("c", "wide"), ("a", "medium"), ("b", "small")]:
    errors.append(f"T9 move c to (0,0): {T.move(pinned, placed, 'c', (0, 0))}")
  if T.move(pinned, placed, "a", (7, 3)) != [("b", "small"), ("c", "wide"), ("a", "medium")]:
    errors.append(f"T9 move a to the end: {T.move(pinned, placed, 'a', (7, 3))}")
  if T.move(pinned, placed, "b", (0, 2)) != pinned or T.move(pinned, placed, "a", (1, 1)) != pinned:
    errors.append("T9 dropping a tile on its own cells reorders")


def check_hits(errors):
  placed = T.place([("a", "medium", ("medium",)), ("b", "small", ("small",))], False)
  ax, ay, aw, ah = T.tile_rect(placed["a"])
  if T.hit(placed, ax + aw + T.GAP / 2, ay + 10) is not None or T.hit(placed, ax + 10, ay + 10) != "a":
    errors.append("T10 hit in a gap or miss inside a tile")
  for size in ALL:
    r = T.size_rect(0, 0, T.SIZES[size])
    buttons = T.corner_buttons(r)
    for name, (cx, cy, rad) in buttons.items():
      if not inside((cx - rad, cy - rad, 2 * rad, 2 * rad), r):
        errors.append(f"T10 {name} button leaves a {size} tile")
    (ux, uy, ur), (sx, sy, sr) = buttons["unpin"], buttons["resize"]
    if (ux - sx) ** 2 + (uy - sy) ** 2 < (ur + sr) ** 2:
      errors.append(f"T10 corner buttons overlap on a {size} tile")
  if T.add_cell(placed, False) != (0, 3) or T.add_cell(T.place([("x", "large", ("large",)), ("y", "large", ("large",))], False), False) is not None:
    errors.append("T14 add cell")
  pinned = [("a", "medium"), ("big", "large"), ("big2", "large"), ("big3", "large")]
  items = [(i, s, (s,)) for i, s in pinned]
  if T.addable(pinned, ["h"], T.place(items, False)) != ["h", "big2", "big3"]:
    errors.append(f"T14 addable {T.addable(pinned, ['h'], T.place(items, False))}")


def check_gesture(errors):
  g = T.Gesture()
  if g.press(0, 0, 0.0) or g.release(5, 5, 0.2) != "tap":
    errors.append("T11 short press is not a tap")
  g = T.Gesture()
  g.press(0, 0, 0.0)
  longs = [g.tick(t / 10) for t in range(20)]
  if longs.count("long") != 1 or longs.index("long") != round(T.LONG_PRESS * 10) or g.release(0, 0, 2.0) is not None:
    errors.append(f"T11 long press {longs}")
  g = T.Gesture()
  g.press(0, 0, 0.0)
  events = [g.move(i * 10, 0, i / 100) for i in range(10)] + [g.tick(1.0)]
  if events.count("drag") != 1 or "long" in events or g.release(90, 0, 1.0) != "drop":
    errors.append(f"T11 drag {events}")
  g = T.Gesture()
  if g.release(0, 0, 0.0) is not None or g.tick(5.0) is not None:
    errors.append("T11 release or tick without press")


def check_poll(errors):
  p = T.Poll(10)
  calls = [t for t in range(100) if p.due(t / 100)]  # 1 s at 100 fps
  if len(calls) != 10:
    errors.append(f"T15 polled {len(calls)} times in 1 s at hz=10")
  p = T.Poll(10)
  seq = [p.changed(s, k) for s, k in (((1, "a"), "small"), ((1, "a"), "small"), ((2, "a"), "small"), ((2, "a"), "medium"), ((2, "a"), "medium"))]
  if seq != [True, False, True, True, False]:
    errors.append(f"T15 redraws {seq}")
  p.invalidate()
  if not p.changed((2, "a"), "medium"):
    errors.append("T15 no redraw after invalidate")


def ascii_strings(path: Path):
  tree = ast.parse(path.read_text())
  docs = {id(n.body[0].value) for n in ast.walk(tree) if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef))
          and n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
  for node in ast.walk(tree):
    if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs and not node.value.isascii():
      yield node.lineno, node.value


def check_text(errors):
  pkg = ROOT / "openpilot/tesla"
  for path in sorted(list((pkg / "ui").rglob("*.py")) + list((pkg / "plugins").glob("*/ui.py"))):
    for line, text in ascii_strings(path):
      errors.append(f"T13 {path.relative_to(ROOT)}:{line} non-ASCII {text!r}")
  for path in sorted((pkg / "plugins").glob("*/plugin.json")):
    m = json.loads(path.read_text())
    for text in [m.get("name", ""), m.get("description", "")] + [s.get("label", "") for s in m.get("settings", [])]:
      if not text.isascii():
        errors.append(f"T13 {path.relative_to(ROOT)} non-ASCII {text!r}")


def main() -> int:
  errors: list[str] = []
  for check in (check_grid, check_view, check_place, check_show, check_spec, check_layout, check_edit, check_hits, check_gesture,
                check_poll, check_text):
    try:
      check(errors)
    except Exception as e:
      errors.append(f"{check.__name__} raised {e!r}")
  print(json.dumps({"view": T.VIEW, "origin": T.ORIGIN, "errors": errors}, indent=1))
  return 1 if errors else 0


if __name__ == "__main__":
  sys.exit(main())
