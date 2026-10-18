#!/usr/bin/env python3
"""Temporal replay E2E and pinned upstream decision oracle; no hardware access."""
import argparse
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SHA = 'e63b678df385748ffe379ebebdd98b73a361c3d8'
ORACLE = r'''
#include <iostream>
#include "auto_blinker_pure.h"
int main(){int d,a,g,c,r,e,t; while(std::cin>>d>>a>>g>>c>>r>>e>>t){
bool allowed=autoBlinkerAlcAllowsDirectionPure(d,a,false,false,false,false);
auto x=autoBlinkerSessionDecisionPure(g,d,c,r,e,allowed,t);
std::cout<<allowed<<" "<<x.cancel<<" "<<x.fire<<" "<<x.retry<<"\n";}}
'''


def main():
  p = argparse.ArgumentParser()
  p.add_argument('--upstream', type=Path, required=True)
  p.add_argument('--output', type=Path, required=True)
  args = p.parse_args()
  args.output.mkdir(parents=True, exist_ok=True)
  assert subprocess.check_output(['git', '-C', str(args.upstream), 'rev-parse', 'HEAD'], text=True).strip() == SHA
  assert not subprocess.check_output(['git', '-C', str(args.upstream), 'status', '--porcelain', '--untracked-files=no'], text=True).strip()
  cpp = args.output / 'oracle.cpp'
  cpp.write_text(ORACLE)
  exe = args.output / 'oracle'
  subprocess.run(['c++', '-std=c++17', '-I', str(args.upstream), str(cpp), '-o', str(exe)], check=True)
  path = ROOT / 'openpilot/sunnypilot/tcan/runtime.py'
  spec = importlib.util.spec_from_file_location('runtime', path)
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  inputs = list(itertools.product(range(3), range(32), range(2), range(3), range(2), range(2), range(2)))
  raw = ''.join(' '.join(map(str, row))+'\n' for row in inputs)
  oracle = subprocess.check_output([str(exe.resolve())], input=raw, text=True).splitlines()
  for row, answer in zip(inputs, oracle, strict=True):
    direction, alc, gate, current, recent, elapsed, due = row
    allowed, cancel, fire, retry = map(int, answer.split())
    assert module.alc_allows(direction, alc) == bool(allowed)
    expected = 'cancel' if cancel else 'fire' if fire else 'retry' if retry else 'wait'
    assert module.session_decision(bool(gate), direction, current, bool(recent), bool(elapsed), bool(allowed), bool(due)) == expected
  events = []

  def engine():
    return module.AutoBlinkerRuntime(delay_ms=500, stabilization_ms=1000, pause_ms=10000)

  def step(obj, now, expected=(), **changes):
    event = dict(authority_ms=now, sp_onroad=False, state_ms=now, ap_state=5, alc_state=8,
                 request_ms=now, behavior=2, enabled=True, cancel=False)
    event.update(changes)
    result = obj.step(now, **event)
    assert [x['direction'] for x in result] == list(expected), (now, event, result, obj.state)
    assert all(x == {'kind': 'blinker_request', 'direction': x['direction'], 'at_ms': now, 'shadow_only': True} for x in result)
    events.append({'now_ms': now, 'input': event, 'output': result, 'state': dict(obj.state)})

  def scenario(end, expected, changes=lambda t: {}):
    obj = engine()
    for t in range(0, end+1, 100):
      step(obj, t, expected.get(t, ()), **changes(t))
    return obj

  scenario(3000, {1500: ('left',)})
  scenario(3000, {1700: ('right',)}, lambda t: {'behavior': 3} if t >= 1200 else {})
  obj = scenario(2000, {1900: ('left',)}, lambda t: {'alc_state': 0} if 1500 <= t < 1900 else {})
  assert obj.state['retry_count'] == 2
  scenario(2000, {1500: ('left',)}, lambda t: {'behavior': 0} if t >= 1400 else {})
  scenario(4000, {}, lambda t: {'behavior': 0, 'alc_state': 0} if t >= 1400 else {})
  scenario(12000, {11800: ('left',)}, lambda t: {'cancel': t == 1300})
  scenario(2000, {1900: ('left',)}, lambda t: {'cancel': t in (1300, 1400)})
  for change in ({'sp_onroad': True}, {'enabled': False}, {'authority_ms': 0}, {'authority_ms': 1400},
                 {'state_ms': 0}, {'state_ms': 1400}, {'authority_ms': None}, {'state_ms': None}):
    scenario(3000, {2900: ('left',)}, lambda t, change=change: change if t == 1300 else {})
  scenario(3000, {2500: ('left',)}, lambda t: {'ap_state': 3} if 1100 <= t < 2000 else {})
  scenario(5000, {4700: ('left',)}, lambda t: {'ap_state': 3} if 1100 <= t < 3200 else {})
  scenario(2500, {2200: ('left',)}, lambda t: {'alc_state': 4 if t < 1800 else 7} if 1500 <= t < 2200 else {})
  obj = scenario(1200, {})
  step(obj, 900)
  for t in range(1000, 2600, 100):
    step(obj, t, ('left',) if t == 2500 else ())
  obj = scenario(1200, {})
  step(obj, 2000)
  for t in range(2100, 3600, 100):
    step(obj, t, ('left',) if t == 3500 else ())
  for change in ({'behavior': 4}, {'ap_state': -1}, {'sp_onroad': 1}, {'authority_ms': 'x'}):
    obj = scenario(1200, {})
    try:
      step(obj, 1300, **change)
    except ValueError:
      pass
    else:
      raise AssertionError(change)
    step(obj, 1400)
  (args.output/'replay.jsonl').write_text(''.join(json.dumps(row, sort_keys=True)+'\n' for row in events))
  sources = [path, Path(__file__), ROOT/'docs/tcan/RUNTIME_ACCEPTANCE.md', args.upstream/'auto_blinker_pure.h']
  report = {'passed': True, 'oracle_cases': len(inputs), 'replay_events': len(events), 'upstream_sha': SHA,
            'host_only': True, 'physical_mapping_verified': False,
            'source_sha256': {str(x): hashlib.sha256(x.read_bytes()).hexdigest() for x in sources},
            'artifact_sha256': {x.name: hashlib.sha256(x.read_bytes()).hexdigest() for x in args.output.iterdir() if x.is_file() and x.name!='report.json'},
            'rerun': shlex.join([sys.executable, str(Path(__file__).resolve()), '--upstream', str(args.upstream.resolve()), '--output', str(args.output.resolve())])}
  (args.output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
  print(json.dumps(report, indent=2))


if __name__ == '__main__':
  main()
