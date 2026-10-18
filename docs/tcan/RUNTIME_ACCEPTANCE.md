# Auto Blinker candidate scheduler acceptance

Pinned upstream: T2CAN `e63b678df385748ffe379ebebdd98b73a361c3d8`.
This ports one request scheduler, not the complete Advanced EAP feature or a CAN transmitter.

## Failure cases recorded before implementation

- Disabled mode, SP onroad, missing/expired/future authority or vehicle state permits a candidate.
- Lost ownership preserves pending direction, NOA stabilization or previously fired history.
- Backwards clock reuses deadlines; invalid replay values leave live authorization behind.
- NOA emits before stabilization; brief NOA dropout loses session; confirmed exit fails to reset.
- Delay resets on repeated same-direction frames, or opposite direction inherits old delay.
- Blocked ALC cancels valid pending request, retries faster than 250ms, or fires wrong direction.
- Missing/off-ramp road context authorizes ALC4 despite no route proof.
- Temporary IN_LANE clears pending prematurely; request older than 2000ms remains eligible.
- A successful candidate repeats for an uninterrupted request.
- Cancel fails to pause, or pause expiration bypasses a fresh request delay.
- Candidate persists across SP onroad, disable, stale authority, stale AP or future frame.

## Inputs and semantic scope

`AutoBlinkerRuntime(delay_ms=2000, stabilization_ms=10000, pause_ms=20000)`.
`step(now_ms, *, authority_ms, sp_onroad, state_ms, ap_state, alc_state,
request_ms, behavior, enabled=False, cancel=False)` consumes an explicit offline snapshot.
Missing timestamps are `None`. `cancel=True` is one discrete button event, not a held level. No bus or mapping is inferred.
`state` reports phase, pending direction, reason, retry count and deadlines.

Source fields: 0x24A behavior = byte7 & 3 (little endian bit56 length2);
0x399 AP = byte0 & 15; ALC = (byte5 >> 6) | ((byte6 & 7) << 2)
(little endian bit46 length5). Behavior2 requests LEFT, behavior3 RIGHT.
AP5 is NOA; ALC6 allows left, 7 right, 8 both. ALC4 requires road context
in upstream and is deliberately blocked by this subset.

Source: `auto_blinker_pure.h` NOA/pause helpers and
`autoBlinkerAlcAllowsDirectionPure`, `autoBlinkerSessionDecisionPure`;
`vehicle_logic.h:2542-2720` request arm/opposite replacement/retry/fire pipeline.
Upstream default stabilization10s, exit confirmation2s, request freshness2s,
delay2s, retry250ms, cancel pause20s are retained. The NOA phase survives a
sub-2s raw dropout but pending requests are cleared while NOA gate is closed.
A repeated same request cannot fire again until request history genuinely expires.

Additional conservative host policy: authority <=250ms and AP/ALC <=1000ms,
non-future timestamps, SP offroad, enabled. A step arriving after the previous authority lease expired clears state even if its new authority timestamp is fresh. Any loss immediately clears pending
and NOA session. This replaces upstream latched authorization. Offline authority
is a declaration, not proof of vehicle ownership. Candidate consumption cannot
be inferred: `blinker_request` is semantic only, with no bus, payload or send API.
No 0x249/0x3C2 templates, counter/checksum, stock-sync250ms, legacy20ms pulses,
S3XY direct mode, hardware cancellation or lamp-state confirmation is implemented.

## Repeatable E2E

Write and run `tools/tcan/runtime_e2e.py` before `runtime.py`; retain missing-module
failure. Compile pinned upstream pure header as an oracle for all ALC combinations
and request-session decisions. Replay complete temporal scenarios and save each
snapshot, candidates, state, source SHA256, oracle, command and pass/fail report.

```sh
python3 tools/tcan/runtime_e2e.py --upstream /tmp/tcan-audit-20261018 --output /tmp/tcan-runtime-e2e
```

A pass proves offline scheduling only. All physical routing, timing, Panda policy,
SP interaction under real IPC and vehicle behavior remain unverified.
