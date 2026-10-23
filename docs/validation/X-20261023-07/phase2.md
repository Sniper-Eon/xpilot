# Phase 2 evidence

Source commits: tests first 6d2b125; ambient gate bc9e1ca; auto session d2a3586; final tests/mutations 001fca2.
First corrected pre-fix run: exit 1, 189 tests, 5 failures, 19 skipped (phase2-red-final.log).
After fixes: exit 0, 189 run / 19 skips reported / 0 failures or errors.
Ambient-only: exit 0, 15 passed. Includes inherited upstream Tesla stock/longitudinal checks with both bits set,
and noOutput:param=1 with plugin bits. Upstream test files, test.sh, Tesla mode and car port are untouched.

Auto session <=60 frames in <30 s, >=2 s idle restarts; rate stays >=250 ms (host normally >=500 ms).
Ambient 0x8000, Tesla + vehicle bus only, preserves disengaged body warning (no controls_allowed gate),
150 frames / <15 s, >=80 ms spacing, >=1 s idle restart. Python bit wiring follows in Phase 3.

From task root:
```
PYTHONPATH=opendbc_repo opendbc_repo/.venv/bin/python3 -m unittest opendbc.safety.tests.test_tesla_plugins
opendbc_repo/.venv/bin/python3 docs/validation/X-20261023-07/mutations.py
```
Both exit 0. 45/45 mutants compile, then fail an RX/TX assertion (each child exit 1). Compile/import errors
are excluded from kills. mutations/results.json has exact replacements, targeted tests, exits and log hashes.
Each source file is restored in finally. Initial mutation iteration exposed 3 masked tests and 4 compile-rejected
mutants; stimuli and mutations were corrected without production changes. The final recorded run kills all 45.

Coverage, after deleting only generated libsafety/*.gcda and *.gcno from older source revisions:
```
SAFETY_COVERAGE=1 PYTHONPATH=opendbc_repo opendbc_repo/.venv/bin/python3 -m unittest opendbc.safety.tests.test_tesla_plugins
cd opendbc_repo/opendbc/safety/tests
../../../.venv/bin/gcovr -r ../ --gcov-executable '/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/llvm-cov gcov' --filter '.*/plugins/.*' --fail-under-line=100 --txt
```
Both exit 0: ambient 50/50, auto 47/47, registry 21/21 = 118/118 executable lines, 100%.
plugin.h is types only. safety.h executable integration lines 193,194,231,238,240,241,452 all ran;
counts in phase2-hook-coverage.json (include is checked by compilation).
First standalone gcovr attempt exit 64: old .gcno referenced earlier function line numbers; clean rebuild fixed it.
A first hook extraction accidentally selected the unrelated allOutput whitelisted assignment (line 234, zero hits);
correct extraction above selects only integration sites and asserts each count >0.

Host checks now exit 0 with errors [], using PYTHONPATH=opendbc_repo:msgq_repo:.
Only registered msgq e7396e76dadbb49e374d4b664ff6bbb43a39bcb0 was initialized in the task worktree.
Venv additions: pyzmq 27.2.0, setproctitle 1.3.8, psutil 7.2.2, Cython 3.3.0, scons 4.11.1, setuptools 84.2.1.
Build msgq from msgq_repo with venv/bin first in PATH: ../opendbc_repo/.venv/bin/scons --minimal -j4 msgq/ipc_pyx.so, exit 0.
Earlier setup attempts: wrong relative venv path exit 2; cythonize missing from PATH made scons exit 2.
No global/Homebrew installs. No panda firmware build, device, USB or CAN replay.
