# Contributing to xpilot

xpilot is a Tesla-only sunnypilot fork. Read `XPILOT.md` (rules, plugin interfaces) and `AGENTS.md` before you change anything.

## Which repository

- **This repository** (`onemiless/xpilot`): the plugin host, the store, the UI, the core plugins (`sp_engagement`, `sp_models`, `sp_safety_fallback`), panda safety code and `opendbc/safety/plugins/safety.json`, checks and docs.
- **`onemiless/xpilot-plugins`**: every other plugin. New features go there as `plugins/<id>/`. CI here rejects new directories under `openpilot/tesla/plugins/`.

A feature that needs both (for example a plugin that sends a new CAN message and needs a panda safety plugin) gets two pull requests. Merge the system one first. CI here runs `store_e2e` against the plugin repository's default branch, so after the plugin pull request is merged, re-run CI on `xpilot` to check that the two work together.

## Pull requests

1. Fork, branch from `xpilot`, open a pull request against `xpilot`.
2. Run the host checks from `XPILOT.md` section 11. CI runs the same checks and must pass before merge.
3. Say in the pull request what you verified where: host checks, build, safety tests, device. Do not report one as another.
4. Changes to panda safety code also need the panda build, `test_tesla.py`, `test_xpilot_plugins.py` and MISRA (XPILOT.md section 6).
5. CI does not build panda or run the safety tests or MISRA. Paste the commands, results and the machine for each of them into the pull request.
6. A new panda safety plugin's header is `<plugin id>.h` (`gen_safety.py` rejects anything else). Every TX it allows without `controls_allowed` is listed in the XPILOT.md section 6 rules with the exact condition; the code must not allow more than the text says.
7. Fill in the pull request template. Leave a box unchecked if you did not do that step and say why.
8. Pull requests from forks wait for a maintainer to approve the CI run. Every new push needs a new approval.
