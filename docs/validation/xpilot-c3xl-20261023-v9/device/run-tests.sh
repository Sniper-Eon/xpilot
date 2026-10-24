set -eu
export PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo
export PYTHONDONTWRITEBYTECODE=1
E=/data/xpilot-X-20261023-16-evidence
cd /data/openpilot
test "$(hostname)" = comma-9c13c9f5
test "$(cat /data/hardware_profile)" = c3xl
test "$(git rev-parse HEAD)" = 9258ebcb48981b95c81ff73471efb2979cc63727
test "$(cat /data/params/d/IsOffroad)" = 1
python3 "$E/preflight.py" > "$E/pre-tests-running.jsonl"
trap 'test "$(cat /data/params/d/IsOffroad)" = 1 && python3 "$E/restore-params.py" > "$E/params-restored-on-test-exit.json" && python3 "$E/panda-read.py" > "$E/panda-on-test-exit.json" && sudo systemctl start comma.service' EXIT
test "$(cat /data/params/d/IsOffroad)" = 1
sudo systemctl stop comma.service
python3 "$E/panda-read.py" > "$E/panda-pre-tests.json"
test "$(cat /data/params/d/IsOffroad)" = 1
mkdir "$E/checks"
set +e
for f in tools/sp_tesla_e2e/*_check.py
do
  test "$(cat /data/params/d/IsOffroad)" = 1 || exit 91
  timeout --signal=INT --kill-after=10 120 python3 "$f" > "$E/checks/$(basename "$f").log" 2>&1
  rc=$?
  printf '%s\t%s\n' "$(basename "$f")" "$rc" >> "$E/check-exit-codes.tsv"
done
test "$(cat /data/params/d/IsOffroad)" = 1 || exit 91
timeout --signal=INT --kill-after=10 180 python3 tools/sp_tesla_e2e/big_screen_e2e.py --output /data/xpilot-ui-check-v9 > "$E/big-screen.log" 2>&1
rc=$?
printf '%s\n' "$rc" > "$E/big-screen.exit"
test "$(cat /data/params/d/IsOffroad)" = 1 || exit 91
timeout --signal=INT --kill-after=10 120 python3 tools/sp_tesla_e2e/store_e2e.py --repo "$E/xpilot-plugins" > "$E/store-e2e.log" 2>&1
rc=$?
printf '%s\n' "$rc" > "$E/store-e2e.exit"
test "$(cat /data/params/d/IsOffroad)" = 1 || exit 91
python3 "$E/default-path.py" > "$E/default-path.json" 2> "$E/default-path.stderr"
rc=$?
printf '%s\n' "$rc" > "$E/default-path.exit"
test "$(cat /data/params/d/IsOffroad)" = 1 || exit 91
timeout --signal=INT --kill-after=10 90 python3 "$E/core-ui-e2e.py" --output "$E/core-ui" > "$E/core-ui.log" 2>&1
rc=$?
printf '%s\n' "$rc" > "$E/core-ui.exit"
set -e
python3 "$E/restore-params.py" > "$E/params-restored-after-tests.json"
python3 "$E/panda-read.py" > "$E/panda-after-tests.json"
test "$(cat /data/params/d/IsOffroad)" = 1
sudo systemctl start comma.service
trap - EXIT
python3 "$E/wait-stable.py" > "$E/final-stable.log"
python3 "$E/restore-params.py" > "$E/params-restored-after-final-start.json"
python3 "$E/preflight.py" > "$E/final-before-alpha.jsonl"
cat "$E/check-exit-codes.tsv"
cat "$E/big-screen.exit"
cat "$E/store-e2e.exit"
cat "$E/default-path.exit"
cat "$E/core-ui.exit"
