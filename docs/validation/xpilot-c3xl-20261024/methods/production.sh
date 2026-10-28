set -eu
cd /data/openpilot
export PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo
export PYTHONDONTWRITEBYTECODE=1
export SUNNYPILOT_HARDWARE_PROFILE=c3xl
E=/data/xpilot-X-20261024-08-evidence
python3 "$E/methods/gate.py" > "$E/gate-head.json"
test "$(tmux display-message -p -t comma:0.0 '#{pane_pipe}')" = 0
tmux capture-pane -p -S -1000 -t comma:0.0 > "$E/production-startup.log"
tmux pipe-pane -t comma:0.0 'cat >> /data/xpilot-X-20261024-08-evidence/production-runtime.log'
trap 'tmux pipe-pane -t comma:0.0' EXIT
python3 "$E/methods/production.py"
tmux pipe-pane -t comma:0.0
trap - EXIT
tmux capture-pane -p -S -1000 -t comma:0.0 > "$E/production-end.log"
