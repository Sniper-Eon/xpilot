# REPORT X-20261023-07

Status: COMPLETE (host scope; unchanged global coverage gate is explicitly waived by the coordinator).
Branch: task/X-20261023-07, based on 00f7924ca05272103dd7cd2063cd5c66d1767b87.
Verified source: f6da24032cd1c33b8dcff3742b76f6ffb487810e. The final evidence commit changes only validation artifacts.
Local/device distinction: no device queried, deployed, flashed or activated; device active commit UNKNOWN.
Task worktree: /Users/mile/Desktop/mo-op/artifacts/xpilot-install-20261022/wt-X-20261023-07.
Verification source checkout and its pre-existing untracked validation directory were preserved.

## Phase checkpoints

- Phase 1: 34563bd, built the existing plugins without needing C compile fixes; recorded baseline and dependencies; pushed.
- Tests first: 6d2b125 (failure list + real libsafety hook tests).
- Ambient fix: bc9e1ca, own 0x8000 bit and Tesla/vehicle-bus gate, removed noOutput:param=1 allowance.
- Auto fix: d2a3586, <=60 frames in <30 seconds, >=2 seconds idle restarts; existing 250 ms limit remains.
- Phase 2: 001fca2 / 065a71d, 45 assertion-killed compiled mutants, 100% plugin line coverage; pushed.
- Phase 3 tests first: 8232d43, file/CLI negative cases before generator implementation.
- Declarations/generator: 8d3ab33; repeatable acceptance proof and final docs: f6da240.

## Final commands and exit codes

Set PATH to the task venv bin first, append Xcode's toolchain bin (keep /usr/bin/cc before naked clang).
Set PYTHONPATH=opendbc_repo:msgq_repo:. From the task root unless noted:

| Command | Exit | Result |
|---|---:|---|
| python3 -m unittest opendbc.safety.tests.test_release_build | 0 | debug + release libsafety compiled; 2 passed |
| python3 -m unittest opendbc.safety.tests.test_tesla | 0 | 381 run, 338 passed, 43 skipped |
| python3 -m unittest opendbc.safety.tests.test_defaults | 0 | 29 run, 28 passed, 1 skipped |
| python3 -m unittest opendbc.safety.tests.test_tesla_plugins | 0 | 189 run, 170 passed, 19 skipped |
| python3 openpilot/tesla/plugins/gen_safety.py | 0 | deterministic registry/bit generation |
| python3 openpilot/tesla/plugins/gen_safety.py --check | 0 | generated registry current |
| python3 openpilot/tesla/plugins/gen_params.py --check | 0 | existing generated params unchanged/current |
| python3 tools/sp_tesla_e2e/safety_manifest_check.py | 0 | 11 CLI/setup scenarios, expected negative children exit 1 |
| python3 tools/sp_tesla_e2e/manifest_check.py | 0 | all 8 plugins, errors [] |
| python3 tools/sp_tesla_e2e/plugin_host_check.py | 0 | all 8 plugins, errors [] |
| python3 docs/validation/X-20261023-07/mutations.py | 0 | 45/45 compiled mutants fail the targeted assertion; children exit 1 |
| bash opendbc/safety/tests/test.sh (cwd opendbc_repo) | 1 | both rounds 609 run / 545 passed / 64 skipped / no failures/errors; global coverage gate only |
| SAFETY_COVERAGE=1 python3 -m unittest opendbc.safety.tests.test_tesla_plugins | 0 | rebuild counters after test.sh's gcovr -d deletes them |
| gcovr -r ../ --gcov-executable '<Xcode>/llvm-cov gcov' --filter '.*/plugins/.*' --fail-under-line=100 --txt (cwd safety/tests) | 0 | 118/118 lines = 100% |
| gcovr -r ../ --gcov-executable '<Xcode>/llvm-cov gcov' --json <output> (cwd safety/tests) | 0 | per-line machine-readable coverage |
| git diff --exit-code BASE -- protected files | 0 | Tesla mode, car ports, Tesla DBCs and safety.h unchanged |
| git diff --exit-code -- verified source paths | 0 | generator and mutations left source unchanged |
| python3 docs/validation/X-20261023-07/verify.py | 0 | asserts every expected exit, source hashes, coverage and mutation result |

Exact argv, absolute cwd, output SHA-256 and exits: final/commands.json. Full logs: final/*.log.
Test source and runtime file SHA-256: final/source.json. Per-line coverage: final/coverage.json and final/hook-coverage.json.
Dependency versions: final/dependency-versions.log. SHA256SUMS covers all committed evidence recursively.

## Coverage and mutation details

Before plugin tests, unchanged test.sh ran 420 tests twice, 375 passed / 45 skipped each; global coverage 778/1094 = 71.1%.
Final unchanged test.sh: 609 tests twice, 545 passed / 64 skipped each; global coverage 855/1102 = 77.6%.
The lost coverage is in generic helpers/lateral/longitudinal and other core paths after non-Tesla modes/tests were removed.
Do not treat test.sh exit 1 as a passing global gate. Coordinator explicitly allowed continuation and required a separate plugin gate.

Plugin gate: auto_speed.h 47/47, ambient_light.h 50/50, registry.h 21/21, total 118/118 = 100%.
plugin.h is typedefs only. safety.h executable integration lines 193,194,231,238,240,241,452 all covered (7/7);
registry include is proved by debug/release compilation. This is line coverage, not a branch/MC/DC claim.

45 one-check mutations: both mode/vehicle/own-bit gates, RX bus/address/length, freshness validity and age,
rate, session frame/time caps and idle restart; auto controls_allowed, RX mux/idle, tick magnitude, both template comparisons;
ambient targets, RGB components, brightness and all preserved template fields; both TX bus/length gates; both mode resets.
Each mutant compiled and exited 1 via an assertion; no compiler/import failures are counted as kills.
final/mutations/results.json records each exact source replacement, target test, exit and log hash.
Source restoration and unchanged-source checks passed. Initial mutation development found masked stimuli/compiler-rejected edits;
those were corrected before the final all-killed run (details in phase2.md).

## Declarations and scope

Both plugin.json files declare their header, bit and TX. gen_safety.py uses only stdlib, generates registry.h and C bit macros,
rejects all five requested invalid cases, and validates single uint16 bits, safe header names, duplicate headers and header .msg identity.
Python setup reads the loaded plugin.json safety bit. The setup check temporarily changes it to 0x2000 to prove there is no hard-coded bit.
Heads stay in opendbc/safety/plugins for the panda build. XPILOT.md step 5.4 and section 6 document generation and actual proof boundaries.

Ambient intentionally preserves disengaged body-warning behavior (no controls_allowed requirement), as authorized.
Its old noOutput:param=1 path is gone; auto still requires controls_allowed. Both additional plugin permissions require Tesla + vehicle bus + own bit.

## Dependencies, earlier commands and open issues

All Python/build deps were installed only into opendbc_repo/.venv, using the repo's setup.sh/uv sync and uv pip install.
No global/Homebrew installs. See phase1.md, phase2.md and logs for earlier setup failures and corrected commands.
Additional host deps: pyzmq 27.2.0, setproctitle 1.3.8, psutil 7.2.2, Cython 3.3.0, scons 4.11.1, setuptools 84.2.1.
msgq alone was initialized at its existing gitlink e7396e76dadbb49e374d4b664ff6bbb43a39bcb0 and ipc_pyx.so built (exit 0).
The initial failed LFS worktree creation was retried with GIT_LFS_SKIP_SMUDGE=1; LFS assets are not needed here.
First final verifier run exited 1 because test.sh gcovr -d had deleted counters before a second coverage read (gcovr exit 2, zero hits).
The verifier now explicitly rebuilds coverage counters; final run exits 0. Source implementation did not change for this.
An optional Ruff run initially found formatting/unused-import issues in new check/evidence scripts; fixed, final run passes.

Open: global 100% gate remains unmet (77.6%, waived for this task). MISRA/cppcheck was not run: test.sh does not invoke it.
Not verified: panda firmware cross-build, real device execution, USB, flashing, CAN replay or vehicle operation.
Host libsafety proof does not establish firmware-build or drive readiness. No device active commit is claimed.
