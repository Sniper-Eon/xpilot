"""Wait for startup's IsOffroad rebuild; fail on any observed started/control/fault.
Then take the full v7 read-only gate separately. Never write runtime state.
"""
import time
from openpilot.common.params import Params
from openpilot.cereal import messaging
sm=messaging.SubMaster(['deviceState','pandaStates','managerState'])
p=Params()
end=time.monotonic()+90
good_since=None
while time.monotonic()<end:
  sm.update(100)
  assert not p.get_bool('IsEngaged')
  if sm.seen['deviceState']:
    assert not sm['deviceState'].started
  if sm.updated['pandaStates']:
    assert sm['pandaStates']
    assert all(not a.controlsAllowed and not a.ignitionLine and not a.ignitionCan and str(a.faultStatus)=='none' and not a.faults for a in sm['pandaStates'])
  ready=p.get_bool('IsOffroad') and all(sm.alive.values())
  good_since=(good_since or time.monotonic()) if ready else None
  if good_since and time.monotonic()-good_since>=5:
    print('stable offroad, all three services alive, no engagement/control/ignition/fault')
    break
else:
  raise AssertionError('offroad startup did not stabilize within 90 seconds')
