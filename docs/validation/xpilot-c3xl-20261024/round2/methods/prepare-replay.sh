set -eu
cd /data/openpilot
export PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo
export PYTHONDONTWRITEBYTECODE=1
export SUNNYPILOT_HARDWARE_PROFILE=c3xl
E=/data/xpilot-X-20261024-08-round2-evidence
test "$(hostname)" = comma-9c13c9f5
test "$(cat /data/hardware_profile)" = c3xl
test "$(cat /data/params/d/IsOffroad)" = 1
test "$(cat /data/params/d/IsEngaged)" = 0
! systemctl is-active --quiet comma
test ! -e /data/xpilot-X-20261024-08-round2-evidence/round1-replay-base
mv /data/xp-replay-base /data/xpilot-X-20261024-08-round2-evidence/round1-replay-base
rsync -a --exclude=.git /data/openpilot/ /data/xp-replay-base/
python3 - <<'PY'
import dataclasses,hashlib,json,pickle,subprocess
from pathlib import Path
from openpilot.common.params import Params
from openpilot.common.version import get_build_metadata
E=Path('/data/xpilot-X-20261024-08-round2-evidence')
root=Path('/data/openpilot')
base=Path('/data/xp-replay-base')
changed=subprocess.check_output(['git','diff','--name-only','65bb09e','4292551111','-z']).decode().strip('\0').split('\0')
proof={}
for name in changed:
  data=subprocess.check_output(['git','show','65bb09e:'+name])
  (base/name).write_bytes(data)
  proof[name]={'base_sha256':hashlib.sha256(data).hexdigest(),'head_sha256':hashlib.sha256((root/name).read_bytes()).hexdigest()}
(E/'base-overwrites.json').write_text(json.dumps(proof,indent=2)+'\n')
native={}
for p in sorted(root.rglob('*')):
  if '.git' in p.relative_to(root).parts or not p.is_file() or p.suffix not in ('.so','.a','.o','.signed'):
    continue
  rel=str(p.relative_to(root))
  a=hashlib.sha256(p.read_bytes()).hexdigest()
  b=hashlib.sha256((base/rel).read_bytes()).hexdigest()
  assert a==b,rel
  native[rel]=a
(E/'native-shared-hashes.json').write_text(json.dumps(native,indent=2)+'\n')
p=Params()
params={}
for key in p.all_keys():
  key=key.decode()
  value=p.get(key)
  if value is not None:
    params[key]=value
# Car identity is constructed by the replay library from the same recorded segment for both trees.
for key in ('CarParams','CarParamsSP','CarParamsCache','CarParamsSPCache','CarParamsPersistent','CarParamsSPPersistent','CarParamsPrevRoute','CarPlatformBundle','ControlsReady','XpilotPluginFaults'):
  params.pop(key,None)
(E/'replay-params-private.pickle').write_bytes(pickle.dumps(params))
(E/'replay-params-proof.json').write_text(json.dumps({'keys':sorted(params),'sha256':hashlib.sha256((E/'replay-params-private.pickle').read_bytes()).hexdigest()},indent=2)+'\n')
(E/'replay-build-metadata.json').write_text(json.dumps(dataclasses.asdict(get_build_metadata()),indent=2)+'\n')
print(json.dumps({'changed_files':len(changed),'native_files_equal':len(native),'params':len(params)}))
PY
