#!/usr/bin/env python3
"""Enable/disable, fault, glyph and base-locale contracts; no window or vehicle IO."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace as N

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def font_merge_contract(source):
  """Failures: absent base catalog crashes; either provider's glyphs/font are
  lost by a merge; changing a role-owned font reuses the previous font cache.
  Execute the actual drawing helper with mock GPU calls, no Params/vehicle IO.
  """
  import ast
  from contextlib import nullcontext
  import tempfile
  tree=ast.parse(source)
  cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='GuiApplication')
  method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='fallback_font')
  calls=[]
  def load(path,size,points,count):
    calls.append((str(path),set(points)))
    return N(texture=None)
  locale=N(language='zh-CHS',extra_glyphs='界',font_override='/plugin/bridge.otf',
           ui_font_path=Path('/plugin/role.ttf'),_translations={'x':'图'})
  rl=N(Font=object,ffi=N(new=lambda kind,points:points,cast=lambda kind,p:p),
       load_font_ex=load,gen_texture_mipmaps=lambda t:None,set_texture_filter=lambda *a:None,
       TextureFilter=N(TEXTURE_FILTER_TRILINEAR=1))
  with tempfile.TemporaryDirectory() as tmp:
    ns=dict(rl=rl,multilang=locale,TRANSLATIONS_DIR=Path(tmp),FONT_DIR=Path(tmp),
            as_file=nullcontext,NOTO_FONTS={'zh-CHS':'base.otf'},EXTRA_FONT_CHARS='')
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),'<actual fallback_font>','exec'),ns)
    host=N(_fallback_fonts={},_plugin_font_chars={'字'})
    ns['fallback_font'](host)
    assert calls[-1][0]=='/plugin/bridge.otf'
    assert set(map(ord,'界图字'))<=calls[-1][1]
    locale.font_override=None
    ns['fallback_font'](host)
    assert calls[-1][0]=='/plugin/role.ttf'
    locale.ui_font_path=Path('/plugin/changed.ttf')
    ns['fallback_font'](host)
    assert calls[-1][0]=='/plugin/changed.ttf'


def main():
  font_merge_contract((ROOT / "openpilot/system/ui/lib/application.py").read_text())
  from openpilot.system.ui.lib.multilang import Multilang
  from openpilot.tesla.ui.localization import TranslationBridge
  clock, enabled, faults = [0.], [True], []

  class Provider:
    plugin_name, language, glyphs = 'test_locale', 'zh-CHS', '\u5f00\u5173\u7ecf\u6d4e'
    def translate(self, text):
      return {'Off': '\u5173', 'Eco': '\u7ecf\u6d4e'}.get(text)

  provider = Provider()
  locale = Multilang()
  locale._translations = {'Off': 'base off'}
  original_language = locale._language
  bridge = TranslationBridge(lambda p: {'test_locale'} if enabled[0] else set(),
      lambda p: [provider], lambda *args: faults.append(args), clock=lambda: clock[0])
  bridge.refresh(None, locale)
  assert locale.tr('Off') == '\u5173' and locale.tr('Eco') == '\u7ecf\u6d4e'
  assert locale.tr('ExtNavAssistEnabled') == 'ExtNavAssistEnabled'
  assert locale.tr('192.168.5.182') == '192.168.5.182'
  assert locale.language == 'zh-CHS' and locale.requires_font_fallback()
  assert '\u7ecf' in locale.extra_glyphs and locale._language == original_language
  first = locale.generation
  clock[0] = .5
  bridge.refresh(None, locale)
  assert locale.generation == first
  enabled[0], clock[0] = False, 1.1
  bridge.refresh(None, locale)
  assert locale.tr('Off') == 'base off' and locale.tr('Eco') == 'Eco'
  assert locale.language == original_language and not locale.extra_glyphs
  assert locale.generation > first
  enabled[0], clock[0] = True, 2.2
  bridge.refresh(None, locale)
  provider.translate = lambda text: 123  # invalid output is a fault, not a coerced label
  assert locale.tr('Off') == 'base off'
  assert faults and not locale.extra_glyphs
  print(json.dumps(dict(passed=True, contracts=8)))


if __name__ == '__main__':
  main()
