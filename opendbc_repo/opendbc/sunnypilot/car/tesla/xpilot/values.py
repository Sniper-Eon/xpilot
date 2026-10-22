"""xpilot Tesla values: upstream values plus the fork's additions, pointed at the fork DBC files."""
from opendbc.car import Bus
from opendbc.car.tesla.values import *  # noqa: F403  upstream platforms, flags, CANBUS, FSD_14_FW, ...
from opendbc.car.tesla.values import CarControllerParams as _UpstreamCarControllerParams, DBC as _UPSTREAM_DBC


class CarControllerParams(_UpstreamCarControllerParams):
  JERK_RATE_UP = 1.0  # m/s^3 per second acceleration ramp


STEER_DISENGAGE_THRESHOLD = 5.0

# Same messages and checksums as upstream; the xpilot files add signals for the fork features.
DBC = {car: {**dbcs, Bus.party: 'tesla_model3_party_xpilot', Bus.adas: 'tesla_model3_vehicle_xpilot'} for car, dbcs in _UPSTREAM_DBC.items()}
