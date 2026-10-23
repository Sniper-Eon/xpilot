"""Recheck saved device evidence only. Fail on wrong source, safety/process/tile
state, failed checks/E2E, parameter drift, UI traceback or damaged/oversized PNG.
No device, repository or parameter writes.
"""
import hashlib
import json
from pathlib import Path
import re
import struct
import zlib

root=Path(__file__).resolve().parent
target='f7af016516db4043bec0af24e6d3133fd864dfc9'
read=lambda name: json.loads((root/name).read_text())
checks=dict(line.split('\t') for line in (root/'check-exit-codes.tsv').read_text().splitlines())
assert len(checks)==8 and set(checks.values())=={'0'}
assert (root/'build.exit').read_text().strip()=='0'
assert (root/'big-screen.exit').read_text().strip()=='0'
assert (root/'store-e2e.exit').read_text().strip()=='0'
big=read('big-screen/result.json')
assert big['head']==target and big['passed'] and not big['errors']
store_text=(root/'store-e2e.log').read_text()
store=json.loads(store_text[store_text.index('{'):])
assert store['installed']==['op_models','overspeed_warning'] and not store['errors']
for state in ['default','enabled','disabled','removed','final']:
  name=f'{state}-running.jsonl' if state!='final' else 'final.jsonl'
  rows=[json.loads(line) for line in (root/name).read_text().splitlines()]
  runtime=rows[0]['runtime_before']
  assert runtime['head']==target and runtime['hostname']=='comma-9c13c9f5' and runtime['hardware_profile']=='c3xl'
  assert runtime['service']=='active' and runtime['IsOffroad'] and not runtime['IsEngaged'] and not runtime['started']
  assert runtime['panda_samples']
  for sample in runtime['panda_samples']:
    assert sample and all(not p['controlsAllowed'] and p['faultStatus']=='none' and not p['faults'] and not p['ignitionLine'] and not p['ignitionCan'] for p in sample)
  panda=rows[1]['panda_readonly']
  assert panda['version_match'] and panda['signature_match']
  procs={p['name']:p for p in runtime['processes']}
  for name in ['models_manager','modeld_warmup']:
    assert procs[name]['running']==(state!='enabled') and procs[name]['exitCode']==0
  assert all(not procs.get(name,{}).get('running',False) for name in ['modeld','modeld_tinygrad','op_modeld'])
  assert all(procs[name]['running'] and procs[name]['exitCode']==0 for name in ['ui','pandad','hardwared'])
  if state!='final':
    ui=read(f'{state}-ui/result.json')
    assert ui['passed'] and not ui['load_errors']
    assert ui['owner']==('op_models' if state=='enabled' else 'sp_models')
    assert ('models' in ui['placed'])==(state!='enabled')
    assert ('op_models' in ui['placed'])==(state=='enabled')
    if state=='enabled':
      assert ui['conflicts']['sp_models']=='op_models' and ui['page_status']['sp_models']=='conflict'
preserved=read('preservation.json')
assert preserved['passed'] and preserved['store_files_exact'] and preserved['dirty_files_exact']
assert preserved['op_models_absent'] and preserved['ExtOpModels_absent']
assert len(preserved['params'])==5 and all(p['byte_equal'] for p in preserved['params'].values())
before=read('params-before.json')
final=json.loads((root/'final.jsonl').read_text().splitlines()[0])['runtime_before']
assert before==final['params']
logs=sorted(set(root.glob('*-startup.log'))|set(root.glob('*ui.log'))|{root/'big-screen.log',root/'ui-runtime.log'})
pattern=re.compile(r'Traceback \(most recent call last\)|ModuleNotFoundError|ui module .* failed to load|ui widget .* failed to construct|xpilot plugin .* failed in|tile .* failed|overlay .* failed')
assert not [(str(p.relative_to(root)),m.group()) for p in logs for m in pattern.finditer(p.read_text())]
pngs=list(root.rglob('*.png'))
scanlines={}
for p in pngs:
  data=p.read_bytes()
  assert len(data)<400000 and data[:8]==b'\x89PNG\r\n\x1a\n'
  offset=8
  compressed=b''
  while offset<len(data):
    size=struct.unpack('>I',data[offset:offset+4])[0]
    kind=data[offset+4:offset+8]
    chunk=data[offset+8:offset+8+size]
    assert zlib.crc32(kind+chunk)&0xffffffff==struct.unpack('>I',data[offset+8+size:offset+12+size])[0]
    if kind==b'IDAT':
      compressed+=chunk
    offset+=size+12
  scanlines[str(p.relative_to(root))]=hashlib.sha256(zlib.decompress(compressed)).hexdigest()
for row in read('png-lossless-compression.json'):
  assert scanlines[row['path']]==row['scanlines_sha256']
  assert hashlib.sha256((root/row['path']).read_bytes()).hexdigest()==row['final_sha256']
print(json.dumps({'passed':True,'source_commit':target,'failure_modes':{c:'PASS' for c in 'abcd'},'checks':{k:int(v) for k,v in checks.items()},'big_screen_passed':True,'store_e2e_errors':[],'png_count':len(pngs),'max_png_bytes':max(p.stat().st_size for p in pngs),'params_exact':5,'dirty_files_exact':preserved['dirty_file_count'],'store_files_exact':preserved['store_file_count'],'op_modeld_onroad':'NOT RUN'},indent=2))
