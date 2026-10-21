#!/usr/bin/env python3
"""List upstream sunnypilot commits after the one-time baseline that touch files this tree still has.

This fork no longer merges upstream; it hand-picks fixes. Usage:
  git fetch sunnypilot master
  python3 tools/dev_sp_release/upstream_watch.py [--since 922513f] [--ref sunnypilot/master]
Pick a candidate with `git cherry-pick -x <sha>`, keeping paths this fork deleted deleted.
opendbc/panda upstreams are separate repos: check them by hand when a Tesla or safety fix lands there.
"""
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "922513f3128b00611d695ce465989a9bc8af9d59"


def git(*args: str) -> str:
  return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True)


def main() -> None:
  parser = argparse.ArgumentParser()
  parser.add_argument("--since", default=BASELINE)
  parser.add_argument("--ref", default="sunnypilot/master")
  args = parser.parse_args()

  kept = set(git("ls-files").splitlines())
  candidates = []
  for block in git("log", "--reverse", "--format=%x01%H%x00%s", "--name-only", f"{args.since}..{args.ref}").split("\x01")[1:]:
    header, *paths = block.strip().split("\n")
    sha, subject = header.split("\x00", 1)
    touched = [p for p in paths if p in kept]
    if touched:
      candidates.append({"sha": sha[:10], "subject": subject, "kept_paths": touched})
  print(json.dumps({"since": args.since, "ref": args.ref, "candidates": candidates}, indent=1))


if __name__ == "__main__":
  main()
