set -eu
cd /data/openpilot
export PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo
export PYTHONDONTWRITEBYTECODE=1
export SUNNYPILOT_HARDWARE_PROFILE=c3xl
E=/data/xpilot-X-20261024-08-evidence
python3 "$E/methods/gate.py" > "$E/gate-pre-checks.json"
sudo systemctl stop comma.service
python3 "$E/methods/panda-read.py" > "$E/panda-pre-checks.json"
python3 "$E/methods/snapshot.py" prechecks-stopped
mkdir -p "$E/checks"
set +e
for script in tools/sp_tesla_e2e/*_check.py tools/sp_tesla_e2e/static_imports.py
 do
 name=$(basename "$script")
 timeout 180 python3 "$script" > "$E/checks/$name.log" 2>&1
 rc=$?
 printf '%s\t%s\n' "$name" "$rc" >> "$E/checks.tsv"
 done
timeout 240 python3 tools/sp_tesla_e2e/big_screen_e2e.py --output "$E/big-screen" > "$E/big-screen.log" 2>&1
printf '%s\t%s\n' big_screen_e2e.py "$?" >> "$E/checks.tsv"
timeout 180 python3 tools/sp_tesla_e2e/store_e2e.py --repo "$E/xpilot-plugins" > "$E/store-e2e.log" 2>&1
printf '%s\t%s\n' store_e2e.py "$?" >> "$E/checks.tsv"
python3 openpilot/tesla/plugins/gen_params.py --check > "$E/gen-params.log" 2>&1
printf '%s\t%s\n' gen_params.py "$?" >> "$E/checks.tsv"
python3 openpilot/tesla/plugins/gen_safety.py --check > "$E/gen-safety.log" 2>&1
printf '%s\t%s\n' gen_safety.py "$?" >> "$E/checks.tsv"
set -e
python3 "$E/methods/restore.py" prechecks-stopped > "$E/params-restored-after-checks.json"
cat "$E/checks.tsv"
