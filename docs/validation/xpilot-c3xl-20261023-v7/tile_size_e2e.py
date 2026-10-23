#!/usr/bin/env python3
"""Real-GPU tile-size screenshots for X-20261023-10.

Failure modes listed before implementation: wrong device, commit, service, or
offroad state; a requested tile or size is unavailable; a size is changed
without entering production edit mode and tapping its resize control; a tile
is missing from its screenshot; drawn text crosses a tile edge, overlaps other
text, uses less than 24 px, or is unexpectedly clipped with "..."; a screenshot
cannot be exported; or any tested parameter is not restored byte-for-byte.

Run with comma.service stopped because the production UI owns DRM exclusively.
The test uses the production BigScreenHost, edit gesture handler, tile classes,
fonts, and GPU renderer. It does not publish messages, send CAN, or change
vehicle/hardware settings.
"""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
import traceback

import pyray as rl

from openpilot.common.params import Params
from openpilot.selfdrive.ui.mici.layouts.main import MiciMainLayout
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import gui_app
from openpilot.tesla.ui import tile as tile_module
from openpilot.tesla.ui import tiles
from openpilot.tesla.ui.screen import BigScreenHost


TARGET = "cc129b8829c8fd6d170ef75d9857840cb25ed726"
TESTS = ("clock", "ip", "map", "car", "speed_card", "lead_card", "bms", "plugins", "tesla")
SIZES = ("small", "medium", "wide")
PATHS = {
  "layout": Path("/data/xpilot_plugins/.params/XpilotTileLayout"),
  "theme": Path("/data/xpilot_plugins/.params/XpilotTileTheme"),
  "bms": Path("/data/params/d/XpilotBms"),
  "car": Path("/data/params/d/CarPlatformBundle"),
}

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--tiles", default=",".join(TESTS))
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
selected = tuple(args.tiles.split(","))
assert selected and set(selected).issubset(TESTS)


def raw(path):
  return path.read_bytes() if path.exists() else None


def digest(value):
  return None if value is None else hashlib.sha256(value).hexdigest()


def restore(path, value):
  if value is None:
    path.unlink(missing_ok=True)
  else:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.xpilot-v7-", delete=False) as f:
      f.write(value)
      tmp = Path(f.name)
    tmp.replace(path)


def center(rect):
  x, y, w, h = rect
  return x + w / 2, y + h / 2


def overlaps(a, b):
  return a["x"] < b["x"] + b["width"] and b["x"] < a["x"] + a["width"] and \
         a["y"] < b["y"] + b["size"] and b["y"] < a["y"] + a["size"]


assert subprocess.check_output(["hostname"], text=True).strip() == "comma-9c13c9f5"
assert Path("/data/hardware_profile").read_text().strip() == "c3xl"
assert subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() == TARGET
assert subprocess.run(["systemctl", "is-active", "--quiet", "comma.service"]).returncode != 0
params = Params()
assert params.get_bool("IsOffroad") and not params.get_bool("IsEngaged")
original = {name: raw(path) for name, path in PATHS.items()}

draws = []
recording = False
original_text = tile_module.text


def recording_text(weight, text, x, y, size, color=rl.WHITE):
  if recording:
    draws.append({"text": text, "x": round(x, 2), "y": round(y, 2), "size": size,
                  "width": round(tile_module.text_w(weight, text, size), 2)})
  original_text(weight, text, x, y, size, color)


tile_module.text = recording_text
gui_app.init_window("xpilot v7 tile size E2E", host=BigScreenHost)
main = MiciMainLayout()
host = gui_app.host
original_render = host.render
original_layouts = deepcopy(host._layouts)
frame = 0
next_step = 1
completed = False
cases = []
errors = []


def screenshot(name):
  target = rl.load_render_texture(*tiles.SCREEN)
  events = gui_app._mouse_events
  try:
    rl.begin_texture_mode(target)
    try:
      rl.clear_background(rl.BLACK)
      gui_app._mouse_events = []
      original_render()
    finally:
      rl.end_texture_mode()
    image = rl.load_image_from_texture(target.texture)
    try:
      rl.image_flip_vertical(image)
      assert rl.export_image(image, str(args.output / f"{name}.png"))
    finally:
      rl.unload_image(image)
  finally:
    gui_app._mouse_events = events
    rl.unload_render_texture(target)


def edit_resize_to(tid, wanted):
  placed = host._place("park")
  assert tid in placed
  if not host._edit:
    x, y = center(tiles.tile_rect(placed[tid]))
    host._on_gesture((x, y, time.monotonic()), "long", x, y, placed)
  assert host._edit and host._selected == tid
  taps = 0
  while host._place("park")[tid][2] != wanted:
    placed = host._place("park")
    x, y, _ = tiles.corner_buttons(tiles.tile_rect(placed[tid]))["resize"]
    before = placed[tid][2]
    host._on_gesture((x, y, time.monotonic()), "tap", x, y, placed)
    after = host._place("park")[tid][2]
    assert after != before
    taps += 1
    assert taps <= len(host._entries[tid].spec.sizes)
  placed = host._place("park")
  done = tiles.bar_buttons(placed, False)["done"]
  x, y = center(done)
  host._on_gesture((x, y, time.monotonic()), "tap", x, y, placed)
  assert not host._edit and host._layout == "park"
  return taps


def steps():
  global completed, recording
  yield 30
  assert not ui_state.started and not ui_state.engaged
  assert gui_app.get_active_widget() is main and not host._stack
  assert set(TESTS).issubset(host._entries)
  for tid in selected:
    spec = host._entries[tid].spec
    assert set(SIZES).issubset(spec.sizes), (tid, spec.sizes)
    park_ids = [i for i, _, _ in host._layouts["park"][0]]
    host._layout = "park"
    host._edit = False
    host._selected = None
    host._save([(tid, spec.sizes[0], None)], [i for i in park_ids if i != tid])
    host._enabled._t = -1.0
    host._placed_key = None
    yield 3
    assert list(host._place("park")) == [tid]
    for size in SIZES:
      taps = edit_resize_to(tid, size)
      entry = host._entries[tid]
      entry.poll.invalidate()
      draws.clear()
      recording = True
      yield 3
      recording = False
      placed = host._place("park")
      assert list(placed) == [tid] and placed[tid][2] == size
      width, height = tiles.tile_rect(placed[tid])[2:]
      actual = deepcopy(draws)
      edge = [d["text"] for d in actual if d["x"] < 0 or d["y"] < 0 or d["x"] + d["width"] > width + 1 or d["y"] + d["size"] > height + 1]
      overlap = [[actual[i]["text"], actual[j]["text"]] for i in range(len(actual)) for j in range(i + 1, len(actual))
                 if overlaps(actual[i], actual[j])]
      clipped = [d["text"] for d in actual if d["text"].endswith("...")]
      too_small = [d["text"] for d in actual if d["size"] < tiles.MIN_FONT]
      name = f"tile-{tid}-{size}"
      screenshot(name)
      cases.append({"tile": tid, "title": spec.title, "size": size, "path": f"{name}.png", "placement": list(placed[tid]),
                    "resize_taps_in_edit_mode": taps, "state": repr(entry.state), "draws": actual, "edge_cut": edge,
                    "overlap": overlap, "too_small": too_small, "ellipsis": clipped})
  completed = True
  gui_app.request_close()
  yield 1


scenario = steps()


def render():
  global frame, next_step
  frame += 1
  original_render()
  if frame >= next_step:
    next_step = frame + next(scenario)


host.render = render
try:
  for _ in gui_app.render():
    ui_state.update()
    assert not ui_state.started and not ui_state.engaged
  assert completed
except Exception:
  errors.append(traceback.format_exc())
finally:
  tile_module.text = original_text
  host.render = original_render
  host._layouts = original_layouts
  host._layout = "park"
  host._edit = False
  host._selected = None
  for name, path in PATHS.items():
    try:
      restore(path, original[name])
    except Exception:
      errors.append(f"restore {name} failed:\n{traceback.format_exc()}")
  final = {name: raw(path) for name, path in PATHS.items()}
  restored = {name: final[name] == original[name] for name in PATHS}
  if not all(restored.values()):
    errors.append(f"parameter restore mismatch: {restored}")
  result = {
    "passed": completed and not errors and all(not c[k] for c in cases for k in ("edge_cut", "overlap", "too_small")),
    "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    "scope": "real GPU and production BigScreenHost edit/resize/done callbacks; service stopped for exclusive DRM; no CAN",
    "cases": cases,
    "original_sha256": {name: digest(value) for name, value in original.items()},
    "final_sha256": {name: digest(value) for name, value in final.items()},
    "restored": restored,
    "errors": errors,
  }
  (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
  print(json.dumps(result, indent=2))

assert result["passed"]
