set -eu
export PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo
export PYTHONDONTWRITEBYTECODE=1
cd /data/openpilot
python3 /data/xpilot-ui-check-v8-evidence/preflight.py > /data/xpilot-ui-check-v8-evidence/pre-stop.jsonl
test "$(git rev-parse HEAD)" = cc129b8829c8fd6d170ef75d9857840cb25ed726
python3 - <<'PY'
import hashlib,json,subprocess
from pathlib import Path
assert hashlib.sha256(Path('/data/xpilot-install-20261022/xpilot-X-20261023-11.bundle').read_bytes()).hexdigest() == '427bc2ce36b40bbeec3ebffa347598d05734d99d835f280f80eaf04df4f71a7f'
assert not Path('/data/xpilot_plugins/op_models').exists()
assert not Path('/data/xpilot_plugins/.params/ExtOpModels').exists()
assert not Path('/data/params/d/ExtOpModels').exists()
root=Path('/data/xpilot_plugins')
store={str(q):hashlib.sha256(q.read_bytes()).hexdigest() for q in sorted(root.rglob('*')) if q.is_file()}
Path('/data/xpilot-ui-check-v8-evidence/store-before.json').write_text(json.dumps(store,indent=2)+'\n')
PY
git bundle verify /data/xpilot-install-20261022/xpilot-X-20261023-11.bundle
git fetch /data/xpilot-install-20261022/xpilot-X-20261023-11.bundle refs/remotes/origin/xpilot:refs/remotes/origin/xpilot
python3 - <<'PY'
import hashlib,json,subprocess
from pathlib import Path
dirty=subprocess.check_output(['git','ls-files','-m','-o','--exclude-standard','-z']).decode().strip('\0').split('\0')
changed=subprocess.check_output(['git','diff','--name-only','HEAD','f7af016516db4043bec0af24e6d3133fd864dfc9','-z']).decode().strip('\0').split('\0')
overlap=sorted(set(dirty)&set(changed))
assert not overlap,overlap
data={q:hashlib.sha256(Path(q).read_bytes()).hexdigest() for q in dirty if q}
Path('/data/xpilot-ui-check-v8-evidence/dirty-before.json').write_text(json.dumps({'files':data,'changed_paths':changed,'overlap':overlap},indent=2)+'\n')
PY
git branch task-X-20261023-11-before HEAD
trap 'python3 /data/xpilot-ui-check-v8-evidence/panda-read.py > /data/xpilot-ui-check-v8-evidence/panda-recovery.json && sudo systemctl start comma.service' EXIT
sudo systemctl stop comma.service
python3 /data/xpilot-ui-check-v8-evidence/panda-read.py > /data/xpilot-ui-check-v8-evidence/panda-pre-deploy.json
git merge --ff-only f7af016516db4043bec0af24e6d3133fd864dfc9
test "$(git rev-parse HEAD)" = f7af016516db4043bec0af24e6d3133fd864dfc9
set +e
/usr/bin/time -p scons -C /data/xpilot-install-20261022/candidate -j4 > /data/xpilot-ui-check-v8-evidence/build.log 2>&1
rc=$?
set -e
printf '%s\n' "$rc" > /data/xpilot-ui-check-v8-evidence/build.exit
python3 /data/xpilot-ui-check-v8-evidence/panda-read.py > /data/xpilot-ui-check-v8-evidence/panda-post-build.json
test "$rc" = 0
sudo systemctl start comma.service
trap - EXIT
git rev-parse HEAD
tail -6 /data/xpilot-ui-check-v8-evidence/build.log
