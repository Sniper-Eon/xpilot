# Working rules

- User requirement (2026-10-26): before development, consult upstream onemiless/xpilot:xpilot `AGENTS.md`, `XPILOT.md` hard rules and relevant sections/API definitions, then compare with this host's actual capabilities. Follow the parent workspace's persistent developer-document requirement. Upstream API changes are references, not authorization to migrate the device or override user-fork routing, Chinese UI, navigation grouping or DS fixes.

- Read `XPILOT.md` first: project scope, plugin interfaces and hard rules for this repository.
- Push routing (XPILOT.md rule 15): plugin changes (`plugins/<id>/`, their tests, `dist/`, `index.json`) go only to `github.com/Sniper-Eon/xpilot-plugins`. System changes (host, store, UI, core plugins, panda safety, `safety.json`, checks, docs) go only to `github.com/Sniper-Eon/xpilot`. A feature that needs both gets two commits and two PRs; merge the system side first. Do not add plugin directories under `openpilot/tesla/plugins/` here; only the core plugins live there (`manifest_check.py` M12).

- Work on `xpilot` for this project. Do not create a feature branch or another worktree unless the user explicitly requests it.
- Verify the checkout, branch, HEAD, and dirty files before editing. Do not switch unrelated worktrees or overwrite another task's changes.
- Complete each coherent change on `xpilot` with a scoped commit. Include only that change's files. Use `git revert <commit>` to undo a committed change while preserving later work.
- Keep test code and candidate implementations in the same branch and record their validation status. Logs and generated replay results may live outside Git; identify the source commit and content hashes.
- Report the local commit and the device's active commit separately. A shared branch name, an uploaded test copy, or a successful replay does not establish deployment or activation.
- NEVER write unit tests after writing code. Prefer E2E validation with repeatable commands and verifiable artifacts. Before isolated testing, list the ways the system can fail.
