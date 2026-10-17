# T-CAN offline shadow acceptance

Scope: candidate bytes only, no CAN transmission, no Panda changes, no process integration.
Upstream: `06066060606060/t2can-universal-unlock` at
`e63b678df385748ffe379ebebdd98b73a361c3d8`.

Before implementation, the failure cases are:

- Missing or invalid profile, missing/ambiguous/invalid offline A/B map.
- Wrong physical-route declaration, wrong address, non-eight-byte frame.
- Frame older than 250 ms, future timestamp, backwards observation clock.
- Missing, inactive, expired (>1 second), or wrong-route AP context.
- SP onroad transition leaves cached AP permission usable on return.
- Features disabled or unknown feature name silently accepted.
- R79 mux other than 1 changed, or unrelated bytes changed.
- ISA inactive AP or already-set flag emits another candidate.
- Country frame invalid checksum, unknown source, or already-US altered.
- Source payload mutated; replay result cannot be reproduced.

The route declaration is an offline input assumption, never proof of C3 wiring.
Profiles: `yl` (A=Party/B=VH), `standard_body` (A=Body/B=Chassis),
`standard_party` (A=Party/B=Chassis). All feature switches default off.
API: `ShadowEngine(profile=None, bus_map=None, features=())`, then
`observe(bus,address,data,now_ns,received_ns=None,sp_onroad=False)` (last two keyword-only).
Returns candidate dictionaries; empty list means no proposed modification.

This deliberately implements only R79 mux1 fixed bits (bit18 STOCK), ISA's
raw warning bit transform, and US country 0x238 transform. ISA output is an
intermediate pure transform, not a transmit-ready counter/checksum composition.
All three require fresh AP state 3..6; this is a conservative shadow policy,
not the upstream full R79/Summon runtime. No timers, retries, DMS, NAG,
Continuous AP, or actuation are included.

E2E: compile the real pinned upstream pure C++ headers as a byte-transform oracle,
replay generated JSONL through the Python engine, compare every candidate to
the oracle and every blocked scenario to zero output. Write input JSONL,
candidate JSONL, oracle source/binary, source hashes, report and rerun command.
The harness is written and run before engine implementation; its first run must
fail due to missing engine. Record that failure outside Git.

Run from repository root:

```sh
python3 tools/tcan/shadow_e2e.py --upstream /tmp/tcan-audit-20261018 --output /tmp/tcan-shadow-e2e
```

Requires Python 3 and a C++ compiler. Clone the upstream repository at the exact
SHA above when the local audit checkout is absent. The harness verifies both
HEAD and tracked cleanliness before using upstream as an oracle. Reports prove
offline behavior only; physical routing, scheduling, Panda acceptance and
vehicle behavior remain unverified.
