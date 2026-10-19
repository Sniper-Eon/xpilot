#!/usr/bin/env python3
"""Replay SCC-V frames through the official, previous fork and candidate code.

Failure cases listed before the change:
- F1 non-Tesla planners keep the Tesla 5-frame entry confirmation.
- F2 non-Tesla planners read desiredCurvature instead of official curvature.
- F3 Tesla loses the 5-frame confirmation or desiredCurvature lateral acceleration.
- F4 the confirmation counter survives disable/override/low speed/prediction drop.
- F5 a planner path (upstream or legacy backend) builds the wrong controller.
- F6 the official vision_controller.py still carries a fork diff.

Each candidate frame (state, lateral acceleration, outputs) must equal the
official blob for non-Tesla and the previous fork blob for Tesla. Messaging,
Params and the capnp enum are stubbed; numpy and constants are real.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
VISION = "openpilot/sunnypilot/selfdrive/controls/lib/smart_cruise_control/vision_controller.py"
TESLA = "openpilot/sunnypilot/selfdrive/car/tesla/scc_vision.py"
PLANNER = "openpilot/sunnypilot/selfdrive/controls/lib/longitudinal_planner.py"
VISION_MODULE = "openpilot.sunnypilot.selfdrive.controls.lib.smart_cruise_control.vision_controller"


def git(*args: str) -> str:
  return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True)


def install_stubs() -> None:
  states = ("disabled", "enabled", "entering", "turning", "leaving", "overriding")
  vision_state = types.SimpleNamespace(**{name: i for i, name in enumerate(states)})
  custom = types.SimpleNamespace(LongitudinalPlanSP=types.SimpleNamespace(
    SmartCruiseControl=types.SimpleNamespace(VisionState=vision_state)))
  cereal = types.ModuleType("openpilot.cereal")
  cereal.custom = custom
  cereal.messaging = types.SimpleNamespace(SubMaster=dict)
  params = types.ModuleType("openpilot.common.params")
  params.Params = lambda: types.SimpleNamespace(get_bool=lambda key: True)
  sys.modules.update({
    "openpilot.cereal": cereal,
    "openpilot.cereal.messaging": cereal.messaging,
    "openpilot.common.params": params,
    "openpilot.common.realtime": types.SimpleNamespace(DT_MDL=0.05),
    "openpilot.selfdrive.car.cruise": types.SimpleNamespace(V_CRUISE_UNSET=255),
  })


def load(name: str, source: str) -> types.ModuleType:
  module = types.ModuleType(name)
  sys.modules[name] = module
  exec(compile(source, name, "exec"), module.__dict__)
  return module


def frames(seed: int, count: int):
  rng = random.Random(seed)
  burst = 0
  for _ in range(count):
    if burst == 0 and rng.random() < 0.08:
      burst = rng.randint(1, 9)  # 1-4 frames must not confirm on Tesla; 5+ must.
    high = burst > 0
    burst = max(burst - 1, 0)
    v = rng.choice((3., 8., 15., 22., 30.))
    rate = rng.uniform(0.06, 0.12) if high else rng.uniform(0., 0.04)
    sm = {
      "modelV2": types.SimpleNamespace(orientationRate=types.SimpleNamespace(z=[rate] * 33),
                                       velocity=types.SimpleNamespace(x=[v] * 33)),
      "controlsState": types.SimpleNamespace(curvature=rng.uniform(-0.006, 0.006),
                                             desiredCurvature=rng.uniform(-0.006, 0.006)),
    }
    yield sm, rng.random() > 0.03, rng.random() < 0.03, v, rng.uniform(-1., 1.), 30.


def trace(controller, seed: int, count: int) -> list[tuple]:
  out = []
  for sm, enabled, override, v, a, v_cruise in frames(seed, count):
    controller.update(sm, enabled, override, v, a, v_cruise)
    out.append((int(controller.state), round(float(controller.current_lat_acc), 9),
                round(float(controller.output_v_target), 9), round(float(controller.output_a_target), 9)))
  return out


def main() -> int:
  parser = argparse.ArgumentParser()
  parser.add_argument("--official", default="27c132984df60e9ef42ebd1a805738b8c851356f")
  parser.add_argument("--previous", default="c3a0d5e77", help="fork commit with the Tesla behavior")
  parser.add_argument("--frames", type=int, default=20000)
  parser.add_argument("--seed", type=int, default=7)
  parser.add_argument("--output", type=Path)
  args = parser.parse_args()

  install_stubs()
  official_src = git("show", f"{args.official}:{VISION}")
  previous_src = git("show", f"{args.previous}:{VISION}")
  official = load("scc_official", official_src).SmartCruiseControlVision
  previous = load("scc_previous", previous_src).SmartCruiseControlVision
  candidate_src = (ROOT / VISION).read_text()
  load(VISION_MODULE, candidate_src)
  checks: dict[str, bool] = {}
  try:
    tesla_module = load("scc_tesla", (ROOT / TESLA).read_text())
    candidate = sys.modules[VISION_MODULE].SmartCruiseControlVision
    tesla = tesla_module.TeslaSmartCruiseControlVision
  except FileNotFoundError:
    candidate = tesla = None

  ref_official = trace(official(), args.seed, args.frames)
  ref_tesla = trace(previous(), args.seed, args.frames)
  checks["scenario_enters_turns"] = sum(s[0] == 2 for s in ref_official) > 50
  checks["scenario_discriminates_tesla"] = ref_official != ref_tesla  # F1-F4 must be observable.
  checks["non_tesla_matches_official"] = candidate is not None and trace(candidate(), args.seed, args.frames) == ref_official
  checks["tesla_matches_previous_fork"] = tesla is not None and trace(tesla(), args.seed, args.frames) == ref_tesla
  checks["official_file_unchanged"] = candidate_src == official_src  # F6
  planner = (ROOT / PLANNER).read_text()
  checks["planner_seam_brand_gated"] = 'if CP.brand == "tesla":\n      self.scc.vision = TeslaSmartCruiseControlVision()' in planner  # F5

  result = {
    "official": args.official, "previous": args.previous, "head": git("rev-parse", "HEAD").strip(),
    "frames": args.frames, "seed": args.seed,
    "sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in (VISION, TESLA, PLANNER) if (ROOT / p).exists()},
    "checks": checks, "pass": all(checks.values()),
  }
  text = json.dumps(result, indent=2)
  if args.output:
    args.output.write_text(text + "\n")
  print(text)
  return 0 if result["pass"] else 1


if __name__ == "__main__":
  sys.exit(main())
