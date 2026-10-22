#!/usr/bin/env python3
"""Big-screen slot placement check for the zone model (stdlib only; runs on hosts without pyray).

Failure cases listed before implementation:
- Z1 two cards overlap each other
- Z2 a card reaches outside its own zone (and so into the center view or another zone)
- Z3 placement depends on input order instead of (order, id)
- Z4 a slot is hidden while its zone ("auto": any zone) still has room for it
- Z5 onroad-only slots show offroad, or offroad-only slots show onroad
- Z6 an oversize slot (more units than a zone holds) is placed, or breaks placement of the others
- Z7 cards touch each other or their zone edge (no inner padding), or the zones overlap the center view / leave the screen
- Z8 a bad zone name or units < 1 is accepted silently
- Z9 "auto" slots fill zones in another order than left, right, bottom, top
"""
import itertools
import json
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from openpilot.tesla.ui.grid import SCREEN, UNITS, VIEW, ZONES, SlotSpec, place  # noqa: E402

AUTO_ORDER = ("left", "right", "bottom", "top")
PAD = 12  # required inset of every card (spec), independent of grid.PAD


def overlap(a, b) -> bool:
  return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def grow(r, d):
  return (r[0] - d, r[1] - d, r[2] + 2 * d, r[3] + 2 * d)


def inside(r, z) -> bool:
  return r[0] >= z[0] and r[1] >= z[1] and r[0] + r[2] <= z[0] + z[2] and r[1] + r[3] <= z[1] + z[3]


def zone_of(r) -> str | None:
  return next((name for name, z in ZONES.items() if inside(r, z)), None)


def used_units(out, zone) -> int:
  """Units taken in a zone, recovered from the placed (padded) rects."""
  z = ZONES[zone]
  vertical = zone in ("left", "right")
  unit = (z[3] if vertical else z[2]) / UNITS
  return sum(round(((r[3] if vertical else r[2]) + 2 * PAD) / unit) for r in out.values() if zone_of(r) == zone)


def main() -> int:
  errors = []
  for a, b in itertools.combinations(list(ZONES.values()) + [VIEW], 2):
    if overlap(a, b):
      errors.append(f"Z7 zones overlap {a} {b}")
  errors += [f"Z7 zone off screen {z}" for z in list(ZONES.values()) + [VIEW] if not inside(z, (0, 0, *SCREEN))]

  specs = [SlotSpec("speed", "Speed", "left", 2, order=10), SlotSpec("car", "Car", "bottom", 1, order=50), SlotSpec("map", "Map", "bottom", 2, order=60),
           SlotSpec("lead", "Lead", "right", 1, order=30), SlotSpec("limit", "Limit", "right", 1, order=20),
           SlotSpec("bms", "Battery", "auto", 2, show="onroad"), SlotSpec("long", "Long", "left", 3, show="offroad", order=120),
           SlotSpec("huge", "Huge", "auto", UNITS + 1), SlotSpec("a1", "A1", "auto", 3, order=200), SlotSpec("a2", "A2", "auto", 4, order=210),
           SlotSpec("a3", "A3", "auto", 4, order=210), SlotSpec("a4", "A4", "auto", 1, order=230), SlotSpec("t1", "T1", "top", 3, order=240),
           SlotSpec("t2", "T2", "top", 2, order=240)]
  cases = 0
  for n, started in itertools.product(range(len(specs) + 1), (True, False)):
    subset = specs[:n]
    out = place(subset, started)
    cases += 1
    shown = [s for s in subset if s.show == "always" or (s.show == "onroad") == started]
    by_id = {s.id: s for s in subset}
    errors += [f"Z1 {a} {b}" for (a, ra), (b, rb) in itertools.combinations(out.items(), 2) if overlap(ra, rb)]
    errors += [f"Z7 {a} {b} closer than {2 * PAD} px" for (a, ra), (b, rb) in itertools.combinations(out.items(), 2)
               if overlap(grow(ra, PAD - 1), grow(rb, PAD - 1))]
    for k, r in out.items():
      zone = zone_of(r)
      if zone is None or (by_id[k].zone != "auto" and zone != by_id[k].zone):
        errors.append(f"Z2 {k} {r} zone={zone}")
      elif not inside(grow(r, PAD), ZONES[zone]):
        errors.append(f"Z7 {k} touches its zone edge {r}")
    shuffled = subset[:]
    random.Random(n).shuffle(shuffled)
    if place(shuffled, started) != out or place(subset[::-1], started) != out:
      errors.append(f"Z3 n={n} started={started}")
    for s in shown:
      if s.id in out or s.units > UNITS:
        continue
      room = [z for z in (AUTO_ORDER if s.zone == "auto" else (s.zone,)) if used_units(out, z) + s.units <= UNITS]
      if room:
        errors.append(f"Z4 {s.id} hidden while {room} has room")
    errors += [f"Z5 {k} started={started}" for k in out if k not in {s.id for s in shown}]
    errors += [f"Z6 {k} oversize placed" for k in out if by_id[k].units > UNITS]
  if place([SlotSpec("huge", "Huge", "left", UNITS + 1)], True):
    errors.append("Z6 oversize fixed-zone slot placed")
  ties = [SlotSpec(f"x{i}", "X", "auto", UNITS) for i in range(5)]  # equal order: id decides
  autos = place(ties, True)
  if place(ties[::-1], True) != autos:
    errors.append("Z3 equal-order slots placed by input order, not id")
  if [zone_of(autos.get(f"x{i}", (-1, -1, 0, 0))) for i in range(5)] != [*AUTO_ORDER, None]:
    errors.append(f"Z9 auto zone order {autos}")
  for bad in ({"zone": "middle"}, {"units": 0}):
    try:
      SlotSpec("bad", "Bad", **bad)
      errors.append(f"Z8 accepted {bad}")
    except ValueError:
      pass
  print(json.dumps({"cases": cases, "placed_onroad_all": place(specs, True), "errors": errors}, indent=1))
  return 1 if errors else 0


if __name__ == "__main__":
  sys.exit(main())
