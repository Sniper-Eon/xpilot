"""External compute plugin: runs externald, which bridges providers (tcp.py first; an LLM API client can follow)
to cereal externalIn/externalOut. It does not control the car: consumers are other plugins, which must check
freshness (provider.is_fresh) and go through their own hooks and limits. Params: XpilotExternal*."""
from openpilot.tesla.plugin import Plugin


def _always(started, params, CP) -> bool:
  return True


class ExternalCompute(Plugin):

  @classmethod
  def processes(cls) -> list:
    from openpilot.system.manager.process import PythonProcess
    return [PythonProcess("externald", "openpilot.tesla.plugins.external_compute.externald", _always)]
