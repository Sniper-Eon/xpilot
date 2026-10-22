"""xpilot Tesla plugin: CarParams/CarParamsSP setup from the Tesla Params snapshot (called once per car init)."""
from opendbc.car import structs
from opendbc.sunnypilot.car.tesla.xpilot.ars408.constants import TeslaRadarBackend
from opendbc.sunnypilot.car.tesla.xpilot.values_sp import MadsScreenButtonType, TeslaFlagsSP, TeslaSafetyFlagsSP


def setup_tesla(CP: structs.CarParams, CP_SP: structs.CarParamsSP, params_dict: dict[str, str]) -> None:
  _initialize_coop_steering(CP, CP_SP, params_dict)
  _initialize_tesla_mads_screen_button(CP, CP_SP, params_dict)
  _initialize_tesla_dynamic_auto_stock(CP, CP_SP, params_dict)
  _initialize_tesla_ap_hybrid(CP, CP_SP, params_dict)
  _initialize_tesla_auto_speed_limit(CP, CP_SP, params_dict)
  _initialize_tesla_radar_backend(CP, CP_SP, params_dict)


def _initialize_coop_steering(CP: structs.CarParams, CP_SP: structs.CarParamsSP,
                              params_dict: dict[str, str]) -> None:
  if CP.brand == 'tesla':
    coop_steering = int(params_dict.get("TeslaCoopSteering", 0)) == 1
    if coop_steering:
      CP_SP.flags |= TeslaFlagsSP.COOP_STEERING.value


def _initialize_tesla_mads_screen_button(CP: structs.CarParams, CP_SP: structs.CarParamsSP,
                                         params_dict: dict[str, str]) -> None:
  if CP.brand == 'tesla' and CP_SP.flags & TeslaFlagsSP.HAS_VEHICLE_BUS:
    selection = int(params_dict.get("TeslaMadsScreenButton", MadsScreenButtonType.THREE_FINGER))
    if selection == 3:  # migrate legacy 5-finger value from when 4-finger option existed
      selection = MadsScreenButtonType.FIVE_FINGER
    if selection == MadsScreenButtonType.THREE_FINGER:
      CP_SP.flags |= TeslaFlagsSP.MADS_SCREEN_BUTTON_3_FINGER.value
      CP_SP.safetyParam |= TeslaSafetyFlagsSP.MADS_SCREEN_BUTTON_3_FINGER
    elif selection == MadsScreenButtonType.FIVE_FINGER:
      CP_SP.flags |= TeslaFlagsSP.MADS_SCREEN_BUTTON_5_FINGER.value
      CP_SP.safetyParam |= TeslaSafetyFlagsSP.MADS_SCREEN_BUTTON_5_FINGER


def _initialize_tesla_dynamic_auto_stock(CP: structs.CarParams, CP_SP: structs.CarParamsSP,
                                         params_dict: dict[str, str]) -> None:
  if CP.brand == 'tesla' and CP.openpilotLongitudinalControl:
    dynamic_auto_stock = int(params_dict.get("DynamicAutoStock", 0)) == 1
    if dynamic_auto_stock:
      CP_SP.flags |= TeslaFlagsSP.DYNAMIC_AUTO_STOCK.value
      CP_SP.safetyParam |= TeslaSafetyFlagsSP.DYNAMIC_AUTO_STOCK


def _initialize_tesla_ap_hybrid(CP: structs.CarParams, CP_SP: structs.CarParamsSP,
                                params_dict: dict[str, str]) -> None:
  if CP.brand == 'tesla' and CP.openpilotLongitudinalControl and int(params_dict.get("TeslaApHybrid", 0)) == 1:
    CP_SP.flags |= TeslaFlagsSP.AP_HYBRID.value
    if int(params_dict.get("TeslaDynamicApLongitudinal", 0)) == 1:
      CP_SP.flags |= TeslaFlagsSP.DYNAMIC_AP_LONGITUDINAL.value
    CP_SP.safetyParam |= TeslaSafetyFlagsSP.AP_HYBRID_HANDOFF | TeslaSafetyFlagsSP.AP_HYBRID_LATERAL_HANDOFF


def _initialize_tesla_auto_speed_limit(CP: structs.CarParams, CP_SP: structs.CarParamsSP,
                                       _params_dict: dict[str, str]) -> None:
  if (CP.brand == 'tesla' and CP.openpilotLongitudinalControl and
      CP_SP.flags & TeslaFlagsSP.HAS_VEHICLE_BUS):
    CP_SP.flags |= TeslaFlagsSP.AUTO_SPEED_LIMIT.value
    CP_SP.safetyParam |= TeslaSafetyFlagsSP.AUTO_SPEED_LIMIT


def _initialize_tesla_radar_backend(CP: structs.CarParams, CP_SP: structs.CarParamsSP,
                                    params_dict: dict[str, str]) -> None:
  if CP.brand != "tesla":
    return
  try:
    backend = TeslaRadarBackend(int(params_dict.get("TeslaARS408Radar", TeslaRadarBackend.OEM)))
  except (TypeError, ValueError):
    backend = TeslaRadarBackend.OFF

  if backend == TeslaRadarBackend.ARS408:
    CP.radarUnavailable = False
    CP.deprecated.radarTimeStep = 1.0 / 14.0
    CP_SP.flags |= TeslaFlagsSP.ARS408_RADAR.value
    CP_SP.safetyParam |= TeslaSafetyFlagsSP.ARS408_RADAR
  elif backend == TeslaRadarBackend.OFF:
    CP.radarUnavailable = True
    CP_SP.flags |= TeslaFlagsSP.RADAR_DISABLED.value
