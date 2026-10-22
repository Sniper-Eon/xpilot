"""xpilot plugins, found from each openpilot/tesla/plugins/<id>/plugin.json, and the small hosts SP processes call.

- Active plugins: enabled (ENABLE_PARAM) and winning every exclusive claim (manifest.resolve: lower priority, then id).
- Claims are enforced: CAN sends outside the plugin's can.tx claims, or long_target / plan_filter / processes without
  their claim, drop the plugin (recorded like a fault).
- Fault isolation: a plugin that raises in any hook is logged, recorded in Params XpilotPluginFaults (shown on the
  Plugins page) and dropped for the rest of the process; the other plugins and SP carry on.
"""
import importlib
import time

from openpilot.common.swaglog import cloudlog
from openpilot.tesla import manifest as mf
from openpilot.tesla.plugin import Plugin

FAULTS_PARAM = "XpilotPluginFaults"


def _discover() -> tuple[tuple, dict[str, str]]:
  manifests, errors = mf.load_all()
  classes = []
  for m in manifests:
    module, name = m.entry.split(":")
    try:
      cls = getattr(importlib.import_module(f"{__name__}.{m.id}.{module}"), name)
      if not (isinstance(cls, type) and issubclass(cls, Plugin)):
        raise TypeError(f"{m.entry} is not a Plugin subclass")
    except Exception as e:
      cloudlog.exception(f"xpilot plugin {m.id} failed to import")
      errors[m.id] = f"import: {e!r}"[:200]
      continue
    cls.NAME, cls.TITLE, cls.DESCRIPTION, cls.CATEGORY = m.id, m.name, m.description, m.category
    cls.PRIORITY, cls.ENABLE_PARAM, cls.CLAIMS, cls.SETTINGS, cls.MANIFEST = m.priority, m.enable_param, m.claims, m.settings, m
    classes.append(cls)
  return tuple(classes), errors


PLUGINS, LOAD_ERRORS = _discover()  # PLUGINS in (category, priority, id) order


def is_enabled(cls, params) -> bool:
  return cls.ENABLE_PARAM is None or params.get_bool(cls.ENABLE_PARAM)


def active(params) -> list:
  """Enabled plugins that win their exclusive claims, in PLUGINS order."""
  names, _ = resolve(params)
  return [cls for cls in PLUGINS if cls.NAME in names]


def resolve(params) -> tuple[set[str], dict[str, str]]:
  """(active names, {losing name: winning name}) for the current enable switches."""
  return mf.resolve([(c.NAME, c.PRIORITY, c.CLAIMS) for c in PLUGINS], {c.NAME for c in PLUGINS if is_enabled(c, params)})


def record_fault(name: str, where: str, exc: Exception) -> None:
  cloudlog.exception(f"xpilot plugin {name} failed in {where}, disabled")
  try:
    from openpilot.common.params import Params
    params = Params()
    faults = params.get(FAULTS_PARAM) or {}
    faults[name] = f"{where}: {exc!r}"[:200]
    params.put(FAULTS_PARAM, faults)
  except Exception:
    cloudlog.exception("could not record plugin fault")


class CarPlugins:
  """card host: forwards each hook to every live plugin, in PLUGINS order."""

  def __init__(self, CP, params):
    self.plugins = []
    if CP.brand != "tesla":
      return
    for cls in active(params):
      try:
        self.plugins.append(cls(CP, params))
      except Exception as e:
        record_fault(cls.NAME, "card.__init__", e)

  def _each(self, hook: str, *args) -> list:
    out = []
    for p in list(self.plugins):
      try:
        out.append(getattr(p, hook)(*args))
      except Exception as e:
        self.plugins.remove(p)
        record_fault(p.NAME, f"card.{hook}", e)
    return out

  def setup(self, CP_SP) -> None:
    self._each("setup", CP_SP)

  def _sends(self, hook: str, *args) -> list:
    """Like _each, but every CanData must match one of the plugin's can.tx claims, else the plugin is dropped."""
    out = []
    for p in list(self.plugins):
      try:
        sends = list(getattr(p, hook)(*args))
        allowed = mf.can_tx(p.CLAIMS)
        if bad := [s for s in sends if (s[0], s[2]) not in allowed]:
          raise PermissionError(f"unclaimed CAN send 0x{bad[0][0]:X} bus {bad[0][2]}")
      except Exception as e:
        self.plugins.remove(p)
        record_fault(p.NAME, f"card.{hook}", e)
        continue
      out += sends
    return out

  def observe_can(self, can_list) -> list:
    return self._sends("observe_can", can_list, time.monotonic_ns())

  def publish_state(self, CS_SP) -> None:
    self._each("publish_state", CS_SP)

  def control_sends(self, CS, CC, now_ns: int) -> list:
    return self._sends("control_sends", CS, CC, now_ns)

  def service_params(self, params) -> None:
    self._each("service_params", params)


def processes() -> list:
  """manager: each plugin process runs only while its plugin is active, and only if the plugin claims it."""
  procs = []
  for cls in PLUGINS:
    for proc in cls.processes():
      if f"process:{proc.name}" not in cls.CLAIMS:
        cloudlog.error(f"xpilot plugin {cls.NAME}: process {proc.name} not claimed, not started")
        continue
      should_run = proc.should_run
      proc.should_run = lambda started, params, CP, run=should_run, name=cls.NAME: name in resolve(params)[0] and run(started, params, CP)
      procs.append(proc)
  return procs


def plan_services() -> list[str]:
  return [svc for p in PLUGINS for svc in p.PLAN_SERVICES]


def long_targets(CP, params) -> list:
  """plannerd: one target object per enabled plugin that has one."""
  if CP.brand != "tesla":
    return []
  targets = []
  for cls in active(params):
    try:
      if (t := cls.long_target(CP, params)) is not None:
        if "long.target" not in cls.CLAIMS:
          raise PermissionError("long_target without a long.target claim")
        t.plugin_name = cls.NAME
        targets.append(t)
    except Exception as e:
      record_fault(cls.NAME, "plannerd.long_target", e)
  return targets


def apply_long_targets(targets: list, sm, candidates: dict, v_ego: float, a_ego: float, v_cruise: float) -> dict:
  """SP update_targets: add plugin speed targets to SP's {source: (v, a)} candidates, from which SP takes the min.
  Lower targets join as xpilotPlugin. Higher ones may only replace the cruise (driver set speed) candidate while
  engaged with no gas, brake or override; the lowest raise wins and is capped at V_CRUISE_MAX."""
  from openpilot.cereal import custom
  from openpilot.common.constants import CV
  from openpilot.selfdrive.car.cruise import V_CRUISE_MAX
  source = custom.LongitudinalPlanSP.LongitudinalPlanSource
  lower, raises = [], []
  for t in list(targets):
    try:
      v = t.update(sm, v_ego, v_cruise)
    except Exception as e:
      targets.remove(t)
      record_fault(getattr(t, "plugin_name", "?"), "plannerd.long_target.update", e)
      continue
    if v is not None and v == v:  # not None, not NaN
      (lower if v < v_cruise else raises).append(max(float(v), 0.0))
  if lower:
    candidates[source.xpilotPlugin] = (min(lower), a_ego)
  cc, cs = sm['carControl'], sm['carState']
  if raises and cc.enabled and not cc.cruiseControl.override and not cs.gasPressed and not cs.brakePressed:
    candidates[source.cruise] = (min(min(raises), V_CRUISE_MAX * CV.KPH_TO_MS), a_ego)
  return candidates


def plan_filters(CP, params) -> list:
  if CP.brand != "tesla":
    return []
  filters = []
  for cls in active(params):
    try:
      if (f := cls.plan_filter(CP, params)) is not None:
        if "plan.filter" not in cls.CLAIMS:
          raise PermissionError("plan_filter without a plan.filter claim")
        f.plugin_name = cls.NAME
        filters.append(f)
    except Exception as e:
      record_fault(cls.NAME, "plannerd.plan_filter", e)
  return filters


class _GuardedSink:
  """Runs one plan filter; if it raises, drops it and still publishes the message (filters only tighten).
  ponytail: the message may carry the filter's partial (tighter) edits for that one cycle, and is sent twice
  if the filter raised after its own send; track sends in the inner sink if that ever matters."""

  def __init__(self, inner, sink, f, filters):
    self._inner, self._sink, self._f, self._filters = inner, sink, f, filters

  def __getattr__(self, name):
    return getattr(self._inner, name)

  def send(self, service, msg) -> None:
    try:
      self._sink.send(service, msg)
    except Exception as e:
      if self._f in self._filters:
        self._filters.remove(self._f)
        record_fault(getattr(self._f, "plugin_name", "?"), f"plannerd.{service}", e)
      self._inner.send(service, msg)


def plan_sink(filters, pm, sm):
  sink = pm
  for f in list(filters):
    try:
      sink = _GuardedSink(sink, f.publisher(sink, sm), f, filters)
    except Exception as e:
      filters.remove(f)
      record_fault(getattr(f, "plugin_name", "?"), "plannerd.publisher", e)
  return sink
