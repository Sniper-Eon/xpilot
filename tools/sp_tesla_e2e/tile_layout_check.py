#!/usr/bin/env python3
"""Big-screen tile check (UI v4, XPILOT.md §9): the pyray-free layout model in openpilot/tesla/ui/tiles.py, plus the text the
tile UI draws. Rendering and real touches are checked on the device by tools/sp_tesla_e2e/big_screen_e2e.py.

Failure cases listed before implementation:
- T1  grid cells overlap, the gap is not GAP px, or the grid leaves the screen / is not centered
- T2  two placed tiles overlap
- T3  a tile is placed outside the grid or on a cell the drive view blocks
- T4  a tile is left out while a position (in first-fit scan order) still fits it, or is placed after a free position that
      fits it (placement is not first-fit, or depends on anything but the list); a tile with a valid fixed position is not
      placed there, or a fixed position that is off the grid, on a drive view cell or on an earlier tile is not ignored
- T16 onroad the free cells are not scanned row by row from both edges inward (left and right columns fill alternately);
      offroad not column by column
- T5  offroad a tile is placed at another size than its saved size; onroad at a larger size than saved, or a size it does
      not support
- T6  the drive VIEW leaves the blocked cells, is not 536:240, is not centered in them, or onroad free cells are not 14
- T7  offroad-only tiles show onroad or onroad-only tiles show offroad
- T8  loading a saved layout: garbage gives no defaults, unknown ids, unsupported sizes or bad positions survive, an id
      appears twice, new tiles are not appended in (order, id) order at their default size, hidden tiles show, the park
      and drive layouts are not kept apart, the v1 format ({"tiles": [[id, size]]}) is not read as the park layout, or
      save/load does not round-trip
- T9  edit ops: resize does not cycle through the tile's sizes or drops the position, unpin/pin do not move between pinned
      and hidden, a drop does not fix the tile at the drop cell (pulled back inside the grid), does not free other fixed
      tiles it now overlaps, moves a tile onto the drive view, or reorders the list
- T17 edit bar: Park, Drive and Done buttons overlap each other or leave the screen; editing the park layout they cover a
      tile while a free cell other than the "+" cell exists (they go into the last free cell), or cover the "+" cell;
      editing the drive layout they are not inside the drive view
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
  """Independent replay: fixed tiles first, then first fit in scan order; also checks overlaps, bounds and sizes."""
  grid = {(c, r) for c in range(T.COLS) for r in range(T.ROWS)}
  taken = set(T.blocked(started))
  want = {}

  def tries(saved, sizes):
    return [saved] if not started else [s for s in sorted(sizes, key=lambda s: -T.area(s)) if T.area(s) <= T.area(saved)]
  flowing = []
  for tid, saved, sizes, anchor in items:
    got = None
    if anchor is not None:
      got = next(((*anchor, s) for s in tries(saved, sizes) if cells(*anchor, s) <= grid and not cells(*anchor, s) & taken), None)
    if got is None:
      flowing.append((tid, saved, sizes))
    else:
      want[tid] = got
      taken |= cells(*got)
  order = scan_order(started)
  for tid, saved, sizes in flowing:
    for size in tries(saved, sizes):
      pos = next((p for p in order if cells(*p, size) <= grid and not cells(*p, size) & taken), None)
      if pos is not None:
        want[tid] = (*pos, size)
        taken |= cells(*pos, size)
        break
  if out != want:
    errors.append(f"T4 {tag}: placed {out}, expected {want}")
    return
  for tid, saved, sizes, _ in items:
    got = out.get(tid)
    if got is not None and (got[2] not in sizes or (not started and got[2] != saved) or T.area(got[2]) > T.area(saved)):
      errors.append(f"T5 {tag} {tid} size {got[2]} saved {saved} sizes {sizes}")
  used = [cells(*p) for p in out.values()]
  if any(a & b for a, b in itertools.combinations(used, 2)):
    errors.append(f"T2 {tag} overlap")
  if any(u & T.blocked(started) or not u <= grid for u in used):
    errors.append(f"T3 {tag} off grid or on the drive view")


def scan_order(started):
  if not started:
    return [(c, r) for c in range(T.COLS) for r in range(T.ROWS)]
  edges = [c for pair in zip(range(T.COLS // 2), range(T.COLS - 1, T.COLS // 2 - 1, -1)) for c in pair]  # 0,7,1,6,...
  return [(c, r) for r in range(T.ROWS) for c in edges]


def check_place(errors):
  rng = random.Random(4)
  for n in range(400):
    items = []
    for i in range(rng.randint(0, 20)):
      sizes = tuple(rng.sample(ALL, rng.randint(1, len(ALL))))
      anchor = (rng.randint(-1, T.COLS), rng.randint(-1, T.ROWS)) if rng.random() < 0.4 else None
      items.append((f"t{i}", rng.choice(sizes), sizes, anchor))
    for started in (False, True):
      out = T.place(items, started)
      first_fit_ok(errors, items, out, started, f"n={n} started={started}")
      if T.place(list(items), started) != out:
        errors.append("T4 placement not deterministic")
  onroad = T.place([(f"s{i}", "small", ("small",), None) for i in range(20)], True)
  if len(onroad) != 14:
    errors.append(f"T6 {len(onroad)} small tiles onroad, expected 14")
  if [onroad[f"s{i}"][:2] for i in range(5)] != [(0, 0), (7, 0), (0, 1), (7, 1), (0, 2)]:
    errors.append(f"T16 onroad fill order {[onroad[f's{i}'][:2] for i in range(5)]}")
  park = T.place([(f"s{i}", "small", ("small",), None) for i in range(5)], False)
  if [park[f"s{i}"][:2] for i in range(5)] != [(0, 0), (0, 1), (0, 2), (0, 3), (1, 0)]:
    errors.append(f"T16 offroad fill order {[park[f's{i}'][:2] for i in range(5)]}")
  fixed = T.place([("a", "small", ("small",), None), ("b", "medium", ("medium",), (6, 2)), ("c", "small", ("small",), (6, 2))], False)
  if fixed.get("b") != (6, 2, "medium") or fixed.get("a") != (0, 0, "small") or fixed.get("c") != (0, 1, "small"):
    errors.append(f"T4 fixed positions {fixed}")


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
  default = T.arrange(sp, None, "park")
  if default != ([("d", "small", None), ("a", "medium", None), ("b", "small", None), ("c", "wide", None)], []):
    errors.append(f"T8 defaults {default}")
  for garbage in ("x", 5, [1], {"park": "x"}, {"park": {"tiles": [[1, 2], ["a"]], "hidden": 3}}, {"tiles": "x"}):
    if T.arrange(sp, garbage, "park") != default:
      errors.append(f"T8 garbage {garbage!r} gives {T.arrange(sp, garbage, 'park')}")
  saved = {"park": {"tiles": [["c", "small", 3, 1], ["zz", "small", 0, 0], ["a", "large", None, None], ["c", "wide", 0, 0], ["d", "small", "x", 2]],
                    "hidden": ["b", "zz"]},
           "drive": {"tiles": [["b", "medium", 7, 3]], "hidden": []}}
  pinned, hidden = T.arrange(sp, saved, "park")
  if pinned != [("c", "small", (3, 1)), ("a", "medium", None), ("d", "small", None)] or hidden != ["b"]:
    errors.append(f"T8 load {pinned} {hidden}")
  drive = T.arrange(sp, saved, "drive")
  if drive != ([("b", "medium", (7, 3)), ("d", "small", None), ("a", "medium", None), ("c", "wide", None)], []):
    errors.append(f"T8 drive layout {drive}")
  if T.arrange(sp, {"tiles": [["c", "small"]], "hidden": ["b"]}, "park") != ([("c", "small", None), ("d", "small", None), ("a", "medium", None)], ["b"]):
    errors.append(f"T8 v1 format {T.arrange(sp, {'tiles': [['c', 'small']], 'hidden': ['b']}, 'park')}")
  if T.arrange(sp, {"tiles": [["c", "small"]]}, "drive") != default:
    errors.append("T8 v1 format leaks into the drive layout")
  both = {"park": T.saved(pinned, hidden), "drive": T.saved(*drive)}
  if T.arrange(sp, json.loads(json.dumps(both)), "park") != (pinned, hidden) or T.arrange(sp, json.loads(json.dumps(both)), "drive") != drive:
    errors.append("T8 save/load does not round trip")


def check_edit(errors):
  sizes = {s.id: s.sizes for s in specs()}
  pinned, hidden = [("a", "medium", None), ("b", "small", None), ("c", "wide", (4, 0))], []
  seen = []
  p = pinned
  for _ in range(4):
    p = T.resize(p, "c", sizes["c"])
    seen.append([e for e in p if e[0] == "c"][0][1:])
  if seen != [("medium", (4, 0)), ("small", (4, 0)), ("wide", (4, 0)), ("medium", (4, 0))] or [e[0] for e in p] != ["a", "b", "c"]:
    errors.append(f"T9 resize cycle {seen}")
  p, h = T.unpin(pinned, hidden, "b")
  if p != [("a", "medium", None), ("c", "wide", (4, 0))] or h != ["b"]:
    errors.append(f"T9 unpin {p} {h}")
  p, h = T.pin(p, h, "b", sizes["b"])
  if p != [("a", "medium", None), ("c", "wide", (4, 0)), ("b", "small", None)] or h:
    errors.append(f"T9 pin {p} {h}")
  placed = T.place([(i, s, sizes[i], a) for i, s, a in pinned], False)  # a (0,0) medium, b (0,2) small, c (4,0) wide
  got = T.move(pinned, placed, "a", (7, 3), False)
  if got != [("a", "medium", (6, 2)), ("b", "small", None), ("c", "wide", (4, 0))]:
    errors.append(f"T9 drop a at (7,3): {got}")
  got = T.move(pinned, placed, "b", (5, 1), False)
  if got != [("a", "medium", None), ("b", "small", (5, 1)), ("c", "wide", None)]:
    errors.append(f"T9 drop b on fixed c: {got}")
  if T.move(pinned, placed, "b", (2, 1), True) != pinned:
    errors.append("T9 drop on the drive view changed the layout")


def check_hits(errors):
  placed = T.place([("a", "medium", ("medium",), None), ("b", "small", ("small",), None)], False)
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
  if T.add_cell(placed, False) != (0, 3) or T.add_cell(T.place([("x", "large", ("large",), None), ("y", "large", ("large",), None)], False), False) is not None:
    errors.append("T14 add cell")
  pinned = [("a", "medium", None), ("big", "large", None), ("big2", "large", None), ("big3", "large", None)]
  items = [(i, s, (s,), a) for i, s, a in pinned]
  if T.addable(pinned, ["h"], T.place(items, False)) != ["h", "big2", "big3"]:
    errors.append(f"T14 addable {T.addable(pinned, ['h'], T.place(items, False))}")


def check_bar(errors):
  rng = random.Random(7)
  for n in range(200):
    items = [(f"t{i}", rng.choice(ALL), ALL, None) for i in range(rng.randint(0, 14))]
    for started in (False, True):
      placed = T.place(items, started)
      b = T.bar_buttons(placed, started)
      rects = list(b.values())
      if set(b) != {"park", "drive", "done"} or any(overlap(x, y) for x, y in itertools.combinations(rects, 2)):
        errors.append(f"T17 bar buttons {b}")
        return
      if any(not inside(r, (0, 0, *T.SCREEN)) for r in rects):
        errors.append(f"T17 bar off screen {b}")
      if started:
        if any(not inside(r, T.VIEW) for r in rects):
          errors.append(f"T17 drive bar outside the view {b}")
        continue
      taken = set().union(*(cells(*p) for p in placed.values())) if placed else set()
      free = [c for c in T.scan(False) if c not in taken]
      add = T.add_cell(placed, False)
      if len(free) > 1:
        tile_rects = [T.tile_rect(p) for p in placed.values()] + [T.cell_rect(*add)]
        if any(overlap(r, t) for r in rects for t in tile_rects):
          errors.append(f"T17 n={n} bar covers a tile or the + cell with {len(free)} free cells: {b}")


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
  for check in (check_grid, check_view, check_place, check_show, check_spec, check_layout, check_edit, check_hits, check_bar, check_gesture,
                check_poll, check_text):
    try:
      check(errors)
    except Exception as e:
      errors.append(f"{check.__name__} raised {e!r}")
  print(json.dumps({"view": T.VIEW, "origin": T.ORIGIN, "errors": errors}, indent=1))
  return 1 if errors else 0


if __name__ == "__main__":
  sys.exit(main())
