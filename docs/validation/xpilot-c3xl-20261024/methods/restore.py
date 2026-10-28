"""Restore all isolated-test parameter bytes/existence while production is stopped; prove byte equality."""
import base64,hashlib,json,socket,subprocess,sys,tempfile
from pathlib import Path
assert socket.gethostname()=='comma-9c13c9f5'
assert Path('/data/hardware_profile').read_text().strip()=='c3xl'
assert Path('/data/params/d/IsOffroad').read_bytes()==b'1'
assert Path('/data/params/d/IsEngaged').read_bytes()==b'0'
assert subprocess.run(['pgrep','-f','^python3 ./manager.py$'],capture_output=True).returncode==1
E=Path('/data/xpilot-X-20261024-08-evidence')
saved=json.loads((E/(sys.argv[1]+'-private.json')).read_text())
current={str(q):q for root in (Path('/data/params/d'),Path('/data/xpilot_plugins/.params')) if root.exists() for q in root.rglob('*') if q.is_file()}
changed=[]
for name in sorted(set(saved)|set(current)):
  q=Path(name)
  expected=base64.b64decode(saved[name]['base64']) if name in saved else None
  assert expected is None or hashlib.sha256(expected).hexdigest()==saved[name]['sha256']
  actual=q.read_bytes() if q.exists() else None
  if actual!=expected:
    changed.append(name)
    if expected is None:
      q.unlink()
    else:
      with tempfile.NamedTemporaryFile(dir=q.parent,delete=False) as f:
        f.write(expected)
      Path(f.name).replace(q)
  assert (q.read_bytes() if q.exists() else None)==expected
print(json.dumps({'snapshot':sys.argv[1],'byte_equal':True,'restored':changed,'files':len(saved)},indent=2))
