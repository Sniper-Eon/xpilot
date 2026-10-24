"""Failures: wrong identity/head or safety state, DRM contention, missing store
plugin, wrong page/source, GPU export failure. Production page; no actions.
"""
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import pyray as rl
from openpilot.common.params import Params
from openpilot.selfdrive.ui.mici.layouts.main import MiciMainLayout
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import gui_app
from openpilot.tesla.plugins import PLUGINS
from openpilot.tesla.ui import tiles
from openpilot.tesla.ui.screen import BigScreenHost
assert subprocess.check_output(['hostname'],text=True).strip()=='comma-9c13c9f5'
assert Path('/data/hardware_profile').read_text().strip()=='c3xl'
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()=='cc129b8829c8fd6d170ef75d9857840cb25ed726'
assert subprocess.run(['systemctl','is-active','--quiet','comma.service']).returncode!=0
assert Params().get_bool('IsOffroad') and not Params().get_bool('IsEngaged')
args=SimpleNamespace(output=Path('/data/xpilot-ui-check-v7-plugin-source'))
args.output.mkdir(exist_ok=False)
gui_app.init_window('xpilot v7 plugin source E2E',host=BigScreenHost)
main=MiciMainLayout()
host=gui_app.host
original_render=host.render
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



def steps():
 global completed
 yield 30
 host.open_tile('plugins')
 yield 4
 page=host._stack[-1][1]
 assert type(page).__name__=='PluginsPage'
 store=next(p for p in PLUGINS if p.NAME=='overspeed_warning')
 assert store.__module__.startswith('xpilot_ext.') and store.NAME in page.jobs.installed
 page._open_plugin(store)
 yield 4
 assert len(host._stack)==2 and host._shown is host._stack[-1][1]
 assert type(host._shown).__name__=='PluginPage' and host.viewport() is None
 screenshot('page-plugins-store-source')
 completed=True
 gui_app.request_close()
 yield 1
completed=False
frame=0
next_step=1
scenario=steps()
def render():
 global frame,next_step
 frame+=1
 original_render()
 if frame>=next_step:
  next_step=frame+next(scenario)
host.render=render
try:
 for _ in gui_app.render():
  ui_state.update()
  assert not ui_state.started and not ui_state.engaged
 assert completed
finally:
 host.render=original_render
 host._show(None)
 (args.output/'result.json').write_text(json.dumps({'passed':completed,'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'plugin':'overspeed_warning','source':'store (removable)','scope':'real GPU, production PluginsPage and PluginPage, no toggle/install/remove actions'},indent=2)+'\n')
