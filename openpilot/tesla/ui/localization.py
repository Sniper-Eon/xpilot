"""Optional UI-only translation provider; polling, failover and cache invalidation are host-owned."""
import time
import inspect
from pathlib import Path


class TranslationBridge:
  def __init__(self, active, collect, fault, clock=time.monotonic):
    self.active, self.collect, self.fault, self.clock = active, collect, fault, clock
    self._next, self._names, self._providers, self._locale = -1., None, [], None
    self._failed = set()
    self._font_paths = {}

  def refresh(self, params, locale):
    now = self.clock()
    if now < self._next:
      return
    self._next = now + 1.
    names = self.active(params)
    if names == self._names:
      return
    self._names, self._locale, self._providers = names, locale, []
    for provider in self.collect(params) if names else []:
      name = getattr(provider, 'plugin_name', '?')
      if name in self._failed:
        continue
      try:
        if provider.language not in locale.codes or not callable(provider.translate):
          raise ValueError('invalid translation provider')
        if not isinstance(provider.glyphs, str) or len(provider.glyphs) > 8192:
          raise ValueError('invalid translation glyphs')
        self._font_paths[id(provider)] = self._font(provider)
        self._providers.append(provider)
      except Exception as exc:
        self._failed.add(name)
        self.fault(name, 'ui.translation.init', exc)
    self._install()

  def _install(self):
    p = self._providers[0] if self._providers else None
    self._locale.set_plugin_translator(self.translate if p else None, p.language if p else None,
                                      p.glyphs if p else '', self._font_paths.get(id(p)) if p else None)

  @staticmethod
  def _font(provider):
    font = getattr(provider, 'font_path', None)
    if font is None:
      return None
    root = Path(inspect.getfile(type(provider))).resolve().parent
    path = Path(font).resolve()
    if not path.is_relative_to(root) or path.suffix.lower() not in ('.otf', '.ttf'):
      raise ValueError('font must belong to the translation provider')
    if not path.is_file() or not 0 < path.stat().st_size <= 20 * 1024 * 1024:
      raise ValueError('missing or oversized font')
    with path.open('rb') as stream:
      if stream.read(4) not in (b'OTTO', b'\x00\x01\x00\x00'):
        raise ValueError('invalid font header')
    return str(path)

  def translate(self, text):
    for provider in list(self._providers):
      try:
        result = provider.translate(text)
        if result is not None and (not isinstance(result, str) or len(result) > 32768):
          raise ValueError('translation must be bounded text or None')
        if result:
          return result
      except Exception as exc:
        self._providers.remove(provider)
        name = getattr(provider, 'plugin_name', '?')
        self._failed.add(name)
        self.fault(name, 'ui.translation.translate', exc)
        self._install()
    return None


def _active(params):
  from openpilot.tesla import plugins
  return {p.NAME for p in plugins.active(params) if 'source:ui.translations' in p.CLAIMS}


def _collect(params):
  from openpilot.tesla import plugins
  return plugins.ui_translations(params)


def _fault(*args):
  from openpilot.tesla.plugins import record_fault
  record_fault(*args)


_bridge = TranslationBridge(_active, _collect, _fault)


def refresh(params):
  from openpilot.system.ui.lib.multilang import multilang
  _bridge.refresh(params, multilang)
