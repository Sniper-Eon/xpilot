"""Host for the replaceable engagement (role:engagement.state) and safety fallback (role:safety.fallback) in selfdrived,
and the card gate. Design: docs/design/xpilot-replaceable-core.md, committee X-20261023-12, user floors 2026-10-23.

With the default owners (sp_engagement, sp_safety_fallback) nothing here runs and selfdrived is SP's own. Otherwise:
- fallback: SP's update_events runs first (DM lockout and every floor detector stay SP's), then the plugin edits
  s.events / s.events_sp in place (it may clear them and build its own); the host puts back every floor event.
- engagement: the plugin's ordinary state machine and MADS replace SP's behind guards that clamp their outputs:
  floor USER/IMMEDIATE disable wins, an engage needs SP's driver ENABLE event (MADS: the LKAS button or an ordinary
  ENABLE) and no floor NO_ENTRY, active implies enabled and matches the state, soft disable ends within
  SOFT_DISABLE_TIME + 1 s, ET.PERMANENT is always shown (FCW, stock AEB), the LKAS button disengages MADS.
- a raise or an invalid output latches both axes off for the rest of the drive (also across selfdrived restarts,
  through XpilotPluginFaults) and shows xpilotPluginFault; no fallback to the default while driving.
- card sends only while selfdriveState is alive, so a hung selfdrived stops actuation within ~0.1 s.
Hangs inside a hook stop selfdrived; the card gate and the panda heartbeat cover them. In-process plugins are trusted
code (claims are not a sandbox); panda safety stays the floor against anything else."""
import time
from types import SimpleNamespace

from openpilot.cereal import custom, log
from opendbc.car.structs import car
from openpilot.selfdrive.selfdrived.events import EVENTS, ET
from openpilot.selfdrive.selfdrived.state import ACTIVE_STATES, ENABLED_STATES, SOFT_DISABLE_TIME, State
from openpilot.sunnypilot.mads.state import ACTIVE_STATES as MADS_ACTIVE, ENABLED_STATES as MADS_ENABLED, State as MadsState
from openpilot.tesla.plugins import FAULTS_PARAM, _collect, event_filters, owner, record_fault

ENGAGEMENT, FALLBACK = "role:engagement.state", "role:safety.fallback"
DEFAULTS = {ENGAGEMENT: "sp_engagement", FALLBACK: "sp_safety_fallback"}
EN, ENSP = log.OnroadEvent.EventName, custom.OnroadEventSP.EventName
LKAS = car.CarState.ButtonEvent.Type.lkas
SOFT_BOUND = SOFT_DISABLE_TIME + 1.0  # s
MISMATCH_FRAMES = 200  # same as SP's MADS lateral mismatch

FLOOR = {EN.pedalPressed, EN.buttonCancel, EN.pcmDisable, EN.fcw, EN.stockAeb, EN.stockFcw, EN.controlsMismatch,
         EN.relayMalfunction, EN.canError, EN.canBusMissing, EN.selfdrivedLagging, EN.commIssue, EN.commIssueAvgFreq,
         EN.processNotRunning, EN.selfdriveInitializing, EN.tooDistracted, EN.driverDistracted1, EN.driverDistracted2,
         EN.driverDistracted3, EN.driverUnresponsive1, EN.driverUnresponsive2, EN.driverUnresponsive3}
FLOOR_SP = {ENSP.controlsMismatchLateral, ENSP.lkasDisable, ENSP.xpilotPluginFault}
MADS_EXEMPT = {EN.pcmDisable, EN.buttonCancel, EN.pedalPressed}  # MADS keeps steering through these (mads.py)
ENABLE_EVENTS = {EN.pcmEnable, EN.buttonEnable}
# Shared event filters may only drop these names (and never floor or enable events).
EVENT_FILTER_ALLOWLIST = {int(EN.invalidLkasSetting)}

now = time.monotonic


def _floor(names, et, exempt=()) -> bool:
  return any(e in FLOOR and e not in exempt and et in EVENTS.get(e, {}) for e in names)


class _Host:
  def __init__(self, s, names):
    self.s, self.names = s, names
    faults = s.params.get(FAULTS_PARAM) or {}
    self.latched = any(n in faults for n in names)
    self.filter_fault = False
    self.filters = [c for c in event_filters(s.params) if c.NAME not in faults]
    self.sp_enable = False  # SP's update_events produced a driver ENABLE event this frame
    self.lkas_press = False
    self.enabled_prev = False
    self.soft_t = None
    self.mismatch = 0

  def fault(self, name, where, exc) -> None:
    record_fault(name, where, exc)
    self.latched = True
    self.mark()

  def mark(self) -> None:
    if not self.s.events_sp.has(ENSP.xpilotPluginFault):
      self.s.events_sp.add(ENSP.xpilotPluginFault)


def _fallback(host, orig, plugin):
  s = host.s

  def update_events(CS):
    orig(CS)
    ev, ev_sp = s.events, s.events_sp
    floor = [e for e in ev.names if e in FLOOR]
    floor_sp = [e for e in ev_sp.names if e in FLOOR_SP]
    host.sp_enable = any(e in ENABLE_EVENTS for e in ev.names)
    host.lkas_press = any(be.type == LKAS and be.pressed for be in CS.buttonEvents)
    if not host.latched:
      ctx = SimpleNamespace(sm=getattr(s, "sm", None), CP=getattr(s, "CP", None), CP_SP=getattr(s, "CP_SP", None), params=s.params)
      for cls in list(host.filters):
        try:
          drop, drop_sp = cls.event_filter(ctx, CS, ev.names.copy(), ev_sp.names.copy())
          if not isinstance(drop, list) or not isinstance(drop_sp, list) or drop_sp:
            raise ValueError("event_filter may only drop OnroadEvent names")
          allowed = []
          for e in drop:
            try:
              value = int(e)
            except Exception:
              raise ValueError("event_filter returned a non-event") from None
            if value not in EVENT_FILTER_ALLOWLIST or e in FLOOR or e in ENABLE_EVENTS:
              raise ValueError("event_filter may only drop allowlisted event names")
            allowed.append(e)
          ev.names[:] = [e for e in ev.names if e not in allowed]
        except Exception as e:
          host.filters.remove(cls)
          record_fault(cls.NAME, "selfdrived.event_filter", e)
          host.filter_fault = True
    if plugin is not None and not host.latched:
      try:
        plugin.update(s, CS)
        if s.events is not ev or s.events_sp is not ev_sp:
          raise TypeError("safety_fallback must edit s.events/s.events_sp in place")
      except Exception as e:
        s.events, s.events_sp = ev, ev_sp
        host.fault(getattr(plugin, "plugin_name", "?"), "selfdrived.safety_fallback.update", e)
    for e in floor:
      if not ev.has(e):
        ev.add(e)
    for e in floor_sp:
      if not ev_sp.has(e):
        ev_sp.add(e)
    if host.latched or host.filter_fault:
      host.mark()
  return update_events


class _GuardedStateMachine:
  """Ordinary state machine (SP's or the plugin's) with the host clamp on its outputs."""

  def __init__(self, host, inner, name):
    object.__setattr__(self, "_h", host)
    object.__setattr__(self, "_inner", inner)
    object.__setattr__(self, "_name", name)

  def __getattr__(self, name):
    return getattr(self._inner, name)

  def __setattr__(self, name, value):
    setattr(self._inner, name, value)

  def update(self, events):
    h, inner = self._h, self._inner
    enabled = active = False
    if not h.latched:
      try:
        enabled, active = (bool(x) for x in inner.update(events))
        if enabled != (inner.state in ENABLED_STATES) or active != (inner.state in ACTIVE_STATES):
          raise ValueError(f"enabled={enabled} active={active} disagree with state {inner.state}")
      except Exception as e:
        h.fault(self._name, "selfdrived.engagement.update", e)
    names = events.names
    types = [t for t in (inner.current_alert_types if isinstance(inner.current_alert_types, list) else []) if isinstance(t, str)]
    forced = None
    if h.latched:
      forced = ET.IMMEDIATE_DISABLE
    elif _floor(names, ET.IMMEDIATE_DISABLE):
      forced = ET.IMMEDIATE_DISABLE
    elif _floor(names, ET.USER_DISABLE):
      forced = ET.USER_DISABLE
    elif enabled and not h.enabled_prev and (not h.sp_enable or _floor(names, ET.NO_ENTRY)):
      forced = ET.NO_ENTRY if h.sp_enable else ""  # engage without a driver ENABLE, or into a floor NO_ENTRY
    soft = enabled and (inner.state == State.softDisabling or _floor(names, ET.SOFT_DISABLE))
    h.soft_t = (h.soft_t if h.soft_t is not None else now()) if soft else None
    if forced is None and soft:
      if now() - h.soft_t > SOFT_BOUND:
        forced = ET.SOFT_DISABLE
      elif ET.SOFT_DISABLE not in types:
        types.append(ET.SOFT_DISABLE)
    if forced is not None:
      if (enabled or h.enabled_prev or forced == ET.NO_ENTRY) and forced and forced not in types:
        types.append(forced)
      inner.state, enabled, active, h.soft_t = State.disabled, False, False, None
    if ET.PERMANENT not in types:
      types.insert(0, ET.PERMANENT)
    inner.current_alert_types = types
    h.enabled_prev = enabled
    return enabled, active


class _GuardedMads:
  """MADS (SP's or the plugin's) with the host clamp; enabled/active are the clamped values."""

  def __init__(self, host, inner, name, toggle):
    for k, v in (("_h", host), ("_inner", inner), ("_name", name), ("_toggle", toggle), ("_enabled", False), ("_active", False)):
      object.__setattr__(self, k, v)

  def __getattr__(self, name):
    return getattr(self._inner, name)

  def __setattr__(self, name, value):
    setattr(self._inner, name, value)

  @property
  def enabled(self):
    return self._enabled

  @property
  def active(self):
    return self._active

  @property
  def enabled_toggle(self):
    return self._toggle

  def update(self, CS):
    h, inner, s = self._h, self._inner, self._h.s
    enabled = active = False
    if self._toggle and not h.latched:
      try:
        inner.update(CS)
        enabled, active = bool(inner.enabled), bool(inner.active)
        state = inner.state_machine.state
        if enabled != (state in MADS_ENABLED) or active != (state in MADS_ACTIVE):
          raise ValueError(f"MADS enabled={enabled} active={active} disagree with state {state}")
      except Exception as e:
        h.fault(self._name, "selfdrived.engagement.mads", e)
        enabled = active = False
    prev = self._enabled
    names, names_sp = s.events.names, s.events_sp.names
    lateral_off = any(not ps.controlsAllowedLateral for ps in s.sm["pandaStates"] if hasattr(ps, "controlsAllowedLateral"))
    h.mismatch = h.mismatch + 1 if (prev and self._active and not s.enabled and lateral_off) else 0
    disable = (h.latched or _floor(names, ET.IMMEDIATE_DISABLE, MADS_EXEMPT) or h.mismatch >= MISMATCH_FRAMES or
               ENSP.controlsMismatchLateral in names_sp or ENSP.lkasDisable in names_sp or
               (prev and h.lkas_press and not s.enabled))
    if enabled and not prev and not (h.lkas_press or h.sp_enable) or (enabled and not prev and _floor(names, ET.NO_ENTRY, MADS_EXEMPT)):
      disable = True
    if disable:
      enabled = active = False
      inner.state_machine.state = MadsState.disabled
    inner.enabled, inner.active = enabled, active
    object.__setattr__(self, "_enabled", enabled)
    object.__setattr__(self, "_active", active)
    s.enabled_prev = s.enabled


def install(s) -> None:
  """selfdrived, end of SelfdriveD.__init__: wrap SP's engagement and fallback when a plugin replaces either."""
  if s.CP.brand != "tesla":
    return
  owners = {role: owner(s.params, role) for role in DEFAULTS}
  if all(o in (None, DEFAULTS[r]) for r, o in owners.items()):
    return
  host = _Host(s, [o for r, o in owners.items() if o not in (None, DEFAULTS[r])])
  owners = {r: (DEFAULTS[r] if o is None else o) for r, o in owners.items()}
  fb = _collect(s.params, "safety_fallback", FALLBACK, "selfdrived", s) if owners[FALLBACK] != DEFAULTS[FALLBACK] else []
  eng = _collect(s.params, "engagement", ENGAGEMENT, "selfdrived", s) if owners[ENGAGEMENT] != DEFAULTS[ENGAGEMENT] else []
  if (owners[FALLBACK] != DEFAULTS[FALLBACK] and not fb) or (owners[ENGAGEMENT] != DEFAULTS[ENGAGEMENT] and not eng):
    host.latched = True  # a replacement's hook raised or returned nothing: no engagement this drive
  s.update_events = _fallback(host, s.update_events, fb[0] if fb else None)
  name = getattr(eng[0], "plugin_name", "?") if eng else DEFAULTS[ENGAGEMENT]
  sm_inner, mads_inner = (eng[0].state_machine, eng[0].mads) if eng else (s.state_machine, s.mads)
  s.state_machine = _GuardedStateMachine(host, sm_inner, name)
  if mads_inner is None:
    from openpilot.sunnypilot.mads.mads import ModularAssistiveDrivingSystem
    mads_inner = ModularAssistiveDrivingSystem(s)  # SP's MADS bound to the plugin's state machine
  s.mads = _GuardedMads(host, mads_inner, name, s.params.get_bool("Mads"))
  if host.latched:
    host.mark()


class CardGate:
  """card: with a replaced engagement or fallback, send only while selfdriveState is alive."""

  def __init__(self, params, sm=None):
    replaced = any(owner(params, role) not in (None, DEFAULTS[role]) for role in DEFAULTS)
    if replaced and sm is None:
      from openpilot.cereal import messaging
      sm = messaging.SubMaster(["selfdriveState"])
    self.sm = sm if replaced else None

  def alive(self) -> bool:
    if self.sm is None:
      return True
    self.sm.update(0)
    return bool(self.sm.alive["selfdriveState"])
