set -eu
export PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONDONTWRITEBYTECODE=1
export SUNNYPILOT_HARDWARE_PROFILE=c3xl
E=/data/xpilot-X-20261024-08-evidence
for tree in base head
 do
 if test "$tree" = base
 then
 root=/data/xp-replay-base
 else
 root=/data/xpilot-agnos19.9-20261025/candidate
 fi
 cd "$root"
 export PYTHONPATH=$root:$root/opendbc_repo:$root/msgq_repo:$root/tinygrad_repo:$root/rednose_repo
 for process in selfdrived controlsd card
 do
 mkdir -p "$E/replay/$tree"
 set +e
 timeout 300 python3 "$E/methods/replay-one.py" "$tree" "$process" > "$E/replay/$tree/$process.log" 2>&1
 rc=$?
 set -e
 printf '%s\t%s\t%s\n' "$tree" "$process" "$rc" >> "$E/replay-rc.tsv"
 test "$rc" = 0
 done
 done
cd /data/openpilot
export PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo
set +e
python3 "$E/methods/compare-replay.py" > "$E/replay-comparison.log" 2>&1
rc=$?
set -e
printf '%s\n' "$rc" > "$E/replay-comparison.exit"
