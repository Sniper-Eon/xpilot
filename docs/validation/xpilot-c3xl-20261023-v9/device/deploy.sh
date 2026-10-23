set -eu
export PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo
export PYTHONDONTWRITEBYTECODE=1
E=/data/xpilot-X-20261023-16-evidence
cd /data/openpilot
test "$(hostname)" = comma-9c13c9f5
test "$(cat /data/hardware_profile)" = c3xl
test "$(cat /data/params/d/IsOffroad)" = 1
test "$(cat /data/params/d/IsEngaged)" = 0
python3 "$E/preflight.py" > "$E/pre-stop.jsonl"
test "$(git rev-parse HEAD)" = f7af016516db4043bec0af24e6d3133fd864dfc9
python3 - <<'PY'
import hashlib,json,subprocess
from pathlib import Path
E=Path('/data/xpilot-X-20261023-16-evidence')
assert Path('/data/params/d/IsOffroad').read_bytes()==b'1'
assert hashlib.sha256((E/'target.bundle').read_bytes()).hexdigest()=='da5e03c53e90025a551dd9d0bf35b6c2c5c960e790432d4303d9ae9c4eb6aad5'
dirty=subprocess.check_output(['git','ls-files','-m','-o','--exclude-standard','-z']).decode().strip('\0').split('\0')
files={q:hashlib.sha256(Path(q).read_bytes()).hexdigest() for q in dirty if q}
(E/'dirty-before.json').write_text(json.dumps(files,indent=2)+'\n')
store={str(q):hashlib.sha256(q.read_bytes()).hexdigest() for q in sorted(Path('/data/xpilot_plugins').rglob('*')) if q.is_file()}
(E/'store-before.json').write_text(json.dumps(store,indent=2)+'\n')
print('dirty_count',len(files),'store_files',len(store))
PY
test "$(cat /data/params/d/IsOffroad)" = 1
git bundle verify "$E/target.bundle"
git fetch "$E/target.bundle" refs/remotes/origin/xpilot:refs/remotes/origin/xpilot
python3 - <<'PY'
import json,subprocess
from pathlib import Path
E=Path('/data/xpilot-X-20261023-16-evidence')
dirty=json.loads((E/'dirty-before.json').read_text())
changed=subprocess.check_output(['git','diff','--name-only','HEAD','9258ebcb48981b95c81ff73471efb2979cc63727','-z']).decode().strip('\0').split('\0')
overlap=sorted(set(dirty)&set(changed))
assert Path('/data/params/d/IsOffroad').read_bytes()==b'1'
(E/'update-paths.json').write_text(json.dumps({'changed':changed,'overlap':overlap},indent=2)+'\n')
assert not overlap,overlap
PY
test "$(cat /data/params/d/IsOffroad)" = 1
git branch task-X-20261023-16-before HEAD
trap 'test "$(cat /data/params/d/IsOffroad)" = 1 && python3 "$E/restore-params.py" > "$E/params-restored-on-deploy-exit.json" && python3 "$E/panda-read.py" > "$E/panda-recovery.json" && sudo systemctl start comma.service' EXIT
test "$(cat /data/params/d/IsOffroad)" = 1
sudo systemctl stop comma.service
python3 "$E/panda-read.py" > "$E/panda-pre-deploy.json"
test "$(cat /data/params/d/IsOffroad)" = 1
git merge --ff-only 9258ebcb48981b95c81ff73471efb2979cc63727
test "$(git rev-parse HEAD)" = 9258ebcb48981b95c81ff73471efb2979cc63727
test "$(cat /data/params/d/IsOffroad)" = 1
set +e
/usr/bin/time -p scons -C /data/xpilot-install-20261022/candidate -j4 > "$E/build.log" 2>&1
rc=$?
set -e
printf '%s\n' "$rc" > "$E/build.exit"
python3 "$E/panda-read.py" > "$E/panda-post-build.json"
test "$rc" = 0
test "$(cat /data/params/d/IsOffroad)" = 1
sudo systemctl start comma.service
trap - EXIT
python3 "$E/wait-stable.py" > "$E/post-build-stable.log"
python3 "$E/preflight.py" > "$E/post-build-running.jsonl"
git rev-parse HEAD
tail -10 "$E/build.log"
