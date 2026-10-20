#!/usr/bin/env python3
"""Process table: candidate process_config vs official and the previous fork. Plain python3, stubbed imports.

Failure cases listed before moving the fork changes out of process_config.py:
- P1 a fork-only process gate is lost (DM switch, C3XL microphone/amplifier) or applied to another process
- P2 trafficcontrold or alert_output disappears or runs on the wrong hardware
- P3 an official process is dropped or changed (webrtcd, copyparty and logging must follow official)
- P4 a fork crash-restart flag returns (official has none)
Every scenario compares which processes would run for started/notCar/DM/audio/profile combinations.
"""
import argparse
import importlib.util
import itertools
import json
import os
import subprocess
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = 'openpilot/system/manager/process_config.py'
FORK_ONLY = {'trafficcontrold', 'alert_output'}
OFFICIAL_ONLY_BEFORE = {'webrtcd', 'copyparty-sfx'}  # removed by the previous fork, official again now
S = {}  # scenario switches read by the stubs


class Params:
  def __init__(self, *a):
    pass

  def get_bool(self, k, block=False):
    return k in ('IsLiveStreaming', 'EnableSunnylinkUploader', 'EnableCopyparty', 'LoggingEnabled')

  def get(self, k, block=False, return_default=False):
    return self.get_bool(k)


class Proc:
  def __init__(self, name, _module, should_run=None, enabled=True, **kw):
    self.name, self.should_run, self.enabled = name, should_run, enabled
    self.restart_if_crash = kw.get('restart_if_crash', False)


class Native(Proc):
  def __init__(self, name, cwd, cmdline, should_run, enabled=True, **kw):
    super().__init__(name, cwd, should_run, enabled, **kw)


class Daemon(Proc):
  def __init__(self, name, module, param_name, enabled=True):
    super().__init__(name, module, lambda *a: True, enabled)


def stub(name, **attrs):
  mod = types.ModuleType(name)
  mod.__path__ = []
  mod.__dict__.update(attrs)
  sys.modules[name] = mod


def load(name, source):
  mod = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
  sys.modules[name] = mod
  mod.__file__ = str(ROOT / CONFIG)  # official copyparty block derives its root from __file__
  exec(compile(source, name, 'exec'), mod.__dict__)
  return mod


def install_stubs():
  runner = types.SimpleNamespace(stock='stock', tinygrad='tinygrad')
  for n in ('opendbc', 'opendbc.car', 'openpilot', 'openpilot.common', 'openpilot.system', 'openpilot.system.manager',
            'openpilot.sunnypilot', 'openpilot.sunnypilot.mapd', 'openpilot.sunnypilot.models', 'openpilot.sunnypilot.hardware',
            'openpilot.sunnypilot.sunnylink', 'openpilot.sunnypilot.system'):
    stub(n)
  stub('opendbc.car.structs', car=types.SimpleNamespace(CarParams=object))
  stub('openpilot.cereal', custom=types.SimpleNamespace(ModelManagerSP=types.SimpleNamespace(Runner=runner)))
  stub('openpilot.common.params', Params=Params)
  stub('openpilot.common.hardware', PC=False, COMMA_HARDWARE=True)
  stub('openpilot.common.hardware.hw', Paths=types.SimpleNamespace(mapd_root=lambda: '/nonexistent/mapd', crash_log_root=lambda: '/c',
                                                                   log_root=lambda: '/l', model_root=lambda: '/m'))
  stub('openpilot.system.manager.process', PythonProcess=Proc, NativeProcess=Native, DaemonProcess=Daemon)
  stub('openpilot.sunnypilot.mapd.mapd_manager', MAPD_PATH='/nonexistent/mapd')
  stub('openpilot.sunnypilot.models.helpers', get_active_model_runner=lambda params, offroad: 'stock')
  stub('openpilot.sunnypilot.hardware.driver_monitoring', driver_monitoring_enabled=lambda p: S['dm'])
  stub('openpilot.sunnypilot.hardware.profile', has_audio_output=lambda: S['audio'], has_microphone=lambda: S['mic'],
       HardwareProfile=types.SimpleNamespace(C3XL='c3xl'), get_hardware_profile=lambda: S['profile'])
  stub('openpilot.sunnypilot.sunnylink.utils', sunnylink_need_register=lambda p: False, sunnylink_ready=lambda p: True,
       use_sunnylink_uploader=lambda p: True)
  fork = ROOT / 'openpilot/sunnypilot/system/fork_processes.py'
  if fork.exists():
    load('openpilot.sunnypilot.system.fork_processes', fork.read_text())


def table(mod, started, not_car):
  cp = types.SimpleNamespace(notCar=not_car)
  return {p.name for p in mod.procs if p.enabled and p.should_run(started, Params(), cp)}


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--official', default='sunnypilot/master')
  parser.add_argument('--previous', default='HEAD')
  parser.add_argument('--output', type=Path)
  args = parser.parse_args()
  sys.path.insert(0, str(ROOT))
  install_stubs()
  os.chdir(ROOT / 'openpilot/system/manager')  # copyparty/uploader existence checks are cwd-relative, as on device
  show = lambda ref: subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{ref}:{CONFIG}'], text=True)  # noqa: E731
  official, previous = load('pc_official', show(args.official)), load('pc_previous', show(args.previous))
  candidate = load('pc_candidate', (ROOT / CONFIG).read_text())

  failures, scenarios = [], 0
  for started, not_car, dm, audio, mic, profile in itertools.product((False, True), (False, True), (False, True), (False, True),
                                                                     (False, True), ('c3', 'c3xl')):
    S.update(dm=dm, audio=audio, mic=mic, profile=profile)
    off, prev, cand = (table(m, started, not_car) for m in (official, previous, candidate))
    scenarios += 1
    expected = set(off)
    for name in ('dmonitoringmodeld', 'dmonitoringd'):
      if not dm:
        expected.discard(name)
    if not mic:
      expected.discard('micd')
    if not audio:
      expected.discard('soundd')
    expected |= {n for n in FORK_ONLY if n in cand}  # checked separately below
    if cand != expected:
      failures.append({'scenario': [started, not_car, dm, audio, mic, profile], 'candidate_vs_expected':
                       {'missing': sorted(expected - cand), 'extra': sorted(cand - expected)}})
    if (cand ^ prev) - OFFICIAL_ONLY_BEFORE:
      failures.append({'scenario': [started, not_car, dm, audio, mic, profile], 'candidate_vs_previous': sorted((cand ^ prev) - OFFICIAL_ONLY_BEFORE)})
    if ('trafficcontrold' in cand) != started or ('alert_output' in cand) != (profile == 'c3xl'):
      failures.append({'scenario': [started, not_car, dm, audio, mic, profile], 'fork_only': sorted(cand & FORK_ONLY)})

  restart = {p.name for p in candidate.procs if p.restart_if_crash}
  checks = {'process_tables': not failures, 'no_fork_crash_restart': not restart,
            'official_names_kept': {p.name for p in official.procs} <= {p.name for p in candidate.procs}}
  result = {'scenarios': scenarios, 'checks': checks, 'failures': failures[:20], 'passed': all(checks.values()),
            'head': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()}
  text = json.dumps(result, indent=2)
  if args.output:
    args.output.write_text(text + '\n')
  print(text)
  return 0 if result['passed'] else 1


if __name__ == '__main__':
  sys.exit(main())
