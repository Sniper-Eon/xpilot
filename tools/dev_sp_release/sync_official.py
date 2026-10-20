#!/usr/bin/env python3
"""Prepare, start and check a dev-sp merge of official sunnypilot master.

  plan   fetch, record an S0 checkpoint (refs + verified bundles) and dry-run the
         parent and fork-submodule merges; nothing in the worktree changes
  merge  merge the fork submodules (commit when clean), point the gitlinks at
         them and start the parent merge without committing
  check  post-merge gates: conflict markers, seams, settings_ui.json, syntax and
         LFS availability on the configured store

Failure cases (checked before anything is changed): not on dev-sp or dirty
tree; origin/dev-sp moved away from local; official submodule commit not
fetchable; checkpoint bundle not restorable. It never resolves conflicts,
pushes, or touches a device. Standard library and the git CLI only.
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORK_SUBMODULES = ("opendbc_repo", "panda")
OFFICIAL_URL = "https://github.com/sunnypilot/sunnypilot.git"


def git(*args, cwd=ROOT, check=True):
  return subprocess.run(["git", *args], cwd=cwd, check=check, text=True, capture_output=True).stdout.strip()


def ok(cmd, cwd=ROOT):
  return subprocess.run(cmd, cwd=cwd, capture_output=True).returncode == 0


def fail(msg):
  print(f"FAIL: {msg}")
  sys.exit(1)


def official_submodule_url(official, path):
  with tempfile.NamedTemporaryFile("w", suffix=".gitmodules") as f:
    f.write(git("show", f"{official}:.gitmodules"))
    f.flush()
    for line in git("config", "-f", f.name, "--get-regexp", r"^submodule\..*\.path$").splitlines():
      key, value = line.split(" ", 1)
      if value == path:
        return git("config", "-f", f.name, key.removesuffix(".path") + ".url")
  fail(f"{path} is not a submodule in {official}")


def conflicts(repo, ours, theirs):
  out = subprocess.run(["git", "merge-tree", "--write-tree", "--name-only", ours, theirs], cwd=repo, text=True,
                       capture_output=True).stdout.splitlines()
  return [line.split("Merge conflict in ", 1)[1] for line in out if line.startswith("CONFLICT") and "Merge conflict in " in line]


def preflight(official_ref):
  if git("rev-parse", "--abbrev-ref", "HEAD") != "dev-sp":
    fail("not on dev-sp")
  if git("status", "--porcelain", "--untracked-files=no"):
    fail("worktree or submodules are dirty")
  for path in FORK_SUBMODULES:
    if not (ROOT / path / ".git").exists():
      fail(f"{path} is not initialized")
  if "sunnypilot" not in git("remote").split():
    git("remote", "add", "sunnypilot", OFFICIAL_URL)
  git("fetch", "-q", "origin", "dev-sp")
  git("fetch", "-q", "sunnypilot", "master")
  if not ok(["git", "merge-base", "--is-ancestor", "origin/dev-sp", "HEAD"]):
    fail("origin/dev-sp has commits that local dev-sp lacks; re-evaluate before syncing")
  return git("rev-parse", official_ref)


def plan(args):
  official = preflight(args.official)
  head = git("rev-parse", "HEAD")
  stamp = datetime.date.today().isoformat() + "-" + head[:9]
  bundle_dir = Path(args.checkpoints).expanduser() / stamp
  bundle_dir.mkdir(parents=True, exist_ok=True)
  report = {"head": head, "official": official, "new_official_commits": int(git("rev-list", "--count", f"HEAD..{official}")),
            "checkpoint": str(bundle_dir), "repos": {}}

  repos = {"parent": (ROOT, head, official)}
  for path in FORK_SUBMODULES:
    repo, ours, theirs = ROOT / path, git("rev-parse", f"HEAD:{path}"), git("rev-parse", f"{official}:{path}")
    if not ok(["git", "cat-file", "-e", f"{theirs}^{{commit}}"], cwd=repo):
      if not ok(["git", "fetch", "-q", official_submodule_url(official, path), theirs], cwd=repo):
        fail(f"{path}: official commit {theirs} is not fetchable")
    repos[path] = (repo, ours, theirs)

  for name, (repo, ours, theirs) in repos.items():
    ref = f"refs/checkpoints/{stamp}/{name}"
    git("update-ref", ref, ours, cwd=ROOT if name == "parent" else repo)
    bundle = bundle_dir / f"{name}.bundle"
    git("bundle", "create", "-q", str(bundle), ref, cwd=ROOT if name == "parent" else repo)
    with tempfile.TemporaryDirectory() as tmp:  # prove the checkpoint restores
      git("init", "-q", tmp)
      git("fetch", "-q", str(bundle), f"{ref}:refs/heads/s0", cwd=tmp)
      if git("rev-parse", "s0", cwd=tmp) != ours:
        fail(f"{name}: checkpoint bundle does not restore {ours}")
    up_to_date = ok(["git", "merge-base", "--is-ancestor", theirs, ours], cwd=repo)
    report["repos"][name] = {"ours": ours, "official": theirs, "up_to_date": up_to_date,
                             "conflicts": [] if up_to_date else conflicts(repo, ours, theirs)}
  print(json.dumps(report, indent=2))


def merge(args):
  official = preflight(args.official)
  for path in FORK_SUBMODULES:
    repo, theirs = ROOT / path, git("rev-parse", f"{official}:{path}")
    if ok(["git", "merge-base", "--is-ancestor", theirs, "HEAD"], cwd=repo):
      continue
    git("checkout", "-q", "-B", "dev-sp", git("rev-parse", f"HEAD:{path}"), cwd=repo)
    if not ok(["git", "merge", "--no-edit", "-m", f"Merge official {path} {theirs[:9]} into dev-sp", theirs], cwd=repo):
      fail(f"{path}: resolve the conflicts in {repo}, commit, then rerun merge")
  heads = {path: git("rev-parse", "HEAD", cwd=ROOT / path) for path in FORK_SUBMODULES}
  for path in FORK_SUBMODULES:  # the parent merge needs the gitlinks at the recorded commits
    git("checkout", "-q", "--detach", git("rev-parse", f"HEAD:{path}"), cwd=ROOT / path)
  clean = ok(["git", "merge", "--no-ff", "--no-commit", official])
  for path, sha in heads.items():
    git("checkout", "-q", sha, cwd=ROOT / path)
    git("add", path)
  print(json.dumps({"official": official, "submodules": heads, "parent_clean": clean,
                    "unresolved": git("diff", "--name-only", "--diff-filter=U").splitlines()}, indent=2))


def lfs_missing(paths):
  config = git("config", "-f", ".lfsconfig", "lfs.url", check=False)
  objects = {}
  for line in git("ls-files", "-s", "--", *paths).splitlines() if paths else []:
    meta, path = line.split("\t", 1)
    mode, sha, _ = meta.split()
    blob = subprocess.run(["git", "cat-file", "-p", sha], cwd=ROOT, capture_output=True).stdout[:200] if mode != "160000" else b""
    if blob.startswith(b"version https://git-lfs"):
      text = blob.decode()
      objects[text.split("oid sha256:")[1].split()[0]] = (int(text.split("size ")[1].split()[0]), path)
  missing, items = [], list(objects.items())
  for i in range(0, len(items), 100):
    body = {"operation": "download", "transfers": ["basic"], "objects": [{"oid": o, "size": s} for o, (s, _) in items[i:i + 100]]}
    request = urllib.request.Request(f"{config}/objects/batch", data=json.dumps(body).encode(),
                                     headers={"Accept": "application/vnd.git-lfs+json", "Content-Type": "application/vnd.git-lfs+json"})
    missing += [objects[o["oid"]][1] for o in json.load(urllib.request.urlopen(request, timeout=120))["objects"] if "error" in o]
  return config, len(objects), missing


def check(args):
  base = args.since or git("merge-base", "HEAD", "origin/dev-sp")
  changed = git("diff", "--name-only", "--diff-filter=AM", base).splitlines() + \
    git("diff", "--cached", "--name-only", "--diff-filter=AM").splitlines()
  changed = sorted({p for p in changed if (ROOT / p).is_file()})
  results = {}
  results["no_unresolved"] = not git("diff", "--name-only", "--diff-filter=U")
  results["no_conflict_markers"] = not [p for p in changed if not p.endswith((".md", ".pkl", ".onnx", ".otf", ".png", ".wav"))
                                        and any(line.startswith(("<<<<<<< ", ">>>>>>> "))
                                                for line in (ROOT / p).read_text(errors="ignore").splitlines())]
  py = [p for p in changed if p.endswith(".py")]
  results["python_compiles"] = all(ok([sys.executable, "-c", f"compile(open({p!r}).read(), {p!r}, 'exec')"]) for p in py)
  results["settings_ui_current"] = ok([sys.executable, "openpilot/sunnypilot/sunnylink/tools/compile_settings_ui.py", "--check"])
  seams = subprocess.run([sys.executable, "tools/sp_tesla_e2e/seam_budget_check.py"], cwd=ROOT, text=True, capture_output=True)
  results["seams_within_budget"] = seams.returncode == 0
  store, count, missing = lfs_missing(changed)
  results["lfs_available"] = not missing
  print(json.dumps({"since": base, "changed_files": len(changed), "checks": results,
                    "seam_report": json.loads(seams.stdout) if seams.stdout.startswith("{") else seams.stdout,
                    "lfs": {"store": store, "changed_objects": count, "missing": missing}}, indent=2))
  sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
  os.chdir(ROOT)
  parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  sub = parser.add_subparsers(dest="command", required=True)
  for name in ("plan", "merge"):
    p = sub.add_parser(name)
    p.add_argument("--official", default="sunnypilot/master")
    p.add_argument("--checkpoints", default="~/dev-sp-checkpoints")
  p = sub.add_parser("check")
  p.add_argument("--since", help="base commit for changed files (default: merge-base with origin/dev-sp)")
  args = parser.parse_args()
  {"plan": plan, "merge": merge, "check": check}[args.command](args)
