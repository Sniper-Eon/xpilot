# Pinned lean-mici integration acceptance (before implementation)

Target: lochuan/lean-mici be16822e572ce8c6e7def7cfd48d21eae7ffeef1.
Failures: absent T-CAN routes in original create_app; patch wrong version or already applied;
missing observer; backend timeout; cross-origin POST; malformed JSON; oversized request;
unknown route cannot become arbitrary proxy; existing / and /api/status still present;
Vue panel must be in original App hash navigation and original Sidebar, compile with upstream
vue-tsc/Vite, no iframe or second-page redirect. Observer independently defaults off/no TX.

Host HTTP harness uses actual upstream lanlinkd.create_app and LanlinkApp routes. Only native
Params uses upstream's own off-device conftest, and live StatusCache.run is replaced by a
waiting fixture (no hardware); these boundaries are recorded. The T-CAN bridge and HTTP
server are real. Original frontend must build before and after patch. No host test proves
hardware availability, deployment or vehicle control.
