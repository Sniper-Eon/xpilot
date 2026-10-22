"""xpilot plugin interface. Rules for writing a plugin: XPILOT.md at the repo root.

One feature = one package openpilot/tesla/plugins/<id>/, found automatically:
  plugin.json  manifest: id, category, priority, claims, enable switch, settings, params (openpilot/tesla/manifest.py)
  plugin.py    the Plugin subclass named by the manifest's "entry"
  ui.py        optional: Slot subclasses (big-screen tiles) and HudOverlay subclasses (onroad HUD), found by the UI
SP stays the main stack: SP files only call these hooks. Every hook has a do-nothing default.
The host (plugins/__init__.py) builds only enabled plugins that win their claims, refuses unclaimed use,
and drops a plugin at its first exception.
"""
from openpilot.tesla.manifest import Setting  # noqa: F401  (re-exported for settings code)


class Plugin:
  # Filled from plugin.json by the host; do not set them in code.
  NAME = ""
  TITLE = ""
  DESCRIPTION = ""
  CATEGORY = "tools"
  PRIORITY = 100
  ENABLE_PARAM: str | None = None
  CLAIMS: tuple[str, ...] = ()
  SETTINGS: tuple = ()
  MANIFEST = None
  PLAN_SERVICES: tuple[str, ...] = ()  # extra services plannerd must subscribe for plan_filter()

  def __init__(self, CP, params):
    """card: once per car, after fingerprinting. Read Params here or in service_params()."""
    self.CP = CP

  # ---- card ----
  def setup(self, CP_SP) -> None:
    """Car init, before CarParamsSP is published: set CP_SP flags or safetyParam bits for a panda plugin."""

  def observe_can(self, can_list, now_ns: int) -> list:
    """Every CAN batch, read-only. Returns CanData to send at once (rare; prefer control_sends)."""
    return []

  def publish_state(self, CS_SP) -> None:
    """Every carState cycle: fill this plugin's fields of the outgoing carStateSP (capnp builder)."""

  def control_sends(self, CS, CC, now_ns: int) -> list:
    """Every control cycle: extra CanData to send. Each address needs a panda safety plugin."""
    return []

  def service_params(self, params) -> None:
    """~10 Hz in card's params thread: reload live settings."""

  # ---- manager ----
  @classmethod
  def processes(cls) -> list:
    """Extra manager processes (ManagerProcess instances). Import manager code inside, not at module level."""
    return []

  # ---- plannerd ----
  @classmethod
  def long_target(cls, CP, params):
    """None, or an object with update(sm, v_ego, v_cruise) -> target speed m/s or None, called every plan cycle.
    Lower than v_cruise: tightens, like SP's own limiters. Higher: replaces only the driver set speed, and only
    while engaged without gas/brake/override, capped at V_CRUISE_MAX. MPC (leads), model and SP limiters still apply."""
    return None

  @classmethod
  def plan_filter(cls, CP, params):
    """None, or an object with publisher(pm, sm) returning a pm-like sink that may only tighten the plan."""
    return None
