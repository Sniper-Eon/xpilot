"""120s production proof: continuous real safety/process/fault samples and logMessage/errorLog, no mutations."""
import json,time
from pathlib import Path
from openpilot.cereal import messaging
from openpilot.common.params import Params
E=Path('/data/xpilot-X-20261024-08-round2-evidence')
p=Params()
sm=messaging.SubMaster(['deviceState','pandaStates','managerState'])
logs=[messaging.sub_sock(s) for s in ('logMessage','errorLog')]
base=json.loads((E/'gate-before.json').read_text())
expected={a['name'] for a in base['processes'] if a['running']}
rows=[]
errors=[]
start=time.monotonic()
with (E/'production-messages.jsonl').open('w') as output:
  while time.monotonic()-start<120:
    sm.update(100)
    for sock in logs:
      for m in messaging.drain_sock(sock):
        output.write(json.dumps(m.to_dict())+'\n')
    faults=p.get('XpilotPluginFaults')
    assert p.get_bool('IsOffroad') and not p.get_bool('IsEngaged')
    assert not faults,faults
    if sm.seen['deviceState']:
      assert not sm['deviceState'].started
    if sm.updated['pandaStates']:
      ps=[{'controlsAllowed':a.controlsAllowed,'ignitionLine':a.ignitionLine,'ignitionCan':a.ignitionCan,'faultStatus':str(a.faultStatus),'faults':[str(f) for f in a.faults]} for a in sm['pandaStates']]
      assert ps and all(not a['controlsAllowed'] and not a['ignitionLine'] and not a['ignitionCan'] and a['faultStatus']=='none' and not a['faults'] for a in ps)
    if sm.updated['managerState']:
      procs=[{'name':a.name,'running':a.running,'pid':a.pid,'exitCode':a.exitCode} for a in sm['managerState'].processes]
      assert len({a['name'] for a in procs})==len(procs)
      running={a['name'] for a in procs if a['running']}
      assert expected<=running,expected-running
      assert all(a['exitCode']==0 for a in procs if a['running'])
      rows.append({'elapsed':time.monotonic()-start,'processes':procs,'panda':ps})
assert rows and all(sm.alive.values()),dict(sm.alive)
result={'elapsed_seconds':time.monotonic()-start,'manager_samples':len(rows),'expected_running':sorted(expected),'alive':dict(sm.alive),'samples':rows,'passed':True}
(E/'production.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='samples'}),flush=True)
