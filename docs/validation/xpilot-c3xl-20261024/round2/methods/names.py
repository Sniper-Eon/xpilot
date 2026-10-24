"""Detect duplicate registrations before dict conversion, and record all managed names."""
import json
from collections import Counter
from openpilot.system.manager.process_config import procs,managed_processes
names=[p.name for p in procs]
r={'names':sorted(names),'duplicates':{n:c for n,c in Counter(names).items() if c>1},'managed_names':sorted(managed_processes)}
print(json.dumps(r,indent=2))
assert not r['duplicates']
assert sorted(names)==sorted(managed_processes)
