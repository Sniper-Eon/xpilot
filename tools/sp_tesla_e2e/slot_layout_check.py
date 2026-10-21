#!/usr/bin/env python3
"""Big-screen slot placement check (stdlib only; runs on hosts without pyray).

Failure cases listed before implementation:
- L1 a slot overlaps the video window
- L2 two slots overlap each other
- L3 a slot reaches outside the 2160x1080 screen
- L4 placement depends on input order instead of (order, id)
- L5 a slot that fits somewhere is hidden while a free spot exists
- L6 onroad-only slots show offroad, or offroad-only slots show onroad
- L7 a window that covers the screen hides every slot without raising
"""
import itertools
import json
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from openpilot.tesla.ui.grid import CELL, COLS, ROWS, SlotSpec, place  # noqa: E402

W, H = COLS * CELL, ROWS * CELL


def overlap(a, b) -> bool:
  return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def free_spot(window, placed, cols, rows) -> bool:
  for r, c in itertools.product(range(ROWS - rows + 1), range(COLS - cols + 1)):
    rect = (c * CELL, r * CELL, cols * CELL, rows * CELL)
    if not overlap(rect, window) and not any(overlap(rect, p) for p in placed):
      return True
  return False


def main() -> int:
  specs = [SlotSpec("car", "Car", (2, 1)), SlotSpec("map", "Map", (3, 2), order=50), SlotSpec("bms", "Battery", (3, 2), show="onroad"),
           SlotSpec("long", "Long", (2, 2), show="offroad", order=120), SlotSpec("wide", "Wide", (6, 1), order=200)]
  windows = [((W - 536) / 2, (H - 240) / 2, 536, 240), (0, 0, 536, 240), (W - 1072, H - 480, 1072, 480), (300, 200, 1608, 720), (0, 0, W, H)]
  errors = []
  for window, started in itertools.product(windows, (True, False)):
    out = place(window, specs, started)
    shown = [s for s in specs if s.show == "always" or (s.show == "onroad") == started]
    rects = list(out.values())
    errors += [f"L1 {k} {window}" for k, r in out.items() if overlap(r, window)]
    errors += [f"L2 {a} {b} {window}" for (a, ra), (b, rb) in itertools.combinations(out.items(), 2) if overlap(ra, rb)]
    errors += [f"L3 {k} {r}" for k, r in out.items() if r[0] < 0 or r[1] < 0 or r[0] + r[2] > W or r[1] + r[3] > H]
    shuffled = specs[:]
    random.Random(0).shuffle(shuffled)
    if place(window, shuffled, started) != out:
      errors.append(f"L4 {window} {started}")
    errors += [f"L5 {s.id} {window}" for s in shown if s.id not in out and free_spot(window, rects, *s.cells)]
    errors += [f"L6 {k} started={started}" for k in out if k not in {s.id for s in shown}]
  if place((0, 0, W, H), specs, True) != {}:
    errors.append("L7 full-screen window still places slots")
  print(json.dumps({"windows": len(windows), "errors": errors}, indent=1))
  return 1 if errors else 0


if __name__ == "__main__":
  sys.exit(main())
