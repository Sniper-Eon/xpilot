"""Failures: identity/head drift, unsafe runtime, stale/missing Panda messages,
firmware/version mismatch, parameter or store-plugin drift. Read only; no
Panda constructor/connect, controlWrite, CAN, service or parameter mutation.
"""
import base64
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import time

from openpilot.common.params import Params
from openpilot.cereal import messaging
from panda import Panda
from panda.python.spi import PandaSpiHandle

assert socket.gethostname() == 'comma-9c13c9f5'
assert Path('/data/hardware_profile').read_text().strip() == 'c3xl'
assert Path('/data/openpilot').resolve() == Path('/data/xpilot-install-20261022/candidate')
paths = {
  'XpilotTileLayout': '/data/xpilot_plugins/.params/XpilotTileLayout',
  'XpilotTileTheme': '/data/xpilot_plugins/.params/XpilotTileTheme',
  'XpilotBms': '/data/params/d/XpilotBms',
  'CarPlatformBundle': '/data/params/d/CarPlatformBundle',
  'IsDriverViewEnabled': '/data/params/d/IsDriverViewEnabled',
  'AlphaLongitudinalEnabled': '/data/params/d/AlphaLongitudinalEnabled',
}
params = {}
for key, path in paths.items():
  q = Path(path)
  data = q.read_bytes() if q.exists() else None
  params[key] = {'path': path, 'exists': data is not None,
                 'size': len(data) if data is not None else None,
                 'sha256': hashlib.sha256(data).hexdigest() if data is not None else None,
                 'base64': base64.b64encode(data).decode() if data is not None else None}
store = {str(q): hashlib.sha256(q.read_bytes()).hexdigest()
         for q in sorted(Path('/data/xpilot_plugins/overspeed_warning').rglob('*')) if q.is_file()}
p = Params()
sm = messaging.SubMaster(['deviceState', 'pandaStates', 'managerState'])
rows = []
end = time.monotonic() + 5
while time.monotonic() < end:
  sm.update(100)
  assert p.get_bool('IsOffroad') and not p.get_bool('IsEngaged')
  if sm.seen['deviceState']:
    assert not sm['deviceState'].started
  if sm.updated['pandaStates']:
    row = [{'controlsAllowed': a.controlsAllowed, 'faultStatus': str(a.faultStatus),
            'faults': [str(f) for f in a.faults], 'pandaType': str(a.pandaType),
            'ignitionLine': a.ignitionLine, 'ignitionCan': a.ignitionCan} for a in sm['pandaStates']]
    assert row and all(not a['controlsAllowed'] and a['faultStatus'] == 'none' and not a['faults']
                       and not a['ignitionLine'] and not a['ignitionCan'] for a in row)
    rows.append(row)
assert rows and all(sm.alive.values())
git = lambda *a: subprocess.check_output(['git', *a], text=True).strip()
r = {'hostname': socket.gethostname(), 'hardware_profile': 'c3xl', 'head': git('rev-parse', 'HEAD'),
     'branch': git('branch', '--show-current'), 'remote': git('remote', 'get-url', 'origin'),
     'active_path': str(Path('/data/openpilot').resolve()),
     'IsOffroad': p.get_bool('IsOffroad'), 'IsEngaged': p.get_bool('IsEngaged'),
     'started': sm['deviceState'].started, 'service': subprocess.check_output(['systemctl', 'is-active', 'comma.service'], text=True).strip(),
     'alive': dict(sm.alive), 'valid': dict(sm.valid), 'panda_samples': rows,
     'processes': [{'name': a.name, 'running': a.running, 'pid': a.pid, 'exitCode': a.exitCode} for a in sm['managerState'].processes],
     'params': params, 'overspeed_warning_files': store,
     'dirty_status': git('status', '--short'), 'timestamp_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
print(json.dumps({'runtime_before': r}), flush=True)
h = PandaSpiHandle()
try:
  info = h.get_info()
  assert info[12] == 9 and info[13] == 0xcc
  panda = Panda.__new__(Panda)
  panda._handle = h
  panda.health_version, panda.can_version = panda.get_packets_versions()
  fw = Path('panda/board/obj/panda_h7.bin.signed')
  version = panda.get_version()
  built = Path('panda/board/obj/gitversion.h').read_text().split('"')[1]
  sig = panda.get_signature()
  expected = Panda.get_signature_from_firmware(str(fw))
  health = panda.health()
  result = {'method': 'PandaSpiHandle get_info/controlRead only; Panda.__init__/connect not called',
            'serial': info[:12].hex(), 'raw_type': info[12:13].hex(), 'bootstub': info[13] == 0xee,
            'version': version, 'built_version': built,
            'firmware_sha256': hashlib.sha256(fw.read_bytes()).hexdigest(),
            'signature': sig.hex(), 'built_signature': expected.hex(), 'health': health,
            'version_match': version == built, 'signature_match': sig == expected}
  print(json.dumps({'panda_readonly': result}), flush=True)
  assert version == built and sig == expected, 'Panda version/signature mismatch: stop, never flash'
  assert not health['controls_allowed'] and health['faults'] == 0 and health['fault_status'] == 0
  assert not health['ignition_line'] and not health['ignition_can']
finally:
  h.close()
