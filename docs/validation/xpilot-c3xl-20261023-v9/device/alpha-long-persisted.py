"""Failures: unsafe write, missing/undecodable CarParamsPersistent, failed readback,
UI clears AlphaLongitudinalEnabled, service stops, onroad/control/ignition/fault during the 60 s wait.
No CarParams edits or override of UI constraints. This is the only intentional final parameter change.
"""
import json
from pathlib import Path
import socket
import subprocess
import time
from openpilot.common.params import Params
from openpilot.cereal import messaging
from opendbc.car.structs import car

assert socket.gethostname()=='comma-9c13c9f5'
assert Path('/data/hardware_profile').read_text().strip()=='c3xl'
p=Params()
assert p.get_bool('IsOffroad') and not p.get_bool('IsEngaged')
assert subprocess.check_output(['systemctl','is-active','comma.service'],text=True).strip()=='active'
with car.CarParams.from_bytes(p.get('CarParamsPersistent')) as CP:
 cp={'alphaLongitudinalAvailable':CP.alphaLongitudinalAvailable,'openpilotLongitudinalControl':CP.openpilotLongitudinalControl,'brand':CP.brand,'carFingerprint':CP.carFingerprint}
print(json.dumps({'stage':'before','CarParamsPersistent':cp,'param_bool':p.get_bool('AlphaLongitudinalEnabled'),'param_raw_hex':p.get('AlphaLongitudinalEnabled').hex() if p.get('AlphaLongitudinalEnabled') is not None else None}),flush=True)
assert p.get_bool('IsOffroad') and not p.get_bool('IsEngaged')
p.put_bool('AlphaLongitudinalEnabled',True,block=True)
print(json.dumps({'stage':'immediate','param_bool':p.get_bool('AlphaLongitudinalEnabled'),'param_raw_hex':p.get('AlphaLongitudinalEnabled').hex() if p.get('AlphaLongitudinalEnabled') is not None else None}),flush=True)
assert p.get_bool('AlphaLongitudinalEnabled')
sm=messaging.SubMaster(['deviceState','pandaStates','managerState'])
start=time.monotonic()
rows=0
while time.monotonic()-start<60:
 sm.update(100)
 assert p.get_bool('IsOffroad') and not p.get_bool('IsEngaged')
 if sm.seen['deviceState']: assert not sm['deviceState'].started
 if sm.updated['pandaStates']:
  assert sm['pandaStates'] and all(not a.controlsAllowed and not a.ignitionLine and not a.ignitionCan and str(a.faultStatus)=='none' and not a.faults for a in sm['pandaStates'])
  rows+=1
assert rows and all(sm.alive.values())
service=subprocess.check_output(['systemctl','is-active','comma.service'],text=True).strip()
assert service=='active'
raw=p.get('AlphaLongitudinalEnabled')
print(json.dumps({'stage':'after_60s','elapsed_seconds':time.monotonic()-start,'param_bool':p.get_bool('AlphaLongitudinalEnabled'),'param_raw_hex':raw.hex() if raw is not None else None,'removed':raw is None,'CarParams_present':p.get('CarParams') is not None,'CarParamsPersistent':cp,'panda_samples':rows,'service':service,'alive':dict(sm.alive)}),flush=True)
