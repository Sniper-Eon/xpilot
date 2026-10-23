"""OSM map plugin: SP's mapd, mapd_manager and map_osm processes, which publish liveMapDataSP.
The switch is the MapProvider param ("osm" or "none", written by the Tesla settings page), so enable_param is null."""
import os

from openpilot.tesla.plugin import Plugin


def _osm(started, params, CP) -> bool:
  return params.get("MapProvider", return_default=True) == "osm"


class OsmMap(Plugin):

  @classmethod
  def processes(cls) -> list:
    from openpilot.common.hardware.hw import Paths
    from openpilot.sunnypilot.mapd import MAPD_PATH
    from openpilot.system.manager.process import NativeProcess, PythonProcess
    return [
      NativeProcess("mapd", Paths.mapd_root(), ["bash", "-c", f"{MAPD_PATH} > /dev/null 2>&1"],
                    lambda started, params, CP: os.path.exists(Paths.mapd_root()) and _osm(started, params, CP)),
      PythonProcess("mapd_manager", "openpilot.sunnypilot.mapd.mapd_manager", _osm),
      PythonProcess("map_osm", "openpilot.sunnypilot.mapd.live_map_data.standalone", lambda started, params, CP: started and _osm(started, params, CP)),
    ]
