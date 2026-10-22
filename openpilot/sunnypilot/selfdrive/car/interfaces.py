"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from typing import Any

from opendbc.car import structs
from opendbc.car.interfaces import CarInterfaceBase
from openpilot.common.params import Params
from openpilot.common.swaglog import cloudlog
from openpilot.sunnypilot.selfdrive.controls.lib.speed_limit.helpers import set_speed_limit_assist_availability




def _cleanup_unsupported_params(CP: structs.CarParams, CP_SP: structs.CarParamsSP, params: Params | None = None) -> None:
  if params is None:
    params = Params()

  if not CP.openpilotLongitudinalControl and CP_SP.pcmCruiseSpeed:
    cloudlog.warning("openpilot Longitudinal Control and ICBM not available, cleaning up params")
    params.remove("CustomAccIncrementsEnabled")
    params.remove("SmartCruiseControlVision")
    params.remove("SmartCruiseControlMap")

  set_speed_limit_assist_availability(CP, CP_SP, params)


def setup_interfaces(CI: CarInterfaceBase, params: Params | None = None) -> None:
  _cleanup_unsupported_params(CI.CP, CI.CP_SP)



def initialize_params(params) -> list[dict[str, Any]]:
  # upstream sunnypilot Tesla options; xpilot plugins read their own Params in card
  keys = ["TeslaCoopSteering", "TeslaMadsScreenButton"]
  return [{k: params.get(k, return_default=True)} for k in keys]
