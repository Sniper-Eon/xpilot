#!/usr/bin/env python3
"""Failure cases: ordinary prompt leaks into restricted GPIO; a permitted
navigation prompt after a suppressed prompt is lost; repeated samples beep;
emergency warnings or MADS on/off are silenced by a plugin. No actual GPIO.
"""
from pathlib import Path
import sys
from unittest.mock import Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from openpilot.sunnypilot.system.alert_output import Beepd, AudibleAlert


def backend():
  b = Beepd.__new__(Beepd)
  b.current_alert = AudibleAlert.none
  b.prompt_suppress_until = 0
  b.mads_enabled = None
  b.dispatch_beep = Mock()
  return b


def main():
  b = backend()
  b.update_alert(AudibleAlert.prompt, prompt_allowed=False)
  b.update_alert(AudibleAlert.promptRepeat, prompt_allowed=False)
  assert not b.dispatch_beep.called
  b.update_alert(AudibleAlert.prompt, prompt_allowed=True)
  b.update_alert(AudibleAlert.prompt, prompt_allowed=True)
  b.dispatch_beep.assert_called_once_with(b.engage)
  for sound in (AudibleAlert.warningSoft, AudibleAlert.warningImmediate):
    b = backend(); b.update_alert(sound, prompt_allowed=False)
    b.dispatch_beep.assert_called_once_with(b.warning)
  b = backend(); b.update_mads(False); b.update_mads(True); b.update_mads(False)
  assert b.dispatch_beep.call_args_list == [((b.engage,),), ((b.disengage,),)]
  from openpilot.tesla import plugins
  assert plugins.buzzer_prompt_allowed([], 'ordinary', 'ordinary')
  p = type('Policy', (), {'allow_prompt': lambda self, title, kind: title == 'allowed'})()
  assert not plugins.buzzer_prompt_allowed([p], 'ordinary', 'ordinary')
  assert plugins.buzzer_prompt_allowed([p], 'allowed', 'ordinary')
  print('{"passed":true,"device_access":false}')


if __name__ == '__main__': main()
