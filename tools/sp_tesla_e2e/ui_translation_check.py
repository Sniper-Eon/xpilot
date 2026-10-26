#!/usr/bin/env python3
"""Enable/disable, fault, glyph and base-locale contracts; no window or vehicle IO."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace as N

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main():
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
