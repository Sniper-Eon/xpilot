set -eu
export PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo
export PYTHONDONTWRITEBYTECODE=1
cd /data/openpilot
test "$(git rev-parse HEAD)" = cc129b8829c8fd6d170ef75d9857840cb25ed726
python3 /data/xpilot-ui-check-v7-evidence/preflight.py > /data/xpilot-ui-check-v7-evidence/production-gate.jsonl
tmux capture-pane -p -S -600 -t comma:0.0 > /data/xpilot-ui-check-v7-evidence/production-startup.log
test "$(tmux display-message -p -t comma:0.0 '#{pane_pipe}')" = 0
tmux pipe-pane -t comma:0.0 'cat >> /data/xpilot-ui-check-v7-evidence/ui-runtime.log'
trap 'tmux pipe-pane -t comma:0.0' EXIT
python3 - <<'PY'
import json,subprocess,time
from pathlib import Path
from openpilot.cereal import messaging
from openpilot.common.params import Params
sm=messaging.SubMaster(['deviceState','pandaStates','managerState'])
params=Params()
rows=[]
processes=[]
start=time.monotonic()
while time.monotonic()-start < 60:
 sm.update(100)
 assert params.get_bool('IsOffroad') and not params.get_bool('IsEngaged')
 if sm.seen['deviceState']: assert not sm['deviceState'].started
 if sm.updated['pandaStates']:
  row=[{'controlsAllowed':p.controlsAllowed,'faultStatus':str(p.faultStatus),'faults':[str(f) for f in p.faults]} for p in sm['pandaStates']]
  assert row and all(not p['controlsAllowed'] and p['faultStatus']=='none' and not p['faults'] for p in row)
  rows.append(row)
 if sm.updated['managerState']:
  procs=[{'name':p.name,'pid':p.pid,'running':p.running,'exitCode':p.exitCode} for p in sm['managerState'].processes if p.name in ('ui','pandad','hardwared')]
  assert len(procs)==3 and all(p['running'] and p['exitCode']==0 for p in procs)
  processes.append(procs)
assert rows and processes and all(sm.alive.values())
r={'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'elapsed_seconds':time.monotonic()-start,'panda_sample_count':len(rows),'panda_samples':rows,'process_samples':processes,'alive':dict(sm.alive),'valid':dict(sm.valid),'IsOffroad':params.get_bool('IsOffroad'),'IsEngaged':params.get_bool('IsEngaged'),'started':sm['deviceState'].started,'passed':True}
Path('/data/xpilot-ui-check-v7-evidence/production-runtime.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps({k:v for k,v in r.items() if k not in ('panda_samples','process_samples')}))
PY
tmux pipe-pane -t comma:0.0
trap - EXIT
tmux capture-pane -p -S -600 -t comma:0.0 > /data/xpilot-ui-check-v7-evidence/production-end.log
