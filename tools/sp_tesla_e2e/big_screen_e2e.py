#!/usr/bin/env python3
"""Real GPU UI E2E for the big-screen host; saves screenshots and JSON, changes no settings.
Failure modes:
- offroad (UI v3) the mici texture is drawn on a native page, or not drawn (FALLBACK_VIEW) on the Models fallback
- onroad viewport not at grid.VIEW, or to_logical and viewport disagree (touches land beside the widget that is drawn)
- a nav row selects the wrong page, shows the wrong native page or leaves pages on the nav stack
- a tap on the nav column or a native page reaches mici as a press inside a mici widget
- the Plugin Store sub-page does not open with its breadcrumb, or Back in the title band does not close it
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
from openpilot.tesla.ui.offroad import FALLBACK_VIEW, NAV, content_rect
from openpilot.tesla.ui.pages.store import StorePage
from openpilot.tesla.ui.screen import NATIVE, BigScreenHost, NAV_TOP, NAV_W, ROW_H
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
draws_before = [0]
NAV_START, NAV_STEP = 30, 30
ONROAD = NAV_START + NAV_STEP * len(NAV) + 10
PLUGINS = NAV.index('Plugins')
mici_draws = 0  # draws of the mici texture outside screenshot(); offroad only the Models fallback may add to it
in_screenshot = False
original_draw_texture_pro = rl.draw_texture_pro


def counting_draw_texture_pro(texture, *rest):
  global mici_draws
  if not in_screenshot and texture.id == gui_app._render_texture.texture.id:
    mici_draws += 1
  original_draw_texture_pro(texture, *rest)


rl.draw_texture_pro = counting_draw_texture_pro


def check(ok, message):
  if not ok:
    errors.append(message)


def rect(r):
  return [r.x, r.y, r.width, r.height]


def screenshot(name):
  global in_screenshot
  in_screenshot = True
  target = rl.load_render_texture(2160, 1080)
  rl.begin_texture_mode(target)
  rl.clear_background(rl.BLACK)
  texture = gui_app._render_texture.texture
  view = host.viewport()
  if view is not None:
    rl.draw_texture_pro(texture, rl.Rectangle(0, 0, texture.width, -texture.height), view, rl.Vector2(0, 0), 0, rl.WHITE)
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
  in_screenshot = False


def tap(x, y, phase):
  """Screen tap: press on phase 0, release on phase 1, mapped like the touch thread does."""
  if phase in (0, 1):
    lx, ly = host.to_logical(x, y)
    check(not (0 <= lx <= 536 and 0 <= ly <= 240) or host.viewport() is not None, f'tap ({x},{y}) maps inside mici ({lx},{ly})')
    gui_app._mouse_events = [MouseEvent(MousePos(lx, ly), 0, phase == 0, phase == 1, phase == 0, time.monotonic())]


def render():
  global frame
  frame += 1
  if frame == 20:
    check(host.viewport() is None, f'offroad Home viewport {host.viewport()}')
    lx, ly = host.to_logical(1080, 540)
    check(not (0 <= lx <= 536 and 0 <= ly <= 240), f'offroad screen centre maps inside mici ({lx},{ly})')
    check(not hasattr(host, '_banner'), 'host still owns an alert banner')
    cases.append({'name': 'offroad', 'viewport': None})
  nav = NAV_START <= frame < NAV_START + NAV_STEP * len(NAV)
  index, phase = divmod(frame - NAV_START, NAV_STEP)
  if nav:
    tap(NAV_W / 2, NAV_TOP + index * ROW_H + ROW_H / 2, phase)
    if index == PLUGINS and phase in (26, 27):
      tap(content_rect()[0] + 40, 40, phase - 26)  # "< Back" in the title band
  if nav and phase == 5:
    draws_before[0] = mici_draws
  original_render()
  if frame == 20:
    screenshot('offroad')
  if nav:
    label = NAV[index]
    if phase == 20:
      active = gui_app.get_active_widget()
      native = label in NATIVE
      check(host._selected == index, f'nav {label} did not select')
      check(len(gui_app._nav_stack) == (1 if native else 2), f'nav {label}: nav stack depth {len(gui_app._nav_stack)}')
      if native:
        check(active is main, f'nav {label}: {type(active).__name__} above main')
        check(type(host._page()) is NATIVE[label] and host._shown is host._page(), f'nav {label} shows {type(host._page()).__name__}')
        check(host.viewport() is None and mici_draws == draws_before[0], f'nav {label}: mici texture drawn on a native page')
      else:
        check(type(active).__name__ == 'ModelsLayoutMici', f'nav {label} shows {type(active).__name__}')
        check(rect(host.viewport()) == list(FALLBACK_VIEW) and mici_draws > draws_before[0], f'nav {label}: mici fallback not drawn')
      screenshot(f'nav-{index}-{label.lower()}')
      cases.append({'name': label, 'active': type(active).__name__, 'page': type(host._page()).__name__, 'stack': len(gui_app._nav_stack),
                    'mici_draws': mici_draws - draws_before[0]})
    if index == PLUGINS and phase == 21:
      host._page()._open_store()  # the "Plugin Store" row callback
    if index == PLUGINS and phase == 24:
      check(host._sub is not None and host._sub[0] == 'Store' and type(host._page()) is StorePage, f'store sub-page {host._sub}')
      check(host.viewport() is None, 'store: mici viewport')
      screenshot('plugins-store')
      cases.append({'name': 'Plugins > Store', 'page': type(host._page()).__name__})
    if index == PLUGINS and phase == 29:
      check(host._sub is None, 'Back did not close the store sub-page')
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
    check(len(cases) == len(NAV) + 3, f'{len(cases)} cases, expected {len(NAV) + 3}')
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
