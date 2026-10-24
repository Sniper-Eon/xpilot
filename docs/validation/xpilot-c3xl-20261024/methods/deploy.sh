set -eu
export PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo
export PYTHONDONTWRITEBYTECODE=1
export SUNNYPILOT_HARDWARE_PROFILE=c3xl
E=/data/xpilot-X-20261024-08-evidence
cd /data/openpilot
test "$(hostname)" = comma-9c13c9f5
test "$(cat /data/hardware_profile)" = c3xl
test "$(git rev-parse HEAD)" = 65bb09e3d5d306487d005f15cef799e31cf37fa2
python3 "$E/methods/gate.py" > "$E/gate-pre-stop.json"
python3 "$E/methods/snapshot.py" initial
python3 "$E/methods/names.py" > "$E/names-base.json"
git bundle verify "$E/target.bundle"
git fetch "$E/target.bundle" refs/remotes/xpilot/task/X-20261024-int:refs/task/X-20261024-08-target
python3 - <<'PY'
import hashlib,json,subprocess
from pathlib import Path
E=Path('/data/xpilot-X-20261024-08-evidence')
dirty=[p for p in subprocess.check_output(['git','ls-files','-m','-o','--exclude-standard','-z']).decode().split('\0') if p]
changed=subprocess.check_output(['git','diff','--name-only','HEAD','369b1e95c83f2e35530129d385fab44bedbce03e','-z']).decode().split('\0')
assert not set(dirty)&set(changed)
assert not any(p.startswith(('panda/','opendbc_repo/','openpilot/cereal/')) or p.endswith(('.c','.cc','.cpp','.cxx','.h','.hpp','.capnp')) for p in changed)
(E/'dirty-before.json').write_text(json.dumps({p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in dirty},indent=2)+'\n')
(E/'device-before.txt').write_text(subprocess.check_output(['git','rev-parse','HEAD'],text=True))
print(json.dumps({'dirty':dirty,'changed':changed,'overlap':[]}))
PY
git branch task-X-20261024-08-before HEAD
test "$(cat /data/params/d/IsOffroad)" = 1
test "$(cat /data/params/d/IsEngaged)" = 0
sudo systemctl stop comma.service
python3 "$E/methods/panda-read.py" > "$E/panda-pre-deploy.json"
python3 "$E/methods/snapshot.py" predeploy-stopped
git merge --ff-only 369b1e95c83f2e35530129d385fab44bedbce03e
test "$(git rev-parse HEAD)" = 369b1e95c83f2e35530129d385fab44bedbce03e
set +e
/usr/bin/time -p scons -j4 > "$E/build.log" 2>&1
rc=$?
set -e
printf '%s\n' "$rc" > "$E/build.exit"
test "$rc" = 0
python3 "$E/methods/panda-read.py" > "$E/panda-post-build.json"
python3 "$E/methods/names.py" > "$E/names-head.json"
python3 - <<'PY'
import json
from pathlib import Path
E=Path('/data/xpilot-X-20261024-08-evidence')
a=json.loads((E/'names-base.json').read_text())
b=json.loads((E/'names-head.json').read_text())
assert a==b,(a,b)
PY
test "$(cat /data/params/d/IsOffroad)" = 1
test "$(cat /data/params/d/IsEngaged)" = 0
sudo systemctl start comma.service
