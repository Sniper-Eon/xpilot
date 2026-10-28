#!/usr/bin/env python3
"""Failures before source sync: upstream commits absent, user fork remotes lost,
Chinese UI or either navigation package removed, old firmware manifests mixed
with a new host. Local Git ancestry is source evidence, never device activation.
"""
import argparse
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
PINS={'xpilot':'38b158fbcc9a3cfad0b12b44d008bb9a32839dae','xpilot-plugins':'36f2bfedca506ef86b79701c550820ef1f8a1a06'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--plugins-repo',type=Path,default=ROOT.parent/'xpilot-plugins');args=ap.parse_args()
 errors=[]
 for name,path in [('xpilot',ROOT),('xpilot-plugins',args.plugins_repo.resolve())]:
  if subprocess.run(['git','merge-base','--is-ancestor',PINS[name],'HEAD'],cwd=path,capture_output=True).returncode:
   errors.append(name+': upstream revision is not an ancestor')
  remote=subprocess.check_output(['git','remote','get-url','origin'],cwd=path,text=True).strip()
  if 'github.com/Sniper-Eon/'+name not in remote:errors.append(name+': wrong push fork')
 for name in ['cp_nav','navassist','zh_cn']:
  path=args.plugins_repo/'plugins'/name/'plugin.json'
  if not path.exists():errors.append('missing preserved plugin '+name)
  else:
   d=json.loads(path.read_text());key=d.get('enable_param')
   if not key or d.get('params',{}).get(key,{}).get('type')!='BOOL':errors.append(name+': missing independent master')
 for name in ['cp_nav','navassist','nav_lane_change']:
  d=json.loads((args.plugins_repo/'plugins'/name/'plugin.json').read_text())
  if 'source:turnsignals' not in d.get('claims',[]):errors.append(name+': competing physical navigation signals not exclusive')
 for path in (args.plugins_repo/'plugins').glob('*/plugin.json'):
  if 'safety' in json.loads(path.read_text()):errors.append(path.parent.name+': legacy firmware manifest remains')
 print(json.dumps({'source_only':True,'errors':errors},indent=2));return bool(errors)

if __name__=='__main__':raise SystemExit(main())
