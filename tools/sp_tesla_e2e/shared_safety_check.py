#!/usr/bin/env python3
"""Failures first: independent mutually-exclusive navigation plugins cannot use
one existing firmware-verified TX policy; an alias grants undeclared addresses,
changes safety bits, or weakens ordinary store validation. Firmware is unchanged.
"""
from pathlib import Path
import json,tempfile,unittest,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from openpilot.tesla import manifest as mf

class SharedSafety(unittest.TestCase):
 def make(self,**changes):
  doc=dict(id='cp_nav',name='CP Navigation',version='0.1.0',api=1,category='navigation',entry='plugin:CPNav',enable_param='ExtCpNavEnabled',claims=['can.tx:0x3E9:1','role:lane_change.policy'],safety_provider='navassist',safety={'header':'navassist.h','param_bit':'0x8000','tx':['0x3E9:1']})
  doc.update(changes)
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'cp_nav';p.mkdir();(p/'plugin.json').write_text(json.dumps(doc));return mf.parse(p/'plugin.json')
 def registry(self):return {'navassist':{'header':'navassist.h','param_bit':'0x8000','tx':['0x3E9:1']}}
 def test_provider_is_preserved_and_bounded_to_existing_policy(self):
  m=self.make();self.assertEqual(m.safety_provider,'navassist');self.assertIsNone(mf.safety_problem(m,self.registry()))
 def test_unknown_provider_denied(self):
  self.assertIsNotNone(mf.safety_problem(self.make(safety_provider='missing'),self.registry()))
 def test_different_address_or_bit_denied(self):
  for changes in ({'claims':['can.tx:0x123:1']},{'safety':{'header':'navassist.h','param_bit':'0x4000','tx':['0x3E9:1']}}):
   self.assertIsNotNone(mf.safety_problem(self.make(**changes),self.registry()))
 def test_ordinary_self_owned_policy_remains_valid(self):
  self.assertIsNone(mf.safety_problem(self.make(safety_provider=None),{'cp_nav':self.registry()['navassist']}))
 def test_claim_conflicts_prevent_two_navigation_senders(self):
  items=[('cp_nav',100,['can.tx:0x3E9:1','role:lane_change.policy']),('navassist',100,['can.tx:0x3E9:1','role:lane_change.policy'])]
  active,conflicts=mf.resolve(items,{'cp_nav','navassist'});self.assertEqual(len(active),1);self.assertEqual(len(conflicts),1)

if __name__=='__main__':unittest.main()
