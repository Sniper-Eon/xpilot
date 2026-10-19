#!/usr/bin/env python3
"""Temporary artifact -> actual Params/selector -> UI state + hardware alerts."""
import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from openpilot.common.params import Params
from openpilot.common.hardware.usb import CHESTNUT_USB_PRODUCT, CHESTNUT_USB_IDS
from openpilot.selfdrive.modeld import helpers as stock
from openpilot.sunnypilot.models import helpers as models
from openpilot.selfdrive.ui.ui_state import UIState
from openpilot.system.hardware.chestnut.status import ChestnutStatus

POINTER = b'version https://git-lfs.github.com/spec/v1\noid sha256:0000\n'


def run(output):
  subprocess.run([sys.executable, '-c',
                  'import sys; from openpilot.selfdrive.modeld.helpers import chestnut_compiled; '
                  + 'assert "openpilot.sunnypilot.models.helpers" not in sys.modules'], check=True)
  records = []
  with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    defaults = root / 'defaults'
    defaults.mkdir()
    selected = root / 'selected'
    selected.mkdir()
    params = Params(str(root / 'params'))
    drive = defaults / 'big_driving_tinygrad.pkl'
    warps = [defaults / f'big_driving_warp_{size}_tinygrad.pkl' for size in ('1344x760', '1928x1208')]
    for path in warps:
      path.write_bytes(b'compiled warp')
    bundle = {'internalName': 'fixture', 'ref': 'fixture', 'minimumSelectorVersion': models.REQUIRED_JSON_VERSION,
              'runner': 'tinygrad', 'models': [{'type': 'supercombo', 'artifact': {'fileName': 'fixture.pkl',
              'downloadUri': {'uri': 'https://example.invalid/fixture.pkl', 'sha256': 'abc'}}}]}
    ui = object.__new__(UIState)
    ui.params = params
    ui.started = False
    ui.chestnut_present = True
    ui.chestnut_active = None
    ui.chestnut_loading = False
    ui.sm = {'deviceState': SimpleNamespace(chestnutPresent=True)}
    ui.CP = None
    ui.CP_SP = None
    ui.has_longitudinal_control = False
    ui._sp_initialized = True
    ui.usb_connected = False
    usb = [{'vendorId': CHESTNUT_USB_IDS[0][0], 'productId': CHESTNUT_USB_IDS[0][1], 'product': CHESTNUT_USB_PRODUCT, 'speedMbps': 5000}]

    def check(name, default, ready):
      actual_default = stock.chestnut_compiled()
      actual = models.selected_chestnut_compiled(params)
      assert (actual_default, actual) == (default, ready), (name, actual_default, actual)
      ui.update_params()
      assert ui.chestnut_compiled == ready, (name, "UI runner override")
      ui._update_chestnut_state()
      assert ui.chestnut_state.value == ('ready' if ready else 'uncompiled'), (name, ui.chestnut_state)
      alerts = {}
      ChestnutStatus().update(True, 'dev-sp', usb, False, False, None, None,
                             lambda key, enabled, *args: alerts.update({key: enabled}))
      # Official removed Offroad_ChestnutUncompiled; a ready selection must not offer the branch switch.
      assert not (ready and alerts['Offroad_ChestnutBranch']), (name, alerts)
      records.append({'scenario': name, 'default_compiled': actual_default, 'selected_compiled': actual,
                      'ui_state': ui.chestnut_state.value})

    with patch.object(stock, 'MODELS_DIR', defaults), patch.object(models.Paths, 'model_root', return_value=str(selected)), \
         patch.object(models, 'Params', return_value=params), patch('openpilot.system.hardware.chestnut.status.MODELS_DIR', defaults), \
         patch('openpilot.system.hardware.chestnut.status.get_build_metadata', return_value=SimpleNamespace(channel='dev-sp')), \
         patch('openpilot.selfdrive.ui.ui_state.cable_connected', return_value=False), \
         patch.object(models, '_compute_hash', side_effect=AssertionError('periodic readiness must not hash')):
      check('absent_default', False, False)
      drive.write_bytes(POINTER)
      check('lfs_default', False, False)
      drive.write_bytes(b'compiled default')
      check('no_selection_default', True, True)
      params.put('ModelManager_ActiveBundleChestnut', {'minimumSelectorVersion': 1}, block=True)
      check('stale_selection_default', True, True)
      params.put('ModelManager_ActiveBundleChestnut', bundle, block=True)
      check('missing_selected_no_default_fallback', True, False)
      path = selected / 'fixture.pkl'
      path.write_bytes(POINTER)
      check('selected_lfs', True, False)
      path.write_bytes(b'')
      check('selected_empty', True, False)
      path.write_bytes(b'compiled selected')
      check('selected_complete', True, True)
      path.unlink()
      check('deletion_after_ready', True, False)
      warps[1].write_bytes(POINTER)
      check('warp_pointer', False, False)
      warps[1].write_bytes(b'compiled warp')
      params.put('ModelManager_ActiveBundleChestnut', {**bundle, 'models': []}, block=True)
      check('empty_bundle', True, False)
      incomplete = {**bundle, 'models': [{'type': 'supercombo', 'artifact': {'fileName': 'fixture.pkl'}}]}
      params.put('ModelManager_ActiveBundleChestnut', incomplete, block=True)
      check('artifact_without_hash', True, False)
      outside = root / 'outside.pkl'
      outside.write_bytes(b'compiled outside')
      for name in ('../outside.pkl', str(outside)):
        unsafe = json.loads(json.dumps(incomplete))
        unsafe['models'][0]['artifact']['fileName'] = name
        unsafe['models'][0]['artifact']['downloadUri'] = {'sha256': 'abc'}
        params.put('ModelManager_ActiveBundleChestnut', unsafe, block=True)
        check('artifact_path_escape_' + ('absolute' if Path(name).is_absolute() else 'relative'), True, False)
      (selected / 'escape.pkl').symlink_to(outside)
      unsafe['models'][0]['artifact']['fileName'] = 'escape.pkl'
      params.put('ModelManager_ActiveBundleChestnut', unsafe, block=True)
      check('artifact_symlink_escape', True, False)
      params.remove('ModelManager_ActiveBundleChestnut')
      params.put('ModelManager_ActiveBundle', bundle, block=True)
      check('qcom_slot_is_independent', True, True)
    with patch.object(models.Paths, 'model_root', return_value=str(selected)), patch.object(models, 'chestnut_present', return_value=True):
      activation = json.loads(json.dumps(bundle))
      artifact = activation['models'][0]['artifact']
      artifact['fileName'] = 'activation.pkl'
      payload = b'activation payload'
      artifact['downloadUri']['sha256'] = hashlib.sha256(payload).hexdigest()
      base = selected / artifact['fileName']

      def activate(name, kept, catalog_hash=None):
        activation['ref'] = name  # Force the existing once-per-selection validation cache to inspect each fixture.
        params.put('ModelManager_ActiveBundleChestnut', activation, block=True)
        current = models.get_selected_bundle(params, 'chestnut')
        if catalog_hash is not None:
          catalog = json.loads(json.dumps(activation))
          catalog['models'][0]['artifact']['downloadUri']['sha256'] = catalog_hash
          current = models.ModelManager.ModelBundle(**catalog)
        models.validate_active_bundles(params, {'chestnut': [current]})
        retained = params.get('ModelManager_ActiveBundleChestnut') is not None
        assert retained == kept, (name, retained)
        records.append({'scenario': name, 'activation_retained': retained, 'actual_activation_flow': True})

      base.write_bytes(payload)
      activate('activation_complete_file', True)
      activate('activation_catalog_sha_changed', False, catalog_hash='0' * 64)
      base.write_bytes(b'corrupt payload')
      activate('activation_corrupt_file', False)
      base.write_bytes(POINTER)
      activate('activation_lfs_pointer', False)
      base.unlink()
      activate('activation_missing_file', False)
      outside = root / 'activation-outside'
      outside.write_bytes(payload)
      base.symlink_to(outside)
      activate('activation_symlink_escape', False)
  result = {'passed': True, 'scope': 'local artifact/Params/UI state/hardware alert integration; no physical inference',
            'stock_import_independent': True, 'periodic_hashing': False, 'cases': records}
  output.parent.mkdir(parents=True, exist_ok=True)
  output.write_text(json.dumps(result, indent=2) + '\n')
  print(output)


if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument('--output', type=Path, required=True)
  run(parser.parse_args().output)
