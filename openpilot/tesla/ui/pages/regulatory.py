"""Regulatory page (native): selfdrive/assets/offroad/mici_fcc.html with the FCC logo, scrollable, like mici MiciFccModal.
Accents are stripped from the html so only ASCII is drawn."""
import os
import unicodedata

import pyray as rl

from openpilot.common.basedir import BASEDIR
from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.lib.scroll_panel import GuiScrollPanel
from openpilot.system.ui.widgets import Widget
from openpilot.system.ui.widgets.html_render import HtmlRenderer

FCC_HTML = os.path.join(BASEDIR, "openpilot/selfdrive/assets/offroad/mici_fcc.html")
PAD = 40


class RegulatoryPage(Widget):
  def __init__(self):
    super().__init__()
    with open(FCC_HTML) as f:
      text = unicodedata.normalize("NFKD", f.read()).encode("ascii", "ignore").decode()
    self._content = HtmlRenderer(text=text)
    self._logo = gui_app.texture("icons_mici/settings/device/fcc_logo.png", 76, 64)
    self._scroll = GuiScrollPanel()

  def show_event(self):
    super().show_event()

  def _render(self, rect: rl.Rectangle):
    width = rect.width - 2 * PAD
    content = rl.Rectangle(rect.x + PAD, rect.y, width, self._logo.height + PAD + self._content.get_total_height(int(width)))
    content.y += self._scroll.update(rect, content)
    rl.begin_scissor_mode(int(rect.x), int(rect.y), int(rect.width), int(rect.height))
    rl.draw_texture_ex(self._logo, rl.Vector2(content.x, content.y + PAD), 0.0, 1.0, rl.WHITE)
    self._content.render(rl.Rectangle(content.x, content.y + self._logo.height + PAD, width, content.height))
    rl.end_scissor_mode()
