"""Car status slot: cluster speed, gear, blinkers and blind spots (validates carState-only slots)."""
from openpilot.common.constants import CV
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.tesla.ui.grid import SlotSpec
from openpilot.tesla.ui.slot import Slot


class CarSlot(Slot):
  SPEC = SlotSpec("car", "Car", cells=(2, 2), hz=10, order=10)

  def __init__(self):
    super().__init__()
    self._lines: list[str] = []

  def update(self, sm) -> None:
    cs = sm['carState']
    speed = cs.vEgoCluster * (CV.MS_TO_KPH if ui_state.is_metric else CV.MS_TO_MPH)
    blink = ("<" if cs.leftBlinker else " ") + (">" if cs.rightBlinker else " ")
    spots = ("L" if cs.leftBlindspot else "-") + ("R" if cs.rightBlindspot else "-")
    self._lines = [f"{speed:.0f} {'km/h' if ui_state.is_metric else 'mph'}", f"{str(cs.gearShifter)[:1].upper()}  {blink}  {spots}"]

  def _render(self, rect):
    self.draw_lines(rect, self._lines)
