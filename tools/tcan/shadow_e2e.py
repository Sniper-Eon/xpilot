#!/usr/bin/env python3
"""Replay shadow scenarios against the pinned upstream C++ transforms."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import subprocess
import sys

SHA = "e63b678df385748ffe379ebebdd98b73a361c3d8"
ROOT = Path(__file__).resolve().parents[2]
ORACLE = r'''
#include <iostream>
#include <string>
#include "r79_fixed_policy_pure.h"
#include "isa_suppression_pure.h"
#include "country_override_pure.h"
int main() {
  std::string kind; unsigned n;
  while (std::cin >> kind) {
    uint8_t data[8]; for (auto &b : data) { std::cin >> n; b=n; }
    if (kind=="r79") r79FixedApplyBitsPure(data, R79_BIT18_STOCK_PURE);
    if (kind=="isa") isaSuppressSpeedWarningPure(data, 8);
    if (kind=="country_us") countryOverrideApply238Pure(data, 8, COUNTRY_OVERRIDE_US_PURE);
    for (auto b : data) std::cout << unsigned(b) << " ";
    std::cout << "\n";
  }
}
'''


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--upstream", required=True, type=Path)
  parser.add_argument("--output", required=True, type=Path)
  args = parser.parse_args()
  args.output.mkdir(parents=True, exist_ok=True)
  upstream = args.upstream.resolve()
  assert subprocess.check_output(["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip() == SHA
  assert not subprocess.check_output(["git", "-C", str(upstream), "status", "--porcelain", "--untracked-files=no"], text=True).strip()
  cpp = args.output / "oracle.cpp"
  cpp.write_text(ORACLE)
  binary = args.output / "oracle"
  subprocess.run(["c++", "-std=c++17", "-I", str(upstream), str(cpp), "-o", str(binary)], check=True)
  engine_path = ROOT / "openpilot/sunnypilot/tcan/engine.py"
  spec = importlib.util.spec_from_file_location("tcan_shadow", engine_path)
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  Engine = module.ShadowEngine
  rows, outputs = [], []
  now = 2_000_000_000
  features = ("r79", "isa", "country_us")
  config = {"profile": "standard_body", "bus_map": {"A": 0, "B": 1}, "features": features}
  ap = bytes([3, 0, 0, 0, 0, 0, 0, 0])
  r79 = bytes([1, 0, 8, 0, 0, 0, 0, 0])
  country = bytearray([0, 0, 154, 1, 0, 0, 240, 0])
  country[7] = (0x238 + 2 + sum(country[:7])) & 255

  def check(name, address=0x3FD, data=r79, bus=1, expected="r79", cfg=None, context=True, age=0, delta=0, onroad=False, ap_data=ap, reset=False):
    settings = dict(config if cfg is None else cfg)
    engine = Engine(**settings)
    if context:
      engine.observe(0 if settings.get("profile") == "yl" else 1, 0x399, ap_data, now)
    if reset:
      engine.observe(1, 0x100, bytes(8), now + 1, sp_onroad=True)
    event = {"bus": bus, "address": address, "data_hex": bytes(data).hex(), "now_ns": now + delta,
             "received_ns": now + delta - age, "sp_onroad": onroad}
    candidate = engine.observe(bus, address, bytes(data), event["now_ns"], received_ns=event["received_ns"], sp_onroad=onroad)
    rows.append({"name": name, "config": settings, "context": context, "ap_data_hex": ap_data.hex(), "reset": reset, "event": event, "expected": expected})
    if expected:
      wire = expected + " " + " ".join(str(b) for b in data) + "\n"
      oracle = bytes(map(int, subprocess.check_output([str(binary.resolve())], input=wire, text=True).split()))
      assert candidate == [{"feature": expected, "bus": bus, "address": address, "data_hex": oracle.hex(), "shadow_only": True}], (name, candidate, oracle.hex())
    else:
      assert candidate == [], (name, candidate)
    outputs.append({"name": name, "candidates": candidate})

  check("r79")
  check("isa", address=0x399, data=ap, expected="isa")
  check("country", address=0x238, data=country, expected="country_us")
  for name, kwargs in [
    ("default_off", {"cfg": {}}), ("missing_map", {"cfg": {"profile": "yl", "features": features}}),
    ("disabled", {"cfg": {**config, "features": ()}}), ("wrong_route", {"bus": 0}),
    ("wrong_id", {"address": 0x123}), ("short", {"data": r79[:7]}), ("long", {"data": r79+b"\0"}),
    ("expired_frame", {"age": 250_000_001}), ("future_frame", {"age": -1}),
    ("backwards_clock", {"delta": -1}), ("missing_ap", {"context": False}),
    ("stale_ap", {"delta": 1_000_000_001}), ("manual_ap", {"ap_data": bytes(8)}),
    ("sp_onroad", {"onroad": True}), ("sp_revokes_context", {"reset": True, "delta": 2}),
    ("wrong_mux", {"data": bytes([2])+r79[1:]}),
    ("country_checksum", {"address": 0x238, "data": bytes(8)}),
    ("isa_already_set", {"address": 0x399, "data": bytes([3,32,0,0,0,0,0,0])}),
  ]:
    check(name, expected=None, **kwargs)
  for profile in ("yl", "standard_party"):
    check(profile, cfg={**config, "profile": profile})
  for invalid in ({"profile": "unknown"}, {"bus_map": {"A": 0, "B": 0}}, {"features": ("unknown",)}, {"bus_map": {"A": -1, "B": 1}}):
    try:
      Engine(**{**config, **invalid})
    except ValueError:
      outputs.append({"invalid_config": invalid, "rejected": True})
    else:
      raise AssertionError(invalid)
  for name, values in (("input.jsonl", rows), ("candidates.jsonl", outputs)):
    (args.output / name).write_text("".join(json.dumps(row, sort_keys=True)+"\n" for row in values))
  sources = [engine_path, Path(__file__), ROOT / "docs/tcan/SHADOW_ACCEPTANCE.md", *sorted(upstream.glob("*.h"))]
  report = {"passed": len(outputs), "upstream_sha": SHA, "host_only": True, "physical_route_proven": False,
            "source_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
            "artifact_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in args.output.iterdir() if p.is_file() and p.name != "report.json"},
            "rerun": shlex.join([sys.executable, str(Path(__file__).resolve()), "--upstream", str(upstream), "--output", str(args.output.resolve())])}
  (args.output / "report.json").write_text(json.dumps(report, indent=2)+"\n")
  print(json.dumps({"passed": len(outputs), "report": str(args.output / "report.json")}))


if __name__ == "__main__":
  main()
