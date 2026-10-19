#!/usr/bin/env python3
"""Ratchet the fork's edits to official files (seams) against seams.json.

Failure cases listed before implementation:
- S1 an official file is modified or deleted without being registered.
- S2 a registered seam grows beyond its recorded changed-line budget.
- S3 the recorded official baseline is not an ancestor of the checked revision.
- S4 a gitlink (opendbc_repo, panda, ...) moves without being registered.
- S5 a registered seam returns to official content but stays in the registry.

Fork-owned added files are not seams. After an official merge or a seam
reduction, rerun with --write and review the JSON diff in the same commit.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "docs/sp-tesla-migration/seams.json"
RETAINED = ROOT / "docs/sp-tesla-migration/retained-features.json"


def git(*args: str) -> str:
  return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True)


def seams(baseline: str, rev: str) -> dict[str, int]:
  out = {}
  for line in git("diff", "--numstat", "--no-renames", "--diff-filter=MDT", baseline, rev).splitlines():
    added, deleted, path = line.split("\t")
    out[path] = (0 if added == "-" else int(added)) + (0 if deleted == "-" else int(deleted))
  return out


def main() -> int:
  parser = argparse.ArgumentParser()
  parser.add_argument("--rev", default="HEAD")
  parser.add_argument("--write", action="store_true", help="record the current seams as the new budget")
  args = parser.parse_args()

  baseline = json.loads(RETAINED.read_text())["official_baseline"]
  if subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", baseline, args.rev]).returncode != 0:
    print(f"FAIL S3: baseline {baseline} is not an ancestor of {args.rev}")
    return 1
  current = seams(baseline, args.rev)

  if args.write:
    REGISTRY.write_text(json.dumps({"official_baseline": baseline, "files": len(current),
                                    "changed_lines": sum(current.values()), "seams": dict(sorted(current.items()))},
                                   indent=2) + "\n")
    print(f"wrote {len(current)} seams, {sum(current.values())} changed lines")
    return 0

  registry = json.loads(REGISTRY.read_text())
  budget = registry["seams"]
  errors = []
  if registry["official_baseline"] != baseline:
    errors.append(f"S3 seams.json baseline {registry['official_baseline']} != retained-features {baseline}")
  errors += [f"S1/S4 unregistered seam {p} ({n} lines)" for p, n in current.items() if p not in budget]
  errors += [f"S2 {p} grew {budget[p]} -> {n} lines" for p, n in current.items() if p in budget and n > budget[p]]
  errors += [f"S5 {p} matches official; drop it from seams.json" for p in budget if p not in current]
  print(json.dumps({"rev": git("rev-parse", args.rev).strip(), "baseline": baseline, "files": len(current),
                    "changed_lines": sum(current.values()), "errors": errors}, indent=2))
  return 1 if errors else 0


if __name__ == "__main__":
  sys.exit(main())
