"""Speed card (left column): ego speed as the car's cluster shows it, and the set speed."""
from openpilot.common.constants import CV
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.tesla.ui.grid import SlotSpec
from openpilot.tesla.ui.slot import Slot

SET_SPEED_NA = 255  # vCruiseCluster (km/h) when cruise is not set


class SpeedCardSlot(Slot):
  SPEC = SlotSpec("speed_card", "Speed", zone="left", units=2, hz=10, order=10)

  def __init__(self):
    super().__init__()
    self._value, self._unit, self._sub = "–", "", ""

  def update(self, sm) -> None:
    cs = sm['carState']
    metric = ui_state.is_metric
    self._value = f"{max(0.0, cs.vEgoCluster) * (CV.MS_TO_KPH if metric else CV.MS_TO_MPH):.0f}"
    self._unit = "km/h" if metric else "mph"
    v_cruise = cs.vCruiseCluster
    self._sub = f"SET {v_cruise * (1 if metric else CV.KPH_TO_MPH):.0f}" if 0 < v_cruise < SET_SPEED_NA else "SET –"

  def _render(self, rect):
    self.draw_value(rect, self._value, self._unit, self._sub)
