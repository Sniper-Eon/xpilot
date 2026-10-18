#!/usr/bin/env python3
"""Launch the actual patched upstream LANLink assembly, never a replacement router."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]



def main():
  p = argparse.ArgumentParser()
  p.add_argument('--lean-root', type=Path, required=True)
  p.add_argument('--artifact', type=Path, required=True)
  args = p.parse_args()
  result = {'lean_sha': 'be16822e572ce8c6e7def7cfd48d21eae7ffeef1', 'checks': [],
            'hardware_fixtures': ['upstream Params conftest', 'StatusCache.run waits without live IPC']}
  with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
  base = f'http://127.0.0.1:{port}'
  env = {**os.environ, 'PYTHONPATH': ':'.join(str(ROOT / d) for d in ('opendbc_repo', 'msgq_repo'))}
  child = subprocess.Popen([sys.executable, str(ROOT / 'tools/tcan/lean_host.py'), '--lean-root', str(args.lean_root), '--port', str(port)], cwd=args.lean_root,
                           env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
  observer = None
  try:
    def request(path, value=None, origin=None):
      headers = {'Content-Type': 'application/json', 'Origin': origin or base}
      data = json.dumps(value).encode() if value is not None else None
      try:
        with urllib.request.urlopen(urllib.request.Request(base + path, data=data, headers=headers), timeout=5) as r:
          return r.status, r.read()
      except urllib.error.HTTPError as e:
        return e.code, e.read()
    for _ in range(60):
      if child.poll() is not None:
        raise AssertionError(child.stdout.read().decode())
      try:
        if request('/')[0] == 200:
          break
      except urllib.error.URLError:
        time.sleep(.1)
    else:
      raise AssertionError('real LANLink did not start')
    code, raw = request('/api/tcan/status')
    assert code == 503, (code, raw.decode())
    result['checks'].append('actual upstream assembly: missing observer returns 503')
    with tempfile.TemporaryDirectory() as directory:
      replay = Path(directory) / 'capture.json'
      replay.write_text(json.dumps({'frames': [{'bus': 1, 'address': 0x399, 'data': '0300000000000000', 'timestamp_ns': 1000000000},
                                              {'bus': 1, 'address': 0x3FD, 'data': '0100080000000000', 'timestamp_ns': 1100000000}]}))
      observer = subprocess.Popen([sys.executable, '-m', 'openpilot.sunnypilot.tcan.service', '--replay', str(replay)], cwd=ROOT,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
      for _ in range(50):
        code, raw = request('/api/tcan/status')
        if code == 200:
          break
        time.sleep(.1)
      assert code == 200 and json.loads(raw)['tx_enabled'] is False
      assert len(json.loads(request('/api/tcan/capture')[1])['frames']) == 2
      preview = {**json.loads(replay.read_text()), 'profile': 'standard_party', 'bus_map': {'A': 0, 'B': 1},
                 'features': ['r79'], 'sp_onroad': False}
      code, raw = request('/api/tcan/preview', preview)
      assert code == 200 and json.loads(raw)['candidates'][0]['data_hex'] == '0100000000800000'
      assert request('/api/tcan/preview', preview, 'http://evil.example')[0] == 403
      assert request('/api/tcan/send', {})[0] == 404
      assert request('/api/tcan/preview', {'frames': [] , 'unknown': 1})[0] == 400
      assert request('/api/tcan/preview', {'oversize': 'x' * 262145})[0] == 413
      assert request('/')[0] == 200
      result['checks'].append('real bridge capture, candidate, CSRF, route allowlist, validation, original index')
    result['passed'] = True
  except Exception as exc:
    result.update(passed=False, error=str(exc))
  finally:
    for process in (observer, child):
      if process:
        process.terminate()
        process.communicate(timeout=10)
    result['rerun'] = f'{sys.executable} {Path(__file__).resolve()} --lean-root {args.lean_root} --artifact {args.artifact}'
    result['sources'] = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in
                         [args.lean_root / 'openpilot/system/lanlinkd/lanlinkd.py',
                          args.lean_root / 'openpilot/system/lanlinkd/tcan_api.py',
                          args.lean_root / 'openpilot/system/lanlinkd/web/src/App.vue',
                          args.lean_root / 'openpilot/system/lanlinkd/web/src/components/Sidebar.vue',
                          args.lean_root / 'openpilot/system/lanlinkd/web/src/components/TcanPanel.vue',
                          ROOT / 'tools/tcan/lean_host.py', Path(__file__)] if path.exists()}
    args.artifact.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
  return 0 if result['passed'] else 1


if __name__ == '__main__':
  sys.exit(main())
