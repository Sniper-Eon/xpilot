"""Standalone CAN observer and offline-only shadow preview. No transmit path."""
import argparse
from collections import Counter, deque
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit

MAX_BODY = 262144
MAX_FRAMES = 1000
FEATURES = {'r79': 'R79 mux1 bit transform only; not a complete summon state machine',
            'isa': 'ISA shadow transform', 'country_us': '0x238 country field only'}


def frames_from(value):
  if not isinstance(value, list) or len(value) > MAX_FRAMES:
    raise ValueError('frames must be a list of at most 1000 frames')
  for frame in value:
    if not isinstance(frame, dict) or set(frame) != {'bus', 'address', 'data', 'timestamp_ns'}:
      raise ValueError('frame fields must be bus,address,data,timestamp_ns')
    if any(type(frame[key]) is not int for key in ('bus', 'address', 'timestamp_ns')):
      raise ValueError('bus,address,timestamp_ns must be integers')
    if not 0 <= frame['bus'] <= 2 or not 0 <= frame['address'] <= 0x1FFFFFFF or frame['timestamp_ns'] < 0:
      raise ValueError('frame number out of range')
    data = frame['data']
    if not isinstance(data, str) or len(data) > 16 or len(data) % 2 or any(c not in '0123456789abcdefABCDEF' for c in data):
      raise ValueError('data must be at most 8 bytes of hex')
  return value


class Capture:
  def __init__(self, source):
    self.source = source
    self.lock = threading.Lock()
    self.frames = deque(maxlen=MAX_FRAMES)
    self.started = None
    self.pandas = []
    self.device_received_ns = None
    self.panda_received_ns = None
    self.error = None

  def snapshot(self):
    with self.lock:
      return list(self.frames), self.started, self.pandas, self.device_received_ns, self.panda_received_ns, self.error

  def live(self):
    try:
      from openpilot.cereal import messaging
      sm = messaging.SubMaster(['can', 'deviceState', 'pandaStates'], poll='can')
      while True:
        sm.update(100)
        with self.lock:
          if sm.updated['can']:
            now = time.monotonic_ns()
            for frame in sm['can']:
              if frame.src <= 2:
                self.frames.append({'bus': frame.src, 'address': frame.address, 'data': bytes(frame.dat).hex(), 'timestamp_ns': now})
          if sm.updated['deviceState']:
            self.started = bool(sm['deviceState'].started)
            self.device_received_ns = time.monotonic_ns()
          if sm.updated['pandaStates']:
            self.panda_received_ns = time.monotonic_ns()
            self.pandas = [{'ignition_line': bool(p.ignitionLine), 'ignition_can': bool(p.ignitionCan),
                            'safety_model': str(p.safetyModel)} for p in sm['pandaStates']]
    except Exception as exc:
      # The observer remains available to report a failed source; no control depends on it.
      with self.lock:
        self.error = f'{type(exc).__name__}: {exc}'


class Handler(BaseHTTPRequestHandler):
  def setup(self):
    super().setup()
    self.connection.settimeout(2)

  def log_message(self, *_args):
    pass

  def reply(self, status, body, content_type='application/json'):
    data = json.dumps(body).encode() if content_type == 'application/json' else body
    self.send_response(status)
    self.send_header('Content-Type', content_type)
    self.send_header('Content-Length', str(len(data)))
    self.send_header('Cache-Control', 'no-store')
    self.send_header('X-Content-Type-Options', 'nosniff')
    self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; frame-ancestors 'none'")
    self.end_headers()
    self.wfile.write(data)

  def valid_host(self):
    host = self.headers.get('Host', '')
    local = self.connection.getsockname()[0]
    allowed = {f'{local}:{self.server.server_port}'}
    if local == '127.0.0.1':
      allowed.add(f'localhost:{self.server.server_port}')
    return host in allowed

  def do_GET(self):
    if not self.valid_host():
      return self.reply(421, {'error': 'use the bound device IP and port'})
    frames, started, pandas, device_received, panda_received, error = self.server.capture.snapshot()
    if self.path == '/':
      return self.reply(200, Path(__file__).with_name('web').joinpath('index.html').read_bytes(), 'text/html; charset=utf-8')
    if self.path == '/api/capture':
      return self.reply(200, {'frames': frames})
    if self.path == '/api/status':
      counts = Counter((f['bus'], f['address'], len(f['data']) // 2) for f in frames)
      return self.reply(200, {'source': self.server.capture.source, 'tx_enabled': False,
                             'physical_mapping_verified': False, 'started': started, 'pandas': pandas,
                             'device_age_ms': None if device_received is None else (time.monotonic_ns() - device_received) / 1e6,
                             'panda_age_ms': None if panda_received is None else (time.monotonic_ns() - panda_received) / 1e6,
                             'source_error': error, 'capture_limit': MAX_FRAMES, 'captured_frames': len(frames),
                             'features': FEATURES, 'counts': [{'bus': b, 'address': a, 'dlc': d, 'count': n}
                                                            for (b, a, d), n in sorted(counts.items())]})
    return self.reply(404, {'error': 'not found'})

  def do_POST(self):
    if not self.valid_host():
      return self.reply(421, {'error': 'use the bound device IP and port'})
    if self.path != '/api/preview':
      return self.reply(404, {'error': 'not found'})
    origin = urlsplit(self.headers.get('Origin', ''))
    if origin.scheme != 'http' or origin.netloc != self.headers.get('Host') or origin.path or origin.query or origin.fragment:
      return self.reply(403, {'error': 'same-origin browser request required'})
    if self.headers.get('Content-Type') != 'application/json':
      return self.reply(415, {'error': 'application/json required'})
    try:
      size = int(self.headers.get('Content-Length', '-1'))
      if not 0 <= size <= MAX_BODY or self.headers.get('Transfer-Encoding'):
        return self.reply(413, {'error': 'body limit 262144 bytes; chunked input unsupported'})
      value = json.loads(self.rfile.read(size))
      if not isinstance(value, dict) or set(value) - {'frames', 'features', 'profile', 'bus_map', 'sp_onroad'}:
        raise ValueError('invalid preview fields')
      frames = frames_from(value.get('frames'))
      if any(frame['address'] > 0x7FF for frame in frames):
        raise ValueError('shadow preview supports only 11-bit CAN IDs; capture preserves extended IDs')
      features = value.get('features', [])
      if not isinstance(features, list) or any(not isinstance(f, str) or f not in FEATURES for f in features):
        raise ValueError('invalid features')
      profile = value.get('profile')
      if profile not in (None, 'yl', 'standard_body', 'standard_party'):
        raise ValueError('invalid profile')
      bus_map = value.get('bus_map')
      if bus_map is not None and (not isinstance(bus_map, dict) or set(bus_map) != {'A', 'B'} or
                                  any(type(b) is not int or not 0 <= b <= 2 for b in bus_map.values()) or
                                  bus_map['A'] == bus_map['B']):
        raise ValueError('invalid declared offline bus map')
      onroad = value.get('sp_onroad', True)
      if type(onroad) is not bool:
        raise ValueError('sp_onroad must be boolean')
      from .engine import ShadowEngine
      engine = ShadowEngine(profile=profile, bus_map=bus_map, features=features)
      candidates = []
      for frame in frames:
        candidates.extend(engine.observe(frame['bus'], frame['address'], bytes.fromhex(frame['data']),
                                         frame['timestamp_ns'], received_ns=frame['timestamp_ns'], sp_onroad=onroad))
    except (ValueError, TypeError, KeyError, UnicodeDecodeError) as exc:
      return self.reply(400, {'error': str(exc)})
    return self.reply(200, {'shadow_only': True, 'tx_enabled': False, 'candidates': candidates})


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--host', default='127.0.0.1')
  parser.add_argument('--port', type=int, default=8099)
  parser.add_argument('--replay', type=Path)
  args = parser.parse_args()
  capture = Capture('replay' if args.replay else 'live')
  if args.replay:
    if args.replay.stat().st_size > MAX_BODY:
      raise ValueError('replay exceeds 262144 bytes')
    capture.frames.extend(frames_from(json.loads(args.replay.read_text())['frames']))
  else:
    threading.Thread(target=capture.live, daemon=True).start()
  server = HTTPServer((args.host, args.port), Handler)
  server.capture = capture
  server.serve_forever()


if __name__ == '__main__':
  main()
