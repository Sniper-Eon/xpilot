"""SP Engagement: the default role:engagement.state plugin. SP's code stays in selfdrived; openpilot/tesla/core_host.py
only steps in when another plugin owns the role."""
from openpilot.tesla.plugin import Plugin


class SpEngagement(Plugin):
  pass
