"""Slot format and zone placement for the big-screen host. No pyray here, so it is checkable anywhere
(tools/sp_tesla_e2e/slot_layout_check.py).

Slot format: a module in openpilot/tesla/ui/slots/ (or a plugin's ui.py) defines a subclass of openpilot.tesla.ui.slot.Slot with
  SPEC = SlotSpec(id, title, zone="left"|"right"|"top"|"bottom"|"auto", units=1, services=(...), show=..., hz=5.0, order=100)
The host finds it at startup and places it in the zones around the onroad view; nothing else needs registering.

Onroad screen (2160x1080 px): left and right columns stack cards vertically (unit 270 px tall, 360 wide); the top and
bottom bands of the center column stack them horizontally (unit 360 px wide, 218 tall); the mici view sits in VIEW.
"""
from dataclasses import dataclass
from typing import Literal

SCREEN = (2160, 1080)
ZONES = {
  "left": (0, 0, 360, 1080),
  "right": (1800, 0, 360, 1080),
  "top": (360, 0, 1440, 218),
  "bottom": (360, 862, 1440, 218),
}
VIEW = (360, 218, 1440, 644)  # mici onroad view at 1440/536 scale
UNITS = 4  # units per zone
PAD = 12   # px inset of each card inside its units
AUTO_ORDER = ("left", "right", "bottom", "top")


@dataclass(frozen=True)
class SlotSpec:
  id: str                          # unique
  title: str
  zone: Literal["left", "right", "top", "bottom", "auto"] = "auto"
  units: int = 1                   # size along the zone (1..UNITS); larger slots are never shown
  services: tuple[str, ...] = ()   # every service update() reads; empty means it reads ui_state.sm
  show: Literal["always", "onroad", "offroad"] = "always"  # the host draws cards only onroad, so "offroad" slots stay hidden
  hz: float = 5.0                  # max redraw rate; other frames reuse the cached texture
  order: int = 100                 # placement priority, lower first

  def __post_init__(self):
    if self.zone not in ZONES and self.zone != "auto":
      raise ValueError(f"slot {self.id}: unknown zone {self.zone}")
    if self.units < 1:
      raise ValueError(f"slot {self.id}: units must be >= 1")


def place(specs: list[SlotSpec], started: bool) -> dict[str, tuple[int, int, int, int]]:
  """Visible slots in (order, id) order, each into its zone (or the first zone with room for "auto").
  Returns slot id -> (x, y, w, h) px, inset by PAD. Slots without room are left out."""
  used = dict.fromkeys(ZONES, 0)
  out = {}
  for spec in sorted(specs, key=lambda s: (s.order, s.id)):
    if spec.show != "always" and (spec.show == "onroad") != started:
      continue
    zone = next((z for z in (AUTO_ORDER if spec.zone == "auto" else (spec.zone,)) if used[z] + spec.units <= UNITS), None)
    if zone is None:
      continue
    x, y, w, h = ZONES[zone]
    if zone in ("left", "right"):
      unit = h // UNITS
      rect = (x, y + used[zone] * unit, w, spec.units * unit)
    else:
      unit = w // UNITS
      rect = (x + used[zone] * unit, y, spec.units * unit, h)
    used[zone] += spec.units
    out[spec.id] = (rect[0] + PAD, rect[1] + PAD, rect[2] - 2 * PAD, rect[3] - 2 * PAD)
  return out
