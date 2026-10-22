"""Registered xpilot plugins and the small hosts that SP processes call. Add a plugin to PLUGINS."""
import time

from openpilot.tesla.plugins.ambient_light.plugin import AmbientLight
from openpilot.tesla.plugins.auto_speed.plugin import AutoSpeed
from openpilot.tesla.plugins.traffic_light.plugin import TrafficLight

PLUGINS = (AutoSpeed, TrafficLight, AmbientLight)


class CarPlugins:
  """card host: forwards each hook to every plugin, in PLUGINS order."""

  def __init__(self, CP, params):
    self.plugins = [p(CP, params) for p in PLUGINS] if CP.brand == "tesla" else []

  def setup(self, CP_SP) -> None:
    for p in self.plugins:
      p.setup(CP_SP)

  def observe_can(self, can_list) -> list:
    now = time.monotonic_ns()
    return [s for p in self.plugins for s in p.observe_can(can_list, now)]

  def publish_state(self, CS_SP) -> None:
    for p in self.plugins:
      p.publish_state(CS_SP)

  def control_sends(self, CS, CC, now_ns: int) -> list:
    return [s for p in self.plugins for s in p.control_sends(CS, CC, now_ns)]

  def service_params(self, params) -> None:
    for p in self.plugins:
      p.service_params(params)


def processes() -> list:
  return [proc for p in PLUGINS for proc in p.processes()]


def plan_services() -> list[str]:
  return [svc for p in PLUGINS for svc in p.PLAN_SERVICES]


def plan_filters(CP, params) -> list:
  if CP.brand != "tesla":
    return []
  return [f for p in PLUGINS if (f := p.plan_filter(CP, params)) is not None]


def plan_sink(filters, pm, sm):
  sink = pm
  for f in filters:
    sink = f.publisher(sink, sm)
  return sink
