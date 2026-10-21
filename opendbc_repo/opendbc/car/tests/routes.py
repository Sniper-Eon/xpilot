from typing import NamedTuple

from opendbc.car.mock.values import CAR as MOCK
from opendbc.car.tesla.values import CAR as TESLA
from opendbc.car.values import Platform

# TODO: add test routes
non_tested_cars = [
  MOCK.MOCK,
  TESLA.TESLA_MODEL_X,
]


class CarTestRoute(NamedTuple):
  route: str
  car_model: Platform | None
  segment: int | None = None


routes = [
  CarTestRoute("79d0f04c82980004/00000003--fb0b5d9cfc", TESLA.TESLA_MODEL_3), # HW4 2025
  CarTestRoute("aebd8f1d4ea16066/000002d8--5850d3ea5c", TESLA.TESLA_MODEL_Y), # openpilot longitudinal
]
