"""Tesla SCC-V: confirm turn entry and use the commanded curvature.

Keeps the official vision_controller.py unchanged; LongitudinalPlannerSP swaps
this controller in for Tesla only.
"""
from openpilot.sunnypilot.selfdrive.controls.lib.smart_cruise_control import MIN_V
from openpilot.sunnypilot.selfdrive.controls.lib.smart_cruise_control.vision_controller import (
  _ENTERING_PRED_LAT_ACC_TH, SmartCruiseControlVision, VisionState,
)

ENTERING_CONFIRMATION_FRAMES = 5  # 0.20 s of continuity at the 20 Hz model rate.


class TeslaSmartCruiseControlVision(SmartCruiseControlVision):
  def __init__(self):
    super().__init__()
    self.entering_prediction_frames = 0

  def _update_calculations(self, sm) -> None:
    super()._update_calculations(sm)
    if self.long_enabled:
      self.current_lat_acc = self.v_ego ** 2 * abs(sm['controlsState'].desiredCurvature)

  def _update_state_machine(self) -> tuple[bool, bool]:
    # The counter only runs while ENABLED would otherwise enter; every other path resets it.
    if (self.state == VisionState.enabled and self.long_enabled and self.enabled and not self.long_override
        and self.v_ego > MIN_V and self.max_pred_lat_acc >= _ENTERING_PRED_LAT_ACC_TH):
      self.entering_prediction_frames += 1
      if self.entering_prediction_frames < ENTERING_CONFIRMATION_FRAMES:
        return True, False
    self.entering_prediction_frames = 0
    return super()._update_state_machine()
