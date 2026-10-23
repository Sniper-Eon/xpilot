"""Failures: changed original param bytes/existence, changed dirty/store files or
path set, leftover op_models/ExtOpModels, wrong final commit/service/safety state.
Read only after final restoration and service start.
"""
import base64
import hashlib
import json
from pathlib import Path
import socket
import subprocess
root=Path('/data/xpilot-ui-check-v8-evidence')
assert socket.gethostname()=='comma-9c13c9f5'
assert Path('/data/hardware_profile').read_text().strip()=='c3xl'
before=json.loads((root/'params-before.json').read_text())
params={}
for key,item in before.items():
  p=Path(item['path'])
  value=p.read_bytes() if p.exists() else None
  old=base64.b64decode(item['base64']) if item['exists'] else None
  assert value==old,key
  params[key]={'exists':p.exists(),'sha256':hashlib.sha256(value).hexdigest() if value is not None else None,'byte_equal':True}
store_before=json.loads((root/'store-before.json').read_text())
store_after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path('/data/xpilot_plugins').rglob('*')) if p.is_file()}
assert store_before==store_after,{'changed':sorted(k for k in store_before if store_before[k]!=store_after.get(k)),'added':sorted(set(store_after)-set(store_before)),'removed':sorted(set(store_before)-set(store_after))}
dirty_before=json.loads((root/'dirty-before.json').read_text())['files']
dirty=subprocess.check_output(['git','ls-files','-m','-o','--exclude-standard','-z']).decode().strip('\0').split('\0')
dirty_after={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in dirty if p}
assert dirty_before==dirty_after
assert not Path('/data/xpilot_plugins/op_models').exists()
assert not Path('/data/xpilot_plugins/.params/ExtOpModels').exists()
assert not Path('/data/params/d/ExtOpModels').exists()
final=json.loads((root/'final.jsonl').read_text().splitlines()[0])['runtime_before']
assert final['head']=='f7af016516db4043bec0af24e6d3133fd864dfc9'
assert final['service']=='active' and final['IsOffroad'] and not final['IsEngaged'] and not final['started']
for name in ['models_manager','modeld_warmup','ui','pandad','hardwared']:
  p=next(p for p in final['processes'] if p['name']==name)
  assert p['running'] and p['exitCode']==0,p
print(json.dumps({'passed':True,'params':params,'store_file_count':len(store_after),'store_files_exact':True,'dirty_file_count':len(dirty_after),'dirty_files_exact':True,'op_models_absent':True,'ExtOpModels_absent':True,'final_head':final['head']},indent=2))
