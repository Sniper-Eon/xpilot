# T-CAN observation and offline preview

This standalone service observes CAN and exports up to 1000 recently sampled frames.
The SubMaster observer can skip batches under load; exports are diagnostic
samples, not a complete or lossless bus recording.
Its web form runs three offline, intermediate transforms: R79 mux1 fixed bits,
ISA warning bits, and the 0x238 US country field. It has no CAN transmitter,
Panda access, persistent feature settings, or manager integration. All preview
features are off by default. This is the first migration stage, not a completed
T2CAN firmware port or a vehicle-ready unlock implementation.

From this checkout with its normal runtime dependencies:

```sh
python -m openpilot.sunnypilot.tcan.service
```

Open `http://127.0.0.1:8099`. An explicit `--host DEVICE_IP` makes the read-only
observer available on that device's local network. Stop the foreground process
with Ctrl-C. No manager or Panda restart is required. Do not expose this local
diagnostic endpoint through an Internet port forward.

For a host-only demonstration, pass `--replay capture.json`. The file has the
same `{"frames": [...]}` shape exported by `/api/capture`; each frame contains
`bus`, `address`, hex `data`, and monotonic `timestamp_ns`. The web preview uses
its own ephemeral engine and never changes the live capture or configuration.
Its A/B selectors declare the input recording's topology, not verified wiring.
Candidate bytes are not transmit-ready frames, especially ISA's intermediate
bit transform. Device and Panda message ages are reported separately; missing
or stale observations do not authorize any vehicle action.

The service only subscribes to `can`, `deviceState`, and `pandaStates`. Existing
`card`, `sendcan`, forwarding, safety, process configuration and model paths are
unchanged. A future transmitting implementation must establish physical bus
identity and arbitrate through the existing single sender. Do not add a second
sender or bypass `NO_OUTPUT` to make these previews actuate the vehicle.

Validation commands and pre-implementation failure lists:

- [HTTP and capture E2E](WEB_ACCEPTANCE.md)
- [Pinned upstream C++ oracle and shadow replay](SHADOW_ACCEPTANCE.md)

An offline Auto Blinker request scheduler is also available in `runtime.py`.
It produces semantic candidates only and is not yet connected to the web form
or a CAN transmitter. Its timing and revocation replay is documented in
[RUNTIME_ACCEPTANCE.md](RUNTIME_ACCEPTANCE.md).

Unimplemented: full R79/Summon runtime and timing, Continuous AP, Auto Blinker CAN transport,
NAG/hands-on, DMS, S3XY BLE, TLSSC, pedal/drive profiles, experimental lane-change
and window controls. Physical CAN mapping, Panda changes and vehicle behavior
are separate acceptance steps and are not established by host E2E.

Native lean-mici LANLink integration (pinned source patch, actual Sanic routes,
Vue hash panel, install/build and host proof): [LEAN_INTEGRATION.md](LEAN_INTEGRATION.md).
