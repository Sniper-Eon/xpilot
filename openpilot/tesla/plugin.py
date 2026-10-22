"""xpilot plugin interface. Rules for writing a plugin: XPILOT.md at the repo root.

One feature = one package openpilot/tesla/plugins/<name>/ whose plugin.py defines a Plugin subclass,
listed in openpilot/tesla/plugins/__init__.py. SP stays the main stack: SP files only call these hooks.
Every hook has a do-nothing default, so a plugin overrides only what it needs.
"""


class Plugin:
  NAME = ""
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
  def plan_filter(cls, CP, params):
    """None, or an object with publisher(pm, sm) returning a pm-like sink that may only tighten the plan."""
    return None
