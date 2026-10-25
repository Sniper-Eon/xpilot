"""Before-fix contracts from real selfdrived/plannerd startup failures.

Failure modes: repeated stock/plugin subscriptions create multiple sockets and
zero receive intervals; zero/nonfinite intervals crash or pass health checks;
plugin exemptions suppress stock health checks; two OSM publishers run together.
"""
import ast
import math
import sys
from pathlib import Path
from types import SimpleNamespace as N
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "opendbc_repo")]

from openpilot.cereal import messaging  # noqa: E402
from openpilot.tesla import plugins  # noqa: E402


class SubscriptionRecovery(unittest.TestCase):
  def test_unique_inputs_keep_order_and_do_not_mutate_caller(self):
    names = ['modelV2', 'carState', 'modelV2', 'carState']
    sm = messaging.SubMaster(names, frequency=100)
    self.assertEqual(sm.services, ['modelV2', 'carState'])
    self.assertEqual(names, ['modelV2', 'carState', 'modelV2', 'carState'])
    self.assertEqual(len(sm.sock), 2)

  def test_equal_timestamps_fail_closed_without_division_by_zero(self):
    f = messaging.FrequencyTracker(20., 100., False)
    f.record_recv_time(1.)
    f.record_recv_time(1.)
    self.assertFalse(f.valid)

  def test_zero_recent_window_fails_closed(self):
    f = messaging.FrequencyTracker(2., 2., True)
    for t in [1., 1.5, 2., 2., 2.]:
      f.record_recv_time(t)
    self.assertFalse(f.valid)

  def test_nonfinite_history_is_unhealthy(self):
    for value in [math.nan, math.inf, -math.inf]:
      f = messaging.FrequencyTracker(20., 100., False)
      f.record_recv_time(1.)
      f.record_recv_time(value)
      self.assertFalse(f.valid)

  def test_normal_twenty_hz_remains_healthy(self):
    f = messaging.FrequencyTracker(20., 20., True)
    for i in range(30):
      f.record_recv_time(1.+i*.05)
    self.assertTrue(f.valid)

  def test_plugin_exemptions_never_include_stock_inputs(self):
    base = ['modelV2', 'carState']
    with patch.object(plugins, 'PLUGINS', [N(SERVICES=('modelV2','carState','trafficRadarState'))]):
      extra = plugins.services(base)
      self.assertEqual(extra, ['trafficRadarState'])
      sm = messaging.SubMaster(base+extra, frequency=100, ignore_alive=extra,
                               ignore_avg_freq=extra, ignore_valid=extra)
      for name in base:
        self.assertNotIn(name, sm.ignore_alive)
        self.assertNotIn(name, sm.ignore_valid)
        self.assertNotIn(name, sm.ignore_average_freq)

  def test_osm_debug_publisher_is_not_a_managed_production_process(self):
    tree = ast.parse((ROOT/'openpilot/system/manager/process_config.py').read_text())
    managed_modules = [n.args[1].value for n in ast.walk(tree)
      if isinstance(n,ast.Call) and getattr(n.func,'id','')=='PythonProcess'
      and len(n.args)>1 and isinstance(n.args[1],ast.Constant)]
    self.assertIn('openpilot.sunnypilot.mapd.mapd_manager', managed_modules)
    self.assertNotIn('openpilot.sunnypilot.mapd.live_map_data.standalone', managed_modules)


if __name__ == '__main__':
  unittest.main()
