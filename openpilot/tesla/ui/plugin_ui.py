"""UI side of plugins: finds Slot and HudOverlay classes in openpilot/tesla/ui/slots/ and in each plugin's ui.py,
and hides a plugin's widgets while the plugin is switched off (Plugins page). A module that fails to import is
logged and skipped, so a broken plugin UI never takes the UI down."""
import importlib
import inspect
import pkgutil
import time

from openpilot.common.swaglog import cloudlog
from openpilot.system.ui.widgets import Widget
from openpilot.tesla.plugins import PLUGINS, is_enabled

MAX_FAILURES = 3  # a widget that raises this many times in a row is not drawn again


class HudOverlay(Widget):
  """Drawn over the mici onroad HUD. Subclass in a plugin's ui.py; must construct with no arguments."""

  def update(self) -> None:
    """Every frame before render(); read ui_state.sm here."""


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
          if issubclass(cls, base) and cls is not base and cls.__module__ == mod.__name__ and (base is HudOverlay or hasattr(cls, "SPEC"))]


def load(base) -> list[tuple[str | None, Widget]]:
  """(plugin NAME or None for core slots, widget instance) for every class deriving from base."""
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
  """Names of switched-on plugins, re-read from Params at most once a second."""

  def __init__(self, params):
    self._params, self._names, self._t = params, set(), -1.0

  def get(self) -> set[str]:
    now = time.monotonic()
    if now - self._t >= 1.0:
      self._t = now
      self._names = {p.NAME for p in PLUGINS if is_enabled(p, self._params)}
    return self._names

  def shows(self, name: str | None) -> bool:
    return name is None or name in self.get()
