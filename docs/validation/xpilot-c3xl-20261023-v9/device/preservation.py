"""Failures: original dirty file content loss, installed plugin/file drift, non-Alpha param drift,
wrong deployment, service down or unsafe final state. Alpha is intentionally changed in part C.
"""
import base64
import hashlib
import json
from pathlib import Path
import socket
import subprocess
from openpilot.common.params import Params
E=Path('/data/xpilot-X-20261023-16-evidence')
assert socket.gethostname()=='comma-9c13c9f5'
assert Path('/data/hardware_profile').read_text().strip()=='c3xl'
p=Params()
assert p.get_bool('IsOffroad') and not p.get_bool('IsEngaged')
dirty=json.loads((E/'dirty-before.json').read_text())
after={q:hashlib.sha256(Path(q).read_bytes()).hexdigest() for q in dirty}
store=json.loads((E/'store-before.json').read_text())
store_after={str(q):hashlib.sha256(q.read_bytes()).hexdigest() for q in sorted(Path('/data/xpilot_plugins').rglob('*')) if q.is_file()}
saved=json.loads((E/'params-before.json').read_text())
params={}
for key,item in saved.items():
 q=Path(item['path'])
 data=q.read_bytes() if q.exists() else None
 original=base64.b64decode(item['base64']) if item['exists'] else None
 params[key]={'exists':data is not None,'sha256':hashlib.sha256(data).hexdigest() if data is not None else None,'byte_equal':data==original,'intentional_part_C':key=='AlphaLongitudinalEnabled'}
version=json.loads(Path('/data/xpilot_plugins/overspeed_warning/plugin.json').read_text())['version']
result={'dirty_count':len(dirty),'dirty_byte_equal':after==dirty,'store_count_before':len(store),'store_count_after':len(store_after),'store_file_set_and_hash_equal':store==store_after,'overspeed_warning_version':version,'params':params,'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'service':subprocess.check_output(['systemctl','is-active','comma.service'],text=True).strip(),'AlphaLongitudinalEnabled':p.get_bool('AlphaLongitudinalEnabled'),'git_status':subprocess.check_output(['git','status','--short'],text=True)}
result['passed']=after==dirty and store==store_after and version=='1.0.0' and all(v['byte_equal'] for k,v in params.items() if k!='AlphaLongitudinalEnabled') and result['head']=='9258ebcb48981b95c81ff73471efb2979cc63727' and result['service']=='active'
print(json.dumps(result,indent=2),flush=True)
assert result['passed']
