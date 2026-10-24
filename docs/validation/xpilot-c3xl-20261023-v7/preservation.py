"""Failures: lost/changed dirty files, store-plugin mutation, or five-param drift.
Read only; compare final bytes with pre-deployment/pre-test authoritative data.
"""
import base64
import hashlib
import json
from pathlib import Path
import socket
import subprocess

assert socket.gethostname() == 'comma-9c13c9f5'
assert Path('/data/hardware_profile').read_text().strip() == 'c3xl'
assert Path('/data/params/d/IsOffroad').read_bytes() == b'1'
assert Path('/data/params/d/IsEngaged').read_bytes() == b'0'
root = Path('/data/xpilot-ui-check-v7-evidence')
before = json.loads((root / 'dirty-before.json').read_text())['files']
after = {name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in before}
initial = json.loads((root / 'pre-stop.jsonl').read_text().splitlines()[0])['runtime_before']
store = {str(q): hashlib.sha256(q.read_bytes()).hexdigest() for q in sorted(Path('/data/xpilot_plugins/overspeed_warning').rglob('*')) if q.is_file()}
saved = json.loads((root / 'params-before.json').read_text())
params = {key: (Path(d['path']).read_bytes() if Path(d['path']).exists() else None) == (base64.b64decode(d['base64']) if d['exists'] else None) for key, d in saved.items()}
result = {'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
          'service': subprocess.check_output(['systemctl', 'is-active', 'comma.service'], text=True).strip(),
          'dirty_file_count': len(before), 'dirty_files_unchanged': before == after,
          'dirty_changed': [n for n in before if before[n] != after[n]], 'final_dirty_file_sha256': after,
          'store_file_count': len(store), 'store_files_unchanged': store == initial['overspeed_warning_files'],
          'store_files': store, 'params_byte_equal': params}
print(json.dumps(result, indent=2))
assert result['head'] == 'cc129b8829c8fd6d170ef75d9857840cb25ed726'
assert result['service'] == 'active' and result['dirty_files_unchanged'] and result['store_files_unchanged'] and all(params.values())
