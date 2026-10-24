"""Offline verification of captured E2E evidence; never connects to a device or mutates parameters."""
import hashlib
import json
from pathlib import Path
import struct

root = Path(__file__).resolve().parent
read = lambda name: json.loads((root / 'evidence' / name).read_text())
for line in (root / 'SHA256SUMS').read_text().splitlines():
  expected, name = line.split('  ', 1)
  assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name
result = json.loads((root / 'result.json').read_text())
assert result['status'] == 'FAILED'
assert result['device_before'] == result['device_after'] == '65bb09e3d5d306487d005f15cef799e31cf37fa2'
assert result['failure_modes'] == dict(a='PASS', b='FAIL', c='FAIL', d='FAIL', e='PASS', f='PASS')
assert {row['script'] for row in result['checks'] if row['rc'] != '0'} == {'store_check.py', 'big_screen_e2e.py', 'store_e2e.py'}
panda = [read(name) for name in ('panda-before.json', 'panda-post-build.json', 'panda-final.json')]
assert len({p['signature'] for p in panda}) == 1
assert all(p['signature'] == p['built_signature'] and p['version'] == p['built_version'] for p in panda)
assert all(not p['health']['controls_allowed'] and not p['health']['faults'] and not p['health']['ignition_line'] and not p['health']['ignition_can'] for p in panda)
assert all(row['total_tx_cnt'] == 0 for row in panda[-1]['can_health'])
assert read('names-base.json') == read('names-head.json')
assert not read('names-head.json')['duplicates']
assert len(read('names-head.json')['names']) == 47
assert {p['name'] for p in read('gate-before.json')['processes']} == {p['name'] for p in read('gate-head.json')['processes']}
assert len(read('gate-head.json')['processes']) == 47
prod = read('production-summary.json')
assert prod['passed'] and prod['elapsed_seconds'] >= 120 and prod['manager_samples'] == 239
assert all(not rows for rows in prod['scanned_errors'].values())
assert all(len(pids) == 1 for pids in prod['pid_sets'].values())
replay = read('replay-comparison.json')
assert not replay['passed'] and replay['tolerance'] == 0
assert replay['ignored_fields'] == ['logMonoTime', 'carState.cumLagMs', 'controlsState.deprecated.cumLagMs', 'controlsState.deprecated.startMonoTime']
counts = {name: sum(p['base_counts'].values()) for name, p in replay['processes'].items()}
assert counts == {'selfdrived': 12069, 'controlsd': 17919, 'card': 19062}
for name, proc in replay['processes'].items():
  assert proc['base_counts'] == proc['head_counts']
  for kind, row in proc['types'].items():
    assert row['differing_frames'] == (5922 if kind == 'selfdriveState' else 0), (name, kind)
first = replay['processes']['selfdrived']['types']['selfdriveState']['first_differences'][0]
assert first['frame'] == 51 and first['base_logMonoTime'] == first['head_logMonoTime'] == 491598328250
ui = read('core-ui-result.json')
assert ui['passed'] and not ui['missing_roles'] and not ui['load_errors']
assert len(ui['categories']) == 3
assert all(row['toggle_state'] and not row['toggle_enabled'] for row in ui['categories'].values())
for path in (root / 'screenshots').glob('*.png'):
  data = path.read_bytes()
  assert len(data) < 400000 and data[:8] == b'\x89PNG\r\n\x1a\n', path
  assert struct.unpack('>II', data[16:24]) == (2160, 1080), path
perf = read('overhead.json')
assert perf['calls_per_variant'] == 10000 and not perf['problem']
assert perf['p99_difference_us'] < 200 and perf['extra']['p99_us'] < 200
preserve = read('preservation-final.json')
assert preserve['all_params_restored_before_start'] and preserve['store_unchanged'] and preserve['dirty_unchanged']
assert preserve['original_count'] == preserve['current_count'] == 156
assert {Path(p).name for p in preserve['final_deltas']} == {'BootCount', 'CurrentBootlog', 'LastUpdateTime', 'UpdaterAvailableBranches', 'UpdaterLastFetchTime', 'UptimeOffroad'}
gate = read('gate-final.json')
assert gate['head'] == result['device_after'] and gate['service'] == 'active'
assert gate['IsOffroad'] and not gate['IsEngaged'] and not gate['started']
assert not gate['load_errors'] and not gate['faults']
assert read('source-identity.json')['forbidden_changed_paths'] == []
assert read('plugins-copy-proof.json')['device_equal']
print(json.dumps({'artifact_verification': 'PASS', 'validation_outcome': 'FAILED', 'compared_messages_per_tree': sum(counts.values()), 'device_after': result['device_after']}, indent=2))
