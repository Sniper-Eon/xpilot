set -eu
E=/data/xpilot-X-20261024-08-evidence
cd /data/openpilot
export PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo
export PYTHONDONTWRITEBYTECODE=1
export SUNNYPILOT_HARDWARE_PROFILE=c3xl
test "$(hostname)" = comma-9c13c9f5
test "$(cat /data/hardware_profile)" = c3xl
test "$(cat /data/params/d/IsOffroad)" = 1
test "$(cat /data/params/d/IsEngaged)" = 0
! systemctl is-active --quiet comma
set +e
timeout 90 python3 "$E/methods/overhead.py" > "$E/overhead.log" 2>&1
printf '%s\n' "$?" > "$E/overhead.exit"
timeout 90 python3 "$E/methods/core-ui.py" --output "$E/core-ui" > "$E/core-ui.log" 2>&1
printf '%s\n' "$?" > "$E/core-ui.exit"
set -e
python3 "$E/methods/restore.py" initial > "$E/params-restored-before-rollback.json"
python3 "$E/methods/panda-read.py" > "$E/panda-before-rollback.json"
git checkout --detach 65bb09e3d5d306487d005f15cef799e31cf37fa2
test "$(git rev-parse HEAD)" = 65bb09e3d5d306487d005f15cef799e31cf37fa2
set +e
/usr/bin/time -p scons -j4 > "$E/rollback-build.log" 2>&1
rc=$?
set -e
printf '%s\n' "$rc" > "$E/rollback-build.exit"
test "$rc" = 0
python3 "$E/methods/panda-read.py" > "$E/panda-rollback-build.json"
python3 "$E/methods/restore.py" initial > "$E/params-restored-pre-final-start.json"
test -f /tmp/booted
test "$(cat /data/params/d/IsOffroad)" = 1
test "$(cat /data/params/d/IsEngaged)" = 0
sudo systemctl start comma.service
