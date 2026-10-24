#!/usr/bin/env python3
"""Failure modes of gen_safety.py (declarations in opendbc/safety/plugins/safety.json):
- A duplicate bit, undeclared header, missing header, tx differing from the header .msg, or a built-in plugin
  can.tx claim missing from safety.json is accepted.
- A stale registry passes --check, regeneration is not deterministic, or invalid input overwrites the registry.
The store side (installed plugins must match safety.json) is store_check S18; the plugins' own use of their
param_bit is tested in the plugin repository. Real files in a disposable miniature repository.
"""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = Path('openpilot/tesla/plugins/gen_safety.py')
HEADERS = Path('opendbc_repo/opendbc/safety/plugins')


def main():
  records = []
  with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    shutil.copytree(ROOT / HEADERS, root / HEADERS)
    (root / SCRIPT).parent.mkdir(parents=True)
    shutil.copyfile(ROOT / SCRIPT, root / SCRIPT)
    declared_path = root / HEADERS / 'safety.json'
    declared = json.loads(declared_path.read_text())
    registry = root / HEADERS / 'registry.h'

    def run(label, expected=0, check=False):
      proc = subprocess.run([sys.executable, str(root / SCRIPT), *(['--check'] if check else [])], capture_output=True, text=True)
      records.append({'label': label, 'exit_code': proc.returncode, 'output': proc.stdout + proc.stderr})
      assert proc.returncode == expected, records[-1]

    run('generate')
    original = registry.read_bytes()
    run('current-check', check=True)
    registry.write_bytes(original + b'\n')
    run('stale-check', 1, check=True)
    run('regenerate')
    assert registry.read_bytes() == original
    builtin = root / 'openpilot/tesla/plugins/x/plugin.json'
    builtin.parent.mkdir()
    for label in ('duplicate-bit', 'missing-header', 'tx-differs-from-header', 'builtin-claim-undeclared'):
      data = json.loads(json.dumps(declared))
      if label == 'duplicate-bit':
        data['ambient_light']['param_bit'] = data['auto_speed']['param_bit']
      elif label == 'missing-header':
        data['ambient_light']['header'] = 'missing.h'
      elif label == 'tx-differs-from-header':
        data['ambient_light']['tx'] = ['0x67A:1']
      else:
        builtin.write_text(json.dumps({'claims': ['can.tx:0x123:0']}))
      declared_path.write_text(json.dumps(data))
      run(label, 1)
      assert registry.read_bytes() == original, label
    builtin.unlink()
    declared_path.write_text(json.dumps(declared))
    (root / HEADERS / 'orphan.h').write_text('#pragma once\n')
    run('undeclared-header', 1)
    assert registry.read_bytes() == original

  assert len(records) == 9, records
  print(json.dumps(records, indent=2))


if __name__ == '__main__':
  main()
