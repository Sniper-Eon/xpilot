"""UI side of plugins: finds Tile, HudOverlay and ScreenOverlay classes in openpilot/tesla/ui/slots/ and in each plugin's ui.py,
and hides a plugin's widgets while the plugin is switched off (Plugins page). A module that fails to import is
logged and skipped, so a broken plugin UI never takes the UI down."""
import importlib
import inspect
import pkgutil
import time

from openpilot.common.swaglog import cloudlog
from openpilot.system.ui.widgets import Widget
from openpilot.tesla.plugins import PLUGINS, resolve

MAX_FAILURES = 3  # a widget that raises this many times in a row is not drawn again


class HudOverlay(Widget):
  """Drawn over the mici onroad HUD. Subclass in a plugin's ui.py; must construct with no arguments."""

  def update(self) -> None:
    """Every frame before render(); read ui_state.sm here."""


class ScreenOverlay:
  """Drawn by the big-screen host onroad, after its tiles, in screen px. Subclass in a plugin's ui.py; must construct with no arguments."""

  def update(self, sm) -> None:
    """Every frame before draw(); sm is ui_state.sm."""

  def draw(self, zones: dict) -> None:
    """zones: "left", "right", "top", "bottom" (strips around the view) and "view" (the mici view) as rl.Rectangle."""


def _classes(module_name: str, base) -> list:
  try:
    mod = importlib.import_module(module_name)
  except ModuleNotFoundError as e:
    if e.name != module_name:
      cloudlog.exception(f"ui module {module_name} failed to load")
    return []
  except Exception:
    cloudlog.exception(f"ui module {module_name} failed to load")
    return []
  return [cls for _, cls in inspect.getmembers(mod, inspect.isclass)
          if issubclass(cls, base) and cls is not base and cls.__module__ == mod.__name__ and (base in (HudOverlay, ScreenOverlay) or hasattr(cls, "SPEC"))]


def load(base) -> list[tuple[str | None, object]]:
  """(plugin NAME or None for core tiles, widget instance) for every class deriving from base."""
  from openpilot.tesla.ui import slots as slots_pkg
  found: list[tuple[str | None, type]] = []
  for info in pkgutil.iter_modules(slots_pkg.__path__):
    found += [(None, cls) for cls in _classes(f"{slots_pkg.__name__}.{info.name}", base)]
  for plugin in PLUGINS:
    found += [(plugin.NAME, cls) for cls in _classes(f"openpilot.tesla.plugins.{plugin.NAME}.ui", base)]
  out = []
  for name, cls in found:
    try:
      out.append((name, cls()))
    except Exception:
      cloudlog.exception(f"ui widget {cls.__name__} failed to construct")
  return out


class EnabledPlugins:
  """Names of active plugins (switched on and winning their claims), re-read from Params at most once a second."""

  def __init__(self, params):
    self._params, self._names, self._t = params, set(), -1.0

  def get(self) -> set[str]:
    now = time.monotonic()
    if now - self._t >= 1.0:
      self._t = now
      self._names = resolve(self._params)[0]
    return self._names

  def shows(self, name: str | None) -> bool:
    return name is None or name in self.get()


class Overlays:
  """Every widget deriving from base; each() skips a widget while its plugin is off, and for good once it raised
  MAX_FAILURES times in a row, so a broken plugin overlay never takes the UI down."""

  def __init__(self, base, params):
    self._entries = [[name, w, 0] for name, w in load(base)]
    self._enabled = EnabledPlugins(params)

  def each(self, fn) -> None:
    for entry in self._entries:
      name, widget, failures = entry
      if failures >= MAX_FAILURES or not self._enabled.shows(name):
        continue
      try:
        fn(widget)
        entry[2] = 0
      except Exception:
        entry[2] += 1
        cloudlog.exception(f"overlay {type(widget).__name__} failed")
