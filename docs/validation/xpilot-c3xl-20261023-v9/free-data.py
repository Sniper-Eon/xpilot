"""Failure modes: live path deletion, wrong host/profile, onroad state, unreadable process list,
in-use path deletion, deletion outside the approved list, missing byte accounting, insufficient free space.
"""
import json
import os
from pathlib import Path
import socket
import subprocess

paths = '''/data/sp-sync-experiment-20261017
/data/agnos-offline-20261013
/data/nav-reboot-baseline-20261013
/data/navassist-track-p0-offline
/data/c3xl194_bmv4_20min_20260917
/data/openpilot-before-offline-20261013
/data/prebuild-baseline-20261013
/data/dev-sp-nav-prebuild-offline
/data/c3xl-1344-build
/data/c3xl-resolution-20261010
/data/dev-sp-nav-prebuild.tar.gz
/data/c3xl-ctm-1344-20260923
/data/c3xl-1344-evidence'''.splitlines()
assert socket.gethostname() == 'comma-9c13c9f5'
assert Path('/data/hardware_profile').read_text().strip() == 'c3xl'
active = subprocess.check_output(['readlink', '-f', '/data/openpilot'], text=True).strip()
print(json.dumps({'active': active}), flush=True)
for path in paths:
 for q in (path, str(Path(path).resolve())):
  assert active != q and not active.startswith(q + '/'), (path, active)
assert Path('/data/params/d/IsOffroad').read_bytes() == b'1'
print(subprocess.check_output(['df', '-B1', '/data'], text=True), flush=True)
before = os.statvfs('/data')
print(json.dumps({'avail_before': before.f_bavail * before.f_frsize}), flush=True)
for path in paths:
 proc = subprocess.run(['sudo', 'lsof'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
 assert proc.returncode == 0, ('lsof', proc.returncode)
 used = [line for line in proc.stdout.splitlines() if path in line]
 if used:
  print(json.dumps({'path': path, 'result': 'SKIP_IN_USE', 'references': used}), flush=True)
  continue
 if not Path(path).exists():
  print(json.dumps({'path': path, 'result': 'ABSENT', 'allocated_bytes': 0, 'df_delta_bytes': 0}), flush=True)
  continue
 size = int(subprocess.check_output(['sudo', 'du', '-sx', '-B1', path], text=True).split()[0])
 a = os.statvfs('/data')
 assert Path('/data/params/d/IsOffroad').read_bytes() == b'1'
 assert Path('/data/params/d/IsEngaged').read_bytes() == b'0'
 print('sudo rm -rf ' + path, flush=True)
 subprocess.run(['sudo', 'rm', '-rf', path], check=True)
 assert not Path(path).exists()
 b = os.statvfs('/data')
 print(json.dumps({'path': path, 'result': 'DELETED', 'allocated_bytes': size, 'df_delta_bytes': b.f_bavail * b.f_frsize - a.f_bavail * a.f_frsize, 'lsof_matches': 0}), flush=True)
after = os.statvfs('/data')
print(subprocess.check_output(['df', '-B1', '/data'], text=True), flush=True)
print(json.dumps({'avail_after': after.f_bavail * after.f_frsize}), flush=True)
assert after.f_bavail * after.f_frsize >= 8589934592
