# T-CAN Web acceptance, before implementation

This phase is observation and offline shadow preview only. No CAN transmit,
Panda safety changes, manager integration or replacement of the active checkout.
Physical bus mapping is unverified. An empty capture is not topology evidence.

Failure scenarios to exercise before accepting the HTTP service:

- Missing implementation must fail the subprocess HTTP harness.
- Offline fixed replay must render a mobile page, expose exact bus/address/DLC counts,
  and export the bounded captured bytes without changing them.
- Unknown or mutation-like routes must fail; no arbitrary CAN or safety API exists.
- Cross-origin preview, missing JSON content type, malformed JSON, oversized bodies,
  invalid IDs/buses/hex/timestamps, extended IDs in shadow preview, excessive frame count and invalid engine options fail.
- Preview must use an ephemeral engine and never change live capture or configuration.
- Status must always say no TX, physical mapping unverified, and identify replay vs live.
- Missing live state must stay unknown, not be interpreted as offroad authorization.
- Capture memory, request body size and HTTP socket idle time are bounded. The server has no per-request
  thread creation; slow clients can delay this observer but cannot create unlimited workers.
- Empty capture must remain empty; source failure must be visible.

Run `python3 tools/tcan/web_e2e.py --artifact /tmp/tcan-web-e2e.json`.
The harness starts a real HTTP subprocess on loopback with a fixed temporary replay,
checks response boundaries, and writes source hashes, HEAD, assertions and replay hash.
The artifact proves host HTTP behavior only, not Panda acceptance, physical mapping,
vehicle behavior, device deployment or full T-CAN functionality.

Live subscription uses `from openpilot.cereal import messaging`, matching this checkout.
Replay HTTP proof does not prove live compiled messaging availability. Capture retains
29-bit extended IDs; shadow preview rejects a request containing one with explicit HTTP 400.
