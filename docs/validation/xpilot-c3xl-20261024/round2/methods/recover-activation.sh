set -eu
E=/data/xpilot-X-20261024-08-round2-evidence
C=/data/xpilot-agnos19.9-20261025/candidate
test "$(hostname)" = comma-9c13c9f5
test "$(cat /data/hardware_profile)" = c3xl
test "$(cat /data/params/d/IsOffroad)" = 1
test "$(cat /data/params/d/IsEngaged)" = 0
! systemctl is-active --quiet comma
test ! -L /data/openpilot
test "$(git -C /data/openpilot rev-parse HEAD)" = 65bb09e3d5d306487d005f15cef799e31cf37fa2
test "$(git -C "$C" rev-parse HEAD)" = 4292551111be2d7afa7cf9aa158841fb712e740b
test -L /data/safe_staging/old_openpilot
test "$(readlink -f /data/safe_staging/old_openpilot)" = "$C"
test ! -e "$E/automatic-overlay-tree"
mv /data/openpilot "$E/automatic-overlay-tree"
mv /data/safe_staging/old_openpilot /data/openpilot
cd /data/openpilot
export PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo
export PYTHONDONTWRITEBYTECODE=1
export SUNNYPILOT_HARDWARE_PROFILE=c3xl
python3 - <<'PY'
import hashlib,json,subprocess
from pathlib import Path
E=Path('/data/xpilot-X-20261024-08-round2-evidence')
assert Path('/data/openpilot').resolve()==Path('/data/xpilot-agnos19.9-20261025/candidate')
for name,value in json.loads((E/'native-shared-hashes.json').read_text()).items():
 assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==value,name
markers={}
for name in ('.overlay_init','.overlay_consistent'):
 path=Path(name)
 assert subprocess.check_output(['git','ls-files','--',name])==b''
 if path.exists():
  markers[name]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'mtime_ns':path.stat().st_mtime_ns}
  path.rename(E/('quarantined'+name))
(E/'activation-recovery.json').write_text(json.dumps({'restored_link':str(Path('/data/openpilot').resolve()),'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'native_unchanged':True,'quarantined_markers':markers,'saved_activated_tree':str(E/'automatic-overlay-tree')},indent=2)+'\n')
PY
python3 "$E/methods/restore.py" initial > "$E/params-restored-activation-recovery.json"
python3 "$E/methods/panda-final.py" > "$E/panda-activation-recovery.json"
test -f /data/xpilot_plugins/.defaults_done
test ! -s /data/xpilot_plugins/.defaults_done
test -f /tmp/booted
sudo systemctl start comma.service
sleep 25
tmux capture-pane -p -S -600 -t comma:0.0 > "$E/recovered-startup.log"
python3 "$E/methods/gate.py" > "$E/gate-recovered.json"
rm /data/xpilot_plugins/.defaults_done
mv "$E/production.json" "$E/production-first.json"
mv "$E/production-messages.jsonl" "$E/production-first-messages.jsonl"
mv "$E/production-runtime.log" "$E/production-first-runtime.log"
mv "$E/production-startup.log" "$E/production-first-startup.log"
mv "$E/production-end.log" "$E/production-first-end.log"
bash "$E/methods/production.sh"
python3 "$E/methods/gate.py" > "$E/gate-final.json"
python3 "$E/methods/panda-final.py" > "$E/panda-final.json"
python3 "$E/methods/final-preservation.py" > "$E/preservation-final.log"
