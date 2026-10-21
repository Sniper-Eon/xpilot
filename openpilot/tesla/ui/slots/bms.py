"""Battery slot: passive Tesla BMS telemetry from the vehicle CAN bus (validates slots that own a raw CAN feed)."""
import time

from openpilot.cereal import messaging
from openpilot.sunnypilot.selfdrive.car.tesla.bms import BmsState, FRAME_LENGTHS
from openpilot.tesla.ui.grid import SlotSpec
from openpilot.tesla.ui.slot import Slot


class BmsSlot(Slot):
  SPEC = SlotSpec("bms", "Battery", cells=(3, 2), hz=2, order=30)  # reads ui_state.sm carState + its own can socket

  def __init__(self):
    super().__init__()
    self._state = BmsState()
    self._sock = messaging.sub_sock('can', timeout=0)
    self._lines: list[str] = []

  def update(self, sm) -> None:
    now = time.monotonic()
    for _ in range(400):  # bounded work per redraw; at 2 Hz this keeps up with the 100 Hz can service
      msg = messaging.recv_one_or_none(self._sock)
      if msg is None:
        break
      timestamp = msg.logMonoTime * 1e-9
      if msg.valid and 0 <= now - timestamp <= 3:
        for frame in msg.can:
          if frame.src == 1 and frame.address in FRAME_LENGTHS:
            self._state.update(frame.address, bytes(frame.dat), frame.src, timestamp)
    self._state.integrate(now, sm['carState'].vEgo if sm.alive['carState'] else None)
    snap = self._state.snapshot(now)
    soc, power, temp = snap['soc_display'] or snap['soc'], snap['power'], snap['temp_max']
    self._lines = [f"{soc:.0f} %" if soc is not None else "SoC --",
                   f"{power:.1f} kW" if power is not None else "Power --",
                   f"{temp:.0f} C max" if temp is not None else "Temp --"]

  def _render(self, rect):
    self.draw_lines(rect, self._lines, size=48)
