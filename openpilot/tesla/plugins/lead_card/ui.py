"""Lead card (right column): distance and relative speed of the lead car from radarState.leadOne."""
from openpilot.common.constants import CV
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.tesla.ui.grid import SlotSpec
from openpilot.tesla.ui.slot import Slot


class LeadCardSlot(Slot):
  SPEC = SlotSpec("lead_card", "Lead", zone="right", units=1, hz=5, order=30)

  def __init__(self):
    super().__init__()
    self._value, self._sub = "–", ""

  def update(self, sm) -> None:
    lead = sm['radarState'].leadOne
    if not sm.alive['radarState'] or not lead.status:
      self._value, self._sub = "–", "no lead"
      return
    metric = ui_state.is_metric
    self._value = f"{lead.dRel:.0f}"
    self._sub = f"{lead.vRel * (CV.MS_TO_KPH if metric else CV.MS_TO_MPH):+.0f} {'km/h' if metric else 'mph'}"

  def _render(self, rect):
    self.draw_value(rect, self._value, "m" if self._value != "–" else "", self._sub)
