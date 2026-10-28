set -eu
export PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo
export PYTHONDONTWRITEBYTECODE=1
export SUNNYPILOT_HARDWARE_PROFILE=c3xl
E=/data/xpilot-X-20261024-08-round2-evidence
cd /data/openpilot
test "$(git rev-parse HEAD)" = 65bb09e3d5d306487d005f15cef799e31cf37fa2
python3 "$E/methods/gate.py" > "$E/gate-pre-deploy.json"
git bundle verify "$E/target.bundle"
git fetch "$E/target.bundle" refs/remotes/xpilot/task/X-20261024-int:refs/task/X-20261024-08-round2-target
python3 - <<'PY'
import hashlib,json,subprocess
from pathlib import Path
E=Path('/data/xpilot-X-20261024-08-round2-evidence')
dirty=json.loads((E/'dirty-before.json').read_text())
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in dirty.items())
changed=[p for p in subprocess.check_output(['git','diff','--name-only','65bb09e','4292551111','-z']).decode().split('\0') if p]
assert not set(dirty)&set(changed)
assert not any(p.startswith(('panda/','opendbc_repo/','openpilot/cereal/')) or p.endswith(('.c','.h','.cc','.cpp','.cxx','.hpp','.capnp')) for p in changed)
print(json.dumps({'changed':changed,'dirty_overlap':[]}))
PY
git branch task-X-20261024-08-round2-before HEAD
test "$(cat /data/params/d/IsOffroad)" = 1
test "$(cat /data/params/d/IsEngaged)" = 0
sudo systemctl stop comma.service
python3 "$E/methods/panda-read.py" > "$E/panda-pre-deploy.json"
python3 "$E/methods/snapshot.py" predeploy-stopped
git merge --ff-only 4292551111be2d7afa7cf9aa158841fb712e740b
test "$(git rev-parse HEAD)" = 4292551111be2d7afa7cf9aa158841fb712e740b
set +e
/usr/bin/time -p scons -j4 > "$E/build.log" 2>&1
rc=$?
set -e
printf '%s\n' "$rc" > "$E/build.exit"
test "$rc" = 0
python3 "$E/methods/panda-final.py" > "$E/panda-post-build.json"
cd /data/openpilot/openpilot/system/manager
python3 "$E/methods/names.py" > "$E/names-head.json"
cd /data/openpilot
python3 - <<'PY'
import json
from pathlib import Path
E=Path('/data/xpilot-X-20261024-08-round2-evidence')
a=json.loads((E/'names-base.json').read_text())
b=json.loads((E/'names-head.json').read_text())
assert a==b and len(a['names'])==47,(a,b)
PY
test ! -e /data/xpilot_plugins/.defaults_done
touch /data/xpilot_plugins/.defaults_done
cat /sys/class/input/input2/device/touch_count > "$E/head-touch-count.txt"
test -f /tmp/booted
sudo systemctl start comma.service
sleep 20
tmux capture-pane -p -S -600 -t comma:0.0 > "$E/head-startup.log"
python3 "$E/methods/gate.py" > "$E/gate-head.json"
