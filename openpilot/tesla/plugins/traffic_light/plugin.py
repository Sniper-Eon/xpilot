"""Traffic light plugin: reads Tesla's own traffic-control perception (APP_trafficControl), runs
trafficcontrold, and lets plannerd stop for red lights through the final plan arbitrator (tighten only).
Params: TeslaTrafficSignalControlEnabled, TeslaTrafficStopReference, TeslaTrafficControlMaxSpeed."""
import time

from openpilot.tesla.plugin import Plugin, Setting
from openpilot.tesla.plugins.traffic_light.final_plan_arbitrator import create_final_plan_arbitrator
from openpilot.tesla.plugins.traffic_light.tesla_observer import TeslaTrafficControlObserver, publish_tesla_traffic_control


def _onroad(started, params, CP) -> bool:
  return started


class TrafficLight(Plugin):
  NAME = "traffic_light"
  TITLE = "Traffic Light Control (Experimental)"
  DESCRIPTION = "Stops for red lights seen by the car's own traffic-control perception. Only ever slows down."
  ENABLE_PARAM = "TeslaTrafficSignalControlEnabled"
  SETTINGS = (Setting("TeslaTrafficStopReference", "Stop Reference", range=(20, 120, 5, "m", 10)),
              Setting("TeslaTrafficControlMaxSpeed", "Max Speed", range=(20, 120, 5, "km/h", 1)))
  PLAN_SERVICES = ("trafficRadarState",)

  def __init__(self, CP, params):
    super().__init__(CP, params)
    self.observer = TeslaTrafficControlObserver()

  def observe_can(self, can_list, now_ns: int) -> list:
    self.observer.update(can_list, now_ns)
    return []

  def publish_state(self, CS_SP) -> None:
    publish_tesla_traffic_control(CS_SP, self.observer.snapshot(time.monotonic_ns()))

  @classmethod
  def processes(cls) -> list:
    from openpilot.system.manager.process import PythonProcess
    return [PythonProcess("trafficcontrold", "openpilot.tesla.plugins.traffic_light.trafficcontrold", _onroad)]

  @classmethod
  def plan_filter(cls, CP, params):
    return create_final_plan_arbitrator(CP, params)
