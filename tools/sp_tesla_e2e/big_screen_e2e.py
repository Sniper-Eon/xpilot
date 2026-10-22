#!/usr/bin/env python3
"""Real GPU UI E2E for the big-screen host; saves screenshots and JSON, changes no settings.
Failure modes:
- offroad viewport not at (456,180,1608,720) or onroad viewport not at grid.VIEW (mici drawn in the wrong place)
- to_logical and viewport disagree (touches land beside the widget that is drawn)
- a nav row selects the wrong page, leaves nested pages behind (nav stack grows) or shows a redundant Back card
- a tap on the nav column reaches mici as a press inside a mici widget
- the host still draws its own alert banner (alerts must appear once, inside the view)
- onroad cards missing, outside their zone, or overlapping the view
- the blind-spot overlay does not draw, or breaks the frame
Run with comma service stopped and native libraries built.
"""
import argparse
import json
import subprocess
import time
from pathlib import Path

import pyray as rl
from openpilot.common.params import Params
from openpilot.system.ui.lib.application import gui_app, MouseEvent, MousePos
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.tesla.ui.grid import VIEW, ZONES
from openpilot.tesla.ui.screen import BigScreenHost, NAV_TOP, NAV_W, OFFROAD_VIEW, PAGES, ROW_H
from openpilot.selfdrive.ui.mici.layouts.main import MiciMainLayout

parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
assert Params().get_bool('IsOffroad') and not Params().get_bool('IsEngaged')
gui_app.init_window('xpilot big screen E2E', host=BigScreenHost)
main = MiciMainLayout()
host = gui_app.host
errors, cases = [], []
original_render = host.render
frame = 0
NAV_START, NAV_STEP = 30, 30
ONROAD = NAV_START + NAV_STEP * len(PAGES) + 10


def check(ok, message):
  if not ok:
    errors.append(message)


def rect(r):
  return [r.x, r.y, r.width, r.height]


def screenshot(name):
  target = rl.load_render_texture(2160, 1080)
  rl.begin_texture_mode(target)
  rl.clear_background(rl.BLACK)
  texture = gui_app._render_texture.texture
  rl.draw_texture_pro(texture, rl.Rectangle(0, 0, texture.width, -texture.height), host.viewport(), rl.Vector2(0, 0), 0, rl.WHITE)
  events = gui_app._mouse_events
  gui_app._mouse_events = []
  original_render()  # slot textures were refreshed by this frame's on-screen render, so nothing nests texture modes
  gui_app._mouse_events = events
  rl.end_texture_mode()
  image = rl.load_image_from_texture(target.texture)
  rl.image_flip_vertical(image)
  rl.export_image(image, str(args.output / (name + '.png')))
  rl.unload_image(image)
  rl.unload_render_texture(target)


def render():
  global frame
  frame += 1
  if frame == 20:
    check(rect(host.viewport()) == list(OFFROAD_VIEW), f'offroad viewport {rect(host.viewport())}')
    lx, ly = host.to_logical(OFFROAD_VIEW[0] + OFFROAD_VIEW[2], OFFROAD_VIEW[1] + OFFROAD_VIEW[3])
    check(abs(lx - 536) < 0.01 and abs(ly - 240) < 0.01, f'offroad to_logical corner {lx},{ly}')
    check(not hasattr(host, '_banner'), 'host still owns an alert banner')
    cases.append({'name': 'offroad', 'viewport': rect(host.viewport())})
  if NAV_START <= frame < NAV_START + NAV_STEP * len(PAGES):
    index, phase = divmod(frame - NAV_START, NAV_STEP)
    if phase in (0, 1):
      lx, ly = host.to_logical(NAV_W / 2, NAV_TOP + index * ROW_H + ROW_H / 2)
      check(lx < 0, f'nav row {index} maps inside the mici viewport ({lx},{ly})')
      gui_app._mouse_events = [MouseEvent(MousePos(lx, ly), 0, phase == 0, phase == 1, phase == 0, time.monotonic())]
  original_render()
  if frame == 20:
    screenshot('offroad')
  if NAV_START <= frame < NAV_START + NAV_STEP * len(PAGES):
    index, phase = divmod(frame - NAV_START, NAV_STEP)
    if phase == 20:
      active = gui_app.get_active_widget()
      check(host._selected == index, f'nav {index} did not select')
      check(len(gui_app._nav_stack) == (1 if index == 0 else 2), f'nav {index}: nav stack depth {len(gui_app._nav_stack)}')
      check(active is main if index == 0 else type(active) is PAGES[index][1], f'nav {index} shows {type(active).__name__}')
      if index:
        visible = [w for w in active._scroller.items if w.is_visible]
        check(not visible or getattr(visible[0], 'text', '') != 'Back', f'nav {index} starts with redundant Back card')
      screenshot(f'nav-{index}-{PAGES[index][0].lower()}')
      cases.append({'name': PAGES[index][0], 'active': type(active).__name__, 'stack': len(gui_app._nav_stack)})
  if frame == ONROAD:
    gui_app.pop_widgets_to(main, instant=True)
    ui_state.started = True
    check(rect(host.viewport()) == list(VIEW), f'onroad viewport {rect(host.viewport())}')
    lx, ly = host.to_logical(VIEW[0], VIEW[1])
    check(abs(lx) < 0.01 and abs(ly) < 0.01, f'onroad to_logical origin {lx},{ly}')
    forced = []
    for entry in host._overlays:
      if type(entry[1]).__name__ == 'BlindspotEdges':
        entry[1].update = lambda sm, o=entry[1]: (setattr(o, 'left', True), setattr(o, 'right', True))
        forced.append(entry)
    check(bool(forced), 'blindspot_edges overlay not loaded (plugin off or import failed)')
    original_render()
    tiles = {t.slot.SPEC.id: t.rect for t in host._tiles if t.rect is not None}
    for sid, r in tiles.items():
      zone = next((z for z, (x, y, w, h) in ZONES.items() if r[0] >= x and r[1] >= y and r[0] + r[2] <= x + w and r[1] + r[3] <= y + h), None)
      spec_zone = next(t.slot.SPEC.zone for t in host._tiles if t.slot.SPEC.id == sid)
      check(zone is not None and spec_zone in ('auto', zone), f'card {sid} {r} outside zone {spec_zone}')
    for sid in ('speed_card', 'lead_card', 'speed_limit_card', 'car', 'map'):
      check(sid in tiles, f'card {sid} not placed')
    check(all(e[2] == 0 for e in forced), 'blindspot overlay raised')
    screenshot('onroad-blindspot')
    cases.append({'name': 'onroad', 'viewport': rect(host.viewport()), 'cards': tiles, 'overlays': len(host._overlays)})
    ui_state.started = False
  if frame == ONROAD + 5:
    check(len(cases) == len(PAGES) + 2, f'{len(cases)} cases, expected {len(PAGES) + 2}')
    gui_app.request_close()


host.render = render
for should_render, *_ in gui_app.render():
  ui_state.update()
result = {'passed': not errors, 'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
          'scope': 'real GPU, production widgets and mapped touch events; no setting changes or CAN transmission',
          'cases': cases, 'errors': errors}
(args.output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
assert result['passed']
