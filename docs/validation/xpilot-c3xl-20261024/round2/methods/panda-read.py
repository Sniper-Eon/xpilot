"""Failures: bootstub/wrong hardware, packet/version/signature mismatch, control,
ignition or fault. Only get_info/controlRead; never Panda.connect or writes.
"""
import hashlib,json
from pathlib import Path
from panda import Panda
from panda.python.spi import PandaSpiHandle
h=PandaSpiHandle()
info=h.get_info()
assert info[:12].hex()=='1d002d000a51303436323838' and info[12] in (0,9) and info[13]==0xcc
p=Panda.__new__(Panda)
p._handle=h
p.health_version,p.can_version=p.get_packets_versions()
fw=Path('panda/board/obj/panda_h7.bin.signed')
version=p.get_version()
built=Path('panda/board/obj/gitversion.h').read_text().split(chr(34))[1]
sig=p.get_signature()
expected=Panda.get_signature_from_firmware(str(fw))
health=p.health()
r={'method':'PandaSpiHandle get_info/controlRead only; Panda.__init__/connect not called','serial':info[:12].hex(),'raw_type':info[12:13].hex(),'bootstub':info[13]==0xee, 'info_hex':info.hex(),'version':version,'built_version':built,'firmware_sha256':hashlib.sha256(fw.read_bytes()).hexdigest(),'signature':sig.hex(),'built_signature':expected.hex(),'health':health}
print(json.dumps(r,indent=2))
assert version==built and sig==expected
assert not health['controls_allowed'] and health['faults']==0 and health['fault_status']==0
assert not health['ignition_line'] and not health['ignition_can']
h.close()
