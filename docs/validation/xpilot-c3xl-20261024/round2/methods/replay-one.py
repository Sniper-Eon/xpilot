"""Failure modes: wrong tree/input/params, production live, missing outputs, un-fed card gate, nondeterministic comparison.
Run repository process_replay without product edits. Outputs are isolated msgq sendcan messages; no pandad or hardware CAN.
"""
import argparse,hashlib,json,os,pickle,subprocess
from collections import Counter
from copy import deepcopy
from pathlib import Path
E=Path('/data/xpilot-X-20261024-08-round2-evidence')
ap=argparse.ArgumentParser()
ap.add_argument('tree',choices=['head','base'])
ap.add_argument('process',choices=['selfdrived','controlsd','card'])
ap.add_argument('--card-unfed',action='store_true')
a=ap.parse_args()
assert subprocess.run(['systemctl','is-active','--quiet','comma']).returncode!=0
assert Path('/data/params/d/IsOffroad').read_bytes()==b'1'
assert Path('/data/params/d/IsEngaged').read_bytes()==b'0'
root=Path.cwd().resolve()
assert root==Path('/data/xpilot-agnos19.9-20261025/candidate' if a.tree=='head' else '/data/xp-replay-base')
os.environ['XPILOT_PLUGINS_DIR']=str(E/'replay-store-empty')
os.environ['PYTHONDONTWRITEBYTECODE']='1'
os.environ['LOG_ROOT']=str(E/'replay-runtime-logs')
from openpilot.common import realtime
online_core=max(os.sched_getaffinity(0))
realtime.set_core_affinity=lambda requested:os.sched_setaffinity(0,{online_core})
from openpilot.common import version
metadata=version.build_metadata_from_dict(json.loads((E/'replay-build-metadata.json').read_text()))
version.get_build_metadata=lambda *args,**kwargs: metadata
from openpilot.selfdrive.test.process_replay.process_replay import get_process_config,replay_process
from openpilot.tools.lib.logreader import LogReader,save_log
cfg=deepcopy(get_process_config(a.process))
if a.process=='selfdrived':
  cfg.subs+=['selfdriveStateSP','onroadEventsSP']
elif a.process=='controlsd':
  cfg.pubs+=['selfdriveStateSP']
  cfg.subs+=['carControlSP']
elif not a.card_unfed:
  cfg.pubs+=['selfdriveState']
# cfg contains the same clock/fingerprint migration logic and native build for both source trees.
lr=list(LogReader(str(E/'tesla-rlog.zst')))
counts=Counter(m.which() for m in lr)
assert counts['carParams'] and counts['can']>5000,counts
# Feed both controller and card from the same base replayed selfdrived outputs; this also supplies CardGate's private SubMaster.
if a.process in ('controlsd','card') and not a.card_unfed:
  prior=list(LogReader(str(E/'replay/base/selfdrived.zst')))
  kinds={'selfdriveState','selfdriveStateSP','onroadEvents','onroadEventsSP'}
  lr=[m for m in lr if m.which() not in kinds]+[m for m in prior if m.which() in kinds]
  lr.sort(key=lambda m:m.logMonoTime)
if a.process=='card' and not a.card_unfed:
  control=list(LogReader(str(E/'replay/base/controlsd.zst')))
  kinds={'carControl','carControlSP','controlsState'}
  lr=[m for m in lr if m.which() not in kinds]+[m for m in control if m.which() in kinds]
  lr.sort(key=lambda m:m.logMonoTime)
  cfg.pubs+=['carControlSP']
params=pickle.loads((E/'replay-params-private.pickle').read_bytes())
out=E/'replay'/a.tree
out.mkdir(parents=True,exist_ok=True)
label=a.process+('-unfed' if a.card_unfed else '')
capture={}
try:
  result=replay_process(cfg,lr,custom_params=params,captured_output_store=capture,disable_progress=True)
finally:
  (out/(label+'-capture.json')).write_text(json.dumps(capture,indent=2)+'\n')
save_log(str(out/(label+'.zst')),result)
r={'tree':a.tree,'process':label,'messages':dict(Counter(m.which() for m in result)),'input_sha256':hashlib.sha256((E/'tesla-rlog.zst').read_bytes()).hexdigest(),'params_sha256':hashlib.sha256((E/'replay-params-private.pickle').read_bytes()).hexdigest(),'cfg_pubs':list(cfg.pubs),'cfg_subs':cfg.subs,'output_sha256':hashlib.sha256((out/(label+'.zst')).read_bytes()).hexdigest()}
(out/(label+'-summary.json')).write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r),flush=True)
