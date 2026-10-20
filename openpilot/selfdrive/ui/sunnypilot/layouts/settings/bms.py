"""Read-only battery dashboard opened from the Tesla settings page. No CAN publication or UDS requests."""
import time
import pyray as rl

from openpilot.cereal import messaging
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.sunnypilot.selfdrive.car.tesla.bms import BmsState, FRAME_LENGTHS
from openpilot.system.ui.lib.application import gui_app, FontWeight, FONT_SCALE
from openpilot.system.ui.lib.text_measure import measure_text_cached
from openpilot.system.ui.widgets import Widget
from openpilot.system.ui.lib.multilang import tr
from openpilot.system.ui.widgets.button import Button, ButtonStyle
from openpilot.system.ui.widgets.network import NavButton


class BmsLayout(Widget):
  def __init__(self, back_btn_callback=None):
    super().__init__()
    self._back_button = NavButton(tr("Back"))
    self._back_button.set_click_callback(back_btn_callback)
    self.state = BmsState()
    self.sock = None
    self.supported = False
    self._visible = False
    self._car_fingerprint = None
    self.page = 0
    self._display = (float('-inf'), None, None)
    self.tabs = [Button(label, click_callback=lambda index=i: self._select_page(index), font_size=42)
                 for i, label in enumerate(('Overview', 'Cells', 'Diagnostics'))]
    for tab in self.tabs:
      self._child(tab)

  def show_event(self):
    super().show_event()
    self._visible = True
    self.state = BmsState()
    self._sync_subscription()

  def hide_event(self):
    self._visible = False
    self.sock = None
    self._car_fingerprint = None
    self.supported = False
    self.state = BmsState()
    super().hide_event()

  def _sync_subscription(self):
    cp = ui_state.CP
    fingerprint = cp.carFingerprint if cp is not None and cp.brand == 'tesla' and any(
      model in cp.carFingerprint for model in ('MODEL_3', 'MODEL_Y')) else None
    if fingerprint != self._car_fingerprint:
      self.state = BmsState()
      self.sock = None
      self._car_fingerprint = fingerprint
    self.supported = fingerprint is not None
    if self._visible and self.supported and self.sock is None:
      self.sock = messaging.sub_sock('can', timeout=0)

  def _update_state(self):
    super()._update_state()
    if self._visible:
      self._sync_subscription()
    if self.sock is None:
      return
    now = time.monotonic()
    for _ in range(200):  # bounded UI work; timestamp is the message's monotonic time
      msg = messaging.recv_one_or_none(self.sock)
      if msg is None:
        break
      timestamp = msg.logMonoTime * 1e-9
      if not msg.valid or not 0 <= now - timestamp <= 3:
        continue
      for frame in msg.can:
        if frame.src != 1 or frame.address not in FRAME_LENGTHS:
          continue
        self.state.update(frame.address, bytes(frame.dat), frame.src, timestamp)
    sm = ui_state.sm
    self.state.integrate(now, sm['carState'].vEgo if sm.alive['carState'] and sm.valid['carState'] else None)

  def _display_data(self, now):
    # 2 Hz text refresh; 100 Hz values redrawn every frame read as flicker.
    shown_at, state, data = self._display
    if state is not self.state or not 0 <= now - shown_at < .5:
      self._display = (now, self.state, self.state.snapshot(now))
    return self._display[2]

  def _select_page(self, index):
    self.page = index

  @staticmethod
  def _text(text, x, y, size, color, bold=False):
    font = gui_app.font(FontWeight.BOLD if bold else FontWeight.NORMAL)
    if text.isascii():
      # Keep large digits on the 200px Inter atlas instead of upscaling the 48px CJK fallback.
      rl._orig_draw_text_ex(font, text, rl.Vector2(x, y), size*FONT_SCALE, 0, color)
    else:
      rl.draw_text_ex(font, text, rl.Vector2(x, y), size, 0, color)

  def _card(self, rect, label, value, unit, precision=1, primary=False, note=None):
    scale = self.scale
    color = rl.Color(23, 47, 43, 255) if primary else rl.Color(28, 33, 42, 255)
    rl.draw_rectangle_rounded(rect, .08, 12, color)
    x, y = rect.x+28*scale, rect.y+22*scale
    self._text(label, x, y, 40*scale, self.muted)
    number = '—' if value is None else f'{value:.{precision}f}'
    size = (144 if primary else 88)*scale
    self._text(number, x, y+57*scale, size, self.white, True)
    # ASCII units use the Inter atlas in _text, not the language fallback.
    unit_width = rl.measure_text_ex(gui_app.font(), unit, 36*scale*FONT_SCALE, 0).x  # noqa: TID251
    self._text(unit, rect.x+rect.width-unit_width-28*scale, rect.y+rect.height-52*scale,
               36*scale, self.accent if primary else self.muted)
    if note:
      self._text(note, x, rect.y+rect.height-57*scale, 34*scale, self.muted)

  def _render(self, rect):
    self._back_button.set_position(rect.x, rect.y + 20)
    self._back_button.render()
    offset = self._back_button.rect.height + 40
    rect = rl.Rectangle(rect.x, rect.y + offset, rect.width, rect.height - offset)
    now = time.monotonic()
    data = self._display_data(now)
    self.scale = min(1., rect.width/1560, rect.height/1030)
    s = self.scale
    self.white, self.muted = rl.Color(245, 247, 250, 255), rl.Color(176, 186, 201, 255)
    self.accent, amber = rl.Color(98, 229, 181, 255), rl.Color(255, 194, 94, 255)
    rl.draw_rectangle_rounded(rect, .025, 12, rl.Color(13, 16, 22, 255))
    x, y, w = rect.x+20*s, rect.y+16*s, rect.width-40*s
    self._text('Battery & Energy', x, y, 56*s, self.white, True)
    fresh = any(v is not None for v in data.values())
    status = ('Live data' if fresh else 'Waiting for vehicle data') if self.supported else 'Model 3 / Y only'
    sw = measure_text_cached(gui_app.font(), status, 34*s).x
    self._text(status, x+w-sw, y+15*s, 34*s, self.accent if fresh else amber)
    gap = 20*s
    for i, tab in enumerate(self.tabs):
      tab.set_button_style(ButtonStyle.PRIMARY if i==self.page else ButtonStyle.NORMAL)
      tab.render(rl.Rectangle(x+i*(w+gap)/3, y+83*s, (w-2*gap)/3, 76*s))
    top = y+184*s
    half = (w-gap)/2
    cs_fresh = ui_state.sm.alive['carState'] and ui_state.sm.valid['carState']
    cs = ui_state.sm['carState']
    speed = cs.vEgo*3.6 if cs_fresh else None
    delta = None if data['cell_min'] is None or data['cell_max'] is None else (data['cell_max']-data['cell_min'])*1000
    if self.page == 0:
      if data['soc_display'] is not None:
        self._card(rl.Rectangle(x, top, half, 310*s), 'State of Charge', data['soc_display'], '%', 0, True,
                   f"BMS {data['soc']:.1f}%")
      else:
        self._card(rl.Rectangle(x, top, half, 310*s), 'State of Charge', data['soc'], '%', 1, True)
      self._card(rl.Rectangle(x+half+gap, top, half, 310*s), 'Avg Consumption', data['consumption'], 'Wh/km', 0, True,
                 'Rolling 2 km average')
      third = (w-2*gap)/3
      for i, (label, key, unit, digits) in enumerate([('Battery Power', 'power', 'kW', 1),
                                                     ('Battery Voltage', 'voltage', 'V', 1), ('Battery Current', 'current', 'A', 1)]):
        self._card(rl.Rectangle(x+i*(third+gap), top+330*s, third, 204*s), label, data[key], unit, digits)
      self._card(rl.Rectangle(x, top+554*s, half, 190*s), 'Remaining Energy', data['remaining'], 'kWh')
      self._card(rl.Rectangle(x+half+gap, top+554*s, half, 190*s), 'BMS Full Capacity', data['capacity'], 'kWh')
      self._text('Positive = discharge, negative = regen. Consumption is a 2 km average.', x, top+775*s, 34*s, self.muted)
    elif self.page == 1:
      temp_delta = None if data['temp_min'] is None or data['temp_max'] is None else data['temp_max']-data['temp_min']
      cards = [('Min Cell Temp', data['temp_min'], '°C', 1), ('Max Cell Temp', data['temp_max'], '°C', 1),
               ('Min Cell Voltage', data['cell_min'], 'V', 3), ('Max Cell Voltage', data['cell_max'], 'V', 3),
               ('Cell Temp Spread', temp_delta, '°C', 1), ('Cell Voltage Spread', delta, 'mV', 0)]
      for i, (label, value, unit, digits) in enumerate(cards):
        self._card(rl.Rectangle(x+(i%2)*(half+gap), top+(i//2)*250*s, half, 230*s), label, value, unit, digits)
      self._text('Stale or untrusted data is hidden. Values are not a battery health verdict.', x, top+770*s, 32*s, self.muted)
    else:
      cards = [('Total Charged', data['charged'], 'kWh'), ('Total Discharged', data['discharged'], 'kWh'),
               ('Vehicle Speed', speed, 'km/h'), ('Steering Angle', cs.steeringAngleDeg if cs_fresh else None, '°')]
      for i, (label, value, unit) in enumerate(cards):
        self._card(rl.Rectangle(x+(i%2)*(half+gap), top+(i//2)*214*s, half, 194*s), label, value, unit)
      warnings = [label for key, label in [('drive_power_low', 'Drive power low'), ('support_power_low', 'Support power low')] if data[key] == 1]
      status = ' / '.join(warnings) if warnings else ('Power warnings: clear' if data['drive_power_low'] is not None else 'Power status: waiting for data')
      self._text(status, x+10*s, top+451*s, 40*s, amber if warnings else self.white)
      brake = ('pressed' if cs.brakePressed else 'released') if cs_fresh else 'waiting for data'
      self._text('Brake pedal: '+brake, x+10*s, top+507*s, 36*s, self.muted)
      from openpilot.sunnypilot.selfdrive.car.tesla.bms import FRAME_LENGTHS
      for i, address in enumerate(FRAME_LENGTHS):
        item = self.state.frames.get(address)
        active = item is not None and 0<=now-item[1]<=3
        label = 'Online' if active else ('Stale' if item else 'Not received')
        bx, by = x+(i%4)*(w+gap)/4, top+579*s+(i//4)*82*s
        rw = (w-3*gap)/4
        rl.draw_rectangle_rounded(rl.Rectangle(bx, by, rw, 65*s), .15, 8, rl.Color(28,33,42,255))
        self._text(f'{address:03X}  ·  {label}', bx+20*s, by+12*s, 34*s, self.accent if active else self.muted)
      self._text('Read-only monitor: sends no CAN commands and runs no fault-code scan.', x, top+777*s, 32*s, self.muted)
