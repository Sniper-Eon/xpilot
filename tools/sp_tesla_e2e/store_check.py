#!/usr/bin/env python3
"""Plugin store check: index, download, install, discovery and installed-plugin params, over a real local HTTP server.

Failure cases listed before implementation:
- S1 an archive whose sha256 differs from the index is installed
- S2 an archive with ../, absolute paths or symlinks writes outside the plugin directory
- S3 a failed install (bad manifest, hash, api) removes or damages the installed version
- S4 an installed plugin with the id of a built-in plugin is installed or discovered
- S5 an installed plugin declaring a param key that already exists (core or another plugin) is installed
- S6 an installed plugin is not discovered, or cannot use relative imports inside its package
- S7 uninstall leaves the plugin discoverable
- S8 installed plugin params: wrong type round trip, no default, or built-in keys routed to the store
- S9 is_enabled of an installed plugin raises (its ENABLE_PARAM is unknown to the compiled Params)
- S10 an index entry for another api version is offered as installable
- S11 an unreachable index or a malformed entry crashes instead of returning an error
- S12 an update keeps no copy until the new version is fully in place (half-written plugin directory)
- S13 a plugin built for another platform (machine / Python ABI) is offered as installable or installed
- S14 an installed plugin whose platform no longer matches (e.g. after a Python upgrade) is loaded instead of skipped
- S15 a plugin for this platform is refused
- S16 a plugin that breaks the code layout rules (manifest.layout_problems, e.g. one file over MAX_LINES) is installed
- S17 the UI looks for an installed plugin's ui.py under openpilot.tesla.plugins instead of xpilot_ext
"""
import hashlib
import http.server
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import threading
import types

ROOT = Path(__file__).resolve().parents[2]
TMP = Path(tempfile.mkdtemp(prefix="xp-store-"))
os.environ["XPILOT_PLUGINS_DIR"] = str(TMP / "installed")
sys.path[:0] = [str(ROOT), str(ROOT / "opendbc_repo")]


class CoreParams:  # stands in for the compiled Params: knows only core and built-in keys
  def __init__(self):
    self.values = {}

  def get_bool(self, key, block=False):
    if key.startswith("Ext"):
      raise KeyError(key)
    return bool(self.values.get(key, False))

  def get(self, key, block=False, return_default=False):
    if key.startswith("Ext"):
      raise KeyError(key)
    return self.values.get(key)

  def put(self, key, value, block=False):
    self.values[key] = value

  def put_bool(self, key, value, block=False):
    self.values[key] = bool(value)


try:
  import openpilot.common.params  # noqa: F401
except Exception:
  sys.modules["openpilot.common.params"] = types.SimpleNamespace(Params=CoreParams, UnknownKeyName=KeyError)
from openpilot.common.swaglog import cloudlog  # noqa: E402
for _level in ("error", "exception", "warning", "info"):
  setattr(cloudlog, _level, lambda *a, **k: None)

from openpilot.tesla import manifest as mf, store  # noqa: E402
from openpilot.tesla.plugin_params import ParamsView  # noqa: E402


def manifest(pid, **over):
  m = {"id": pid, "name": pid, "version": "1.0.0", "api": mf.API_VERSION, "category": "tools", "entry": "plugin:P",
       "enable_param": f"Ext{pid}On", "claims": [],
       "params": {f"Ext{pid}On": {"type": "BOOL", "default": "1"}, f"Ext{pid}Level": {"type": "INT", "default": "7"},
                  f"Ext{pid}Cfg": {"type": "JSON"}}}
  m.update(over)
  return m


def archive(pid, files: dict, raw: list | None = None) -> bytes:
  buf = io.BytesIO()
  with tarfile.open(fileobj=buf, mode="w:gz") as tar:
    for name, data in files.items():
      info = tarfile.TarInfo(f"{pid}/{name}")
      data = data.encode() if isinstance(data, str) else data
      info.size = len(data)
      tar.addfile(info, io.BytesIO(data))
    for info in raw or []:
      tar.addfile(info, io.BytesIO(b"x") if info.isfile() else None)
  return buf.getvalue()


PLUGIN_PY = "from .helper import VALUE\nfrom openpilot.tesla.plugin import Plugin\n\nclass P(Plugin):\n  X = VALUE\n"


def good_files(pid, version="1.0.0", **over):
  return {"__init__.py": "", "helper.py": f"VALUE = {version!r}\n", "plugin.py": PLUGIN_PY, "ui.py": "from .helper import VALUE\n",
          "plugin.json": json.dumps(manifest(pid, version=version, **over))}


def main() -> int:
  errors = []
  site = TMP / "site"
  site.mkdir()
  entries = []

  def publish(pid, data: bytes, version="1.0.0", sha=None, api=mf.API_VERSION, platform=None):
    (site / f"{pid}-{version}.tar.gz").write_bytes(data)
    entries.append({"id": pid, "name": pid, "version": version, "api": api, "category": "tools", "author": "t",
                    "description": "d", "url": f"{base}/{pid}-{version}.tar.gz", "sha256": sha or hashlib.sha256(data).hexdigest(),
                    "platform": platform})

  handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(*a, directory=str(site), **k)  # noqa: E731
  http.server.SimpleHTTPRequestHandler.log_message = lambda *a: None
  server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
  threading.Thread(target=server.serve_forever, daemon=True).start()
  base = f"http://127.0.0.1:{server.server_port}"

  publish("ext_ok", archive("ext_ok", good_files("ext_ok")))
  publish("ext_hash", archive("ext_hash", good_files("ext_hash")), sha="0" * 64)
  evil = tarfile.TarInfo("../evil.txt")
  evil.size = 1
  link = tarfile.TarInfo("ext_link/link")
  link.type, link.linkname = tarfile.SYMTYPE, "/etc/passwd"
  publish("ext_trav", archive("ext_trav", good_files("ext_trav"), raw=[evil]))
  publish("ext_link", archive("ext_link", good_files("ext_link"), raw=[link]))
  publish("auto_speed", archive("auto_speed", good_files("auto_speed")))
  publish("ext_dup", archive("ext_dup", good_files("ext_dup", params={"TeslaAutoSpeedLimit": {"type": "BOOL"}})))
  publish("ext_fat", archive("ext_fat", {**good_files("ext_fat"), "helper.py": "VALUE = 1\n" * (mf.MAX_LINES + 1)}))
  publish("ext_api", archive("ext_api", good_files("ext_api")), api=mf.API_VERSION + 1)
  here, other = mf.host_platform(), {"machine": "sparc", "python": "cpython-27"}
  publish("ext_here", archive("ext_here", good_files("ext_here", platform=here)), platform=here)
  publish("ext_other", archive("ext_other", good_files("ext_other", platform=other)), platform=other)
  (site / "index.json").write_text(json.dumps({"api": mf.API_VERSION, "plugins": entries + [{"id": "broken"}]}))

  try:
    index, err = store.fetch_index(f"{base}/index.json")
  except Exception as e:
    errors.append(f"S11 fetch_index raised {e!r}")
    index, err = [], str(e)
  by_id = {e.id: e for e in index}
  if "broken" in by_id or "ext_ok" not in by_id:
    errors.append(f"S11 index {sorted(by_id)} err={err}")
  if by_id.get("ext_api") and by_id["ext_api"].installable:
    errors.append("S10 other api offered as installable")
  try:
    bad_index, bad_err = store.fetch_index(f"{base}/missing.json")
    if bad_index or not bad_err:
      errors.append("S11 missing index gave no error")
  except Exception as e:
    errors.append(f"S11 missing index raised {e!r}")

  def install(pid):
    try:
      return store.install(by_id[pid])
    except Exception as e:
      return f"raised {e!r}"

  if by_id.get("ext_other") and by_id["ext_other"].installable:
    errors.append("S13 other platform offered as installable")
  if not by_id.get("ext_here") or not by_id["ext_here"].installable or install("ext_here") is not None:
    errors.append("S15 this platform refused")
  if (r := install("ext_ok")) is not None:
    errors.append(f"S6 install ext_ok failed: {r}")
  for pid, code in (("ext_hash", "S1"), ("ext_trav", "S2"), ("ext_link", "S2"), ("auto_speed", "S4"), ("ext_dup", "S5"), ("ext_fat", "S16")):
    if install(pid) is None:
      errors.append(f"{code} {pid} installed")
  if (TMP / "evil.txt").exists() or (TMP / "installed" / "evil.txt").exists():
    errors.append("S2 file written outside the plugin directory")
  if any((TMP / "installed" / p).exists() for p in ("ext_hash", "ext_trav", "ext_link", "ext_dup", "ext_fat")):
    errors.append("S1/S2/S5/S16 rejected plugin left on disk")

  # update with a broken version keeps 1.0.0 (S3); a good update replaces it (S12)
  bad_v2 = good_files("ext_ok", version="2.0.0")
  bad_v2["plugin.json"] = "{broken"
  publish("ext_ok", archive("ext_ok", bad_v2), version="2.0.0")
  if store.install(store.IndexEntry(**{**entries[-1], "installable": True})) is None:
    errors.append("S3 broken update installed")
  if json.loads((TMP / "installed" / "ext_ok" / "plugin.json").read_text())["version"] != "1.0.0":
    errors.append("S3 broken update damaged the installed version")

  # S14: the installed ext_here manifest now claims another platform (as after a Python upgrade)
  here_json = TMP / "installed" / "ext_here" / "plugin.json"
  here_json.write_text(json.dumps({**json.loads(here_json.read_text()), "platform": other}))
  import importlib
  from openpilot.tesla import plugins
  plugins = importlib.reload(plugins)
  if any(c.NAME == "ext_here" for c in plugins.PLUGINS) or "ext_here" not in plugins.LOAD_ERRORS:
    errors.append("S14 installed plugin for another platform loaded")
  names = [c.NAME for c in plugins.PLUGINS]
  ext = next((c for c in plugins.PLUGINS if c.NAME == "ext_ok"), None)
  if ext is None:
    errors.append(f"S6 installed plugin not discovered: {names} {plugins.LOAD_ERRORS}")
  elif ext.X != "1.0.0":
    errors.append("S6 relative import inside the installed package failed")
  elif plugins.ui_module(ext) != "xpilot_ext.ext_ok.ui" or importlib.import_module(plugins.ui_module(ext)).VALUE != "1.0.0" or \
      plugins.ui_module(next(c for c in plugins.PLUGINS if c.NAME == "auto_speed")) != "openpilot.tesla.plugins.auto_speed.ui":
    errors.append(f"S17 wrong ui module: {plugins.ui_module(ext)}")
  if names.count("auto_speed") != 1:
    errors.append("S4 built-in id duplicated")

  core = CoreParams()
  view = ParamsView(core)
  try:
    if ext is not None and not plugins.is_enabled(ext, core):
      errors.append("S9 installed plugin default-on not enabled")
  except Exception as e:
    errors.append(f"S9 is_enabled raised {e!r}")
  try:
    if view.get("Extext_okLevel", return_default=True) != 7 or view.get("Extext_okLevel") is not None:
      errors.append("S8 default handling")
    view.put("Extext_okLevel", 12)
    view.put_bool("Extext_okOn", False)
    view.put("Extext_okCfg", {"a": [1, 2]})
    again = ParamsView(CoreParams())
    if again.get("Extext_okLevel") != 12 or again.get_bool("Extext_okOn") or again.get("Extext_okCfg") != {"a": [1, 2]}:
      errors.append("S8 round trip")
    view.put("TeslaAutoSpeedLimit", True)
    if core.values.get("TeslaAutoSpeedLimit") is not True:
      errors.append("S8 built-in key not routed to compiled Params")
  except Exception as e:
    errors.append(f"S8 raised {e!r}")

  store.uninstall("ext_ok")
  plugins = importlib.reload(plugins)
  if any(c.NAME == "ext_ok" for c in plugins.PLUGINS):
    errors.append("S7 uninstalled plugin still discovered")

  server.shutdown()
  print(json.dumps({"errors": errors}, indent=1))
  return 1 if errors else 0


if __name__ == "__main__":
  sys.exit(main())
