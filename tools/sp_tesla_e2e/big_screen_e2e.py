#!/usr/bin/env python3
"""Real GPU UI E2E, offroad only; saves screenshots and JSON, changes no settings.
Failure modes: tiny viewport, offroad stale alerts, lost onroad alerts, side-menu
coordinates selecting the wrong page, category navigation leaving nested pages behind.
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
from openpilot.selfdrive.ui.mici.onroad.alert_renderer import Alert, AlertSize, AlertStatus
from openpilot.tesla.ui.screen import BigScreenHost
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
banner_calls = []
original_banner = host._banner.render
host._banner.render = lambda rect: (banner_calls.append(ui_state.started), original_banner(rect))[1]
original_render = host.render
frame = 0

def check(ok, message):
  if not ok:
    errors.append(message)

def screenshot(name):
  target = rl.load_render_texture(2160, 1080)
  rl.begin_texture_mode(target)
  rl.clear_background(rl.BLACK)
  texture = gui_app._render_texture.texture
  rl.draw_texture_pro(texture, rl.Rectangle(0,0,texture.width,-texture.height), host.viewport(), rl.Vector2(0,0), 0, rl.WHITE)
  events = gui_app._mouse_events
  gui_app._mouse_events = []
  original_render()
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
    v = host.viewport()
    check(v.width >= 1500 and v.height >= 700, 'central viewport is too small')
    check(not banner_calls, 'offroad renders stale onroad alert banner')
    screenshot('offroad')
    cases.append({'name':'offroad', 'viewport':[v.x,v.y,v.width,v.height], 'banner_calls':len(banner_calls)})
  if hasattr(host, '_menu') and frame >= 30:
    index, phase = divmod(frame - 30, 30)
    if index < len(host._menu):
      x, y = (130 if index < 5 else 2030), 162 + (index % 5) * 180
      if phase in (0, 1):
        lx, ly = host.to_logical(x, y)
        gui_app._mouse_events = [MouseEvent(MousePos(lx,ly),0,phase==0,phase==1,phase==0,time.monotonic())]
      if phase == 20:
        check(host._selected == index, f'menu {index} did not select')
        active = gui_app.get_active_widget()
        check(active is main if index == 0 else active is not main and active is not main._settings_layout,
              f'menu {index} does not show concrete settings')
        screenshot(f'menu-{index}')
        cases.append({'name':host._menu[index][0], 'active':type(active).__name__})
  original_render()
  if frame == 320:
    before = len(banner_calls)
    ui_state.started = True
    get_alert = host._banner.get_alert
    host._banner.get_alert = lambda sm: Alert('TAKE CONTROL', 'UI verification', AlertSize.full, AlertStatus.critical)
    screenshot('onroad-alert')
    host._banner.get_alert = get_alert
    ui_state.started = False
    check(len(banner_calls) == before + 1, 'onroad banner no longer renders')
  if frame == 325:
    check(hasattr(host, '_menu'), 'side settings menu missing')
    check(len(cases) == 10, 'not all nine menu entries were exercised')
    gui_app.request_close()

host.render = render
for should_render, *_ in gui_app.render():
  ui_state.update()
result = {'passed':not errors,'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
          'scope':'real GPU, production widgets and mapped touch events; no setting changes or CAN transmission',
          'cases':cases,'errors':errors}
(args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
assert result['passed']
