"""xpilot plugin interface. Rules for writing a plugin: XPILOT.md at the repo root.

One feature = one package openpilot/tesla/plugins/<name>/ (name == NAME):
  plugin.py  a Plugin subclass, listed in openpilot/tesla/plugins/__init__.py
  ui.py      optional: Slot subclasses (big-screen tiles) and HudOverlay subclasses (onroad HUD), found by the UI
SP stays the main stack: SP files only call these hooks. Every hook has a do-nothing default.
The host (plugins/__init__.py) builds only enabled plugins and drops a plugin at its first exception.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Setting:
  """One row on the plugin's settings page. No range/choices: toggle. range=(min, max, step, unit, divisor).
  choices=((label, value), ...). The key must be declared in the plugin's params.json."""
  key: str
  label: str
  range: tuple[int, int, int, str, int] | None = None
  choices: tuple[tuple[str, int], ...] | None = None


class Plugin:
  NAME = ""                        # package directory name
  TITLE = ""                       # shown on the Plugins page
  DESCRIPTION = ""
  ENABLE_PARAM: str | None = None  # BOOL param in params.json; off: not built, no process, no plan filter/target
  SETTINGS: tuple[Setting, ...] = ()
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
