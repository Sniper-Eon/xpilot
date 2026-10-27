"""Failure cases: float core settings reject integer choice values; onroad
callbacks write anyway; toggles or integer delays are coerced to wrong types.
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from openpilot.tesla.ui.settings_meta import write_setting

class P:
  def __init__(self):self.values={'speed':19.,'delay':2,'on':True};self.writes=[]
  def get(self,key,**kw):return self.values[key]
  def put(self,key,value,**kw):
    assert type(value)==type(self.values[key])
    self.values[key]=value;self.writes.append((key,value))

p=P()
assert not write_setting(p,'speed',18,False) and not p.writes
assert write_setting(p,'speed',18,True) and p.values['speed']==18.
assert type(p.values['speed']) is float
assert write_setting(p,'delay',3,True) and type(p.values['delay']) is int
assert write_setting(p,'on',False,True) and p.values['on'] is False
print('parked typed settings: passed')
