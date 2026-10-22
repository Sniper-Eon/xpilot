"""Map slot: speed limit, road name and next maneuver from the map interface
(liveMapDataSP from any map provider, navInstruction from any navigation provider)."""
from openpilot.common.constants import CV
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.tesla.ui.grid import SlotSpec
from openpilot.tesla.ui.slot import Slot


class MapSlot(Slot):
  SPEC = SlotSpec("map", "Map", zone="bottom", units=2, services=("liveMapDataSP", "navInstruction"), hz=2, order=60)

  def __init__(self):
    super().__init__()
    self._lines: list[str] = []

  def update(self, sm) -> None:
    lines = []
    if sm.alive['liveMapDataSP']:
      m = sm['liveMapDataSP']
      factor = CV.MS_TO_KPH if ui_state.is_metric else CV.MS_TO_MPH
      if m.speedLimitValid:
        lines.append(f"Limit {m.speedLimit * factor:.0f}")
      if m.roadName:
        lines.append(m.roadName[:32])
    if sm.alive['navInstruction'] and sm['navInstruction'].maneuverPrimaryText:
      nav = sm['navInstruction']
      lines.append(f"{nav.maneuverDistance:.0f} m {nav.maneuverPrimaryText}"[:32])
    self._lines = lines or ["No map data"]

  def _render(self, rect):
    self.draw_lines(rect, self._lines, size=36)
