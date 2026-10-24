"""Read-only gate: reject wrong identity, stale telemetry, ignition/control/fault, missing manager or plugin faults."""
import json, socket, subprocess, time
from pathlib import Path
from openpilot.common.params import Params
from openpilot.cereal import messaging
assert socket.gethostname() == 'comma-9c13c9f5'
assert Path('/data/hardware_profile').read_text().strip() == 'c3xl'
assert Path('/data/openpilot').resolve() == Path('/data/xpilot-agnos19.9-20261025/candidate')
p=Params()
sm=messaging.SubMaster(['deviceState','pandaStates','managerState'])
rows=[]
end=time.monotonic()+5
while time.monotonic()<end:
  sm.update(100)
  assert p.get_bool('IsOffroad') and not p.get_bool('IsEngaged')
  if sm.seen['deviceState']:
    assert not sm['deviceState'].started
  if sm.updated['pandaStates']:
    row=[{'controlsAllowed':a.controlsAllowed,'faultStatus':str(a.faultStatus),'faults':[str(f) for f in a.faults], 'pandaType':str(a.pandaType),'ignitionLine':a.ignitionLine,'ignitionCan':a.ignitionCan,'safetyModel':str(a.safetyModel)} for a in sm['pandaStates']]
    assert row and all(not a['controlsAllowed'] and a['faultStatus']=='none' and not a['faults'] and not a['ignitionLine'] and not a['ignitionCan'] for a in row),row
    rows.append(row)
assert rows and all(sm.alive.values()),dict(sm.alive)
procs=[{'name':a.name,'running':a.running,'pid':a.pid,'exitCode':a.exitCode} for a in sm['managerState'].processes]
assert len({a['name'] for a in procs})==len(procs)
assert all(next(a for a in procs if a['name']==name)['running'] for name in ('ui','pandad','hardwared','models_manager'))
from openpilot.tesla import plugins
faults=p.get('XpilotPluginFaults')
assert not faults,faults
assert not plugins.LOAD_ERRORS,plugins.LOAD_ERRORS
result={'hostname':socket.gethostname(),'profile':'c3xl','active_path':str(Path('/data/openpilot').resolve()),'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'service':subprocess.check_output(['systemctl','is-active','comma'],text=True).strip(),'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'IsOffroad':p.get_bool('IsOffroad'),'IsEngaged':p.get_bool('IsEngaged'),'started':sm['deviceState'].started,'alive':dict(sm.alive),'panda_samples':rows,'processes':procs,'load_errors':plugins.LOAD_ERRORS,'faults':faults,'owners':{r:plugins.owner(p,r) for r in ('role:engagement.state','role:safety.fallback','role:perception.model')}}
print(json.dumps(result,indent=2))
