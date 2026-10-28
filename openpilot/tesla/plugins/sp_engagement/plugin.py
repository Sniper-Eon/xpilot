"""SP's own engagement instances, subject to the same host floors as every role owner."""
from types import SimpleNamespace

from openpilot.tesla.plugin import Plugin


class SpEngagement(Plugin):
  @classmethod
  def engagement(cls, selfdrive):
    return SimpleNamespace(state_machine=selfdrive.state_machine, mads=selfdrive.mads)
