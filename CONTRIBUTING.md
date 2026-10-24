# Contributing to xpilot

xpilot is a Tesla-only sunnypilot fork. Read `XPILOT.md` (rules, plugin interfaces) and `AGENTS.md` before you change anything.

## Which repository

- **This repository** (`onemiless/xpilot`): the plugin host, the store, the UI, the core plugins (`sp_engagement`, `sp_models`, `sp_safety_fallback`), panda safety code and `opendbc/safety/plugins/safety.json`, checks and docs.
- **`onemiless/xpilot-plugins`**: every other plugin. New features go there as `plugins/<id>/`. CI here rejects new directories under `openpilot/tesla/plugins/`.

A feature that needs both (for example a plugin that sends a new CAN message and needs a panda safety plugin) gets two pull requests. Merge the system one first.

## Pull requests

1. Fork, branch from `xpilot`, open a pull request against `xpilot`.
2. Run the host checks from `XPILOT.md` section 11. CI runs the same checks and must pass before merge.
3. Say in the pull request what you verified where: host checks, build, safety tests, device. Do not report one as another.
4. Changes to panda safety code also need the panda build, `test_tesla.py`, `test_xpilot_plugins.py` and MISRA (XPILOT.md section 6).
