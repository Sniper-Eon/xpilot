"""Recheck saved evidence without a device: hashes, build, rc inventory, E2Es,
default path, production safety, params/store preservation, Alpha persistence, image limits.
"""
import hashlib
import json
from pathlib import Path
import struct
import zlib

root=Path(__file__).resolve().parent
for line in (root/'SHA256SUMS').read_text().splitlines():
 digest,path=line.split('  ',1)
 assert hashlib.sha256((root/path).read_bytes()).hexdigest()==digest,path
E=root/'device'
load=lambda name:json.loads((E/name).read_text())
assert (E/'build.exit').read_text().strip()=='0'
build=(E/'build.log').read_text()
assert 'capnpc ' in build and 'custom.capnp' in build and 'scons: done building targets.' in build
rc=dict(line.split('\t') for line in (E/'check-exit-codes.tsv').read_text().splitlines())
assert len(rc)==9 and rc['phase4_check.py']=='0' and all(v=='0' for v in rc.values()),rc
assert (E/'big-screen.exit').read_text().strip()=='0'
assert (E/'store-e2e.exit').read_text().strip()=='0'
assert load('big-screen/result.json')['passed']
store_text=(E/'store-e2e.log').read_text()
store=json.loads(store_text[store_text.index('{'):])
assert store['errors']==[],store
p=load('default-path.json')
assert p['core_alive'] and p['gate_sm_is_none'] and p['install_core_noop'] and p['xpilotPluginFault_enum']==29
assert p['owners']=={'role:engagement.state':'sp_engagement','role:safety.fallback':'sp_safety_fallback'}
assert not p['LOAD_ERRORS'] and not p['faults']
prod=load('production-runtime.json')
assert prod['passed'] and prod['elapsed_seconds']>=60 and prod['panda_sample_count']>=500
assert all(not q['controlsAllowed'] and not q['faults'] and q['faultStatus']=='none' and not q['ignitionLine'] and not q['ignitionCan'] for row in prod['panda_samples'] for q in row)
ui=load('core-ui/result.json')
assert ui['passed']
assert len(ui['categories'])==2
assert all(v['enable_param'] is None and not v['toggle_enabled'] and v['toggle_state'] for v in ui['categories'].values())
assert all(v['byte_equal'] for v in load('params-restored-after-final-start.json').values())
assert load('preservation.json')['passed']
alpha=[json.loads(line) for line in (E/'alpha-long.jsonl').read_text().splitlines()]
assert alpha[-1]['elapsed_seconds']>=60 and alpha[-1]['param_bool'] and not alpha[-1]['removed']
png_rows=json.loads((root/'png-lossless-compression.json').read_text())
for row in png_rows:
 data=(root/row['path']).read_bytes()
 pos=8
 packed=[]
 while pos<len(data):
  n=struct.unpack('>I',data[pos:pos+4])[0]
  if data[pos+4:pos+8]==b'IDAT': packed.append(data[pos+8:pos+8+n])
  pos+=12+n
 assert hashlib.sha256(zlib.decompress(b''.join(packed))).hexdigest()==row['scanlines_sha256']
 assert hashlib.sha256(data).hexdigest()==row['final_sha256']
images=list(E.rglob('*.png'))
assert images and all(p.stat().st_size<400000 for p in images)
assert all(struct.unpack('>II',p.read_bytes()[16:24])==(2160,1080) for p in images)
print(json.dumps({'passed':True,'checks':rc,'screenshots':len(images),'maximum_png_bytes':max(p.stat().st_size for p in images),'build_rc':0,'big_screen_passed':True,'store_errors':store['errors'],'alpha_param_after_60s':alpha[-1]['param_bool']},indent=2))
