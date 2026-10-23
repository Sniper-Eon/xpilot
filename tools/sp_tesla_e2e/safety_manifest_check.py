#!/usr/bin/env python3
"""Failure modes, before generator/manifest implementation:
- A duplicate bit, undeclared header, missing header, CAN claim without safety TX, or safety TX without a claim is accepted.
- A stale registry passes --check, regeneration is not deterministic, or invalid input overwrites the registry.
- Python setup uses a hard-coded bit instead of its manifest; disabled vehicle/longitudinal gates are bypassed.
Run from the repo root with the task venv. CLI tests use real files in a disposable miniature repository.
"""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types

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
    manifests = {}
    for name in ('auto_speed', 'ambient_light'):
      path = root / 'openpilot/tesla/plugins' / name / 'plugin.json'
      path.parent.mkdir()
      manifests[name] = json.loads((ROOT / path.relative_to(root)).read_text())
      path.write_text(json.dumps(manifests[name]))
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
    ambient = root / 'openpilot/tesla/plugins/ambient_light/plugin.json'
    for label in ('duplicate-bit', 'missing-header', 'claim-without-safety-tx', 'safety-tx-without-claim'):
      data = json.loads(json.dumps(manifests['ambient_light']))
      if label == 'duplicate-bit':
        data['safety']['param_bit'] = manifests['auto_speed']['safety']['param_bit']
      elif label == 'missing-header':
        data['safety']['header'] = 'missing.h'
      elif label == 'claim-without-safety-tx':
        data['safety']['tx'] = []
      else:
        data['claims'] = []
      ambient.write_text(json.dumps(data))
      run(label, 1)
      assert registry.read_bytes() == original, label
    ambient.write_text(json.dumps(manifests['ambient_light']))
    (root / HEADERS / 'orphan.h').write_text('#pragma once\n')
    run('undeclared-header', 1)
    assert registry.read_bytes() == original

  sys.path[:0] = [str(ROOT), str(ROOT / 'opendbc_repo'), str(ROOT / 'msgq_repo')]
  sys.modules['openpilot.common.params'] = types.SimpleNamespace(Params=object, UnknownKeyName=KeyError)
  from openpilot.tesla import plugins

  for cls in plugins.PLUGINS:
    if cls.NAME not in ('auto_speed', 'ambient_light'):
      continue
    # Change the loaded declaration to prove setup consumes it, without constructing a CANParser.
    original_bit = cls.MANIFEST.safety['param_bit']
    cls.MANIFEST.safety['param_bit'] = '0x2000'
    try:
      plugin = object.__new__(cls)
      plugin.CP = types.SimpleNamespace(openpilotLongitudinalControl=True)
      plugin.controller = types.SimpleNamespace(configured=False)
      for flags in (0, 1):
        cp_sp = types.SimpleNamespace(flags=flags, safetyParam=0)
        plugin.setup(cp_sp)
        assert cp_sp.safetyParam == (0x2000 if flags else 0), (cls.NAME, flags, cp_sp.safetyParam)
      if cls.NAME == 'auto_speed':
        plugin.CP.openpilotLongitudinalControl = False
        cp_sp = types.SimpleNamespace(flags=1, safetyParam=0)
        plugin.setup(cp_sp)
        assert cp_sp.safetyParam == 0
      records.append({'label': cls.NAME + '-manifest-bit-setup', 'exit_code': 0})
    finally:
      cls.MANIFEST.safety['param_bit'] = original_bit
  assert len(records) == 11, records
  print(json.dumps(records, indent=2))


if __name__ == '__main__':
  main()
