"""Repeat the host acceptance commands and keep source hashes, exit codes and complete logs.
Failure modes: tests fail behind the known coverage exit, stale generated output, protected-file drift,
missing line coverage or treating compiler errors as mutation kills. All are asserted below.
"""

import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
OUT = Path('/private/tmp/X-20261023-07-final')
OUT.mkdir(exist_ok=True)
PYTHON = ROOT / 'opendbc_repo/.venv/bin/python3'
ENV = dict(os.environ, PYTHONPATH=os.pathsep.join(str(ROOT / p) for p in ('opendbc_repo', 'msgq_repo', '.')), GIT_LFS_SKIP_SMUDGE='1', UV_PYTHON='3.12')
ENV['PATH'] = str(PYTHON.parent) + os.pathsep + ENV['PATH'] + ':/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin'
RECORDS = []


def run(name, command, cwd=ROOT, expected=0):
  log = OUT / (name + '.log')
  with log.open('w') as output:
    proc = subprocess.run([str(c) for c in command], cwd=cwd, env=ENV, stdout=output, stderr=subprocess.STDOUT)
  result = {
    'name': name,
    'command': [str(c) for c in command],
    'cwd': str(cwd),
    'exit_code': proc.returncode,
    'expected_exit_code': expected,
    'log': log.name,
    'sha256': hashlib.sha256(log.read_bytes()).hexdigest(),
  }
  RECORDS.append(result)
  (OUT / 'commands.json').write_text(json.dumps(RECORDS, indent=2) + '\n')
  print(name, 'exit=' + str(proc.returncode), flush=True)
  assert proc.returncode == expected, result
  return log.read_text()


source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
paths = subprocess.check_output(
  ['git', 'diff', '--name-only', '00f7924ca05272103dd7cd2063cd5c66d1767b87', '--', 'opendbc_repo/opendbc/safety', 'openpilot/tesla', 'tools/sp_tesla_e2e'],
  cwd=ROOT,
  text=True,
).splitlines()
(OUT / 'source.json').write_text(
  json.dumps({'commit': source, 'sha256': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}}, indent=2) + '\n'
)
run(
  'protected-files',
  [
    'git',
    'diff',
    '--exit-code',
    '00f7924ca05272103dd7cd2063cd5c66d1767b87',
    '--',
    'opendbc_repo/opendbc/safety/safety.h',
    'opendbc_repo/opendbc/safety/modes/tesla.h',
    'opendbc_repo/opendbc/car/tesla',
    'opendbc_repo/opendbc/sunnypilot/car/tesla',
    'opendbc_repo/opendbc/dbc/tesla_model3_*.dbc',
  ],
)
run('libsafety-build', [PYTHON, '-m', 'unittest', 'opendbc.safety.tests.test_release_build'])
run('tesla', [PYTHON, '-m', 'unittest', 'opendbc.safety.tests.test_tesla'])
run('defaults', [PYTHON, '-m', 'unittest', 'opendbc.safety.tests.test_defaults'])
run('tesla-plugins', [PYTHON, '-m', 'unittest', 'opendbc.safety.tests.test_tesla_plugins'])
run('gen-safety', [PYTHON, 'openpilot/tesla/plugins/gen_safety.py'])
run('gen-safety-check', [PYTHON, 'openpilot/tesla/plugins/gen_safety.py', '--check'])
run('gen-params-check', [PYTHON, 'openpilot/tesla/plugins/gen_params.py', '--check'])
run('safety-manifest', [PYTHON, 'tools/sp_tesla_e2e/safety_manifest_check.py'])
run('manifest', [PYTHON, 'tools/sp_tesla_e2e/manifest_check.py'])
run('plugin-host', [PYTHON, 'tools/sp_tesla_e2e/plugin_host_check.py'])
run('mutations', [PYTHON, 'docs/validation/X-20261023-07/mutations.py'])
full = run('full-safety', ['bash', 'opendbc/safety/tests/test.sh'], ROOT / 'opendbc_repo', expected=1)
assert full.count('OK (skipped=') == 2 and 'FAILED (' not in full and 'Failed minimum line coverage' in full, full[-4000:]
coverage_cmd = [
  PYTHON.parent / 'gcovr',
  '-r',
  '../',
  '--gcov-executable',
  '/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/llvm-cov gcov',
]
tests = ROOT / 'opendbc_repo/opendbc/safety/tests'
ENV['SAFETY_COVERAGE'] = '1'
run('plugin-coverage-tests', [PYTHON, '-m', 'unittest', 'opendbc.safety.tests.test_tesla_plugins'])
ENV.pop('SAFETY_COVERAGE')
run('plugin-coverage', [*coverage_cmd, '--filter', '.*/plugins/.*', '--fail-under-line=100', '--txt'], tests)
run('coverage-json', [*coverage_cmd, '--json', OUT / 'coverage.json'], tests)
coverage = json.loads((OUT / 'coverage.json').read_text())
plugin_files = [f for f in coverage['files'] if f['file'].startswith('plugins/')]
plugin_lines = [l for f in plugin_files for l in f['lines'] if not l.get('gcovr/noncode')]
assert len(plugin_files) == 3 and len(plugin_lines) == 118 and all(l['count'] > 0 for l in plugin_lines)
safety = next(f for f in coverage['files'] if f['file'] == 'safety.h')
hooks = [l for l in safety['lines'] if l['line_number'] in (193, 194, 231, 238, 240, 241, 452)]
assert len(hooks) == 7 and all(l['count'] > 0 for l in hooks)
(OUT / 'hook-coverage.json').write_text(json.dumps(hooks, indent=2) + '\n')
run('source-unchanged', ['git', 'diff', '--exit-code', '--', *paths])
run(
  'dependency-versions',
  [PYTHON, '-c', 'import importlib.metadata as m; print(*sorted(d.metadata["Name"]+"=="+d.version for d in m.distributions()), sep=chr(10))'],
)
print('118/118 plugin lines; 7/7 executable integration lines covered; all expected exits verified.')
