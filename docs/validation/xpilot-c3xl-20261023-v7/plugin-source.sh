set -eu
export PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo
export PYTHONDONTWRITEBYTECODE=1
cd /data/openpilot
python3 /data/xpilot-ui-check-v7-evidence/preflight.py > /data/xpilot-ui-check-v7-evidence/pre-source-screenshot.jsonl
trap 'python3 /data/xpilot-ui-check-v7-evidence/restore-params.py > /data/xpilot-ui-check-v7-evidence/source-restore.json; python3 /data/xpilot-ui-check-v7-evidence/panda-read.py > /data/xpilot-ui-check-v7-evidence/source-panda.json && sudo systemctl start comma.service' EXIT
sudo systemctl stop comma.service
set +e
timeout --signal=INT --kill-after=10 60 python3 /data/xpilot-ui-check-v7-evidence/plugin-source-e2e.py > /data/xpilot-ui-check-v7-evidence/plugin-source.log 2>&1
rc=$?
set -e
printf '%s\n' "$rc" > /data/xpilot-ui-check-v7-evidence/plugin-source.exit
python3 /data/xpilot-ui-check-v7-evidence/restore-params.py > /data/xpilot-ui-check-v7-evidence/source-restore.json
python3 /data/xpilot-ui-check-v7-evidence/panda-read.py > /data/xpilot-ui-check-v7-evidence/source-panda.json
sudo systemctl start comma.service
trap - EXIT
sleep 10
python3 /data/xpilot-ui-check-v7-evidence/preflight.py > /data/xpilot-ui-check-v7-evidence/final-after-source.jsonl
exit "$rc"
