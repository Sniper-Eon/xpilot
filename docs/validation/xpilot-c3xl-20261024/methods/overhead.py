"""Failure modes: unequal SP state/params, fake MADS, latent faults, timing noise, >200us p99 host cost.
Real SP StateMachine + MADS, default role plugins and empty events; 10,000 paired per-call samples, 1,000 warmups.
"""
import gc,json,os,pickle,time,subprocess
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from openpilot.common.params import Params
from openpilot.common.prefix import OpenpilotPrefix
from openpilot.cereal import messaging
from opendbc.car.structs import car
from opendbc.car.car_helpers import interfaces
from openpilot.selfdrive.selfdrived.events import Events
from openpilot.selfdrive.selfdrived.state import StateMachine
from openpilot.sunnypilot.selfdrive.selfdrived.events import EventsSP
from openpilot.sunnypilot.mads.mads import ModularAssistiveDrivingSystem
from openpilot.tesla import core_host,plugins
E=Path('/data/xpilot-X-20261024-08-evidence')
assert subprocess.run(['systemctl','is-active','--quiet','comma']).returncode!=0
assert Path('/data/params/d/IsOffroad').read_bytes()==b'1'
os.environ['XPILOT_PLUGINS_DIR']=str(E/'replay-store-empty')
CI=interfaces['TESLA_MODEL_Y']
CP=CI.get_non_essential_params('TESLA_MODEL_Y')
CP_SP=CI.get_non_essential_params_sp(CP,'TESLA_MODEL_Y')
CS=car.CarState.new_message(vEgo=10,gearShifter='drive',canValid=True)
CS.cruiseState.available=True
with OpenpilotPrefix('X2026102408overhead'):
  p=Params()
  p.put_bool('Mads',True,block=True)
  p.put_bool('MadsMainCruiseAllowed',True,block=True)
  p.put('MadsSteeringMode',0,block=True)
  p.put_bool('DisengageOnAccelerator',False,block=True)
  objects=[]
  for wrapped in (False,True):
    s=SimpleNamespace(CP=CP,CP_SP=CP_SP,params=p,sm={'pandaStates':[]},events=Events(),events_sp=EventsSP(),enabled=False,active=False,initialized=True,CS_prev=CS,state_machine=StateMachine(),update_events=lambda CS:None)
    s.mads=ModularAssistiveDrivingSystem(s)
    if wrapped:
      core_host.install(s)
      assert type(s.state_machine).__name__=='_GuardedStateMachine'
      assert s.mads._inner.enabled_toggle
    objects.append(s)
  def step(s):
    s.enabled,s.active=s.state_machine.update(s.events)
    s.mads.update(CS)
  for _ in range(1000):
    for s in objects:
      step(s)
  samples=[[],[]]
  gc.disable()
  try:
    for i in range(10000):
      for j in ((0,1) if i%2==0 else (1,0)):
        before=time.perf_counter_ns()
        step(objects[j])
        samples[j].append((time.perf_counter_ns()-before)/1000)
  finally:
    gc.enable()
  assert not p.get('XpilotPluginFaults')
  assert all(not s.enabled and not s.active and not s.mads.enabled and not s.mads.active for s in objects)
  stats=lambda xs:{'p50_us':float(np.percentile(xs,50)),'p99_us':float(np.percentile(xs,99))}
  result={'calls_per_variant':10000,'warmups_per_variant':1000,'unit':'us per state_machine.update + mads.update pair','input':'empty Events/EventsSP, disabled, vEgo=10, cruise available, Mads=1; no hardware inputs','bare':stats(samples[0]),'wrapped':stats(samples[1]),'extra':stats([b-a for a,b in zip(*samples)]),'p99_difference_us':stats(samples[1])['p99_us']-stats(samples[0])['p99_us']}
  result['problem']=result['p99_difference_us']>200 or result['extra']['p99_us']>200
  (E/'overhead-samples.json').write_text(json.dumps(samples)+'\n')
  (E/'overhead.json').write_text(json.dumps(result,indent=2)+'\n')
  print(json.dumps(result,indent=2))
