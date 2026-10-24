"""Read-only final preservation proof; record all differences and distinguish manager-generated metadata from user configuration."""
import base64,hashlib,json,subprocess
from pathlib import Path
from openpilot.common.params import Params
E=Path('/data/xpilot-X-20261024-08-evidence')
saved=json.loads((E/'initial-private.json').read_text())
current={str(q):q.read_bytes() for root in (Path('/data/params/d'),Path('/data/xpilot_plugins/.params')) for q in root.rglob('*') if q.is_file()}
delta={}
for name in sorted(set(saved)|set(current)):
  original=base64.b64decode(saved[name]['base64']) if name in saved else None
  actual=current.get(name)
  if original!=actual:
    delta[name]={'before_sha256':hashlib.sha256(original).hexdigest() if original is not None else None,'after_sha256':hashlib.sha256(actual).hexdigest() if actual is not None else None}
store={str(q):hashlib.sha256(q.read_bytes()).hexdigest() for q in sorted(Path('/data/xpilot_plugins').rglob('*')) if q.is_file() and '.params' not in q.parts}
assert store==json.loads((E/'initial-store.json').read_text()),store
dirty=json.loads((E/'dirty-before.json').read_text())
assert all(hashlib.sha256(Path(name).read_bytes()).hexdigest()==value for name,value in dirty.items())
status=subprocess.check_output(['git','status','--porcelain'],text=True)
assert status.strip()=='?? prebuilt',status
p=Params()
import re
persistent=set(re.findall(r'\{"([^"]+)", \{[^}]*PERSISTENT',Path('openpilot/common/params_keys.h').read_text()))
persistent_deltas=[path for path in delta if Path(path).name in persistent or path.startswith('/data/xpilot_plugins/')]
r={'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'service':subprocess.check_output(['systemctl','is-active','comma'],text=True).strip(),'all_params_restored_before_start':json.loads((E/'params-restored-final-start.json').read_text())['byte_equal'],'original_count':len(saved),'current_count':len(current),'final_deltas':delta,'persistent_deltas':persistent_deltas,'store_unchanged':True,'store_files':len(store),'dirty_unchanged':True,'dirty_status':status}
(E/'preservation-final.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2))
runtime={'LastUpdateTime','UpdaterLastFetchTime','BootCount','CurrentBootlog','UptimeOffroad','LastUpdateException','UpdateFailedCount','UpdaterAvailableBranches','UpdaterCurrentDescription','UpdaterFetchAvailable','UpdaterNewDescription','UpdaterNewReleaseNotes','Offroad_TiciSupport'}
assert not [path for path in delta if Path(path).name not in runtime],delta
