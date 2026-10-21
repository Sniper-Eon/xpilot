"""Big-screen host for C3/C3X/C3XL: the mici UI in a movable window, a fixed alert banner on top.

The window rect lives in Params "TeslaVideoWindow" as {"x", "y", "scale"} in screen pixels; the default is
mici size (536x240) centered. Slots will fill the rest of the screen.
"""
from contextlib import contextmanager
import math

import pyray as rl

from openpilot.common.hardware import HARDWARE
from openpilot.common.params import Params
from openpilot.selfdrive.ui.mici.onroad.alert_renderer import AlertRenderer
from openpilot.sunnypilot.hardware.profile import HardwareProfile, get_hardware_profile

SCREEN = (2160, 1080)
MICI = (536, 240)
BANNER_SCALE = 2  # the mici alert layout at 2x: 1080x160 logical, full width and 320 px tall on screen


def is_big_screen() -> bool:
  return HARDWARE.get_device_type() in ("tici", "tizi") or get_hardware_profile() == HardwareProfile.C3XL


@contextmanager
def scaled(s: float):
  """Draw logical coordinates at s times size. gui_app patched scissor for its own texture scale, so swap it."""
  prev = rl.begin_scissor_mode
  rl.begin_scissor_mode = lambda x, y, w, h: rl._orig_begin_scissor_mode(int(x * s), int(y * s), int(math.ceil(w * s)), int(math.ceil(h * s)))
  rl.rl_push_matrix()
  rl.rl_scalef(s, s, 1.0)
  try:
    yield
  finally:
    rl.rl_pop_matrix()
    rl.begin_scissor_mode = prev


class BigScreenHost:
  size = SCREEN

  def __init__(self):
    w = Params().get("TeslaVideoWindow") or {}
    self._s = min(max(float(w.get("scale", 1.0)), 1.0), min(SCREEN[0] / MICI[0], SCREEN[1] / MICI[1]))
    width, height = MICI[0] * self._s, MICI[1] * self._s
    self._x = min(max(float(w.get("x", (SCREEN[0] - width) / 2)), 0.0), SCREEN[0] - width)
    self._y = min(max(float(w.get("y", (SCREEN[1] - height) / 2)), 0.0), SCREEN[1] - height)
    self._banner = AlertRenderer()

  def viewport(self) -> rl.Rectangle:
    return rl.Rectangle(self._x, self._y, MICI[0] * self._s, MICI[1] * self._s)

  def to_logical(self, x: float, y: float) -> tuple[float, float]:
    return (x - self._x) / self._s, (y - self._y) / self._s

  def render(self) -> None:
    # Alerts never shrink with the window: same renderer and timeout logic as mici, drawn across the top.
    with scaled(BANNER_SCALE):
      self._banner.render(rl.Rectangle(0, 0, SCREEN[0] / BANNER_SCALE, 160))
