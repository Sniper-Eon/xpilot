set -eu
export PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo
export PYTHONDONTWRITEBYTECODE=1
cd /data/openpilot
test "$(git rev-parse HEAD)" = cc129b8829c8fd6d170ef75d9857840cb25ed726
python3 /data/xpilot-ui-check-v7-evidence/preflight.py > /data/xpilot-ui-check-v7-evidence/pre-tests.jsonl
trap 'python3 /data/xpilot-ui-check-v7-evidence/restore-params.py > /data/xpilot-ui-check-v7-evidence/restore-on-exit.json; python3 /data/xpilot-ui-check-v7-evidence/panda-read.py > /data/xpilot-ui-check-v7-evidence/panda-on-exit.json && sudo systemctl start comma.service' EXIT
sudo systemctl stop comma.service
python3 /data/xpilot-ui-check-v7-evidence/panda-read.py > /data/xpilot-ui-check-v7-evidence/panda-pre-tests.json
mkdir /data/xpilot-ui-check-v7-evidence/checks
mkdir /data/xpilot-ui-check-v7-tiles
set +e
for f in tools/sp_tesla_e2e/*_check.py
do
  python3 "$f" > "/data/xpilot-ui-check-v7-evidence/checks/$(basename "$f").log" 2>&1
  rc=$?
  printf '%s\t%s\n' "$(basename "$f")" "$rc" >> /data/xpilot-ui-check-v7-evidence/check-exit-codes.tsv
done
timeout --signal=INT --kill-after=10 180 python3 tools/sp_tesla_e2e/big_screen_e2e.py --output /data/xpilot-ui-check-v7 > /data/xpilot-ui-check-v7-evidence/big-screen.log 2>&1
rc=$?
printf '%s\n' "$rc" > /data/xpilot-ui-check-v7-evidence/big-screen.exit
for tile in clock ip map car speed_card lead_card bms plugins tesla
do
  timeout --signal=INT --kill-after=10 60 python3 /data/xpilot-ui-check-v7-evidence/tile_size_e2e.py --tiles "$tile" --output "/data/xpilot-ui-check-v7-tiles/$tile" > "/data/xpilot-ui-check-v7-evidence/tile-size-$tile.log" 2>&1
  rc=$?
  printf '%s\t%s\n' "$tile" "$rc" >> /data/xpilot-ui-check-v7-evidence/tile-exit-codes.tsv
done
set -e
test ! -e tools/sp_tesla_e2e/ui_smoke.py
printf 'removed; not executed\n' > /data/xpilot-ui-check-v7-evidence/ui-smoke-status.txt
python3 /data/xpilot-ui-check-v7-evidence/restore-params.py > /data/xpilot-ui-check-v7-evidence/params-restored.json
python3 /data/xpilot-ui-check-v7-evidence/panda-read.py > /data/xpilot-ui-check-v7-evidence/panda-final-stopped.json
sudo systemctl start comma.service
trap - EXIT
python3 /data/xpilot-ui-check-v7-evidence/preflight.py > /data/xpilot-ui-check-v7-evidence/final.jsonl
cat /data/xpilot-ui-check-v7-evidence/check-exit-codes.tsv
cat /data/xpilot-ui-check-v7-evidence/big-screen.exit
cat /data/xpilot-ui-check-v7-evidence/tile-exit-codes.tsv
