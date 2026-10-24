"""Keep the events SP's update_events already produced."""
from openpilot.tesla.plugin import Plugin


class SpSafetyFallback(Plugin):
  @classmethod
  def safety_fallback(cls, ctx):
    return cls(ctx.CP, ctx.params)

  def update(self, ctx, CS, names, names_sp):
    return names, names_sp
