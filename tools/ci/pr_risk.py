#!/usr/bin/env python3
"""Decide whether a pull request may merge without a human review.

  python3 tools/ci/pr_risk.py <base> <head>   # prints {"auto": bool, "reasons": [...]}; exit 0 either way
  python3 tools/ci/pr_risk.py --check         # failure modes of the path rules

Auto only when every changed path is documentation or big-screen tile UI host code. Everything that runs a car
process, panda safety, the store, checks, CI or SP files needs a review. Reads git objects only, never runs
pull request code.
"""
from fnmatch import fnmatch
import json
import subprocess
import sys

AUTO = ("*.md", "docs/*", "openpilot/tesla/ui/*")
NEVER = ("XPILOT.md", "AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md", ".github/*")  # rules and CI: always reviewed


def reasons_for(paths: list[str]) -> list[str]:
  return [f"{p}: needs review" for p in paths if any(fnmatch(p, g) for g in NEVER) or not any(fnmatch(p, g) for g in AUTO)]


def check():
  cases = {"README.md": True, "docs/design/x.md": True, "openpilot/tesla/ui/tiles.py": True,
           "XPILOT.md": False, "AGENTS.md": False, ".github/workflows/xpilot.yaml": False, ".github/x.md": False,
           "opendbc_repo/opendbc/safety/plugins/navassist.h": False, "openpilot/tesla/store.py": False,
           "openpilot/selfdrive/ui/ui.py": False, "tools/sp_tesla_e2e/store_check.py": False, "tools/ci/pr_risk.py": False}
  for path, auto in cases.items():
    assert (not reasons_for([path])) is auto, path
  assert reasons_for(["README.md", "openpilot/tesla/store.py"]) == ["openpilot/tesla/store.py: needs review"]
  assert not reasons_for([])
  print(json.dumps({"cases": len(cases) + 2, "ok": True}))


if __name__ == "__main__":
  if sys.argv[1:] == ["--check"]:
    check()
  else:
    diff = subprocess.run(["git", "diff", "--name-only", "--no-renames", f"{sys.argv[1]}...{sys.argv[2]}"],
                          capture_output=True, text=True, check=True).stdout.split()
    reasons = reasons_for(diff)
    print(json.dumps({"auto": not reasons, "reasons": reasons}, indent=2))
