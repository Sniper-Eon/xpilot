"""Plugin store client: read the plugin repository index, install, update and remove downloaded plugins.

Repository (https://github.com/onemiless/xpilot-plugins): plugins/<id>/ sources, dist/<id>-<version>.tar.gz built
reproducibly by its tools/build_index.py, and index.json:
  {"api": 1, "plugins": [{"id", "name", "version", "api", "category", "author", "description", "url", "sha256"}]}
Third parties send pull requests; the maintainer reviews and merges. Archives are not signed (yet): the sha256 only
guards against corrupt or swapped downloads, trust comes from the reviewed repository.

Install: download (size-capped), check sha256, extract regular files only into a staging directory next to the
target, validate the manifest (id, api, entry module, no built-in id, no clashing or unsupported param keys), then
swap it into INSTALL_DIR/<id> with renames. Any failure leaves the installed version as it was. Changes apply after
a restart (plugins are discovered at process start). Call only while offroad.
"""
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import tempfile
import urllib.request

from openpilot.tesla import manifest as mf
from openpilot.tesla.plugin_params import STORE_TYPES

INDEX_URL = "https://raw.githubusercontent.com/onemiless/xpilot-plugins/main/index.json"
MAX_ARCHIVE = 20 * 1024 * 1024
TIMEOUT_S = 15


@dataclass(frozen=True)
class IndexEntry:
  id: str
  name: str
  version: str
  api: int
  category: str
  author: str
  description: str
  url: str
  sha256: str
  platform: dict | None = None  # None: pure Python; else must equal manifest.host_platform()
  installable: bool = False  # api and platform match this host and the id is not a built-in plugin


def _get(url: str, limit: int) -> bytes:
  with urllib.request.urlopen(url, timeout=TIMEOUT_S) as r:  # noqa: S310 (https URLs from the index)
    data = r.read(limit + 1)
  if len(data) > limit:
    raise ValueError(f"download over {limit} bytes")
  return data


def builtin_ids() -> set[str]:
  return {p.parent.name for p in mf.PLUGINS_DIR.glob("*/plugin.json")}


def fetch_index(url: str = INDEX_URL) -> tuple[list[IndexEntry], str | None]:
  """(entries, error). Malformed entries are skipped; an unreachable or broken index returns ([], reason)."""
  try:
    doc = json.loads(_get(url, 2 * 1024 * 1024))
  except Exception as e:
    return [], f"index: {e}"
  entries, builtin = [], builtin_ids()
  for raw in doc.get("plugins", []) if isinstance(doc, dict) else []:
    try:
      e = IndexEntry(**{f: raw[f] for f in ("id", "name", "version", "api", "category", "author", "description", "url", "sha256")},
                     platform=raw.get("platform"))
    except (KeyError, TypeError):
      continue
    ok = e.api == mf.API_VERSION and e.id not in builtin and mf.platform_ok(e.platform)
    entries.append(IndexEntry(**{**e.__dict__, "installable": ok}))
  return entries, None


def installed_versions() -> dict[str, str]:
  return {m.id: m.version for m in mf.load_all(mf.INSTALL_DIR)[0]}


def _extract(data: bytes, pid: str, dest: Path) -> None:
  """Regular files and directories under <pid>/ only; anything else (links, devices, ../, absolute) is refused."""
  with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
    for member in tar.getmembers():
      path = PurePosixPath(member.name)
      if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != pid:
        raise ValueError(f"unsafe path {member.name!r}")
      if not (member.isfile() or member.isdir()):
        raise ValueError(f"not a regular file: {member.name!r}")
      target = dest.joinpath(*path.parts[1:])
      if member.isdir():
        target.mkdir(parents=True, exist_ok=True)
        continue
      target.parent.mkdir(parents=True, exist_ok=True)
      src = tar.extractfile(member)
      target.write_bytes(src.read() if src else b"")


def _validate(staged: Path, entry: IndexEntry) -> None:
  m = mf.parse(staged / "plugin.json")  # id == directory name, api, category, entry, claims
  if m.id != entry.id:
    raise ValueError(f"manifest id {m.id!r} != index id {entry.id!r}")
  if m.id in builtin_ids():
    raise ValueError("id used by a built-in plugin")
  if not mf.platform_ok(m.platform):
    raise ValueError(f"built for {m.platform}, this device is {mf.host_platform()}")
  module = m.entry.split(":")[0]
  for f in ("__init__.py", f"{module}.py"):
    if not (staged / f).is_file():
      raise ValueError(f"missing {f}")
  taken = mf.compiled_param_keys() | {k for o in mf.load_all(mf.INSTALL_DIR)[0] if o.id != m.id for k in o.params}
  for key, spec in m.params.items():
    if key in taken:
      raise ValueError(f"param {key} already exists")
    if not key.isidentifier() or spec.get("type") not in STORE_TYPES:
      raise ValueError(f"param {key}: unsupported type {spec.get('type')!r}")


def install(entry: IndexEntry) -> str | None:
  """None on success, else the reason. The previous version stays in place on any failure."""
  if not entry.installable:
    return f"not installable (api {entry.api} vs {mf.API_VERSION}, platform {entry.platform}, or a built-in id)"
  mf.INSTALL_DIR.mkdir(parents=True, exist_ok=True)
  staging = Path(tempfile.mkdtemp(prefix=f".staging-{entry.id}-", dir=mf.INSTALL_DIR))
  try:
    data = _get(entry.url, MAX_ARCHIVE)
    if hashlib.sha256(data).hexdigest() != entry.sha256.lower():
      raise ValueError("sha256 mismatch")
    staged = staging / entry.id
    staged.mkdir()
    _extract(data, entry.id, staged)
    _validate(staged, entry)
    target, old = mf.INSTALL_DIR / entry.id, staging / "old"
    if target.exists():
      os.replace(target, old)
    os.replace(staged, target)
    return None
  except Exception as e:
    return str(e) or repr(e)
  finally:
    shutil.rmtree(staging, ignore_errors=True)


def uninstall(pid: str) -> None:
  """Remove an installed plugin (its stored param values stay, so a reinstall keeps its settings)."""
  target = mf.INSTALL_DIR / pid
  if pid and "/" not in pid and target.is_dir():
    trash = Path(tempfile.mkdtemp(prefix=f".removing-{pid}-", dir=mf.INSTALL_DIR))
    os.replace(target, trash / pid)
    shutil.rmtree(trash, ignore_errors=True)
