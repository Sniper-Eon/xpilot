"""Snapshot trust-boundary files; raw params remain private outside Git."""
import base64,hashlib,json,subprocess,sys
from pathlib import Path
E=Path('/data/xpilot-X-20261024-08-round2-evidence')
assert Path('/data/params/d/IsOffroad').read_bytes()==b'1'
assert Path('/data/params/d/IsEngaged').read_bytes()==b'0'
roots=[Path('/data/params/d'),Path('/data/xpilot_plugins/.params')]
params={str(q):{'base64':base64.b64encode(q.read_bytes()).decode(),'sha256':hashlib.sha256(q.read_bytes()).hexdigest()} for root in roots if root.exists() for q in sorted(root.rglob('*')) if q.is_file()}
(E/(sys.argv[1]+'-private.json')).write_text(json.dumps(params,indent=2)+'\n')
(E/(sys.argv[1]+'-hashes.json')).write_text(json.dumps({q:r['sha256'] for q,r in params.items()},indent=2)+'\n')
store={str(q):hashlib.sha256(q.read_bytes()).hexdigest() for q in sorted(Path('/data/xpilot_plugins').rglob('*')) if q.is_file() and '.params' not in q.parts}
(E/(sys.argv[1]+'-store.json')).write_text(json.dumps(store,indent=2)+'\n')
print(json.dumps({'tag':sys.argv[1],'params_count':len(params),'store_files':len(store)}))
