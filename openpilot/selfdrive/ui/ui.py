#!/usr/bin/env python3
import os
import time

from openpilot.cereal import messaging
from openpilot.common.hardware import COMMA_HARDWARE
from openpilot.common.realtime import Priority, config_realtime_process, set_core_affinity
from openpilot.common.swaglog import cloudlog
from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.lib.multilang import multilang, tr
from openpilot.selfdrive.ui.mici.layouts.main import MiciMainLayout
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.tesla.ui.offroad import install_defaults_later
from openpilot.tesla.ui.screen import BigScreenHost, is_big_screen
from openpilot.tesla.ui.localization import refresh as refresh_translations


def main():
  cores = {5, }
  # above plannerd and radard
  config_realtime_process(0, Priority.CTRL_HIGH)

  refresh_translations(ui_state.params)
  gui_app.init_window("UI", host=BigScreenHost if is_big_screen() else None)
  MiciMainLayout()
  install_defaults_later(ui_state.is_offroad, ui_state.params)
  cloudlog.info(f"ui i18n language={multilang.language} entries={len(multilang._translations)} "
                f"param={ui_state.params.get('LanguageSetting')!r} sample={tr('Device')!r}")

  pm = messaging.PubMaster(['uiDebug'])
  for should_render, frame_time, cpu_time in gui_app.render():
    extra_start = time.monotonic()
    ui_state.update()
    refresh_translations(ui_state.params)

    if should_render:
      # reaffine after power save offlines our core
      if COMMA_HARDWARE and os.sched_getaffinity(0) != cores:
        try:
          set_core_affinity(list(cores))
        except OSError:
          pass

      extra_cpu = time.monotonic() - extra_start
      msg = messaging.new_message('uiDebug')
      msg.uiDebug.cpuTimeMillis = (cpu_time + extra_cpu) * 1000
      msg.uiDebug.frameTimeMillis = frame_time * 1000
      pm.send('uiDebug', msg)


if __name__ == "__main__":
  main()
