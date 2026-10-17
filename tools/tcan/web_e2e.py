#!/usr/bin/env python3
"""Real HTTP/subprocess acceptance; writes a repeatable proof artifact."""
import argparse
import hashlib
import json
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
  parser = argparse.ArgumentParser()
  parser.add_argument('--artifact', required=True)
  args = parser.parse_args()
  result = {'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), 'checks': []}
  replay = {'frames': [{'bus': 0, 'address': 0x399, 'data': '0000000000000000', 'timestamp_ns': 1000000000},
                       {'bus': 1, 'address': 0x238, 'data': '0000000000000000', 'timestamp_ns': 1100000000}]}
  process = None
  try:
    with tempfile.TemporaryDirectory() as directory:
      fixture = Path(directory) / 'replay.json'
      fixture.write_text(json.dumps(replay))
      result['replay_sha256'] = hashlib.sha256(fixture.read_bytes()).hexdigest()
      with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
      base = f'http://127.0.0.1:{port}'
      process = subprocess.Popen([sys.executable, '-m', 'openpilot.sunnypilot.tcan.service', '--port', str(port),
                                  '--replay', str(fixture)], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

      def request(path, body=None, headers=None):
        data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
        req = urllib.request.Request(base + path, data=data, headers=headers or {})
        try:
          with urllib.request.urlopen(req, timeout=3) as response:
            return response.status, response.read()
        except urllib.error.HTTPError as exc:
          return exc.code, exc.read()

      for _ in range(50):
        if process.poll() is not None:
          raise AssertionError('service exited: ' + process.stderr.read().decode())
        try:
          status, raw = request('/api/status')
          break
        except urllib.error.URLError:
          time.sleep(0.1)
      else:
        raise AssertionError('service did not start')
      state = json.loads(raw)
      assert status == 200 and state['tx_enabled'] is False and state['physical_mapping_verified'] is False
      assert state['source'] == 'replay' and len(state['counts']) == 2
      assert state['device_age_ms'] is None and state['panda_age_ms'] is None
      assert state['started'] is None and state['pandas'] == []
      result['checks'].append('status and exact replay counters')
      status, raw = request('/api/capture')
      assert status == 200 and json.loads(raw)['frames'] == replay['frames']
      result['checks'].append('capture byte preservation')
      assert b'viewport' in request('/')[1]
      assert request('/api/send', {})[0] == 404
      assert request('/api/safety', {})[0] == 404
      result['checks'].append('mobile page and absent TX/safety routes')
      headers = {'Content-Type': 'application/json', 'Origin': base}
      preview = {'frames': replay['frames'], 'features': [], 'profile': 'standard_party', 'bus_map': {'A': 0, 'B': 1}}
      status, raw = request('/api/preview', preview, headers)
      assert status == 200 and json.loads(raw)['shadow_only'] is True
      assert json.loads(raw)['candidates'] == []
      active_frames = [{'bus': 1, 'address': 0x399, 'data': '0300000000000000', 'timestamp_ns': 1000000000},
                       {'bus': 1, 'address': 0x3FD, 'data': '0100080000000000', 'timestamp_ns': 1100000000}]
      enabled = {**preview, 'frames': active_frames, 'features': ['r79'], 'sp_onroad': False}
      candidate = json.loads(request('/api/preview', enabled, headers)[1])['candidates']
      assert candidate == [{'feature': 'r79', 'bus': 1, 'address': 0x3FD, 'data_hex': '0100000000800000', 'shadow_only': True}]
      assert json.loads(request('/api/preview', {**enabled, 'sp_onroad': True}, headers)[1])['candidates'] == []
      assert request('/api/status', headers={'Host': 'evil.example'})[0] == 421
      assert request('/api/preview', {**preview, 'frames': replay['frames'] * 501}, headers)[0] == 400
      result['checks'].append('R79 candidate, SP-onroad suppression, Host and count bounds')
      assert request('/api/preview', preview, {**headers, 'Origin': 'http://evil.example'})[0] == 403
      assert request('/api/preview', preview, {'Origin': base})[0] == 415
      assert request('/api/preview', b'{', headers)[0] == 400
      assert request('/api/preview', b'x' * 262145, headers)[0] == 413
      for frame in ({'bus': 8, 'address': 1, 'data': '', 'timestamp_ns': 1},
                    {'bus': 0, 'address': 1, 'data': 'xx', 'timestamp_ns': 1},
                    {'bus': 0, 'address': -1, 'data': '', 'timestamp_ns': 1},
                    {'bus': 0, 'address': 0x800, 'data': '0000000000000000', 'timestamp_ns': 1}):
        assert request('/api/preview', {**preview, 'frames': [frame]}, headers)[0] == 400
      assert request('/api/preview', {**preview, 'features': ['send_anything']}, headers)[0] == 400
      result['checks'].append('preview and network trust boundaries')
      assert json.loads(request('/api/capture')[1])['frames'] == replay['frames']
      result['checks'].append('preview cannot alter capture')
    result['passed'] = True
  except Exception as exc:
    result['passed'] = False
    result['error'] = str(exc)
  finally:
    if process is not None:
      process.terminate()
      process.communicate(timeout=5)
    result['source_sha256'] = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                               for path in [ROOT / 'tools/tcan/web_e2e.py', ROOT / 'openpilot/sunnypilot/tcan/service.py',
                                            ROOT / 'openpilot/sunnypilot/tcan/web/index.html', ROOT / 'openpilot/sunnypilot/tcan/engine.py'] if path.exists()}
    Path(args.artifact).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
  return 0 if result['passed'] else 1


if __name__ == '__main__':
  sys.exit(main())
