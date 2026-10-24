set -eu
E=/data/xpilot-X-20261024-08-round2-evidence
cd /data/openpilot
export PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo
export PYTHONDONTWRITEBYTECODE=1
export SUNNYPILOT_HARDWARE_PROFILE=c3xl
! systemctl is-active --quiet comma
test "$(cat /data/params/d/IsOffroad)" = 1
test "$(cat /data/params/d/IsEngaged)" = 0
set +e
timeout 90 python3 "$E/methods/overhead.py" > "$E/overhead.log" 2>&1
printf '%s\n' "$?" > "$E/overhead.exit"
timeout 90 python3 "$E/methods/core-ui.py" --output "$E/core-ui" > "$E/core-ui.log" 2>&1
printf '%s\n' "$?" > "$E/core-ui.exit"
set -e
python3 - <<'PY'
import hashlib,json,re
from pathlib import Path
E=Path('/data/xpilot-X-20261024-08-round2-evidence')
base=json.loads((E/'base-big-screen/result.json').read_text())
head=json.loads((E/'big-screen/result.json').read_text())
base_error='\n'.join(base['errors'])
head_error='\n'.join(head['errors'])
ui_env=(int((E/'base-big-screen.exit').read_text())==1 and dict(line.split('\t') for line in (E/'checks.tsv').read_text().splitlines())['big_screen_e2e.py']=='1' and "line 332, in steps" in base_error and "line 332, in steps" in head_error and "AssertionError: no data tile to drag" in base_error and "AssertionError: no data tile to drag" in head_error)
base_sha=(E/'base-big-screen-source.sha256').read_text().split()[0]
head_sha=(E/'head-big-screen-source.sha256').read_text().split()[0]
ui_env=ui_env and base_sha==head_sha
bp=json.loads((E/'pre-base-ui-private.json').read_text())
hp=json.loads((E/'pre-head-ui-private.json').read_text())
plugin_param_names={n for n in set(bp)|set(hp) if n.startswith('/data/xpilot_plugins/.params/')}
assert all(bp.get(n)==hp.get(n) for n in plugin_param_names)
assert json.loads((E/'pre-base-ui-store.json').read_text())==json.loads((E/'pre-head-ui-store.json').read_text())
checks=dict(line.split('\t') for line in (E/'checks.tsv').read_text().splitlines())
check_pass=all(rc=='0' or (name=='big_screen_e2e.py' and ui_env) for name,rc in checks.items())
prod=json.loads((E/'production.json').read_text())
expected_names=set(json.loads((E/'names-base.json').read_text())['names'])
expected_running=set(prod['expected_running'])
processes_ok=all({p['name'] for p in row['processes']}==expected_names and {p['name'] for p in row['processes'] if p['running']}==expected_running for row in prod['samples'])
errors={}
network=[]
for name in ('production-startup.log','production-runtime.log','production-messages.jsonl'):
 lines=(E/name).read_text().splitlines()
 errors[name]=[line for line in lines if re.search(r'Traceback|UnknownKeyName|failed to import|xpilot.*(?:fault|failed|error)',line,re.I)]
 network.extend(line for line in lines if ('Request transport error while fetching models' in line or 'Network is unreachable' in line or 'Connection reset by peer' in line))
panda=json.loads((E/'panda-post-build.json').read_text())
replay=json.loads((E/'replay-comparison.json').read_text())
a=(E/'build.exit').read_text().strip()=='0' and panda['signature']==panda['built_signature']
b=prod['passed'] and prod['elapsed_seconds']>=120 and processes_ok and all(not v for v in errors.values())
c=check_pass
d=replay['passed']
result={'a':a,'b':b,'c':c,'d':d,'keep_head':a and b and c and d,'big_screen_classification':'ENV' if ui_env else ('PASS' if checks['big_screen_e2e.py']=='0' else 'FAIL'),'base_ui_rc':int((E/'base-big-screen.exit').read_text()),'head_ui_rc':int(checks['big_screen_e2e.py']),'ui_failing_line':332 if ui_env else None,'same_plugin_params':True,'same_store_files':True,'production_errors':errors,'network_log_lines':network}
(E/'outcome-pre-final.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('production_errors','network_log_lines')}))
PY
keep=$(python3 -c 'import json; print(int(json.load(open("/data/xpilot-X-20261024-08-round2-evidence/outcome-pre-final.json"))["keep_head"]))')
python3 "$E/methods/restore.py" initial > "$E/params-restored-final-start.json"
if test "$keep" = 0
then
 git checkout --detach 65bb09e3d5d306487d005f15cef799e31cf37fa2
 set +e
 /usr/bin/time -p scons -j4 > "$E/rollback-build.log" 2>&1
 rc=$?
 set -e
 printf '%s\n' "$rc" > "$E/rollback-build.exit"
 test "$rc" = 0
 git update-ref refs/heads/xpilot 65bb09e3d5d306487d005f15cef799e31cf37fa2 4292551111be2d7afa7cf9aa158841fb712e740b
 git checkout xpilot
fi
python3 "$E/methods/panda-final.py" > "$E/panda-before-final-start.json"
test ! -e /data/xpilot_plugins/.defaults_done
touch /data/xpilot_plugins/.defaults_done
test -f /tmp/booted
sudo systemctl start comma.service
sleep 20
python3 "$E/methods/gate.py" > "$E/gate-final.json"
rm /data/xpilot_plugins/.defaults_done
python3 "$E/methods/panda-final.py" > "$E/panda-final.json"
tmux capture-pane -p -S -600 -t comma:0.0 > "$E/final-startup.log"
