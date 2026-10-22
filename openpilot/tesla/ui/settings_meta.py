"""Tesla settings metadata. Add a setting: declare the key in common/params_keys.h, then list it here.
BOOL_KEYS become toggles; RANGES (min, max, step, unit, divisor) and CHOICES become pickers."""
from openpilot.system.ui.lib.multilang import tr_noop

LABELS = {
  # upstream sunnypilot Tesla options
  'TeslaCoopSteering': tr_noop('Cooperative Steering'), 'TeslaMadsScreenButton': tr_noop('MADS Screen Activation'),
  # plugin auto_speed
  'TeslaAutoSpeedLimit': tr_noop('Auto Speed Limit'), 'TeslaAutoSpeedLimitOffset': tr_noop('Auto Speed Limit Offset'),
  # plugin traffic_light
  'TeslaTrafficSignalControlEnabled': tr_noop('Traffic Light Control (Experimental)'),
  'TeslaTrafficStopReference': tr_noop('Traffic Light Stop Reference'), 'TeslaTrafficControlMaxSpeed': tr_noop('Traffic Light Control Max Speed'),
  # plugin ambient_light
  'TeslaBlindspotAmbientEnabled': tr_noop('Blindspot Ambient Lights'),
  'TeslaBlindspotAmbientDayBrightness': tr_noop('Blindspot Lights: Day Brightness'),
  'TeslaBlindspotAmbientBrightness': tr_noop('Blindspot Lights: Night Brightness'),
}

BOOL_KEYS = ('TeslaCoopSteering', 'TeslaAutoSpeedLimit', 'TeslaTrafficSignalControlEnabled', 'TeslaBlindspotAmbientEnabled')
RANGES = {
  'TeslaAutoSpeedLimitOffset': (-10, 20, 1, 'km/h|mph', 1),
  'TeslaTrafficStopReference': (20, 120, 5, 'm', 10),
  'TeslaTrafficControlMaxSpeed': (20, 120, 5, 'km/h', 1),
  'TeslaBlindspotAmbientDayBrightness': (0, 100, 1, '%', 1),
  'TeslaBlindspotAmbientBrightness': (0, 100, 1, '%', 1),
}
CHOICES = {
  'TeslaMadsScreenButton': [('Off', 0), ('3-Finger', 1), ('4-Finger', 2), ('5-Finger', 3)],  # upstream MadsScreenButtonType
}


def setting_label(key, value):
  if key in RANGES:
    _, _, _, unit, divisor = RANGES[key]
    number = f'{value / divisor:.1f}' if divisor != 1 else str(value)
    return number + ('%' if unit == '%' else ' ' + unit)
  return next((label for label, choice in CHOICES[key] if choice == value), str(value))


for key, (minimum, maximum, step, _, _) in RANGES.items():
  CHOICES[key] = [(setting_label(key, value), value) for value in range(minimum, maximum + 1, step)]
