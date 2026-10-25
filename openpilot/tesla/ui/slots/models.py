"""Models tile of the SP model manager; hidden while another plugin owns role:perception.model."""
from openpilot.tesla.ui.pages.models import ModelsPage
from openpilot.tesla.ui.slots.settings import _Settings
from openpilot.tesla.ui.tiles import TileSpec


class ModelsTile(_Settings):
  SPEC = TileSpec("models", "Models", sizes=("small", "medium", "wide"), show="offroad", order=4)
  PAGE = ModelsPage
  ICON = "icons_mici/chestnut.png"
