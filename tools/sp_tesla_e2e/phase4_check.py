#!/usr/bin/env python3
"""Replaceable engagement (role:engagement.state) and safety fallback (role:safety.fallback) check.

User floors (2026-10-23): a plugin may replace SP's whole engagement state machines (ordinary + MADS) or its whole
fallback policy (which events fire), but never panda safety, real brake/gas/cancel disengage, FCW, stock AEB, the
MADS disengage inputs (LKAS button, cruise main off), core-data liveness, selfdrivedLagging, DM, and an engage
always needs a driver ENABLE trigger. Runs where the openpilot python env (cereal, msgq) exists, i.e. the device.

Failure cases listed before implementation:
- C1 with the default owners (sp_engagement, sp_safety_fallback) install_core changes selfdrived at all
- C2 an engagement plugin that raises keeps control, or the drive re-engages later (latch), or no fault alert shows
- C3 a state machine returning enabled/active that disagree with its state (enabled=False, active=True) keeps control
- C4 a state machine ignoring a floor USER_DISABLE (pedalPressed, buttonCancel, pcmDisable) or IMMEDIATE_DISABLE
     (canError, controlsMismatch) event stays engaged
- C5 a state machine stuck in softDisabling, or engaged under a floor SOFT_DISABLE event (commIssue,
     selfdrivedLagging, processNotRunning), longer than SOFT_DISABLE_TIME + 1 s
- C6 a state machine engages without a driver ENABLE event, or with one while a floor NO_ENTRY event is present
- C7 a state machine dropping ET.PERMANENT hides FCW / stock AEB alerts
- C8 a fallback that clears the events loses a floor event (pedalPressed, fcw, stockAeb, commIssue, DM tooDistracted);
     a non-floor event it removed (doorOpen) comes back
- C9 a fallback that replaces s.events instead of editing it, or raises, keeps control
- C10 a MADS replacement ignores the LKAS button (also the Tesla screen gesture) or a floor IMMEDIATE_DISABLE event,
      engages laterally without a trigger, reports active without enabled, or overrides the Mads toggle
      (Tesla has no ACC main button, so SP's cruise-main-off disengage does not apply)
- C11 a plugin fault recorded earlier in this drive (selfdrived restarted) does not start the new process latched
- C12 card keeps sending while a replacement owns a role and selfdriveState is not alive; or the gate changes the
      default path
"""
import json
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "opendbc_repo")]
try:
  import openpilot.common.params  # noqa: F401
except Exception:
  sys.modules["openpilot.common.params"] = types.SimpleNamespace(Params=object, UnknownKeyName=KeyError)
from openpilot.common.swaglog import cloudlog  # noqa: E402
for _level in ("error", "exception", "warning", "info"):
  setattr(cloudlog, _level, lambda *a, **k: None)

from openpilot.cereal import custom, log  # noqa: E402
from openpilot.selfdrive.selfdrived.events import ET, Events  # noqa: E402
from openpilot.selfdrive.selfdrived.state import State, StateMachine  # noqa: E402
from openpilot.sunnypilot.mads.state import State as MadsState  # noqa: E402
from openpilot.sunnypilot.selfdrive.selfdrived.events import EventsSP  # noqa: E402
from openpilot.tesla import core_host, plugins  # noqa: E402
from openpilot.tesla.plugin import Plugin  # noqa: E402
from opendbc.car.structs import car  # noqa: E402

EN = log.OnroadEvent.EventName
ENSP = custom.OnroadEventSP.EventName
FAULTS = {}
plugins.record_fault = lambda name, where, exc: FAULTS.__setitem__(name, where)
core_host.record_fault = plugins.record_fault


class Params:
  def __init__(self, values=None):
    self.values = dict(values or {})

  def get_bool(self, key, block=False):
    return bool(self.values.get(key, False))

  def get(self, key, block=False, return_default=False):
    return self.values.get(key)


class Clock:
  t = 0.0

  def __call__(self):
    return self.t


def cs(**kw):
  d = dict(buttonEvents=[], cruiseState=types.SimpleNamespace(available=True), standstill=False)
  d.update(kw)
  return types.SimpleNamespace(**d)


def selfdrive(params=None):
  s = types.SimpleNamespace(events=Events(), events_sp=EventsSP(), state_machine=StateMachine(), enabled=False,
                            active=False, params=params or Params({"Mads": True}), CP=types.SimpleNamespace(brand="tesla"),
                            sm={"pandaStates": []}, CS_prev=cs())
  s.mads = types.SimpleNamespace(enabled=False, active=False, enabled_toggle=True, update=lambda CS: None,
                                 read_params=lambda: None, state_machine=types.SimpleNamespace(state=MadsState.disabled))
  s.update_events = lambda CS: None
  return s


def role_plugin(name, claim, hook, value):
  return type(name, (Plugin,), {"NAME": name, "ENABLE_PARAM": None, "CLAIMS": (claim,), "PRIORITY": 100,
                                hook: classmethod(lambda cls, *a: value)})


def default_plugins():
  return tuple(type(n, (Plugin,), {"NAME": n, "ENABLE_PARAM": None, "CLAIMS": (c,), "PRIORITY": 10000})
               for n, c in (("sp_engagement", core_host.ENGAGEMENT), ("sp_safety_fallback", core_host.FALLBACK)))


class Scripted:
  """A replacement ordinary state machine that returns whatever the test sets."""

  def __init__(self):
    self.state, self.current_alert_types, self.soft_disable_timer = State.disabled, [ET.PERMANENT], 0
    self.out = (State.disabled, False, False, [ET.PERMANENT])
    self.raises = False

  def update(self, events):
    if self.raises:
      raise RuntimeError("engagement")
    self.state, enabled, active, types_ = self.out
    self.current_alert_types = list(types_)
    return enabled, active


class Mads:
  """A replacement MADS that reports whatever the test sets."""

  def __init__(self):
    self.enabled = self.active = False
    self.want = (False, False)
    self.enabled_toggle = True
    self.state_machine = types.SimpleNamespace(state=MadsState.disabled)

  def update(self, CS):
    self.enabled, self.active = self.want
    self.state_machine.state = MadsState.enabled if self.enabled else MadsState.disabled

  def read_params(self):
    pass


def engagement(sm, mads=None):
  return types.SimpleNamespace(state_machine=sm, mads=mads or Mads())


def install(engagement_sm=None, fallback=None, params=None, mads=None):
  plugins.PLUGINS = default_plugins()
  if engagement_sm is not None:
    plugins.PLUGINS += (role_plugin("rep_eng", core_host.ENGAGEMENT, "engagement", engagement(engagement_sm, mads)),)
  if fallback is not None:
    plugins.PLUGINS += (role_plugin("rep_fb", core_host.FALLBACK, "safety_fallback", fallback),)
  s = selfdrive(params)
  plugins.install_core(s)
  return s


def step(s, CS=None, events=(), events_sp=()):
  """One selfdrived step in SP's order: update_events, ordinary state machine, MADS."""
  CS = CS or cs()
  s.events.clear()
  s.events_sp.clear()
  for e in events:
    s.events.add(e)
  for e in events_sp:
    s.events_sp.add(e)
  s.update_events(CS)
  s.enabled, s.active = s.state_machine.update(s.events)
  s.mads.update(CS)
  s.CS_prev = CS
  return s.enabled, s.active


def main() -> int:
  errors = []
  clock = Clock()
  core_host.now = clock
  ENGAGED = (State.enabled, True, True, [ET.PERMANENT, ET.WARNING])

  # C1 defaults: nothing replaced
  plugins.PLUGINS = default_plugins()
  s = selfdrive()
  sm, mads, ue = s.state_machine, s.mads, s.update_events
  plugins.install_core(s)
  if s.state_machine is not sm or s.mads is not mads or s.update_events is not ue:
    errors.append("C1 install_core changed selfdrived with the default owners")

  # C2 raise -> latched, fault alert, no re-engage
  FAULTS.clear()
  rep = Scripted()
  s = install(engagement_sm=rep)
  rep.out = ENGAGED
  step(s, events=[EN.buttonEnable])
  rep.raises = True
  out = step(s)
  latch_types = list(s.state_machine.current_alert_types)
  rep.raises, rep.out = False, ENGAGED
  later = step(s, events=[EN.buttonEnable])
  if out != (False, False) or later != (False, False) or "rep_eng" not in FAULTS:
    errors.append(f"C2 raise: out {out}, later {later}, faults {FAULTS}")
  if ET.IMMEDIATE_DISABLE not in latch_types or not s.events_sp.has(ENSP.xpilotPluginFault):
    errors.append(f"C2 no fault alert: types {latch_types}, events_sp {s.events_sp.names}")

  # C3 inconsistent outputs
  for bad in [(State.disabled, False, True, [ET.PERMANENT]), (State.enabled, False, True, [ET.PERMANENT])]:
    FAULTS.clear()
    rep = Scripted()
    s = install(engagement_sm=rep)
    rep.out = bad
    if step(s, events=[EN.buttonEnable]) != (False, False) or "rep_eng" not in FAULTS:
      errors.append(f"C3 {bad[:3]} kept control or no fault")

  # C4 floor disable events ignored by the plugin
  for ev, et in [(EN.pedalPressed, ET.USER_DISABLE), (EN.buttonCancel, ET.USER_DISABLE), (EN.pcmDisable, ET.USER_DISABLE),
                 (EN.canError, ET.IMMEDIATE_DISABLE), (EN.controlsMismatch, ET.IMMEDIATE_DISABLE)]:
    rep = Scripted()
    s = install(engagement_sm=rep)
    rep.out = ENGAGED
    step(s, events=[EN.buttonEnable])
    if step(s, events=[ev]) != (False, False) or et not in s.state_machine.current_alert_types:
      errors.append(f"C4 ignored {ev}: types {s.state_machine.current_alert_types}")

  # C5 soft-disable bound
  for state, ev in [(State.softDisabling, None), (State.enabled, EN.commIssue), (State.enabled, EN.selfdrivedLagging),
                    (State.enabled, EN.processNotRunning)]:
    rep = Scripted()
    s = install(engagement_sm=rep)
    rep.out = ENGAGED
    clock.t = 0.0
    step(s, events=[EN.buttonEnable])
    rep.out = (state, True, True, [ET.PERMANENT, ET.SOFT_DISABLE])
    held = []
    for t in (0.1, 2.0, 3.9, 4.2):
      clock.t = t
      held.append(step(s, events=[ev] if ev is not None else [])[0])
    if held != [True, True, True, False]:
      errors.append(f"C5 {state} {ev}: engaged at 0.1/2.0/3.9/4.2 s = {held}")

  # C6 engage gate
  rep = Scripted()
  s = install(engagement_sm=rep)
  rep.out = ENGAGED
  if step(s) != (False, False):
    errors.append("C6 engaged without an ENABLE event")
  if step(s, events=[EN.buttonEnable, EN.canError]) != (False, False):
    errors.append("C6 engaged with a floor NO_ENTRY event")
  if step(s, events=[EN.buttonEnable]) != (True, True):
    errors.append("C6 a driver ENABLE did not engage the replacement")

  # C7 PERMANENT always kept
  rep = Scripted()
  s = install(engagement_sm=rep)
  rep.out = (State.disabled, False, False, [])
  step(s, events=[EN.fcw, EN.stockAeb])
  if ET.PERMANENT not in s.state_machine.current_alert_types:
    errors.append("C7 PERMANENT dropped, FCW/AEB alerts hidden")

  # C8 / C9 fallback
  class Clearing:
    def update(self, s, CS):
      s.events.clear()
      s.events_sp.clear()

  s = install(fallback=Clearing())
  step(s, events=[EN.pedalPressed, EN.fcw, EN.stockAeb, EN.commIssue, EN.tooDistracted, EN.doorOpen])
  kept = {e for e in (EN.pedalPressed, EN.fcw, EN.stockAeb, EN.commIssue, EN.tooDistracted) if s.events.has(e)}
  if len(kept) != 5 or s.events.has(EN.doorOpen):
    errors.append(f"C8 floor after a clearing fallback: {sorted(kept)}, doorOpen {s.events.has(EN.doorOpen)}")

  class Replacing:
    def update(self, s, CS):
      s.events = Events()

  class Raising:
    def update(self, s, CS):
      raise RuntimeError("fallback")

  for fb in (Replacing(), Raising()):
    FAULTS.clear()
    s = install(fallback=fb)
    s.state_machine.state = State.enabled
    if step(s) != (False, False) or "rep_fb" not in FAULTS:
      errors.append(f"C9 {type(fb).__name__} fallback kept control or no fault")

  # C10 MADS replacement
  lkas = [types.SimpleNamespace(type=car.CarState.ButtonEvent.Type.lkas, pressed=True)]
  m = Mads()
  s = install(engagement_sm=Scripted(), mads=m)
  m.want = (True, True)
  step(s)
  if s.mads.enabled:
    errors.append("C10 MADS engaged without a trigger")
  step(s, CS=cs(buttonEvents=lkas))
  engaged = s.mads.enabled
  step(s, CS=cs(buttonEvents=lkas))
  if not engaged or s.mads.enabled:
    errors.append(f"C10 LKAS button: engage {engaged}, still engaged after a second press {s.mads.enabled}")
  step(s, CS=cs(buttonEvents=lkas))
  step(s, events=[EN.canError])
  if s.mads.enabled:
    errors.append("C10 MADS stayed engaged under a floor IMMEDIATE_DISABLE event")
  FAULTS.clear()
  m = Mads()
  s = install(engagement_sm=Scripted(), mads=m)
  m.want = (False, True)
  step(s, CS=cs(buttonEvents=lkas))
  if s.mads.active or "rep_eng" not in FAULTS:
    errors.append("C10 MADS active without enabled kept steering or no fault")
  m = Mads()
  s = install(engagement_sm=Scripted(), mads=m, params=Params({"Mads": False}))
  m.want = (True, True)
  step(s, CS=cs(buttonEvents=lkas))
  if s.mads.enabled_toggle or s.mads.enabled:
    errors.append("C10 MADS ignores the Mads param (toggle from the plugin)")

  # C11 latch across a selfdrived restart
  plugins.PLUGINS = default_plugins() + (role_plugin("rep_eng", core_host.ENGAGEMENT, "engagement", engagement(Scripted())),)
  rep = plugins.PLUGINS[-1].engagement(None).state_machine
  rep.out = ENGAGED
  s = selfdrive(Params({"Mads": True, plugins.FAULTS_PARAM: {"rep_eng": "earlier"}}))
  plugins.install_core(s)
  if step(s, events=[EN.buttonEnable]) != (False, False):
    errors.append("C11 a fault from earlier in the drive did not latch the restarted selfdrived")

  # C12 card gate
  plugins.PLUGINS = default_plugins()
  gate = core_host.CardGate(Params())
  if not gate.alive() or gate.sm is not None:
    errors.append("C12 card gate active with the default owners")
  plugins.PLUGINS += (role_plugin("rep_eng", core_host.ENGAGEMENT, "engagement", engagement(Scripted())),)
  gate = core_host.CardGate(Params(), sm=types.SimpleNamespace(update=lambda t: None, alive={"selfdriveState": False}))
  if gate.alive():
    errors.append("C12 card sends while selfdriveState is not alive and a replacement owns a role")
  card = (ROOT / "openpilot/selfdrive/car/card.py").read_text()
  if "self.sm.all_alive(['carControl']) and self.plugins.core_alive()" not in card:
    errors.append("C12 card.py does not gate CI.apply on plugins.core_alive()")
  sd = (ROOT / "openpilot/selfdrive/selfdrived/selfdrived.py").read_text()
  if "plugins.install_core(self)" not in sd:
    errors.append("C1 selfdrived.py does not call plugins.install_core(self)")

  print(json.dumps({"errors": errors}, indent=1))
  return 1 if errors else 0


if __name__ == "__main__":
  sys.exit(main())
