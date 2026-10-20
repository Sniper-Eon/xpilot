"""Fork-only process changes, applied once to the official process list.

Keeps openpilot/system/manager/process_config.py official except for one call:
- driver monitoring follows the DM switch (C3XL has no cabin camera)
- micd/soundd only run on hardware with a microphone/amplifier (C3XL has neither)
- C3XL routes alerts to its GPIO buzzer; Tesla traffic control runs onroad
- the UI restarts after a crash
"""
from openpilot.common.hardware import PC
from openpilot.sunnypilot.hardware.driver_monitoring import driver_monitoring_enabled
from openpilot.sunnypilot.hardware.profile import HardwareProfile, get_hardware_profile, has_audio_output, has_microphone
from openpilot.system.manager.process import PythonProcess


def _gate(process, condition) -> None:
  official = process.should_run
  process.should_run = lambda started, params, CP: condition(params) and official(started, params, CP)


def apply_fork_processes(procs: list, only_onroad) -> list:
  by_name = {p.name: p for p in procs}
  for name in ("dmonitoringmodeld", "dmonitoringd"):
    _gate(by_name[name], driver_monitoring_enabled)
  _gate(by_name["micd"], lambda params: has_microphone())
  _gate(by_name["soundd"], lambda params: has_audio_output())
  return procs + [
    PythonProcess("trafficcontrold", "openpilot.sunnypilot.selfdrive.traffic_control.trafficcontrold", only_onroad),
    PythonProcess("alert_output", "openpilot.sunnypilot.system.alert_output",
                  lambda started, params, CP: not PC and get_hardware_profile() == HardwareProfile.C3XL),
  ]
