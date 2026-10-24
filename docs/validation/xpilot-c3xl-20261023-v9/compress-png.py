"""Only repack PNG IDAT losslessly when required by the report's 400 KB limit.
Assert decompressed scanlines unchanged; keep every device original on the device.
"""
import hashlib
import json
from pathlib import Path
import struct
import zlib
root=Path(__file__).resolve().parent/'device'
rows=[]
for p in root.rglob('*.png'):
 before=p.read_bytes()
 pos=8
 chunks=[]
 while pos<len(before):
  n=struct.unpack('>I',before[pos:pos+4])[0]
  kind=before[pos+4:pos+8]
  payload=before[pos+8:pos+8+n]
  chunks.append((kind,payload))
  pos+=12+n
 raw=zlib.decompress(b''.join(d for k,d in chunks if k==b'IDAT'))
 if len(before)>=400000:
  out=before[:8]
  done=False
  for kind,payload in chunks:
   if kind==b'IDAT':
    if done: continue
    payload=zlib.compress(raw,9)
    done=True
   out+=struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload))
  assert zlib.decompress(zlib.compress(raw,9))==raw
  p.write_bytes(out)
 after=p.read_bytes()
 assert len(after)<400000,(str(p),len(after))
 rows.append({'path':str(p.relative_to(root.parent)),'original_bytes':len(before),'final_bytes':len(after),'original_sha256':hashlib.sha256(before).hexdigest(),'final_sha256':hashlib.sha256(after).hexdigest(),'scanlines_sha256':hashlib.sha256(raw).hexdigest(),'scanlines_unchanged':True})
(root.parent/'png-lossless-compression.json').write_text(json.dumps(rows,indent=2)+'\n')
print('PNG count',len(rows),'maximum bytes',max(r['final_bytes'] for r in rows))
