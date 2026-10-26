"""Optional language-pack owner. All locale resources belong to the plugin."""
import inspect
from pathlib import Path
from string import Formatter


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
