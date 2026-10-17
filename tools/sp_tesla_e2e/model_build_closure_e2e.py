#!/usr/bin/env python3
"""Execute model compiler CLI and CI catalog extraction from the checked-out source."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
from types import SimpleNamespace

import yaml


def run(output: Path):
  root = Path(__file__).resolve().parents[2]
  records = []
  result = {'passed': False, 'source': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
            'scope': 'real compiler CLI, workflow script paths and executed CI catalog matrix; no native GPU build', 'cases': records}
  try:
    build_tree = ast.parse((root / 'openpilot/selfdrive/modeld/SConscript').read_text())
    flag_assignment = next(node for node in ast.walk(build_tree) if isinstance(node, ast.Assign) and
                           any(isinstance(target, ast.Name) and target.id == 'chestnut_tg_flags' for target in node.targets))
    generated = []
    namespace = {'File': lambda path: SimpleNamespace(abspath=path), 'Value': lambda value: value,
                 'chestnut_tg_flags': ast.literal_eval(flag_assignment.value), 'tg_flags': 'DEV=QCOM',
                 'mac_brew_string': '', 'taskset': 'taskset -c 7 ', 'compiler': 'tinygrad_repo/examples/openpilot',
                 'tinygrad_files': [], 'chestnut_lock': 'model-lock', 'chestnut_action': lambda command: command,
                 'lenv': SimpleNamespace(Command=lambda target, source, action: generated.append(action) or ['model'],
                                         SideEffect=lambda *args: None)}
    function = next(node for node in build_tree.body if isinstance(node, ast.FunctionDef) and node.name == 'compile_model')
    exec(compile(ast.Module(body=[function], type_ignores=[]), '<actual SCons compile_model>', 'exec'), namespace)
    namespace['compile_model']('big-original.onnx', 'big-native.pkl', chestnut=True)
    workflow_doc = yaml.safe_load((root / '.github/workflows/build-default-models.yaml').read_text())
    ci_step = next(step for step in workflow_doc['jobs']['build_big_model']['steps']
                   if step.get('name') == 'Compile native big model from original ONNX')
    ci_prefix = ci_step['run'].split(' env ', 1)[1].split('python3', 1)[0]
    ci_flags = dict(word.split('=', 1) for word in shlex.split(ci_prefix) if '=' in word)
    local_flags = dict(word.split('=', 1) for word in shlex.split(generated[0].split('python3', 1)[0]) if '=' in word and not word.startswith('DEBUG='))
    assert ci_flags.get('OPENPILOT_HACKS') == '1' and local_flags == ci_flags, (local_flags, ci_flags)
    records.append({'scenario': 'actual_native_big_build_command_parity', 'scons_command': generated[0], 'env': local_flags})
    workflow = root / '.github/workflows/build-default-models.yaml'
    text = workflow.read_text()
    for relative in set(re.findall(r'tinygrad_repo/examples/openpilot/compile\w*\.py', text)):
      assert (root / relative).is_file(), f'CI compiler is missing: {relative}'
    completed = subprocess.run([sys.executable, str(root / 'tinygrad_repo/examples/openpilot/compile_onnx.py'), '--help'],
                               cwd=root, env=os.environ | {'DEV': 'CPU:LLVM',
                               'PYTHONPATH': f"{root / 'tinygrad_repo'}:{root}:{os.environ.get('PYTHONPATH', '')}"},
                               capture_output=True, text=True, check=True)
    assert '--out-of-band' in completed.stdout and '--benchmark-runs' in completed.stdout
    records.append({'scenario': 'real_native_compiler_cli', 'stdout': completed.stdout})
    source = root / 'openpilot/selfdrive/modeld/models/big_driving_supercombo.onnx'
    with source.open('rb') as stream:
      is_pointer = stream.read(64).startswith(b'version https://git-lfs.github.com/spec/v1')
    pointer = source.read_text() if is_pointer else subprocess.check_output(['git', 'lfs', 'pointer', '--file', str(source)], cwd=root, text=True)
    assert 'oid sha256:6fee5937923c74848df4a63f6239eb6331c6274dd4bdb7a5d6ec0388a8b543d5' in pointer
    assert 'size 766018462' in pointer
    records.append({'scenario': 'original_default_big_source_identity', 'lfs_pointer': pointer})
    document = yaml.safe_load((root / '.github/workflows/test_models.yml').read_text())
    matrix_step = next(step for step in document['jobs']['generate-matrix']['steps'] if step.get('id') == 'set-matrix')
    with tempfile.TemporaryDirectory() as temp:
      github_output = Path(temp) / 'matrix.txt'
      subprocess.run(['bash', '-e', '-c', matrix_step['run']], cwd=root,
                     env=os.environ | {'GITHUB_OUTPUT': str(github_output),
                     'PATH': f"{Path(sys.executable).parent}:{os.environ.get('PATH', '')}"}, check=True)
      line = github_output.read_text().strip()
      assert line.startswith('models=')
      artifacts = json.loads(line.removeprefix('models='))
      assert len(artifacts) == 93, len(artifacts)
      assert all(len(artifact['download_uri']['sha256']) == 64 for artifact in artifacts)
      records.append({'scenario': 'executed_ci_catalog_matrix', 'models': len(artifacts),
                      'unique_artifacts': len({artifact['download_uri']['sha256'] for artifact in artifacts}),
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
