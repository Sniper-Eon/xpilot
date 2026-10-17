#!/usr/bin/env python3
"""Execute model compiler CLI and CI catalog extraction from the checked-out source."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import yaml


def run(output: Path):
  root = Path(__file__).resolve().parents[2]
  records = []
  result = {'passed': False, 'source': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
            'scope': 'real compiler CLI, workflow script paths and executed CI catalog matrix; no native GPU build', 'cases': records}
  try:
    workflow = root / '.github/workflows/build-default-models.yaml'
    text = workflow.read_text()
    for relative in set(re.findall(r'tinygrad_repo/examples/openpilot/compile\w*\.py', text)):
      assert (root / relative).is_file(), f'CI compiler is missing: {relative}'
    completed = subprocess.run([sys.executable, str(root / 'tinygrad_repo/examples/openpilot/compile_onnx.py'), '--help'],
                               cwd=root, env=os.environ | {'DEV': 'CPU:LLVM'}, capture_output=True, text=True, check=True)
    assert '--out-of-band' in completed.stdout and '--benchmark-runs' in completed.stdout
    records.append({'scenario': 'real_native_compiler_cli', 'stdout': completed.stdout})
    source = root / 'openpilot/selfdrive/modeld/models/big_driving_supercombo.onnx'
    pointer = subprocess.check_output(['git', 'lfs', 'pointer', '--file', str(source)], cwd=root, text=True)
    assert 'oid sha256:6fee5937923c74848df4a63f6239eb6331c6274dd4bdb7a5d6ec0388a8b543d5' in pointer
    assert 'size 766018462' in pointer
    records.append({'scenario': 'original_default_big_source_identity', 'lfs_pointer': pointer})
    document = yaml.safe_load((root / '.github/workflows/test_models.yml').read_text())
    matrix_step = next(step for step in document['jobs']['generate-matrix']['steps'] if step.get('id') == 'set-matrix')
    with tempfile.TemporaryDirectory() as temp:
      github_output = Path(temp) / 'matrix.txt'
      subprocess.run(['bash', '-e', '-c', matrix_step['run']], cwd=root,
                     env=os.environ | {'GITHUB_OUTPUT': str(github_output)}, check=True)
      line = github_output.read_text().strip()
      assert line.startswith('models=')
      artifacts = json.loads(line.removeprefix('models='))
      assert len(artifacts) == 93, len(artifacts)
      assert len({artifact['download_uri']['sha256'] for artifact in artifacts}) == 93
      records.append({'scenario': 'executed_ci_catalog_matrix', 'models': len(artifacts),
                      'matrix_sha256': hashlib.sha256(line.encode()).hexdigest()})
    result['passed'] = True
  except Exception as error:
    result['error'] = f'{type(error).__name__}: {error}'
    raise
  finally:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(output)


if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument('--output', type=Path, required=True)
  run(parser.parse_args().output)
