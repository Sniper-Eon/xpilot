#!/usr/bin/env python3
"""Apply the narrow LANLink integration to an explicitly selected pinned snapshot."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--lean-root', type=Path, required=True)
args = p.parse_args()
source = Path(__file__).resolve().parent / 'lean'
manifest = json.loads((source / 'upstream.json').read_text())
root = args.lean_root.resolve()
for relative, expected in manifest['sha256'].items():
  if hashlib.sha256((root / relative).read_bytes()).hexdigest() != expected:
    raise SystemExit(f'Pinned source mismatch or already applied: {relative}')
copies = {'tcan_api.py': 'openpilot/system/lanlinkd/tcan_api.py',
          'TcanPanel.vue': 'openpilot/system/lanlinkd/web/src/components/TcanPanel.vue'}
for destination in copies.values():
  if (root / destination).exists():
    raise SystemExit(f'Refusing overwrite: {destination}')
subprocess.run(['git', 'apply', '--check', str(source / 'integration.patch')], cwd=root, check=True)
subprocess.run(['git', 'apply', str(source / 'integration.patch')], cwd=root, check=True)
for filename, destination in copies.items():
  shutil.copyfile(source / filename, root / destination)
print(json.dumps({'target': str(root), 'upstream': manifest['sha'], 'installed': list(copies.values()),
                  'patched': list(manifest['sha256']), 'frontend_build_required': True}, indent=2))
