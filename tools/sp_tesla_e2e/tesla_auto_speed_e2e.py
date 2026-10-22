#!/usr/bin/env python3
"""Tesla auto speed: car speed limit + Tesla offset -> 0x3C2 wheel ticks, without official SLA.

Synthetic CAN -> actual Tesla CarInterface/CarState -> TeslaCardAdapter Params
-> TeslaSpeedLimitController, with wheel ticks fed back into DI_digitalSpeed.

Failure modes checked:
1. Tesla toggle off, but official SpeedLimitMode=assist still ticks the wheel.
2. Tesla toggle on, but official SLA off blocks ticks.
3. Target ignores the Tesla offset, or uses the official SpeedLimitValueOffset.
4. MPH cars use a km/h target conversion.
5. Missing car limit (SNA) or an offset driving the target <= 0 still ticks.
6. Official SLA/events keep Tesla-specific hooks.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess

from opendbc.can import CANPacker
from opendbc.car import structs
from opendbc.sunnypilot.car.tesla.xpilot.interface import CarInterface
from opendbc.sunnypilot.car.tesla.xpilot.values import CAR
from opendbc.sunnypilot.car.tesla.xpilot.values_sp import TeslaFlagsSP, TeslaSafetyFlagsSP
from openpilot.tesla.car.card_adapter import TeslaCardAdapter

ROOT = Path(__file__).resolve().parents[2]
IDLE_WHEEL = bytes([1, 0, 0, 0, 0, 0, 0, 0])
DEFAULTS = dict(re.findall(r'\{"(\w+)", \{[^}]*?,\s*\w+, "([^"]*)"\}\}', (ROOT / "openpilot/common/params_keys.h").read_text()))
KPH, MPH = 1, 0  # DI_speedUnits


class FakeParams:
  def __init__(self, **values):
    self.values = {**DEFAULTS, **{k: str(v) for k, v in values.items()}}

  def get(self, key, block=False, encoding=None, return_default=False):
    value = self.values.get(key)
    return int(value) if value is not None and re.fullmatch(r"-?\d+", value) else value

  def get_bool(self, key, block=False):
    return self.values.get(key) == "1"


def drive(params, *, units=KPH, limit=60, set_speed=70, seconds=6.0):
  cp = CarInterface.get_non_essential_params(CAR.TESLA_MODEL_Y)
  cp.openpilotLongitudinalControl = True
  sp = CarInterface.get_non_essential_params_sp(cp, CAR.TESLA_MODEL_Y)
  sp.flags |= TeslaFlagsSP.HAS_VEHICLE_BUS | TeslaFlagsSP.AUTO_SPEED_LIMIT
  sp.safetyParam |= TeslaSafetyFlagsSP.HAS_VEHICLE_BUS | TeslaSafetyFlagsSP.AUTO_SPEED_LIMIT
  ci = CarInterface(cp, sp)
  ci.update([])
  packers = {bus: CANPacker(parser.dbc_name) for bus, parser in ci.can_parsers.items()}
  adapter = TeslaCardAdapter("tesla", ci, None, params)

  cc = structs.CarControl()
  cc.enabled = cc.latActive = cc.longActive = True
  ticks = []
  now = 1_000_000_000
  for _ in range(int(seconds * 50)):
    values = {
      "DI_state": {"DI_cruiseState": 2, "DI_speedUnits": units, "DI_digitalSpeed": set_speed},
      "DI_speed": {"DI_vehicleSpeed": 80.0},
      "DI_systemStatus": {"DI_gear": 4},
      "ESP_B": {"ESP_vehicleSpeed": 80.0, "ESP_wheelSpeedsQF": 1},
      "EPAS3S_sysStatus": {"EPAS3S_eacStatus": 1},
      "UI_warning": {"buckleStatus": 1},
      "DAS_status": {"DAS_fusedSpeedLimit": limit},
    }
    frames = [packers[bus].make_can_msg(name, parser.bus, values.get(name, {}))
              for bus, parser in ci.can_parsers.items() for name in list(parser.vl) if isinstance(name, str)]
    ci.update([(now, frames)])
    adapter.service_params(params)
    ci.CS.update_speed_button_template(IDLE_WHEEL, now)
    for msg in ci.CC.speed_limit_controller.update(cc, ci.CS, now):
      tick = 1 if (msg.dat[3] & 0x3F) == 1 else -1
      ticks.append(tick)
      set_speed += tick  # the car accepts each detent
    now += 20_000_000
  return set_speed, ticks


def official_sla_untouched():
  same = subprocess.run(["git", "diff", "--quiet", "sunnypilot/master", "--",
                         "openpilot/sunnypilot/selfdrive/controls/lib/speed_limit/__init__.py",
                         "openpilot/sunnypilot/selfdrive/controls/lib/speed_limit/speed_limit_assist.py"], cwd=ROOT).returncode == 0
  events = (ROOT / "openpilot/sunnypilot/selfdrive/selfdrived/events.py").read_text()
  adapter = (ROOT / "openpilot/tesla/car/card_adapter.py").read_text()
  return (same and "resolve_pcm_long_required_max" not in events and "SpeedLimitMode" not in adapter and
          not (ROOT / "openpilot/tesla/car/speed_limit_policy.py").exists())


def main():
  official_on = dict(SpeedLimitMode=3, SpeedLimitOffsetType=1, SpeedLimitValueOffset=10)
  results = {}
  final, ticks = drive(FakeParams(**official_on, TeslaAutoSpeedLimit=0))
  results["1_tesla_off_official_assist_no_tx"] = (final, ticks) == (70, [])
  final, ticks = drive(FakeParams(**official_on, TeslaAutoSpeedLimit=1, TeslaAutoSpeedLimitOffset=5))
  results["3_offset_from_tesla_not_official"] = final == 65 and set(ticks) == {-1}
  final, ticks = drive(FakeParams(SpeedLimitMode=0, TeslaAutoSpeedLimit=1, TeslaAutoSpeedLimitOffset=5), set_speed=60)
  results["2_official_off_still_ticks_up"] = final == 65 and set(ticks) == {1}
  final, ticks = drive(FakeParams(SpeedLimitMode=0, TeslaAutoSpeedLimit=1, TeslaAutoSpeedLimitOffset=5), units=MPH, limit=45, set_speed=55)
  results["4_mph_target"] = final == 50 and set(ticks) == {-1}
  results["5_sna_limit_no_tx"] = drive(FakeParams(TeslaAutoSpeedLimit=1), limit=0) == (70, [])
  results["5_nonpositive_target_no_tx"] = drive(FakeParams(TeslaAutoSpeedLimit=1, TeslaAutoSpeedLimitOffset=-10),
                                                limit=5, set_speed=30) == (30, [])
  results["6_official_sla_untouched"] = official_sla_untouched()

  files = ["openpilot/tesla/car/card_adapter.py", "opendbc_repo/opendbc/sunnypilot/car/tesla/xpilot/carstate_ext.py",
           "opendbc_repo/opendbc/sunnypilot/car/tesla/xpilot/speed_limit_controller.py"]
  print(json.dumps({
    "commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
    "dirty": bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip()),
    "sha256": {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest()[:16] for f in files},
    "results": results,
  }, indent=1))
  assert all(results.values()), [k for k, v in results.items() if not v]


if __name__ == "__main__":
  main()
