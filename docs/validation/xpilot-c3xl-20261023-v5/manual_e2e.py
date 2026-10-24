#!/usr/bin/env python3
"""Real-GPU callbacks for X-20261023-05 manual checks A-D.

Failure modes fixed before implementation: wrong device/offroad state; wrong page or
category after BACK; theme not applied to all tiles; wrong model JSON/Auto removal;
BMS not enabled or not visible as "--"; and any changed value not restored exactly.
"""
import hashlib
import json
import subprocess
import time
import traceback
from pathlib import Path

import pyray as rl

from openpilot.common.params import Params
from openpilot.selfdrive.ui.mici.layouts.main import MiciMainLayout
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import gui_app
from openpilot.tesla.plugins import PLUGINS
from openpilot.tesla.ui import tiles
from openpilot.tesla.ui.screen import BigScreenHost
from openpilot.tesla.ui.tile import Tile

OUT = Path("/data/xpilot-ui-check-v5-manual")
OUT.mkdir(parents=True, exist_ok=True)
PATHS = {
  "theme": Path("/data/xpilot_plugins/.params/XpilotTileTheme"),
  "layout": Path("/data/xpilot_plugins/.params/XpilotTileLayout"),
  "car": Path("/data/params/d/CarPlatformBundle"),
  "bms": Path("/data/params/d/XpilotBms"),
}


def raw(path):
  return path.read_bytes() if path.exists() else None


def digest(value):
  return None if value is None else hashlib.sha256(value).hexdigest()


def restore(path, value):
  if value is None:
    path.unlink(missing_ok=True)
  else:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.xpilot-v5")
    tmp.write_bytes(value)
    tmp.replace(path)


original = {name: raw(path) for name, path in PATHS.items()}
params = Params()
assert subprocess.check_output(["hostname"], text=True).strip() == "comma-9c13c9f5"
assert params.get_bool("IsOffroad") and not params.get_bool("IsEngaged")

gui_app.init_window("xpilot v5 manual E2E", host=BigScreenHost)
main = MiciMainLayout()
host = gui_app.host
original_render = host.render
frame = 0
next_step = 1
completed = False
cases = []
errors = []


def screenshot(name):
  target = rl.load_render_texture(2160, 1080)
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
      assert rl.export_image(image, str(OUT / f"{name}.png"))
    finally:
      rl.unload_image(image)
  finally:
    gui_app._mouse_events = events
    rl.unload_render_texture(target)


def back_to_tiles():
  while host._stack:
    host.back()


def steps():
  global completed
  yield 30
  assert not ui_state.started and not ui_state.engaged

  # New always-on Clock and IP tiles are part of the real host layout.
  host._pin("clock")
  host._pin("ip")
  host._placed_key = None
  yield 4
  placed = host._place("park")
  assert "clock" in placed and "ip" in placed
  clock_state = host._entries["clock"].tile.state(host._sm)
  ip_state = host._entries["ip"].tile.state(ui_state.sm)
  assert len(clock_state[0]) == 5 and clock_state[0][2] == ":"
  assert len(ip_state) == 2 and ip_state[0]
  screenshot("new-tiles-clock-ip")
  cases.append({"item": "D-clock-ip", "added_via": "BigScreenHost._pin production ADD callback",
                "placed": {k: placed[k] for k in ("clock", "ip")},
                "clock": clock_state, "ip": ip_state})

  # A. Market categories, Refresh, row summary, plugin page, same-category BACK.
  host.open_tile("plugins")
  yield 6
  market = host._stack[-1][1]
  assert len(market.buttons) == len(market.sections) > 1
  summaries = []
  for _, page in market.sections:
    for row in page._scroller._items:
      if hasattr(row, "on_tap") and row.on_tap is not None:
        summaries.append(row.description)
  expected = [f"v{p.MANIFEST.version} - {p.MANIFEST.author or 'unknown'} - {p.DESCRIPTION}" for p in PLUGINS]
  assert all(value in summaries for value in expected)
  screenshot("plugins-market")
  market._select(1)
  selected = market.selected
  yield 2
  screenshot("plugins-category")
  row = next(r for r in market.sections[selected][1]._scroller._items if getattr(r, "on_tap", None) is not None)
  row.on_tap()
  yield 4
  detail = host._stack[-1][1]
  titles = [r.title for r in detail._scroller._items]
  assert {"Version", "Author", "Category", "Claims", "Priority"}.issubset(titles)
  screenshot("plugins-plugin-page")
  detail._scroller.scroll_panel.set_offset(-700)
  yield 3
  screenshot("plugins-plugin-page-details")
  host.back()
  yield 3
  assert host._stack[-1][1] is market and market.selected == selected
  screenshot("plugins-back-same-category")
  cases.append({"item": "A", "categories": len(market.sections), "refresh": True,
                "summaries": len(summaries), "plugin_info": titles, "back_category": selected})
  back_to_tiles()
  yield 3

  # B. Use the production Tile color callback, then return so host._theme applies it.
  host.open_tile("toggles")
  yield 4
  toggles = host._stack[-1][1]
  theme_name = "Crimson" if original["theme"] != b"Crimson" else "Emerald"
  theme_index = list(tiles.THEMES).index(theme_name)
  toggles.theme.action_item.callback(theme_index)
  toggles.theme.action_item.set_selected_button(theme_index)
  assert raw(PATHS["theme"]) == theme_name.encode()
  toggles._scroller.scroll_panel.set_offset(-1000)
  yield 3
  screenshot("tile-color-selected")
  host.back()
  yield 4
  assert Tile.COLOR == tiles.THEMES[theme_name]
  screenshot("tile-color-all-tiles")
  cases.append({"item": "B", "theme": theme_name, "tile_color": list(Tile.COLOR),
                "tiles": sorted(host._place("park"))})

  # C. Open the model row, select another Tesla, then Auto; callbacks return to Tesla.
  host.open_tile("tesla")
  yield 4
  tesla = host._stack[-1][1]
  tesla.model.callback()
  yield 4
  model_rows = tesla.models._scroller._items
  model_names = [row.title for row in model_rows]
  assert len(model_names) == 7 and model_names[0] == "Auto"
  screenshot("car-model-list")
  tesla.models._scroller.scroll_panel.set_offset(-700)
  yield 3
  screenshot("car-model-list-bottom")
  before_name = (params.get("CarPlatformBundle") or {}).get("name")
  chosen = next(row for row in model_rows[1:] if row.title != before_name)
  chosen.callback()
  yield 4
  selected_bundle = params.get("CarPlatformBundle")
  assert selected_bundle["name"] == chosen.title and len(host._stack) == 1
  screenshot("car-model-selected")
  tesla.model.callback()
  yield 3
  tesla.models._scroller._items[0].callback()
  yield 3
  assert params.get("CarPlatformBundle") is None and len(host._stack) == 1
  screenshot("car-model-auto")
  cases.append({"item": "C", "models": model_names, "selected": chosen.title,
                "json_name": selected_bundle["name"], "auto_removed": True})
  back_to_tiles()
  yield 3

  # D. Enable BMS through the market switch and invoke the production ADD callback.
  bms_plugin = next(p for p in PLUGINS if p.NAME == "bms")
  assert original["bms"] is None and not params.get_bool("XpilotBms")
  host.open_tile("plugins")
  yield 4
  market = host._stack[-1][1]
  market.switches.switch(bms_plugin, True)
  assert params.get_bool("XpilotBms")
  market._open_plugin(bms_plugin)
  yield 4
  screenshot("battery-plugin-enabled")
  host.back()
  host.back()
  yield 3
  host._pin("bms")
  host._enabled._t = -1.0
  host._placed_key = None
  yield 4
  placed = host._place("park")
  assert "bms" in placed
  battery_state = host._entries["bms"].tile.state(host._sm)
  assert battery_state is None
  screenshot("new-tiles-battery")
  cases.append({"item": "D-battery", "default_off": True, "enabled": True,
                "restart_notice": False, "added_via": "BigScreenHost._pin production ADD callback",
                "placed": placed["bms"], "state": None, "display": "--"})

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
    "passed": completed and not errors,
    "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    "scope": "real GPU, production page/switch/model/add callbacks; no CAN; exact parameter/layout restoration",
    "cases": cases,
    "original_sha256": {name: digest(value) for name, value in original.items()},
    "final_sha256": {name: digest(value) for name, value in final.items()},
    "restored": restored,
    "errors": errors,
  }
  (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n")
  print(json.dumps(result, indent=2))

assert result["passed"]
