"""Preserve stale activation markers after observed automatic downgrade; no product/Params/network edits."""
import hashlib,json,subprocess,time
from pathlib import Path
E=Path('/data/xpilot-X-20261024-08-round2-evidence')
root=Path('/data/openpilot')
assert root.resolve()==Path('/data/xpilot-agnos19.9-20261025/candidate')
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()=='4292551111be2d7afa7cf9aa158841fb712e740b'
assert Path('/data/params/d/IsOffroad').read_bytes()==b'1' and Path('/data/params/d/IsEngaged').read_bytes()==b'0'
staged=Path('/data/safe_staging/finalized')
sha=subprocess.check_output(['git','-C',str(staged),'rev-parse','HEAD'],text=True).strip() if staged.exists() else None
saved={}
if sha=='65bb09e3d5d306487d005f15cef799e31cf37fa2':
 for name,path in [('candidate-init',root/'.overlay_init'),('finalized-consistent',staged/'.overlay_consistent')]:
  if path.exists():
   destination=E/('publish-quarantined-'+name)
   assert not destination.exists()
   saved[str(path)]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'mtime_ns':path.stat().st_mtime_ns,'saved_to':str(destination)}
   path.rename(destination)
r={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'active_commit':'4292551111be2d7afa7cf9aa158841fb712e740b','staged_commit':sha,'saved_markers':saved,'init_exists':(root/'.overlay_init').exists(),'consistent_exists':(staged/'.overlay_consistent').exists(),'updated_config_changed':False,'future_updater_can_restage':True}
(E/'pending-update-quarantine.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2))
