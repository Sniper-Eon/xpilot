"""External compute plugin: runs externald, which bridges providers (tcp.py first; an LLM API client can follow)
to cereal externalIn/externalOut. It does not control the car: consumers are other plugins, which must check
freshness (provider.is_fresh) and go through their own hooks and limits. Params: XpilotExternal*."""
from openpilot.tesla.plugin import Plugin, Setting


def _always(started, params, CP) -> bool:
  return True


class ExternalCompute(Plugin):
  NAME = "external_compute"
  TITLE = "External Compute"
  DESCRIPTION = ("Lets a laptop, LLM server or accelerator exchange data with the device over a cable or WiFi "
                 "(TCP JSON lines). Peers need the token in /data/params/d/XpilotExternalToken.")
  ENABLE_PARAM = "XpilotExternalEnabled"
  SETTINGS = (Setting("XpilotExternalPort", "Port", range=(8770, 8779, 1, "", 1)),)

  @classmethod
  def processes(cls) -> list:
    from openpilot.system.manager.process import PythonProcess
    return [PythonProcess("externald", "openpilot.tesla.plugins.external_compute.externald", _always)]
