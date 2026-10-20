#!/usr/bin/env python3
"""UI text follows official: no fork CJK literals, official alert/font path. Plain python3.

Failure cases listed before removing the fork Chinese display path:
- T1 a fork UI string literal contains CJK that the official font path cannot render in English UI
- T2 alert renderers, application.py or .gitattributes still differ from official
- T3 the CJK font blob differs from official (fork subset font kept)
- T4 fork-only localizer/font helpers remain importable
"""
import ast
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OFFICIAL = "sunnypilot/master"
UI_DIRS = ("openpilot/selfdrive/ui", "openpilot/system/ui")
CJK = re.compile(r"[　-〿一-鿿＀-￯]")
MATCH_OFFICIAL = ("openpilot/selfdrive/ui/onroad/alert_renderer.py", "openpilot/selfdrive/ui/mici/onroad/alert_renderer.py",
                  "openpilot/system/ui/lib/application.py", ".gitattributes",
                  "openpilot/selfdrive/assets/fonts/NotoSansCJKsc-Regular.otf")
FORK_ONLY = ("openpilot/selfdrive/ui/onroad/alert_localizer.py", "openpilot/system/ui/lib/font_characters.py",
             "tools/sp_tesla_e2e/build_chinese_font.py")


def git(*args):
  return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)


def cjk_literals(source):
  return {c for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Constant) and isinstance(node.value, str)
          for c in CJK.findall(node.value)}


def main():
  t1 = {}
  for path in git("ls-files", *UI_DIRS).stdout.split():
    if not path.endswith(".py") or "/tests/" in path:
      continue
    official = git("show", f"{OFFICIAL}:{path}")
    extra = cjk_literals((ROOT / path).read_text(encoding="utf-8")) - (cjk_literals(official.stdout) if official.returncode == 0 else set())
    if extra:
      t1[path] = "".join(sorted(extra))[:40]
  t2_t3 = [p for p in MATCH_OFFICIAL if git("diff", "--quiet", OFFICIAL, "--", p).returncode != 0]
  t4 = [p for p in FORK_ONLY if (ROOT / p).exists()]
  checks = {"T1_no_fork_cjk_literals": not t1, "T2_T3_match_official": not t2_t3, "T4_fork_helpers_removed": not t4}
  print(json.dumps({"head": git("rev-parse", "HEAD").stdout.strip(), "dirty": bool(git("status", "--porcelain").stdout.strip()),
                    "checks": checks, "t1": t1, "t2_t3": t2_t3, "t4": t4}, indent=1, ensure_ascii=False))
  assert all(checks.values())


if __name__ == "__main__":
  main()
