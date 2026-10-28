# Upstream source synchronization — 2026-10-28

Source targets: onemiless/xpilot:xpilot
`1de0b807d1ffde580dd2fd19f49b2f18b329e794` and onemiless/xpilot-plugins:main
`36f2bfedca506ef86b79701c550820ef1f8a1a06`. User forks remain the only push/store
and CI peer targets. No device connection, update, restart or flash was performed.

## Retained user behavior and integration

Keep integrated TesNav navassist and independent CP, the broker crash repair,
Chinese catalog/font hooks, glass/branding displays, parked settings access,
strict separation of additional plugin subscriptions from mandatory service
health checks, SCC-V repairs and the single cooperative steering limiter in the
user's mixed-control variant. Preserve signed and unsigned 16-bit safetyParam
round trips without mutating the native value. Context/filter faults retain the
new upstream isolation while accepting native event enums, never bool/float/text.

Migrate CP 0.2.0 and navassist 2.0.0 to the exact upstream NAV ABI-1 rule table;
legacy safetyParam feature bits/registries are retired. Keep their separate BOOL
masters. The upstream navigation-signal alternative also claims the exclusive
source:turnsignals resource so it cannot drive the lamps alongside CP/TesNav.
It is 0.4.1 in this fork; mixed_control 1.1.2 retains the user's limiter pipeline.
Phone vision and extended Chinese remain paired plugins, with explicit use
metadata and unchanged companion App identity. New metadata is translated.

## Validation

Failure acceptance checks were written/run before synchronization: ancestry was
absent, legacy manifests remained and navigation signal ownership was not
exclusive. Existing regression cases were updated for the intentional upstream
runtime-rule contract, while retaining real wire, native guard and GPIO coverage.

- Workflow host checks, typed parked settings, SCC-V compatibility, package
  discovery/enable/disable, store activation transaction (40 cases): passed.
- Full store plugin suite: 779 passed; headless tests use SCALE=1 so GUI imports
  do not create an auto-scale window.
- Native Tesla safety: 350 passed, 115 abstract/inapplicable skips, 243 subtests.
- Native runtime rules/data: 48 passed, 6 abstract skips, 388 subtests.
- Actual C++ host -> native C app-loader check: native_rc=0.
- Longitudinal owner deterministic host/planner/API replay: PASS, all four groups.
- F4 Panda, H7 Panda and H7 Body app+bootstub compiled, signed DEBUG artifacts;
  app text/data: 32532 / 41704 / 38536 bytes respectively (ELF size evidence local).
- H7 MISRA code analysis: zero violations using cppcheck 2.22.0. The tool-version
  coverage/checker-list diff was skipped; generated checklist restored. This is
  not an unqualified MISRA certification claim. Native host build needed the OS
  zlib in the existing SCons library allowlist for Panda rule-table CRC.
- Runtime archive/source rule tables match the canonical AUTO/AMBIENT/NAV bytes.
  Linux broker credential/big-datagram CI and paired branch CI are separate gates.

Builds and native replays used isolated local fixtures; no synthetic messages
were injected into the live device. Private evidence under the workspace's
upstream-sync-20261028 directory includes input/output hashes and firmware sizes.

## Deployment limits

This is source synchronization, not vehicle activation or road validation. The
running device was last observed on the older host with protected overlays.
It needs a coherent host/store/ABI-1 Panda qualification before installation;
never copy these manifests onto that old firmware alone or update AGNOS/boot
partitions merely to satisfy source compatibility.

Upstream ABI 1 requires primary controls_allowed for active navigation signal
requests; cancel remains exempt under its template/rate rules. The old fork's
MADS-only signal authority is **not equivalent**. That behavior needs an explicit
compatibility design and stationary verification before promising parity or
activating it. Native tests enforce the upstream permission floor rather than
silently broadening all runtime rules. Physical ACC/SP handoff, the phone CP
handshake, final device UI and road behavior remain unvalidated.

Latest upstream follow-up #57 is included: parked editable() gates, integer-sized
dragged view textures, and no owner-switch pause for interruptRateCan2 alone.
Typed setting validation is preserved at the new editable() call sites.
