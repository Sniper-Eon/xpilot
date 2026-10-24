"""Compare every required message with compare_logs, zero numerical tolerance, preserving first differing frame evidence."""
import json
from collections import Counter
from pathlib import Path
from openpilot.selfdrive.test.process_replay.compare_logs import compare_logs
from openpilot.tools.lib.logreader import LogReader
E=Path('/data/xpilot-X-20261024-08-round2-evidence')
required={'selfdrived':['selfdriveState','selfdriveStateSP','onroadEvents','onroadEventsSP'],'controlsd':['carControl'],'card':['sendcan']}
ignore=['logMonoTime','carState.cumLagMs','controlsState.deprecated.cumLagMs','controlsState.deprecated.startMonoTime']
r={'ignored_fields':ignore,'tolerance':0,'processes':{},'passed':True}
for proc,kinds in required.items():
  all_a=list(LogReader(str(E/'replay/base'/(proc+'.zst'))))
  all_b=list(LogReader(str(E/'replay/head'/(proc+'.zst'))))
  pr={'base_counts':dict(Counter(m.which() for m in all_a)),'head_counts':dict(Counter(m.which() for m in all_b)),'types':{},'passed':True}
  pr['required_types']=kinds
  for kind in sorted(set(pr['base_counts'])|set(pr['head_counts'])):
    a=[m for m in all_a if m.which()==kind]
    b=[m for m in all_b if m.which()==kind]
    diffs=[]
    if not a or not b or len(a)!=len(b):
      diffs.append({'kind':'message_count','base':len(a),'head':len(b)})
    for index,(ma,mb) in enumerate(zip(a,b)):
      dd=compare_logs([ma],[mb],ignore_fields=ignore,tolerance=0)
      if dd:
        diffs.append({'frame':index,'base_logMonoTime':ma.logMonoTime,'head_logMonoTime':mb.logMonoTime,'diff':dd})
    pr['types'][kind]={'base':len(a),'head':len(b),'differing_frames':len(diffs),'first_differences':diffs[:5]}
    if diffs:
      pr['passed']=r['passed']=False
      (E/'replay'/(proc+'-'+kind+'-diffs.json')).write_text(json.dumps(diffs,indent=2,default=str)+'\n')
  r['processes'][proc]=pr
(E/'replay-comparison.json').write_text(json.dumps(r,indent=2,default=str)+'\n')
print(json.dumps(r,indent=2,default=str))
raise SystemExit(0 if r['passed'] else 1)
