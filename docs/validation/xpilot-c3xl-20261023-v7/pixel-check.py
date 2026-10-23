"""Failures: wrong crop, unsupported PNG, foreground on the right edge, or
YMAX conversion drift. Calibrate against six archived v6 PNGs before v7.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

root = Path(__file__).resolve().parent
logs = []

def ymax(path, x, y, h):
  filt = f"format=yuv444p,crop=1:{h}:{x}:{y},signalstats,metadata=print"
  command = ["ffmpeg", "-hide_banner", "-nostdin", "-i", str(path), "-vf", filt, "-frames:v", "1", "-f", "null", "-"]
  p = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
  logs.append({"command": command, "rc": p.returncode, "output": p.stdout})
  assert p.returncode == 0, p.stdout
  values = re.findall(r"lavfi.signalstats.YMAX=(\d+)", p.stdout)
  assert len(values) == 1, values
  return int(values[0])

reference = []
with tempfile.TemporaryDirectory() as tmp:
  for tid in ("clock", "ip"):
    for size, w, h in (("small", 250, 250), ("medium", 512, 512), ("wide", 1036, 512)):
      name = f"tile-{tid}-{size}.png"
      path = Path(tmp) / name
      path.write_bytes(subprocess.check_output(["git", "show", "origin/task/X-20261023-09:docs/validation/xpilot-c3xl-20261023-v6/" + name]))
      value = ymax(path, 38 + w - 1, 22, h)
      expected = 64 if size == "wide" else 120 if tid == "ip" and size == "small" else 235
      assert value == expected, (name, value, expected)
      reference.append({"path": name, "YMAX": value, "expected": expected, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
cases = []
for result_file in sorted((root / "tile-results").glob("*/result.json")):
  for case in json.loads(result_file.read_text())["cases"]:
    col, row, size = case["placement"]
    cols, rows = {"small": (1, 1), "medium": (2, 2), "wide": (4, 2)}[size]
    x, y, w, h = 38 + col * 262, 22 + row * 262, cols * 262 - 12, rows * 262 - 12
    value = ymax(root / case["path"], x + w - 1, y, h)
    cases.append({"tile": case["tile"], "size": size, "path": case["path"], "rect": [x, y, w, h], "rightmost_column_YMAX": value,
                  "clipping": value > 64, "overlap": case["overlap"], "too_small": case["too_small"], "ellipsis": case["ellipsis"],
                  "minimum_font_px": min(d["size"] for d in case["draws"]), "sha256": hashlib.sha256((root / case["path"]).read_bytes()).hexdigest()})
assert len(cases) == 27 and len({(c["tile"], c["size"]) for c in cases}) == 27
passed = all(not c["clipping"] for c in cases)
(root / "pixel-results.json").write_text(json.dumps({"passed": passed, "method": "FFmpeg format=yuv444p; last-column crop; signalstats.YMAX; Graphite=64", "v6_reference": reference, "cases": cases}, indent=2) + "\n")
(root / "pixel-ffmpeg.json").write_text(json.dumps(logs, indent=2) + "\n")
print(json.dumps({"passed": passed, "v6_reference": [(c["path"], c["YMAX"]) for c in reference], "v7_cases": [(c["tile"], c["size"], c["rightmost_column_YMAX"]) for c in cases]}))
assert passed
