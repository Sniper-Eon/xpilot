set -eu
E=/data/xpilot-X-20261024-08-round2-evidence
cd /data/openpilot
export PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo
export PYTHONDONTWRITEBYTECODE=1
export SUNNYPILOT_HARDWARE_PROFILE=c3xl
test "$(git rev-parse HEAD)" = 65bb09e3d5d306487d005f15cef799e31cf37fa2
python3 "$E/methods/gate.py" > "$E/gate-before.json"
python3 "$E/methods/panda-final.py" > "$E/panda-before.json"
python3 "$E/methods/snapshot.py" initial
python3 - <<'PY'
import hashlib,json,subprocess
from pathlib import Path
E=Path('/data/xpilot-X-20261024-08-round2-evidence')
files=[p for p in subprocess.check_output(['git','ls-files','-m','-o','--exclude-standard','-z']).decode().split('\0') if p]
assert files==['prebuilt'],files
(E/'dirty-before.json').write_text(json.dumps({p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in files},indent=2)+'\n')
(E/'device-before.txt').write_text(subprocess.check_output(['git','rev-parse','HEAD'],text=True))
(E/'store-marker-before.json').write_text(json.dumps({'exists':Path('/data/xpilot_plugins/.defaults_done').exists()})+'\n')
assert not Path('/data/xpilot_plugins/.defaults_done').exists()
(E/'base-big-screen-source.sha256').write_text(hashlib.sha256(Path('tools/sp_tesla_e2e/big_screen_e2e.py').read_bytes()).hexdigest()+'\n')
PY
cd /data/openpilot/openpilot/system/manager
python3 "$E/methods/names.py" > "$E/names-base.json"
cd /data/openpilot
test "$(cat /data/params/d/IsOffroad)" = 1
test "$(cat /data/params/d/IsEngaged)" = 0
sudo systemctl stop comma.service
python3 "$E/methods/snapshot.py" pre-base-ui
python3 "$E/methods/panda-read.py" > "$E/panda-base-ui.json"
set +e
timeout 240 python3 tools/sp_tesla_e2e/big_screen_e2e.py --output "$E/base-big-screen" > "$E/base-big-screen.log" 2>&1
rc=$?
set -e
printf '%s\n' "$rc" > "$E/base-big-screen.exit"
python3 "$E/methods/restore.py" pre-base-ui > "$E/params-restored-base-ui.json"
test ! -e /data/xpilot_plugins/.defaults_done
touch /data/xpilot_plugins/.defaults_done
python3 "$E/methods/panda-read.py" > "$E/panda-base-start.json"
test -f /tmp/booted
cat /sys/class/input/input2/device/touch_count > "$E/base-touch-count.txt"
sudo systemctl start comma.service
sleep 8
tmux capture-pane -p -S -500 -t comma:0.0 > "$E/base-startup.log"
python3 "$E/methods/gate.py" > "$E/gate-base-restarted.json"
rm /data/xpilot_plugins/.defaults_done
