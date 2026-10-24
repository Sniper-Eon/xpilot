set -eu
export PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo
export PYTHONDONTWRITEBYTECODE=1
cd /data/openpilot
test "$(git rev-parse HEAD)" = f7af016516db4043bec0af24e6d3133fd864dfc9
test "$(cat /data/xpilot-ui-check-v8-evidence/big-screen.exit)" = 0
test "$(cat /data/xpilot-ui-check-v8-evidence/store-e2e.exit)" = 0
trap 'sh /data/xpilot-ui-check-v8-evidence/recover.sh > /data/xpilot-ui-check-v8-evidence/recovery.log 2>&1' EXIT
python3 /data/xpilot-ui-check-v8-evidence/panda-read.py > /data/xpilot-ui-check-v8-evidence/panda-pre-install.json
python3 /data/xpilot-ui-check-v8-evidence/store-action.py install-enable > /data/xpilot-ui-check-v8-evidence/install-enable.json
for state in enabled disabled removed
do
  python3 /data/xpilot-ui-check-v8-evidence/panda-read.py > "/data/xpilot-ui-check-v8-evidence/panda-pre-$state-start.json"
  sudo systemctl start comma.service
  python3 /data/xpilot-ui-check-v8-evidence/wait-stable.py > "/data/xpilot-ui-check-v8-evidence/$state-stable.log"
  python3 /data/xpilot-ui-check-v8-evidence/preflight.py > "/data/xpilot-ui-check-v8-evidence/$state-running.jsonl"
  python3 /data/xpilot-ui-check-v8-evidence/record-state.py "$state" > "/data/xpilot-ui-check-v8-evidence/$state-processes.json"
  tmux capture-pane -p -S -2000 -t comma:0.0 > "/data/xpilot-ui-check-v8-evidence/$state-startup.log"
  sudo systemctl stop comma.service
  python3 /data/xpilot-ui-check-v8-evidence/panda-read.py > "/data/xpilot-ui-check-v8-evidence/panda-pre-$state-ui.json"
  timeout --signal=INT --kill-after=10 60 python3 /data/xpilot-ui-check-v8-evidence/model-ui-e2e.py --state "$state" --output "/data/xpilot-ui-check-v8-evidence/$state-ui" > "/data/xpilot-ui-check-v8-evidence/$state-ui.log" 2>&1
  printf '%s\t0\n' "$state" >> /data/xpilot-ui-check-v8-evidence/swap-ui-exit-codes.tsv
  if test "$state" = enabled
  then
    python3 /data/xpilot-ui-check-v8-evidence/store-action.py disable > /data/xpilot-ui-check-v8-evidence/disable.json
  fi
  if test "$state" = disabled
  then
    python3 /data/xpilot-ui-check-v8-evidence/store-action.py uninstall > /data/xpilot-ui-check-v8-evidence/uninstall.json
  fi
done
python3 /data/xpilot-ui-check-v8-evidence/restore-params.py > /data/xpilot-ui-check-v8-evidence/params-restored-pre-final-start.json
python3 /data/xpilot-ui-check-v8-evidence/panda-read.py > /data/xpilot-ui-check-v8-evidence/panda-pre-final-start.json
sudo systemctl start comma.service
python3 /data/xpilot-ui-check-v8-evidence/wait-stable.py > /data/xpilot-ui-check-v8-evidence/final-stable.log
python3 /data/xpilot-ui-check-v8-evidence/restore-params.py > /data/xpilot-ui-check-v8-evidence/params-restored-after-final-start.json
python3 /data/xpilot-ui-check-v8-evidence/preflight.py > /data/xpilot-ui-check-v8-evidence/final.jsonl
trap - EXIT
