"""Restore existence and exact bytes from the pre-test snapshot; assert all five.
Failures: wrong identity, unsafe state, bad backup hash, partial write, byte drift.
"""
import base64
import hashlib
import json
from pathlib import Path
import socket
import tempfile
from openpilot.common.params import Params

assert socket.gethostname() == 'comma-9c13c9f5'
assert Path('/data/hardware_profile').read_text().strip() == 'c3xl'
assert Params().get_bool('IsOffroad') and not Params().get_bool('IsEngaged')
saved = json.loads(Path('/data/xpilot-ui-check-v8-evidence/params-before.json').read_text())
result = {}
for key, item in saved.items():
  path = Path(item['path'])
  data = base64.b64decode(item['base64']) if item['exists'] else None
  assert data is None or hashlib.sha256(data).hexdigest() == item['sha256']
  current = path.read_bytes() if path.exists() else None
  if current != data:
    if data is None:
      path.unlink()
    else:
      with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
        f.write(data)
      Path(f.name).replace(path)
  final = path.read_bytes() if path.exists() else None
  assert final == data
  result[key] = {'exists': path.exists(), 'sha256': hashlib.sha256(final).hexdigest() if final is not None else None,
                 'byte_equal': final == data, 'rewrite_needed': current != data}
print(json.dumps(result, indent=2))
