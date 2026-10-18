# Actual lean-mici LANLink integration

Target source: `lochuan/lean-mici` `lean-master` at
`be16822e572ce8c6e7def7cfd48d21eae7ffeef1`.

This integration adds a native Vue panel to the existing LANLink sidebar and
`#/tcan` hash route, served by LANLink's existing Sanic process and compiled Vite
assets. It is not an iframe, redirect, second standalone page, or replacement
server. The separately running T-CAN observer remains the only capture/preview
implementation. Neither process transmits CAN.

## Exact target changes

`tools/tcan/apply_lean.py` checks SHA-256 of the three upstream files before
applying `tools/tcan/lean/integration.patch`:

- `openpilot/system/lanlinkd/lanlinkd.py`: register three T-CAN routes in the
  actual existing `create_app`.
- `openpilot/system/lanlinkd/web/src/App.vue`: render the native TcanPanel for
  the `tcan` hash route.
- `openpilot/system/lanlinkd/web/src/components/Sidebar.vue`: T-CAN navigation.

Two new target files are copied from `tools/tcan/lean/`:

- `openpilot/system/lanlinkd/tcan_api.py`.
- `openpilot/system/lanlinkd/web/src/components/TcanPanel.vue`.

No Toyota diagnostics, manager process rules, Panda ownership, Params settings,
or other vehicle-control modules are copied or changed. The source manifest
checks integration inputs, not the integrity of every file in a repository.
Start from the exact target SHA; mismatched/already patched inputs fail before
mutation. Native frontend compilation updates target `static/` build products.

## Apply and build

On a separately selected local lean checkout/snapshot at the exact SHA above:

```sh
python3 tools/tcan/apply_lean.py --lean-root /absolute/path/to/lean-mici
cd /absolute/path/to/lean-mici/openpilot/system/lanlinkd/web
npm ci --ignore-scripts
npm run build
```

The applicator is intentionally not an updater and does not create branches,
push, deploy, restart processes, or bypass a version mismatch. Preserve the
original files/build output before applying on a device. Revert the patch and
remove only the two installed files to undo integration, then rebuild frontend.

## Observer / bridge contract

The fixed backend is **http://127.0.0.1:8099**. Start the observer on loopback,
using its normal Python environment from the dev-sp checkout:

```sh
python -m openpilot.sunnypilot.tcan.service --host 127.0.0.1 --port 8099
```

Then launch LANLink through lean-mici's normal enabled service flow. LANLink's
own enable setting still governs its availability. Browser entry is LANLink's
existing port, e.g. `http://DEVICE_IP:8088/#/tcan`.

The earlier observer bound only to `172.16.1.210:8099` is **not** a loopback
backend and has not automatically become LANLink-integrated. This change was
validated on the host; it does not claim that device has the integrated service.

LANLink exposes only GET `/api/tcan/status`, GET `/api/tcan/capture`, POST
`/api/tcan/preview`. The proxy destination cannot be supplied by a request.
Before rewriting backend Host/Origin, the bridge validates the incoming Host
against its bound device IP/port and requires exact same-origin JSON POST.
One in-flight backend request is allowed; others get 503. Backend timeout is
2 seconds; unavailable backend returns 503, timeout 504, invalid backend response
502. Request/response bounds are 262144 bytes. Backend redirects are refused.

Use the device's IP and port in the browser. Hostname/mDNS aliases are not
accepted by this narrow endpoint. No HTTPS reverse-proxy support is claimed.

## Evidence and repeatability

Pre-implementation failure list: [LEAN_ACCEPTANCE.md](LEAN_ACCEPTANCE.md).
`tools/tcan/lean_http_e2e.py` launches the actual upstream `create_app` in a
subprocess, checks absent backend, starts the real observer with replay, and
verifies capture, nonempty R79 candidate, CSRF, unknown route, malformed input,
body bound and original index through real HTTP. The original unpatched app
fails with 404 for `/api/tcan/status` (RED); the patched app passes (GREEN).

Host dependency setup (isolated environment, no repository dependency changes):

```sh
uv venv /tmp/tcan-lean-python --python 3.12
uv pip install --python /tmp/tcan-lean-python/bin/python sanic==25.12.1 numpy pycapnp pyzmq requests psutil pycryptodome cffi zstandard setproctitle
/tmp/tcan-lean-python/bin/python tools/tcan/lean_http_e2e.py \
  --lean-root /absolute/path/to/pinned-lean-snapshot --artifact /tmp/tcan-lean-green.json
```

Stop any demonstration observer on 8099 before running this harness; it asserts
that backend absence is initially visible. The artifact records source hashes,
assertions, explicit hardware fixtures, and rerun command. For host-only browser
QA with compiled static assets, `tools/tcan/lean_host.py --lean-root ... --port
18088` starts that same actual app on loopback; set PYTHONPATH to this dev-sp
checkout's `opendbc_repo:msgq_repo`. Run the observer separately with `--replay`
and open `http://127.0.0.1:18088/#/tcan`. Stop both foreground processes with Ctrl-C.

Hardware fixtures are explicit: upstream's own off-device Params conftest, and
StatusCache.run waiting without live IPC. The actual LanlinkApp methods,
create_app, Sanic routes, bridge, observer, Vue panel and compiled static files
remain real. Host proof does not establish live message availability, full
vehicle behavior, or deployment. The codeload snapshot has no Git index, so the
upstream Git-index-based frontend build-hash checker is not claimed as passed.

The new AutoBlinker scheduler is an independent offline semantic-candidate
runtime. It is not exposed by this panel yet. Existing three transforms remain
limited R79 mux1 bits, ISA intermediate bits, and Country US 0x238, all default
off. This adaptation does not complete the full T2CAN migration or enable CAN TX.
