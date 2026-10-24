"""Failures: wrong device/head, unsafe state, running service, unexpected install
or params, wrong repository, install/hash/load error, wrong owner or failed removal.
Only op_models is installed/removed; only ExtOpModels is written through ParamsView.
"""
import argparse
import json
from pathlib import Path
import socket
import subprocess
from openpilot.common.params import Params
from openpilot.tesla import store,manifest
from openpilot.tesla.plugin_params import ParamsView

ap=argparse.ArgumentParser()
ap.add_argument('action',choices=['install-enable','disable','uninstall'])
action=ap.parse_args().action
assert socket.gethostname()=='comma-9c13c9f5'
assert Path('/data/hardware_profile').read_text().strip()=='c3xl'
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()=='f7af016516db4043bec0af24e6d3133fd864dfc9'
assert subprocess.run(['systemctl','is-active','--quiet','comma.service']).returncode!=0
params=Params()
assert params.get_bool('IsOffroad') and not params.get_bool('IsEngaged')
assert manifest.INSTALL_DIR==Path('/data/xpilot_plugins')
repo=Path('/data/xpilot-install-20261022/xpilot-X-20261023-11-plugins')
assert subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()=='edab6ec127a40c6e4d56e08409d9d9f53435c075'
result={'action':action,'install_dir':str(manifest.INSTALL_DIR)}
if action=='install-enable':
  assert not (manifest.INSTALL_DIR/'op_models').exists()
  assert not (manifest.INSTALL_DIR/'.params/ExtOpModels').exists()
  index=json.loads((repo/'index.json').read_text())
  for e in index['plugins']:
    e['url']=(repo/e['url'].split('/main/',1)[1]).as_uri()
  path=Path('/data/xpilot-ui-check-v8-evidence/local-index.json')
  path.write_text(json.dumps(index,indent=2)+'\n')
  entries,error=store.fetch_index(path.as_uri())
  assert error is None,error
  entry=next(e for e in entries if e.id=='op_models')
  error=store.install(entry)
  result.update(entry=entry.__dict__,install_error=error)
  print(json.dumps(result),flush=True)
  assert error is None,error
  ParamsView(params).put_bool('ExtOpModels',True)
elif action=='disable':
  ParamsView(params).put_bool('ExtOpModels',False)
else:
  ParamsView(params).remove('ExtOpModels')
  store.uninstall('op_models')
  assert not (manifest.INSTALL_DIR/'op_models').exists()
  assert not (manifest.INSTALL_DIR/'.params/ExtOpModels').exists()
from openpilot.tesla import plugins
assert not plugins.LOAD_ERRORS,plugins.LOAD_ERRORS
owner=plugins.owner(params,'role:perception.model')
assert owner==('op_models' if action=='install-enable' else 'sp_models'),owner
result.update(owner=owner,load_errors=plugins.LOAD_ERRORS,installed_versions=store.installed_versions())
print(json.dumps(result,indent=2))
