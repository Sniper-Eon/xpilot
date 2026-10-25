#!/usr/bin/env python3
"""Before implementation: personal builds must not fetch another owner's plugins.

Check the real store URL, generated artifact URLs, CI peer checkout and documented
push routing. A complete store install is checked separately by store_e2e.py.
"""
import argparse
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def assignment(path, name):
  for node in ast.parse(path.read_text()).body:
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
      return ast.literal_eval(node.value)
  return None


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('--repo', type=Path, required=True)
  parser.add_argument('--owner', default='Sniper-Eon')
  args = parser.parse_args()
  raw = f'https://raw.githubusercontent.com/{args.owner}/xpilot-plugins/main'
  errors = []
  if assignment(ROOT/'openpilot/tesla/store.py', 'INDEX_URL') != raw+'/index.json':
    errors.append('Host downloads the wrong catalog')
  if assignment(args.repo/'tools/build_index.py', 'RAW') != raw:
    errors.append('Builder publishes another owners artifact URLs')
  for entry in json.loads((args.repo/'index.json').read_text())['plugins']:
    if not entry['url'].startswith(raw+'/dist/'):
      errors.append('Wrong artifact owner: '+entry['id'])
  for path, peer in [(ROOT/'.github/workflows/xpilot.yaml', 'xpilot-plugins'),
                     (args.repo/'.github/workflows/ci.yml', 'xpilot')]:
    if f'repository: {args.owner}/{peer}' not in path.read_text():
      errors.append('Wrong CI peer: '+str(path))
  print(json.dumps({'errors': errors}, indent=2))
  return bool(errors)


if __name__ == '__main__':
  raise SystemExit(main())
