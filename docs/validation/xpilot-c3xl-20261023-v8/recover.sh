set -eu
export PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo
export PYTHONDONTWRITEBYTECODE=1
cd /data/openpilot
sudo systemctl stop comma.service
python3 /data/xpilot-ui-check-v8-evidence/panda-read.py > /data/xpilot-ui-check-v8-evidence/panda-recover-swap.json
python3 - <<'PY'
import socket
from pathlib import Path
from openpilot.common.params import Params
from openpilot.tesla import store
from openpilot.tesla.plugin_params import ParamsView
assert socket.gethostname()=='comma-9c13c9f5'
assert Path('/data/hardware_profile').read_text().strip()=='c3xl'
assert Params().get_bool('IsOffroad') and not Params().get_bool('IsEngaged')
ParamsView(Params(),{'ExtOpModels':{'type':'BOOL','default':'0'}}).remove('ExtOpModels')
store.uninstall('op_models')
PY
python3 /data/xpilot-ui-check-v8-evidence/restore-params.py > /data/xpilot-ui-check-v8-evidence/restore-on-swap-failure.json
sudo systemctl start comma.service
python3 /data/xpilot-ui-check-v8-evidence/wait-stable.py
python3 /data/xpilot-ui-check-v8-evidence/restore-params.py > /data/xpilot-ui-check-v8-evidence/restore-after-recovery-start.json
python3 /data/xpilot-ui-check-v8-evidence/preflight.py > /data/xpilot-ui-check-v8-evidence/recovery-final.jsonl
