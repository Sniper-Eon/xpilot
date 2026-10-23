set -eu
export PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo
export PYTHONDONTWRITEBYTECODE=1
cd /data/openpilot
test "$(git rev-parse HEAD)" = f7af016516db4043bec0af24e6d3133fd864dfc9
python3 /data/xpilot-ui-check-v8-evidence/preflight.py > /data/xpilot-ui-check-v8-evidence/default-running.jsonl
trap 'python3 /data/xpilot-ui-check-v8-evidence/restore-params.py > /data/xpilot-ui-check-v8-evidence/restore-on-test-exit.json; python3 /data/xpilot-ui-check-v8-evidence/panda-read.py > /data/xpilot-ui-check-v8-evidence/panda-on-test-exit.json && sudo systemctl start comma.service' EXIT
sudo systemctl stop comma.service
python3 /data/xpilot-ui-check-v8-evidence/panda-read.py > /data/xpilot-ui-check-v8-evidence/panda-pre-tests.json
timeout --signal=INT --kill-after=10 60 python3 /data/xpilot-ui-check-v8-evidence/model-ui-e2e.py --state default --output /data/xpilot-ui-check-v8-evidence/default-ui > /data/xpilot-ui-check-v8-evidence/default-ui.log 2>&1
mkdir /data/xpilot-ui-check-v8-evidence/checks
set +e
for f in tools/sp_tesla_e2e/*_check.py
do
  python3 "$f" > "/data/xpilot-ui-check-v8-evidence/checks/$(basename "$f").log" 2>&1
  rc=$?
  printf '%s\t%s\n' "$(basename "$f")" "$rc" >> /data/xpilot-ui-check-v8-evidence/check-exit-codes.tsv
done
timeout --signal=INT --kill-after=10 180 python3 tools/sp_tesla_e2e/big_screen_e2e.py --output /data/xpilot-ui-check-v8 > /data/xpilot-ui-check-v8-evidence/big-screen.log 2>&1
rc=$?
printf '%s\n' "$rc" > /data/xpilot-ui-check-v8-evidence/big-screen.exit
timeout --signal=INT --kill-after=10 120 python3 tools/sp_tesla_e2e/store_e2e.py --repo /data/xpilot-install-20261022/xpilot-X-20261023-11-plugins > /data/xpilot-ui-check-v8-evidence/store-e2e.log 2>&1
rc=$?
printf '%s\n' "$rc" > /data/xpilot-ui-check-v8-evidence/store-e2e.exit
set -e
python3 /data/xpilot-ui-check-v8-evidence/restore-params.py > /data/xpilot-ui-check-v8-evidence/params-restored-after-tests.json
python3 /data/xpilot-ui-check-v8-evidence/panda-read.py > /data/xpilot-ui-check-v8-evidence/panda-after-tests.json
cat /data/xpilot-ui-check-v8-evidence/check-exit-codes.tsv
cat /data/xpilot-ui-check-v8-evidence/big-screen.exit
cat /data/xpilot-ui-check-v8-evidence/store-e2e.exit
trap - EXIT
