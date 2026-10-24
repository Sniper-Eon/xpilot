"""Failures: real imports fail, unexpected role owners, default install wraps state,
card gate subscribes or blocks, native enum absent, plugin load/fault errors.
No SelfdriveD/Car construction, onroad process, ignition simulation or CAN hooks.
"""
import importlib
import json
from pathlib import Path
import socket
import subprocess
import types
import msgq
import zmq
from openpilot.common.params import Params
from openpilot.cereal import custom
from opendbc.car.structs import car
from openpilot.tesla import plugins

assert socket.gethostname()=='comma-9c13c9f5'
assert Path('/data/hardware_profile').read_text().strip()=='c3xl'
assert Params().get_bool('IsOffroad') and not Params().get_bool('IsEngaged')
p=Params()
raw=p.get('CarParamsPersistent')
assert raw
with car.CarParams.from_bytes(raw) as CP:
 assert CP.brand=='tesla'
 cp={'brand':CP.brand,'carFingerprint':CP.carFingerprint,'alphaLongitudinalAvailable':CP.alphaLongitudinalAvailable,'openpilotLongitudinalControl':CP.openpilotLongitudinalControl}
 owners={r:plugins.owner(p,r) for r in ('role:engagement.state','role:safety.fallback')}
 host=plugins.CarPlugins(CP,p)
 s=types.SimpleNamespace(CP=CP,params=p,state_machine=object(),mads=object(),update_events=lambda CS:None)
 before=(s.state_machine,s.mads,s.update_events)
 plugins.install_core(s)
 noop=all(a is b for a,b in zip(before,(s.state_machine,s.mads,s.update_events)))
 enum=custom.OnroadEventSP.EventName.schema.enumerants['xpilotPluginFault']
 imports=[importlib.import_module(m).__file__ for m in ('openpilot.selfdrive.selfdrived.selfdrived','openpilot.selfdrive.car.card')]
 result={'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'CarParamsPersistent':cp,'owners':owners,'core_alive':host.core_alive(),'gate_sm_is_none':host._gate.sm is None,'install_core_noop':noop,'xpilotPluginFault_enum':enum,'LOAD_ERRORS':plugins.LOAD_ERRORS,'faults':p.get(plugins.FAULTS_PARAM),'imports':imports,'Params_module':Params.__module__,'zmq_path':zmq.__file__,'msgq_path':msgq.__file__,'instantiated_plugins':[c.NAME for c in host.plugins]}
 print(json.dumps(result,indent=2),flush=True)
 assert owners=={'role:engagement.state':'sp_engagement','role:safety.fallback':'sp_safety_fallback'}
 assert host.core_alive() and host._gate.sm is None and noop and enum==29
 assert not plugins.LOAD_ERRORS and not p.get(plugins.FAULTS_PARAM)
