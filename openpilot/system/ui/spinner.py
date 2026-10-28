#!/usr/bin/env python3
import pyray as rl
import select
import sys

from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.lib.text_measure import measure_text_cached
from openpilot.system.ui.text import wrap_text
from openpilot.system.ui.widgets import Widget
from openpilot.tesla.ui.brand_layout import spinner_layout
from openpilot.tesla.ui.branding import draw_logo

# Constants
if gui_app.big_ui():
  PROGRESS_BAR_WIDTH = 1000
  PROGRESS_BAR_HEIGHT = 20
  TEXTURE_SIZE = 360
  WRAPPED_SPACING = 50
  CENTERED_SPACING = 150
else:
  PROGRESS_BAR_WIDTH = 268
  PROGRESS_BAR_HEIGHT = 10
  TEXTURE_SIZE = 140
  WRAPPED_SPACING = 10
  CENTERED_SPACING = 20
DEGREES_PER_SECOND = 360.0  # one full rotation per second
MARGIN_H = 100
FONT_SIZE = 96
LINE_HEIGHT = 104
DARKGRAY = (55, 55, 55, 255)


def clamp(value, min_value, max_value):
  return max(min(value, max_value), min_value)


class Spinner(Widget):
  def __init__(self):
    super().__init__()
    self._spinner_texture = gui_app.texture("images/spinner_track.png", TEXTURE_SIZE, TEXTURE_SIZE, alpha_premultiply=True)
    self._rotation = 0.0
    self._progress: int | None = None
    self._wrapped_lines: list[str] = []

  def set_text(self, text: str) -> None:
    if text.isdigit():
      self._progress = clamp(int(text), 0, 100)
      self._wrapped_lines = []
    else:
      self._progress = None
      self._wrapped_lines = wrap_text(text, spinner_layout(gui_app.width, gui_app.height)["font"], gui_app.width * 0.8)

  def _render(self, rect: rl.Rectangle):
    layout = spinner_layout(rect.width, rect.height, len(self._wrapped_lines))
    draw_logo(rl.Rectangle(rect.x + layout["logo"][0], rect.y + layout["logo"][1], *layout["logo"][2:]))
    x, y, w, h = layout["spinner"]
    self._rotation = (self._rotation + DEGREES_PER_SECOND * rl.get_frame_time()) % 360.0
    rl.draw_texture_pro(
      self._spinner_texture,
      rl.Rectangle(0, 0, self._spinner_texture.width, self._spinner_texture.height),
      rl.Rectangle(rect.x + x + w / 2, rect.y + y + h / 2, w, h),
      rl.Vector2(w / 2, h / 2),
      self._rotation,
      rl.WHITE,
    )
    x, y, w, h = layout["status"]
    if self._progress is not None:
      bar = rl.Rectangle(rect.x + x, rect.y + y, w, h)
      rl.draw_rectangle_rounded(bar, 1, 10, DARKGRAY)
      bar.width *= self._progress / 100.0
      rl.draw_rectangle_rounded(bar, 1, 10, rl.WHITE)
    elif self._wrapped_lines:
      size = layout["font"]
      step = h / len(self._wrapped_lines)
      for i, line in enumerate(self._wrapped_lines):
        measured = measure_text_cached(gui_app.font(), line, size)
        rl.draw_text_ex(gui_app.font(), line, rl.Vector2(rect.x + (rect.width - measured.x) / 2, rect.y + y + i * step), size, 0, rl.WHITE)


def _read_stdin():
  """Non-blocking read of available lines from stdin."""
  lines = []
  while True:
    rlist, _, _ = select.select([sys.stdin], [], [], 0.0)
    if not rlist:
      break
    line = sys.stdin.readline().strip()
    if line == "":
      break
    lines.append(line)
  return lines


def main():
  gui_app.init_window("Spinner")
  spinner = Spinner()
  for _ in gui_app.render():
    text_list = _read_stdin()
    if text_list:
      spinner.set_text(text_list[-1])

    spinner.render(rl.Rectangle(0, 0, gui_app.width, gui_app.height))


if __name__ == "__main__":
  main()
