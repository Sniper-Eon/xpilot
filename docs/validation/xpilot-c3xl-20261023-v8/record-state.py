"""Failures: wrong role, load errors, missing SP offroad processes or unexpected
SP/op inference process in any parked state. Runtime evidence, not predicates.
"""
import json
from pathlib import Path
import subprocess
import sys
from openpilot.common.params import Params
from openpilot.tesla import plugins
state=sys.argv[1]
root=Path('/data/xpilot-ui-check-v8-evidence')
runtime=json.loads((root/f'{state}-running.jsonl').read_text().splitlines()[0])['runtime_before']
assert runtime['head']=='f7af016516db4043bec0af24e6d3133fd864dfc9'
assert runtime['service']=='active' and runtime['IsOffroad'] and not runtime['IsEngaged'] and not runtime['started']
procs={p['name']:p for p in runtime['processes']}
enabled=state=='enabled'
for name in ['models_manager','modeld_warmup']:
  assert procs[name]['running']==(not enabled),procs[name]
for name in ['modeld','modeld_tinygrad','op_modeld']:
  assert name not in procs or not procs[name]['running'],procs.get(name)
for name in ['ui','pandad','hardwared']:
  assert procs[name]['running'] and procs[name]['exitCode']==0,procs[name]
assert not plugins.LOAD_ERRORS,plugins.LOAD_ERRORS
assert not Params().get(plugins.FAULTS_PARAM)
owner=plugins.owner(Params(),'role:perception.model')
assert owner==('op_models' if enabled else 'sp_models')
(root/f'{state}-ps.txt').write_text(subprocess.check_output(['ps','-eo','pid,ppid,comm,args'],text=True))
print(json.dumps({'state':state,'owner':owner,'processes':runtime['processes'],'load_errors':plugins.LOAD_ERRORS,'passed':True},indent=2))
