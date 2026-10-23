# X-20261023-07 Phase 1

Source: `00f7924ca05272103dd7cd2063cd5c66d1767b87` (origin/xpilot verified after fetch).
Task worktree: `../wt-X-20261023-07`, branch `task/X-20261023-07`.
No C/source fixes were needed. No device, USB, or firmware action.

## Build and baseline

Use `opendbc_repo/.venv/bin/python3` (CPython 3.12.13). From the task root:

```
export PYTHONPATH=opendbc_repo:.
opendbc_repo/.venv/bin/python3 -m unittest opendbc.safety.tests.test_release_build
opendbc_repo/.venv/bin/python3 -m unittest opendbc.safety.tests.test_tesla
opendbc_repo/.venv/bin/python3 -m unittest opendbc.safety.tests.test_defaults
```

The direct `_build_libsafety(release=False/True)` command in commands.json exited 0;
its log records both library paths and SHA-256. This checkout has no opendbc SConstruct;
libsafety_py.py compiles with the repo's own cc commands, also exercised by test.sh.
Tesla: exit 0, 381 run / 338 passed / 43 skipped. Defaults: exit 0, 29 run / 28 passed / 1 skipped.

From opendbc_repo:

```
export PATH="$PATH:/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin"
GIT_LFS_SKIP_SMUDGE=1 UV_PYTHON=3.12 bash opendbc/safety/tests/test.sh
```

Exit 1. Both UBSan and coverage rounds: 420 run / 375 passed / 45 skipped / 0 failures / 0 errors.
Global line coverage: 778/1094 = 71.1%, fails unchanged 100% gate.
Tesla mode: 245/245 = 100%; auto_speed 9/37, ambient_light 15/52, registry 19/21.
Unchanged helpers/lateral/longitudinal and safety core have uncovered lines after non-Tesla modes/tests were removed.
Coordinator explicitly waived this global gate as a stop condition; Phase 2 must reach 100% plugin/integration line coverage.
Do not change test.sh or upstream tests. test.sh does NOT invoke MISRA/cppcheck; neither was run.

## Setup and unsuccessful attempts

Fetch initially exit 255 (sandbox FETCH_HEAD); approved retry succeeded, origin/xpilot matched base.
First worktree creation exit 128: unrelated Hugging Face LFS credentials missing. Recovery restore exit 128: failed worktree had been removed.
GIT_LFS_SKIP_SMUDGE=1 worktree add succeeded (exit 0). Future Git checkout/fetch/worktree operations skip LFS.
First test.sh: exit 1 after both passing rounds, llvm-cov absent from PATH.
Second test.sh with Xcode PATH prepended: exit 1 (420 errors): bare clang lacked SDK stdio.h.
Final PATH appends the toolchain so /usr/bin/cc remains selected; builds and all tests pass, only the global coverage gate fails.

The repo's setup.sh / uv sync installed 31 packages in opendbc_repo/.venv, including cffi, numpy, pycapnp,
gcovr and cppcheck. Full versions are in the first test.sh log. No global/Homebrew installs.
The two host checks initially exited 1 for missing pyzmq; after installing pyzmq==27.2.0 they exited 1 for missing setproctitle.
Further host dependencies and final results are in host-deps-2.log, manifest-final.log and plugin-host-final.log.
commands.json preserves exact direct commands, original exits and hashes (including a failed package-list one-liner, later replaced).

## Open issues / remaining phases

Global coverage is a known baseline failure; no upstream fixes authorized.
Ambient currently has no own param bit and permits noOutput:param=1; auto_speed has no session cap.
Both must get tests before fixes, each fix in its own commit, then manifest declarations/generator.
Plugin-specific tests, mutations, panda firmware build, device and CAN replay are not yet verified.
