"""Plugin alerts in selfdrived: three SP events whose text comes from the plugins (plugins.update_alerts fills
`current`). They show regardless of engagement, never disengage, and rank at most MID so SP's own disengage and
critical alerts always win. xpilotPluginFault is the host's own: a replaced engagement or fallback failed (core_host.py)."""
from openpilot.cereal import custom, log
from opendbc.car.structs import car
from openpilot.sunnypilot.selfdrive.selfdrived.events_base import ET, Alert, ImmediateDisableAlert, NoEntryAlert, Priority

AlertSize = log.SelfdriveState.AlertSize
AlertStatus = log.SelfdriveState.AlertStatus
AudibleAlert = car.CarControl.HUDControl.AudibleAlert
VisualAlert = car.CarControl.HUDControl.VisualAlert
EventNameSP = custom.OnroadEventSP.EventName

MAX_TITLE, MAX_BODY = 60, 80
EVENT_NAMES = {"info": EventNameSP.xpilotPluginInfo, "warning": EventNameSP.xpilotPluginWarning,
               "critical": EventNameSP.xpilotPluginCritical}
_STYLE = {  # status, priority, sound
  "info": (AlertStatus.normal, Priority.LOWER, AudibleAlert.none),
  "warning": (AlertStatus.userPrompt, Priority.LOW, AudibleAlert.prompt),
  "critical": (AlertStatus.critical, Priority.MID, AudibleAlert.warningSoft),
}

current: dict[str, tuple[str, str]] = {}  # severity -> (title, body), replaced every selfdrived cycle


def _callback(severity: str):
  status, priority, sound = _STYLE[severity]

  def alert(CP, CS, sm, metric, soft_disable_time, personality) -> Alert:
    title, body = current.get(severity, ("", ""))
    return Alert(title, body, status, AlertSize.mid if body else AlertSize.small, priority, VisualAlert.none, sound, 0.2)
  return alert


EVENTS = {name: {ET.PERMANENT: _callback(sev)} for sev, name in EVENT_NAMES.items()}
EVENTS[EventNameSP.xpilotPluginFault] = {  # core_host.py: never part of the plugin alert text
  ET.IMMEDIATE_DISABLE: ImmediateDisableAlert("xpilot Plugin Fault"),
  ET.NO_ENTRY: NoEntryAlert("xpilot Plugin Fault"),
  ET.PERMANENT: Alert("xpilot Plugin Fault", "Take control. Engagement is off until the car is parked",
                      AlertStatus.critical, AlertSize.mid, Priority.MID, VisualAlert.none, AudibleAlert.none, 0.2),
}
