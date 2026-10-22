#!/usr/bin/env python3
"""End to end: a checkout of the plugin repository -> its index and archives served locally -> store install ->
discovery -> enable via the params view -> the plugin's hook runs in the host. Usage:
  python3 tools/sp_tesla_e2e/store_e2e.py --repo ~/xpilot-plugins

Failure cases listed before running:
- E1 an index entry from the repository is not installable on this host, or fails to install
- E2 an installed repository plugin is not discovered, or reports a load error
- E3 a plugin that is off by default is active before it is switched on
- E4 after switching on, its alert hook is not collected or gives no alert when it should (overspeed_warning)
- E5 the alert fires below the margin or without a known limit
- E6 a setting written through the params view does not reach the plugin on the next start
"""
import argparse
import http.server
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import types

ROOT = Path(__file__).resolve().parents[2]
TMP = Path(tempfile.mkdtemp(prefix="xp-e2e-"))
os.environ["XPILOT_PLUGINS_DIR"] = str(TMP / "installed")
sys.path[:0] = [str(ROOT), str(ROOT / "opendbc_repo")]


class CoreParams:
  def get_bool(self, key, block=False):
    return False

  def get(self, key, block=False, return_default=False):
    return None


try:
  import openpilot.common.params  # noqa: F401
except Exception:
  sys.modules["openpilot.common.params"] = types.SimpleNamespace(Params=CoreParams, UnknownKeyName=KeyError)
from openpilot.common.swaglog import cloudlog  # noqa: E402
for _level in ("error", "exception", "warning", "info"):
  setattr(cloudlog, _level, lambda *a, **k: None)
from openpilot.tesla import store  # noqa: E402


class CP:
  brand = "tesla"


def sm(v_ego: float, limit: float) -> dict:
  plan = types.SimpleNamespace(speedLimit=types.SimpleNamespace(resolver=types.SimpleNamespace(speedLimit=limit)))
  return {"carState": types.SimpleNamespace(vEgo=v_ego), "longitudinalPlanSP": plan}


def main() -> int:
  ap = argparse.ArgumentParser()
  ap.add_argument("--repo", type=Path, required=True)
  repo = ap.parse_args().repo.expanduser().resolve()
  errors = []

  http.server.SimpleHTTPRequestHandler.log_message = lambda *a: None
  server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), lambda *a, **k: http.server.SimpleHTTPRequestHandler(*a, directory=str(repo), **k))
  threading.Thread(target=server.serve_forever, daemon=True).start()
  base = f"http://127.0.0.1:{server.server_port}"
  index = json.loads((repo / "index.json").read_text())
  for e in index["plugins"]:  # serve the repository's own archives instead of GitHub
    e["url"] = base + "/" + e["url"].split("/main/", 1)[1]
  (TMP / "index.json").write_text(json.dumps(index))
  entries, err = store.fetch_index((TMP / "index.json").as_uri())
  if err or not entries:
    errors.append(f"E1 index: {err}")
  for e in entries:
    if not e.installable or (r := store.install(e)) is not None:
      errors.append(f"E1 {e.id}: installable={e.installable} {r if e.installable else ''}")

  from openpilot.tesla import plugins
  from openpilot.tesla.plugin_params import ParamsView
  ids = {e.id for e in entries}
  found = {c.NAME for c in plugins.PLUGINS} & ids
  if found != ids or ids & set(plugins.LOAD_ERRORS):
    errors.append(f"E2 discovered {found}, load errors {plugins.LOAD_ERRORS}")

  if "overspeed_warning" in found:
    core = CoreParams()
    if plugins.alert_sources(CP, core):
      errors.append("E3 active while switched off")
    view = ParamsView(core, plugins.INSTALLED_SPECS)
    view.put_bool("ExtOverspeedWarning", True)
    view.put("ExtOverspeedMargin", 8)
    sources = plugins.alert_sources(CP, core)
    if len(sources) != 1:
      errors.append(f"E4 sources {sources}")
    else:
      src = sources[0]
      limit = 50 / 3.6
      over = src.update(sm(limit + 10 / 3.6, limit))
      if [a.severity for a in over] != ["warning"] or "10 km/h" not in over[0].title:
        errors.append(f"E4/E6 alert at +10 km/h with margin 8: {over}")
      if src.update(sm(limit + 6 / 3.6, limit)) or src.update(sm(30.0, 0.0)):
        errors.append("E5 alert below margin or without a limit")

  server.shutdown()
  print(json.dumps({"installed": sorted(found), "errors": errors}, indent=1))
  return 1 if errors else 0


if __name__ == "__main__":
  sys.exit(main())
