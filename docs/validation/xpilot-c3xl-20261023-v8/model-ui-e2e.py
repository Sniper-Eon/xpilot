"""Failures: unsafe identity/state, wrong role owner, missing/extra model tile,
wrong conflict status, plugin load fault, GPU export failure or UI exception.
Production BigScreenHost/pages on device GPU, offroad only; no UI actions that
change params. Run with comma.service stopped, as in the v7 screenshot method.
"""
import argparse
import json
from pathlib import Path
import socket
import subprocess
import pyray as rl
from openpilot.common.params import Params
from openpilot.selfdrive.ui.mici.layouts.main import MiciMainLayout
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import gui_app
from openpilot.tesla import plugins
from openpilot.tesla.ui import tiles
from openpilot.tesla.ui.screen import BigScreenHost

ap=argparse.ArgumentParser()
ap.add_argument('--state', choices=['default','enabled','disabled','removed'], required=True)
ap.add_argument('--output',type=Path,required=True)
args=ap.parse_args()
assert socket.gethostname()=='comma-9c13c9f5'
assert Path('/data/hardware_profile').read_text().strip()=='c3xl'
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()=='f7af016516db4043bec0af24e6d3133fd864dfc9'
assert subprocess.run(['systemctl','is-active','--quiet','comma.service']).returncode!=0
assert Params().get_bool('IsOffroad') and not Params().get_bool('IsEngaged')
assert not plugins.LOAD_ERRORS,plugins.LOAD_ERRORS
assert not Params().get(plugins.FAULTS_PARAM)
enabled=args.state=='enabled'
owner=plugins.owner(Params(),'role:perception.model')
active,conflicts=plugins.resolve(Params())
assert owner==('op_models' if enabled else 'sp_models')
if enabled:
  assert conflicts['sp_models']=='op_models' and 'op_models' in active
args.output.mkdir(exist_ok=False)
gui_app.init_window('xpilot v8 model stack E2E',host=BigScreenHost)
main=MiciMainLayout()
host=gui_app.host
original_render=host.render
result={'state':args.state,'owner':owner,'active':sorted(active),'conflicts':conflicts,'load_errors':plugins.LOAD_ERRORS,'passed':False}

def screenshot(name):
  target=rl.load_render_texture(*tiles.SCREEN)
  events=gui_app._mouse_events
  try:
    rl.begin_texture_mode(target)
    try:
      rl.clear_background(rl.BLACK)
      gui_app._mouse_events=[]
      original_render()
    finally:
      rl.end_texture_mode()
    image=rl.load_image_from_texture(target.texture)
    try:
      rl.image_flip_vertical(image)
      assert rl.export_image(image,str(args.output/f'{name}.png'))
    finally:
      rl.unload_image(image)
  finally:
    gui_app._mouse_events=events
    rl.unload_render_texture(target)

def steps():
  yield 30
  placed=host._place('park')
  result['placed']=placed
  assert ('models' in placed)==(not enabled),placed
  assert ('op_models' in placed)==enabled,placed
  assert all(e.failures==0 for e in host._entries.values())
  screenshot('tiles')
  host.open_tile('plugins')
  yield 4
  page=host._stack[-1][1]
  assert type(page).__name__=='PluginsPage'
  page._select(next(i for i,(name,_) in enumerate(page.sections) if name=='Perception Models'))
  page.switches.refresh()
  yield 4
  result['page_status']={p.NAME:s[''] for p,_,s in page.switches.items if p.NAME in ('sp_models','op_models')}
  if enabled:
    assert result['page_status']['sp_models']=='conflict'
    assert result['page_status']['op_models']==''
    assert 'op_models' in page.jobs.installed
  screenshot('plugins')
  result['passed']=True
  gui_app.request_close()
  yield 1

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
  assert result['passed']
finally:
  host.render=original_render
  host._show(None)
  (args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
