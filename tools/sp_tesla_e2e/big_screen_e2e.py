#!/usr/bin/env python3
"""Real GPU E2E for the UI v4 tiles; saves screenshots and result.json.

Failure modes (listed before implementation):
1. Offroad tile screen has a viewport, draws mici, or omits a settings tile.
2. A mapped tap at a settings tile's center opens the wrong title/PAGE; Models
   or its Small models sub-page is not native, or BACK loses the parent page.
3. A native detail page draws mici or grows the application nav stack beyond 1.
4. BACK does not return to tiles; Plugins -> Store does not push a second detail
   level, or BACK from Store does not return to the same Plugins page.
5. Holding Toggles for LONG_PRESS+0.2 s does not select it in edit mode; its
   resize corner does not change size; + does not open "add tiles"; tapping the
   selected tile or an empty non-add cell does not deselect while staying in
   edit mode; Done does not leave edit mode and return to the park layout.
6. Editing permanently changes XpilotTileLayout bytes (including absence),
   or either of the deep-copied park/drive layouts; restore even on failure.
7. More than 2 tile faces redraw over 60 idle, touch-free tile-screen frames.
8. Synthetic onroad has the wrong tiles.VIEW, a tile overlaps VIEW/blocked
   cells, settings remain placed, a required data tile is missing, or the
   forced blind-spot overlay is absent, never draws, or raises.
9. Drive in the edit bar does not show only data tiles outside blocked cells;
   the default layout does not alternate left/right; a 20-move drag to (7,3)
   does not save that fixed cell (clamped for size) or persist into onroad.
10. Device rows open the wrong native sub-page/title or BACK loses Device;
    training leaves its first step, or driver camera BACK leaves driver view on.
11. A separate, untouched native OnboardingPage cannot render full screen;
    the real onboarding window is pushed, or any offroad frame draws mici.
12. IsDriverViewEnabled is not restored to its original value on exit.

Run with comma service stopped and native libraries built. No CAN transmission,
settings actions, store refresh/install, or reboot/reset/uninstall confirmation.
"""
import argparse
from copy import deepcopy
import json
import subprocess
import tempfile
import time
import traceback
from pathlib import Path

import pyray as rl
from openpilot.common.params import Params
from openpilot.system.ui.lib.application import gui_app, MouseEvent, MousePos
from openpilot.selfdrive.ui.mici.layouts.main import MiciMainLayout
from openpilot.selfdrive.ui.sunnypilot.model_info import bundles_for_source
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.tesla.ui import tiles
from openpilot.tesla.plugins import PLUGINS
from openpilot.tesla.ui.offroad import BACK, CONTENT
from openpilot.tesla.ui.pages.plugins import CAT_H, GAP, LEFT_W
from openpilot.tesla.ui.pages.onboarding import OnboardingPage, onboarding_needed
from openpilot.tesla.ui.screen import BigScreenHost

parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
assert Params().get_bool('IsOffroad') and not Params().get_bool('IsEngaged')
gui_app.init_window('xpilot big screen E2E', host=BigScreenHost)
assert not onboarding_needed(), 'complete onboarding before E2E; never push its real window during this test'
main = MiciMainLayout()
host = gui_app.host
driver_view_before = ui_state.params.get_bool('IsDriverViewEnabled')
SETTINGS = ('status', 'toggles', 'plugins', 'tesla', 'models', 'network', 'device', 'software', 'developer')
errors, cases = [], []
original_render = host.render
original_draw_texture_pro = rl.draw_texture_pro
original_begin_texture_mode = rl.begin_texture_mode
frame, next_step = 0, 1
mici_draws, tile_redraws = 0, 0
in_screenshot, completed = False, False
pending_events = []
layout_path = host._layout_params._path(tiles.LAYOUT_PARAM)
layout_backup = None


def counting_draw_texture_pro(texture, *rest):
  global mici_draws
  if not in_screenshot and texture.id == gui_app._render_texture.texture.id:
    mici_draws += 1
  original_draw_texture_pro(texture, *rest)


def counting_begin_texture_mode(target):
  global tile_redraws
  if not in_screenshot and any(e.texture is not None and target.id == e.texture.id for e in host._entries.values()):
    tile_redraws += 1
  original_begin_texture_mode(target)


rl.draw_texture_pro = counting_draw_texture_pro
rl.begin_texture_mode = counting_begin_texture_mode


def check(ok, message):
  if not ok:
    errors.append(message)


def rect(r):
  return None if r is None else [r.x, r.y, r.width, r.height]


def center(r):
  x, y, w, h = r
  return x + w / 2, y + h / 2


def screenshot(name):
  global in_screenshot
  in_screenshot = True
  target = rl.load_render_texture(2160, 1080)
  events = gui_app._mouse_events
  try:
    rl.begin_texture_mode(target)
    try:
      rl.clear_background(rl.BLACK)
      gui_app._mouse_events = []
      if name == 'onboarding':
        with host._native([]):
          OnboardingPage(on_done=lambda: None).render(rl.Rectangle(0, 0, 2160, 1080))
      else:
        texture = gui_app._render_texture.texture
        view = host.viewport()
        if view is not None:
          rl.draw_texture_pro(texture, rl.Rectangle(0, 0, texture.width, -texture.height), view, rl.Vector2(0, 0), 0, rl.WHITE)
        original_render()  # tile textures were refreshed by this frame's on-screen render
    finally:
      rl.end_texture_mode()
    image = rl.load_image_from_texture(target.texture)
    try:
      rl.image_flip_vertical(image)
      path = args.output / (name + '.png')
      check(rl.export_image(image, str(path)), f'screenshot export failed: {name}')
    finally:
      rl.unload_image(image)
  finally:
    gui_app._mouse_events = events
    rl.unload_render_texture(target)
    in_screenshot = False


def tap(x, y, phase):
  """Queue screen press (0), release (1) or move (2) through the real touch mapping."""
  global pending_events
  lx, ly = host.to_logical(x, y)
  check(not (0 <= lx <= 536 and 0 <= ly <= 240) or host.viewport() is not None, f'tap ({x},{y}) maps inside mici ({lx},{ly})')
  pending_events = [MouseEvent(MousePos(lx, ly), 0, phase == 0, phase == 1, phase != 1, time.monotonic())]


def touch(point):
  tap(*point, 0)
  yield 1
  tap(*point, 1)
  yield 4


def hold_toggles():
  point = center(tiles.tile_rect(host._placed['toggles']))
  start = time.monotonic()
  tap(*point, 0)
  while time.monotonic() - start < tiles.LONG_PRESS + 0.2:
    yield 1
  tap(*point, 1)
  yield 3
  assert host._edit and host._selected == 'toggles', f'long press: edit={host._edit}, selected={host._selected}'


def tile_screen():
  assert not host._stack and gui_app.get_active_widget() is main, 'BACK did not return to the tile screen'
  check(host.viewport() is None and host._shown is None, 'tile screen still shows a detail page or mici viewport')


def layout_bytes():
  return layout_path.read_bytes() if layout_path.exists() else None


def restore_layout():
  if layout_backup is None:
    return
  layouts, raw = layout_backup
  host._layouts, host._layout = deepcopy(layouts), 'park'
  host._edit, host._selected, host._drag = False, None, None
  if layout_bytes() != raw:
    if raw is None:
      layout_path.unlink(missing_ok=True)
    else:
      with tempfile.NamedTemporaryFile(dir=layout_path.parent, delete=False) as saved:
        saved.write(raw)
      Path(saved.name).replace(layout_path)
  check(layout_bytes() == raw and host._layouts == layouts, 'saved park/drive layouts were not restored exactly')


def steps():
  global layout_backup, completed
  yield 30
  tile_screen()
  check(mici_draws == 0, f'offroad tile screen drew mici {mici_draws} times')
  for tid in SETTINGS:
    check(tid in host._placed, f'offroad settings tile {tid} not placed')
  screenshot('start')
  cases.append({'name': 'offroad', 'viewport': rect(host.viewport()), 'placed': dict(host._placed), 'mici_draws': mici_draws})
  screenshot('onboarding')
  cases.append({'name': 'onboarding', 'standalone': True, 'size': [2160, 1080], 'touches': 0})
  before = tile_redraws
  yield 60
  check(tile_redraws - before <= 2, f'60 idle frames redrew {tile_redraws - before} tile faces')
  check(mici_draws == 0, 'idle tile screen drew mici')
  cases.append({'name': 'idle', 'frames': 60, 'tile_redraws': tile_redraws - before})

  for tid in SETTINGS:
    if tid not in host._placed:
      continue  # already reported; do not tap where an absent tile should have been
    tile = host._entries[tid].tile
    before = mici_draws
    yield from touch(center(tiles.tile_rect(host._placed[tid])))
    assert len(host._stack) == 1 and host._stack[-1][0] == tile.SPEC.title, f'tile {tid}: detail stack {host._stack}'
    page = host._stack[-1][1]
    active = gui_app.get_active_widget()
    assert not tile.MICI and type(page) is tile.PAGE, f'tile {tid}: page {type(page).__name__}, expected native {tile.PAGE.__name__}'
    check(host._shown is page and active is main and len(gui_app._nav_stack) == 1, f'tile {tid}: native page/application stack mismatch')
    check(host.viewport() is None and mici_draws == 0, f'tile {tid}: native page drew mici')
    screenshot('page-' + tid)
    cases.append({'name': tid, 'title': host._stack[-1][0], 'page': type(page).__name__, 'active': type(active).__name__,
                  'stack': len(host._stack), 'nav_stack': len(gui_app._nav_stack), 'mici_draws': mici_draws - before})
    if tid == 'plugins':
      if len(page.buttons) > 1:
        yield from touch(center((CONTENT[0], CONTENT[1] + GAP + CAT_H + GAP, LEFT_W, CAT_H)))
        check(page.selected == 1, 'Plugins: tapping the second category did not select it')
        screenshot('page-plugins-category')
      plugin = PLUGINS[0]
      page._open_plugin(plugin)
      yield 4
      check(len(host._stack) == 2 and host._stack[-1][0] == plugin.TITLE and type(host._stack[-1][1]).__name__ == 'PluginPage',
            'Plugins -> plugin did not push a second detail level')
      check(host._shown is host._stack[-1][1] and host.viewport() is None and mici_draws == before, 'plugin page did not show natively')
      check(len(gui_app._nav_stack) == 1, 'plugin page grew the application nav stack')
      screenshot('page-plugins-plugin')
      yield from touch(center(BACK))
      assert host._stack == [(tile.SPEC.title, page)] and host._shown is page, 'BACK from the plugin page did not return to Plugins'
      cases.append({'name': 'Plugins > plugin > BACK', 'page': type(page).__name__, 'stack': len(host._stack)})
    if tid == 'models':
      if bundles_for_source('qcom'):
        page._choose('qcom')
        yield 4
        check(len(host._stack) == 2 and host._stack[-1][0] == 'Small models' and type(host._stack[-1][1]).__name__ == 'BundlesPage', 'Models -> Small models did not push the native bundle list')
        check(host._shown is host._stack[-1][1] and host.viewport() is None and mici_draws == 0, 'Small models did not show natively')
        check(len(gui_app._nav_stack) == 1, 'Small models grew the application nav stack')
        screenshot('page-models-small')
        yield from touch(center(BACK))
        assert host._stack == [(tile.SPEC.title, page)] and host._shown is page, 'BACK from Small models did not return to Models'
        cases.append({'name': 'Models > Small models > BACK', 'page': 'BundlesPage', 'skipped': False})
      else:
        cases.append({'name': 'Models > Small models > BACK', 'skipped': True, 'reason': 'no qcom bundles available'})
    if tid == 'device':
      for title, row_title, expected in (
        ('training guide', 'Review training guide', 'TrainingGuidePage'),
        ('driver camera', 'Driver camera preview', 'DriverCameraPage'),
        ('terms', 'Terms & conditions', 'TermsPage'),
        ('regulatory', 'Regulatory info', 'RegulatoryPage'),
      ):
        row = next(row for row in page._scroller._items if row.title == row_title)
        if not row.is_visible:
          cases.append({'name': 'Device > ' + title, 'skipped': True, 'reason': 'row hidden on this hardware'})
          continue
        row.callback()
        yield 360 if title == 'driver camera' else 4  # camerad needs a few seconds after IsDriverViewEnabled
        assert len(host._stack) == 2 and host._stack[-1][0] == title, f'Device -> {title}: detail stack {host._stack}'
        sub = host._stack[-1][1]
        check(type(sub).__name__ == expected and host._shown is sub, f'Device -> {title}: page {type(sub).__name__}, expected {expected}')
        check(host.viewport() is None and mici_draws == 0 and len(gui_app._nav_stack) == 1, f'Device -> {title} did not stay native')
        if title == 'training guide':
          check(sub._step == 0, 'training guide left its first step')
        screenshot('page-device-' + title.replace(' ', '-'))
        yield from touch(center(BACK))
        assert host._stack == [(tile.SPEC.title, page)] and host._shown is page, f'BACK from {title} did not return to Device'
        case = {'name': 'Device > ' + title + ' > BACK', 'page': type(sub).__name__, 'stack': len(host._stack)}
        if title == 'driver camera':
          case['driver_view_after_back'] = ui_state.params.get_bool('IsDriverViewEnabled')
          check(not case['driver_view_after_back'], 'driver camera BACK left IsDriverViewEnabled on')
        cases.append(case)
    yield from touch(center(BACK))
    tile_screen()
    check(mici_draws == 0, f'BACK from {tid} drew mici')

  layout_backup = (deepcopy(host._layouts), layout_bytes())
  yield from hold_toggles()
  screenshot('edit')
  old_size = host._placed['toggles'][2]
  yield from touch(tiles.corner_buttons(tiles.tile_rect(host._placed['toggles']))['resize'][:2])
  check('toggles' in host._placed and host._placed['toggles'][2] != old_size, 'resize corner did not change Toggles size')
  check(host._edit and host._selected == 'toggles', 'resize left edit mode or changed selection')
  screenshot('edit-resized')
  cell = tiles.add_cell(host._placed, False)
  assert cell is not None, 'no add cell after resize'
  yield from touch(center(tiles.cell_rect(*cell)))
  assert len(host._stack) == 1 and host._stack[-1][0] == 'add tiles', '+ did not open add tiles'
  check(type(host._shown).__name__ == 'AddTilesPage' and host._shown is host._stack[-1][1] and host.viewport() is None, 'wrong add tiles page')
  screenshot('add-tiles')
  yield from touch(center(BACK))
  tile_screen()
  assert host._edit and host._selected == 'toggles', 'BACK from add tiles lost edit mode'
  yield from touch(center(tiles.tile_rect(host._placed['toggles'])))
  check(host._edit and host._selected is None and not host._stack, 'selected tile tap did not deselect in edit mode')
  yield from touch(center(tiles.tile_rect(host._placed['toggles'])))
  check(host._edit and host._selected == 'toggles', 'tile tap did not reselect Toggles')
  add = tiles.add_cell(host._placed, False)
  empty = next(((c, r) for c in range(tiles.COLS) for r in range(tiles.ROWS)
                if (c, r) != add and tiles.hit(host._placed, *center(tiles.cell_rect(c, r))) is None), None)
  assert empty is not None, 'no empty non-add cell to test edit exit'
  yield from touch(center(tiles.cell_rect(*empty)))
  check(host._edit and host._selected is None and not host._stack, 'empty cell tap did not deselect in edit mode')
  cases.append({'name': 'edit', 'old_size': old_size, 'new_size': host._placed['toggles'][2], 'empty_cell': empty})

  host._layouts['drive'] = tiles.arrange([e.tile.SPEC for e in host._entries.values() if tiles.shows(e.tile.SPEC, True)], None, 'drive')
  yield from touch(center(tiles.bar_buttons(host._placed, host._layout == 'drive')['drive']))
  assert host._edit and host._layout == 'drive', 'Drive bar button did not select the drive layout'
  data = [tid for tid, _, _, _ in host._visible('drive')]  # enabled onroad tiles, built-in, plugin or store
  check(set(host._placed) == set(data), f'drive edit tiles: {list(host._placed)}, expected {data}')
  default_order = [tid for tid, _, _ in host._layouts['drive'][0] if tid in data]
  free = [cell for cell in tiles.scan(True) if cell not in tiles.blocked(True)]
  for tid, cell in zip(default_order, free):
    check(tid in host._placed and host._placed[tid][:2] == cell, f'default drive tile {tid}: {host._placed.get(tid)}, expected {cell}')
  for tid, (col, row, size) in host._placed.items():
    cols, rows = tiles.SIZES[size]
    check(not {(col + c, row + r) for c in range(cols) for r in range(rows)} & tiles.blocked(True), f'drive edit tile {tid} overlaps blocked cells')
  screenshot('edit-drive')
  cases.append({'name': 'edit drive default', 'order': default_order, 'placed': dict(host._placed)})

  moved = next((tid for tid in data if tid in host._placed), None)
  assert moved is not None, 'no data tile to drag'
  sx, sy = center(tiles.tile_rect(host._placed[moved]))
  ex, ey = center(tiles.cell_rect(7, 3))
  cols, rows = tiles.SIZES[host._placed[moved][2]]
  drop_cell = (min(7, tiles.COLS - cols), min(3, tiles.ROWS - rows))
  tap(sx, sy, 0)
  yield 1
  for step in range(1, 21):
    tap(sx + (ex - sx) * step / 20, sy + (ey - sy) * step / 20, 2)
    yield 1
  tap(ex, ey, 1)
  yield 4
  fixed = next(fixed for tid, _, fixed in host._layouts['drive'][0] if tid == moved)
  check(fixed == drop_cell, f'dragged {moved}: saved fixed cell {fixed}, expected {drop_cell}')
  check(moved in host._placed and host._placed[moved][:2] == drop_cell, f'dragged {moved} not placed at {drop_cell}')
  screenshot('edit-drive-moved')
  cases.append({'name': 'edit drive moved', 'tile': moved, 'fixed': fixed, 'expected': drop_cell, 'moves': 20})
  yield from touch(center(tiles.bar_buttons(host._placed, host._layout == 'drive')['done']))
  check(not host._edit and host._layout == 'park', 'Done did not leave edit mode and restore the park layout')
  tile_screen()

  gui_app.pop_widgets_to(main, instant=True)
  ui_state.started = True  # synthetic composition only; never write IsOffroad or send CAN
  check(rect(host.viewport()) == list(tiles.VIEW), f'onroad viewport {rect(host.viewport())}')
  lx, ly = host.to_logical(*tiles.VIEW[:2])
  check(abs(lx) < 0.01 and abs(ly) < 0.01, f'onroad to_logical origin {lx},{ly}')
  forced, drawn = [], []
  for entry in host._overlays._entries:
    overlay = entry[1]
    if type(overlay).__name__ == 'BlindspotEdges':
      overlay.update = lambda sm, o=overlay: (setattr(o, 'left', True), setattr(o, 'right', True))

      def draw(zones, original=overlay.draw):
        original(zones)
        drawn.append(True)

      overlay.draw = draw
      forced.append(entry)
  check(bool(forced), 'blindspot_edges overlay not loaded (plugin off or import failed)')
  original_render()
  vx, vy, vw, vh = tiles.VIEW
  for tid, placed in host._placed.items():
    x, y, w, h = tiles.tile_rect(placed)
    check(not (x < vx + vw and vx < x + w and y < vy + vh and vy < y + h), f'onroad tile {tid} overlaps VIEW')
    col, row, size = placed
    cols, rows = tiles.SIZES[size]
    cells = {(col + c, row + r) for c in range(cols) for r in range(rows)}
    check(not cells & tiles.blocked(True), f'onroad tile {tid} overlaps blocked cells')
    check(tid not in SETTINGS and host._entries[tid].tile.SPEC.show != 'offroad', f'onroad settings tile {tid} placed')
  for tid in data:
    check(tid in host._placed, f'onroad data tile {tid} not placed')
  check(moved in host._placed and host._placed[moved][:2] == drop_cell, f'onroad lost fixed position of {moved}: {host._placed.get(moved)}')
  check(len(drawn) == len(forced), 'blindspot overlay did not draw successfully')
  screenshot('onroad-blindspot')
  check(all(e[2] == 0 for e in forced), 'blindspot overlay raised')
  cases.append({'name': 'onroad', 'viewport': rect(host.viewport()), 'placed': dict(host._placed), 'blindspot_draws': len(drawn)})
  ui_state.started = False
  host.viewport()
  restore_layout()
  yield 4
  tile_screen()
  completed = True
  gui_app.request_close()
  yield 1


scenario = steps()


def render():
  global frame, next_step, pending_events
  frame += 1
  gui_app._mouse_events, pending_events = pending_events, []
  original_render()
  assert mici_draws == 0, f'offroad frame {frame} drew the mici texture'
  assert not host._is_modal(gui_app.get_active_widget()), 'unexpected dialog; no confirmation was sent'
  if frame >= next_step:
    next_step = frame + next(scenario)


host.render = render
try:
  for should_render, *_ in gui_app.render():
    ui_state.update()
    assert not ui_state.started and not ui_state.engaged, 'device must remain offroad and unengaged'
  check(completed, 'E2E closed before all steps completed')
except Exception:
  errors.append(traceback.format_exc())
finally:
  ui_state.started = False
  try:
    restore_layout()
    if layout_backup is not None:
      cases.append({'name': 'layout restored', 'file_matches': layout_bytes() == layout_backup[1],
                    'layouts_match': host._layouts == layout_backup[0]})
  except Exception:
    errors.append('layout restore failed:\n' + traceback.format_exc())
  try:
    try:
      host._show(None)
    finally:
      if ui_state.params.get_bool('IsDriverViewEnabled') != driver_view_before:
        ui_state.params.put_bool('IsDriverViewEnabled', driver_view_before, block=True)
    driver_view_after = ui_state.params.get_bool('IsDriverViewEnabled')
    check(driver_view_after == driver_view_before, 'IsDriverViewEnabled was not restored')
    cases.append({'name': 'driver view restored', 'before': driver_view_before, 'after': driver_view_after})
  except Exception:
    errors.append('driver view restore failed:\n' + traceback.format_exc())
  rl.draw_texture_pro = original_draw_texture_pro
  rl.begin_texture_mode = original_begin_texture_mode
  host.render = original_render
  result = {'passed': not errors, 'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
            'scope': 'real GPU, production widgets and mapped touch events; layout restored; synthetic onroad; no CAN transmission',
            'cases': cases, 'errors': errors}
  (args.output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
  print(json.dumps(result, indent=2))
assert result['passed']
