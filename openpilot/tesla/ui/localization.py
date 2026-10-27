"""Optional UI-only translation provider; polling, failover and cache invalidation are host-owned."""
import time
import inspect
from pathlib import Path
from string import Formatter


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


def _fields(text):
  return sorted((name, spec, conversion) for _, name, spec, conversion in Formatter().parse(text) if name is not None)


def extra_glyphs(params):
  from openpilot.tesla.plugins import active, record_fault
  chars = set()
  for plugin in active(params):
    if 'ui.glyphs' not in plugin.CLAIMS:
      continue
    try:
      text = plugin.ui_glyphs()
      if not isinstance(text, str) or len(text) > 16384:
        raise ValueError('invalid extra glyph text')
      addition = {c for c in text if c.isprintable()}
      if len(chars | addition) > 4096:
        raise ValueError('extra glyph budget exceeded')
      chars.update(addition)
    except Exception as exc:
      record_fault(plugin.NAME, 'ui_glyphs', exc)
  return chars


def configure(multilang, params, plugins=None):
  from openpilot.tesla.plugins import PLUGINS, record_fault, resolve
  active, _ = resolve(params)
  for plugin in PLUGINS if plugins is None else plugins:
    if plugin.NAME not in active or 'role:ui.language' not in plugin.CLAIMS:
      continue
    try:
      pack = plugin.ui_language()
      if not isinstance(pack, dict) or pack.get('code') not in ('zh-CHS', 'zh-CHT', 'ja', 'ko', 'th'):
        raise ValueError('unsupported language pack')
      font = Path(pack['font']).resolve()
      root = Path(inspect.getfile(plugin)).resolve().parent
      if not font.is_relative_to(root) or not font.is_file() or font.suffix not in ('.otf', '.ttf'):
        raise ValueError('font must be bundled inside the language plugin')
      with font.open('rb') as f:
        if f.read(4) not in (b'OTTO', b'\x00\x01\x00\x00'):
          raise ValueError('invalid font header')
      translations = pack['translations']
      if not isinstance(translations, dict) or len(translations) > 10000:
        raise ValueError('invalid translation catalog')
      for source, translated in translations.items():
        if not isinstance(source, str) or not isinstance(translated, str) or not translated or _fields(source) != _fields(translated):
          raise ValueError('translation format fields differ')
      multilang._language = pack['code']
      multilang._translations = {**multilang._translations, **translations}
      multilang.ui_font_path = font
      return
    except Exception as exc:
      record_fault(plugin.NAME, 'ui_language', exc)
      return
