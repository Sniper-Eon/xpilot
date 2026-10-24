"""Default model role: select SP's model manager and runners with their original conditions."""
from openpilot.tesla.plugin import Plugin


class SpModels(Plugin):
  @classmethod
  def role_processes(cls, role, procs) -> list:
    return list(procs.values()) if role == "role:perception.model" else []
