"""Speed limit card (right column): the limit sunnypilot resolved (longitudinalPlanSP.speedLimit.resolver)."""
from openpilot.common.constants import CV
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.tesla.ui.grid import SlotSpec
from openpilot.tesla.ui.slot import Slot


class SpeedLimitCardSlot(Slot):
  SPEC = SlotSpec("speed_limit_card", "Speed Limit", zone="right", units=1, hz=2, order=20)

  def __init__(self):
    super().__init__()
    self._value, self._unit = "-", ""

  def update(self, sm) -> None:
    limit = sm['longitudinalPlanSP'].speedLimit.resolver.speedLimit if sm.alive['longitudinalPlanSP'] else 0.0
    metric = ui_state.is_metric
    self._value = f"{limit * (CV.MS_TO_KPH if metric else CV.MS_TO_MPH):.0f}" if limit > 0 else "-"
    self._unit = ("km/h" if metric else "mph") if limit > 0 else ""

  def _render(self, rect):
    self.draw_value(rect, self._value, self._unit)
