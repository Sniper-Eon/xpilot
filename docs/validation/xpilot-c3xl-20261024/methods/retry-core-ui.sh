set -eu
E=/data/xpilot-X-20261024-08-evidence
cd /data/openpilot
export PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo
export PYTHONDONTWRITEBYTECODE=1
export SUNNYPILOT_HARDWARE_PROFILE=c3xl
python3 "$E/methods/gate.py" > "$E/gate-rollback-before-ui.json"
test ! -e "$E/head-ui-tree"
cp -al /data/xp-replay-base "$E/head-ui-tree"
python3 - <<'PY'
import hashlib,json,subprocess,tempfile
from pathlib import Path
E=Path('/data/xpilot-X-20261024-08-evidence')
proof=json.loads((E/'base-overwrites.json').read_text())
for name,hashes in proof.items():
  data=subprocess.check_output(['git','show','369b1e95c83f2e35530129d385fab44bedbce03e:'+name])
  assert hashlib.sha256(data).hexdigest()==hashes['head_sha256']
  p=E/'head-ui-tree'/name
  with tempfile.NamedTemporaryFile(dir=p.parent,delete=False) as f:
    f.write(data)
  Path(f.name).replace(p)
  assert hashlib.sha256((Path('/data/xp-replay-base')/name).read_bytes()).hexdigest()==hashes['base_sha256']
print('head-ui-tree: 22 exact target files, base copy preserved')
PY
mv "$E/core-ui" "$E/core-ui-attempt1"
mv "$E/core-ui.log" "$E/core-ui-attempt1.log"
mv "$E/core-ui.exit" "$E/core-ui-attempt1.exit"
test "$(cat /data/params/d/IsOffroad)" = 1
test "$(cat /data/params/d/IsEngaged)" = 0
sudo systemctl stop comma.service
python3 "$E/methods/snapshot.py" pre-ui-retry
trap 'cd /data/openpilot; export PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo; python3 "$E/methods/restore.py" pre-ui-retry > "$E/params-restored-after-ui.json"; python3 "$E/methods/panda-read.py" > "$E/panda-after-ui.json" && sudo systemctl start comma.service' EXIT
cd "$E/head-ui-tree"
export PYTHONPATH=$E/head-ui-tree:$E/head-ui-tree/opendbc_repo:$E/head-ui-tree/msgq_repo:$E/head-ui-tree/tinygrad_repo:$E/head-ui-tree/rednose_repo
set +e
timeout 90 python3 "$E/methods/core-ui.py" --output "$E/core-ui" > "$E/core-ui.log" 2>&1
rc=$?
set -e
printf '%s\n' "$rc" > "$E/core-ui.exit"
