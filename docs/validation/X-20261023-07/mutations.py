"""Remove one safety check at a time; each compiled mutant must fail a real RX/TX assertion.
Failure modes: no-op/ambiguous replacement, compile/import errors mistaken for kills,
surviving mutants, or mutated source left on disk. Assert all; restore in finally.
"""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path.cwd()
OUT = Path('/private/tmp/X-20261023-07-evidence/mutations')
OUT.mkdir(exist_ok=True)
BASE = 'opendbc/safety/plugins/'
CASES = []


def add(file, label, old, new, test):
  CASES.append((BASE + file, label, old, new, test))


for file, cls, prefix, bit in (
  ('auto_speed.h', 'TestTeslaAutoSpeed', 'auto_speed', 'XPILOT_PARAM_SP_AUTO_SPEED'),
  ('ambient_light.h', 'TestTeslaAmbientLight', 'ambient', 'XPILOT_PARAM_SP_AMBIENT_LIGHT'),
):
  add(file, prefix + '-mode', '(current_safety_mode == SAFETY_TESLA)', 'true', cls + '.test_mode_gate')
  add(file, prefix + '-vehicle', '&& tesla_has_vehicle_bus &&', '&& true &&', cls + '.test_vehicle_bus_gate')
  add(file, prefix + '-param', f'GET_FLAG(current_safety_param_sp, {bit})', 'true', cls + '.test_own_param_bit')
  addr, length = ('0x3C2U', '8U') if prefix == 'auto_speed' else ('0x679U', '7U')
  for label, old in [('rx-bus', '(msg->bus == 1U)'), ('rx-address', f'(msg->addr == {addr})'), ('rx-length', f'(GET_LEN(msg) == {length})')]:
    add(file, prefix + '-' + label, old, 'true', cls + '.test_rx_template_gate')
  add(file, prefix + '-fresh-valid', prefix + '_template_valid &&', 'true &&', cls + '.test_template_freshness')
  age = '1500000U' if prefix == 'auto_speed' else '1000000U'
  add(file, prefix + '-fresh-age', f'(safety_get_ts_elapsed(now, {prefix}_template_ts) <= {age})', 'true', cls + '.test_template_freshness')
  last = 'auto_speed_last_tx_ts' if prefix == 'auto_speed' else 'ambient_tx_ts'
  rate = '250000U' if prefix == 'auto_speed' else '80000U'
  add(file, prefix + '-rate', f'(safety_get_ts_elapsed(now, {last}) >= {rate})', 'true', cls + '.test_rate_limit')
  limit = '60U' if prefix == 'auto_speed' else 'session_frames'
  duration = '30000000U' if prefix == 'auto_speed' else 'session_us'
  add(
    file,
    prefix + '-session-frames',
    f'({prefix}_session_count < {limit})',
    f'(({prefix}_session_count < {limit}) || ({limit} > 0U))',
    cls + '.test_session_frame_cap',
  )
  add(
    file,
    prefix + '-session-time',
    f'(safety_get_ts_elapsed(now, {prefix}_session_ts) < {duration})',
    f'((safety_get_ts_elapsed(now, {prefix}_session_ts) < {duration}) || ({duration} > 0U))',
    cls + '.test_session_time_cap',
  )
  valid = 'auto_speed_last_tx_valid' if prefix == 'auto_speed' else 'ambient_tx_valid'
  idle = '2000000U' if prefix == 'auto_speed' else '1000000U'
  add(file, prefix + '-idle-restart', f'!{valid} || (safety_get_ts_elapsed(now, {last}) >= {idle})', f'!{valid}', cls + '.test_session_frame_cap')

add('auto_speed.h', 'auto-controls', 'controls_allowed && tick_allowed', 'true && tick_allowed', 'TestTeslaAutoSpeed.test_controls_allowed')
add('auto_speed.h', 'auto-rx-mux', '((msg->data[0] & 0x03U) == 1U)', 'true', 'TestTeslaAutoSpeed.test_rx_template_gate')
add('auto_speed.h', 'auto-rx-idle', '((msg->data[3] & 0x3FU) == 0U)', 'true', 'TestTeslaAutoSpeed.test_rx_template_gate')
add('auto_speed.h', 'auto-tick', '(ticks == 1U) || (ticks == 0x3FU)', '(ticks <= 0x3FU)', 'TestTeslaAutoSpeed.test_content')
add(
  'auto_speed.h',
  'auto-template-reserved',
  '(msg->data[3] & 0xC0U) == (auto_speed_template[3] & 0xC0U)',
  '(msg->data[3] & 0xC0U) <= 0xC0U',
  'TestTeslaAutoSpeed.test_content',
)
add('auto_speed.h', 'auto-template-bytes', '(msg->data[i] == auto_speed_template[i])', '(msg->data[i] <= 255U)', 'TestTeslaAutoSpeed.test_content')
for label, old, new in [
  ('target', '((zone == 0xA8U) && !side) || ((zone == 0x50U) && side) || ((zone == 0xF8U) && side)', '(zone <= 0xF8U) || side'),
  ('red', '(msg->data[1] == 255U)', '(msg->data[1] <= 255U)'),
  ('green', '(msg->data[2] == 0U)', '(msg->data[2] <= 255U)'),
  ('blue', '(msg->data[3] == 0U)', '(msg->data[3] <= 255U)'),
  ('brightness', '(brightness <= 100U)', '(brightness <= 127U)'),
  ('template-power', '(msg->data[0] == ((ambient_template[0] & 1U) | 2U))', '(msg->data[0] <= 255U)'),
  ('template-brightness', '((msg->data[4] & 0x80U) == (ambient_template[4] & 0x80U))', '(msg->data[4] <= 255U)'),
  ('template-zone', '((msg->data[5] & 7U) == (ambient_template[5] & 6U))', '(msg->data[5] <= 255U)'),
  ('template-side', '((msg->data[6] & 0xFEU) == (ambient_template[6] & 0xFEU))', '(msg->data[6] <= 255U)'),
]:
  add('ambient_light.h', 'ambient-' + label, old, new, 'TestTeslaAmbientLight.test_content')
for check, replacement in [('bus', '(msg->addr == m->addr) && (GET_LEN(msg) == m->len)'), ('length', 'msg_matches(msg, m->addr, m->bus)')]:
  for cls in ('TestTeslaAutoSpeed', 'TestTeslaAmbientLight'):
    add('registry.h', cls + '-tx-' + check, 'msg_matches(msg, m->addr, m->bus, m->len)', replacement, cls + '.test_tx_bus_and_length')
CASES.append(
  (
    'opendbc/safety/safety.h',
    'mode-reset-call',
    '      safety_plugins_reset();',
    '      if (current_safety_mode == SAFETY_NOOUTPUT) { safety_plugins_reset(); }',
    'TestTeslaAutoSpeed.test_mode_reset',
  )
)
CASES.append(
  (
    'opendbc/safety/safety.h',
    'mode-reset-call-ambient',
    '      safety_plugins_reset();',
    '      if (current_safety_mode == SAFETY_NOOUTPUT) { safety_plugins_reset(); }',
    'TestTeslaAmbientLight.test_mode_reset',
  )
)

records = []
env = dict(os.environ, PYTHONPATH=str(ROOT / 'opendbc_repo'), SAFETY_COVERAGE='0')
for relative, label, old, new, test in CASES:
  path = ROOT / 'opendbc_repo' / relative
  original = path.read_text()
  assert original.count(old) == 1, (label, original.count(old))
  log = OUT / (label + '.log')
  try:
    path.write_text(original.replace(old, new))
    with log.open('w') as output:
      proc = subprocess.run(
        [sys.executable, '-m', 'unittest', 'opendbc.safety.tests.test_tesla_plugins.' + test], env=env, stdout=output, stderr=subprocess.STDOUT
      )
    text = log.read_text()
    killed = proc.returncode == 1 and 'FAIL:' in text and 'ERROR:' not in text and 'error:' not in text
    records.append(
      {
        'label': label,
        'file': relative,
        'old': old,
        'new': new,
        'test': test,
        'exit_code': proc.returncode,
        'killed': killed,
        'log': log.name,
        'sha256': hashlib.sha256(log.read_bytes()).hexdigest(),
      }
    )
    print(label, 'KILLED' if killed else 'SURVIVED/INVALID', flush=True)
  finally:
    path.write_text(original)
(OUT / 'results.json').write_text(json.dumps(records, indent=2) + '\n')
assert all(r['killed'] for r in records), [r['label'] for r in records if not r['killed']]
print(f'{len(records)}/{len(records)} compiled mutants killed by assertions')
