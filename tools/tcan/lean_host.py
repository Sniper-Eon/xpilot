#!/usr/bin/env python3
"""Host-only upstream LANLink runner; only Params and live IPC are fixtures."""
import argparse
from pathlib import Path
import runpy
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--lean-root', type=Path, required=True)
p.add_argument('--port', type=int, default=18088)
a = p.parse_args()
sys.path.insert(0, str(a.lean_root.resolve()))
runpy.run_path(str(a.lean_root / 'openpilot/system/lanlinkd/tests/conftest.py'))
from openpilot.system.lanlinkd import lanlinkd

lanlinkd.StatusCache.run = lambda self, exit_event: exit_event.wait()
app = lanlinkd.create_app('tcan_integration_proof')
app.run(host='127.0.0.1', port=a.port, single_process=True, access_log=False, motd=False)
