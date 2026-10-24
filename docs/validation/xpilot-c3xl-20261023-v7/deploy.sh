set -eu
export PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo
export PYTHONDONTWRITEBYTECODE=1
export PWD=/data/openpilot
cd /data/openpilot
python3 /data/xpilot-ui-check-v7-evidence/preflight.py > /data/xpilot-ui-check-v7-evidence/pre-stop.jsonl
python3 - <<'PY'
import hashlib
from pathlib import Path
assert hashlib.sha256(Path('/data/xpilot-install-20261022/xpilot-20261023-v7.bundle').read_bytes()).hexdigest() == 'f797990c260c631cfece6810666966699a69208fc3b97d6d5ff1b098c66d420d'
PY
git bundle verify /data/xpilot-install-20261022/xpilot-20261023-v7.bundle
test "$(git rev-parse HEAD)" = b3130009d9bd3a61e143bf1e34dd48cc9ef6834f
git fetch /data/xpilot-install-20261022/xpilot-20261023-v7.bundle refs/remotes/origin/xpilot:refs/remotes/origin/xpilot
python3 - <<'PY'
import hashlib,json,subprocess
from pathlib import Path
dirty = subprocess.check_output(['git','ls-files','-m','-o','--exclude-standard','-z']).decode().strip('\0').split('\0')
changed = subprocess.check_output(['git','diff','--name-only','HEAD','cc129b8829c8fd6d170ef75d9857840cb25ed726','-z']).decode().strip('\0').split('\0')
overlap = sorted(set(dirty) & set(changed))
assert not overlap, overlap
data = {q:hashlib.sha256(Path(q).read_bytes()).hexdigest() for q in dirty if q}
Path('/data/xpilot-ui-check-v7-evidence/dirty-before.json').write_text(json.dumps({'files':data,'changed_paths':changed,'overlap':overlap},indent=2)+'\n')
PY
git branch task-X-20261023-10-before HEAD
trap 'python3 /data/xpilot-ui-check-v7-evidence/panda-read.py > /data/xpilot-ui-check-v7-evidence/panda-recovery.json && sudo systemctl start comma.service' EXIT
sudo systemctl stop comma.service
python3 /data/xpilot-ui-check-v7-evidence/panda-read.py > /data/xpilot-ui-check-v7-evidence/panda-pre-deploy.json
git merge --ff-only cc129b8829c8fd6d170ef75d9857840cb25ed726
test "$(git rev-parse HEAD)" = cc129b8829c8fd6d170ef75d9857840cb25ed726
set +e
/usr/bin/time -p scons -C /data/xpilot-install-20261022/candidate -j4 > /data/xpilot-ui-check-v7-evidence/build.log 2>&1
rc=$?
set -e
printf '%s\n' "$rc" > /data/xpilot-ui-check-v7-evidence/build.exit
python3 /data/xpilot-ui-check-v7-evidence/panda-read.py > /data/xpilot-ui-check-v7-evidence/panda-post-build.json
test "$rc" = 0
sudo systemctl start comma.service
trap - EXIT
git rev-parse HEAD
tail -6 /data/xpilot-ui-check-v7-evidence/build.log
