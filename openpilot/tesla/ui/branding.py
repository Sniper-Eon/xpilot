"""Shared cached bitmap identity for software startup and parked displays."""

from functools import lru_cache
import pyray as rl
from openpilot.system.ui.lib.application import ASSETS_DIR, FONT_SCALE, GL_VERSION, gui_app
from openpilot.system.ui.widgets import Widget
from .brand_layout import contain

LOGO_ASSET = "branding/xpilot.png"
# Source pixel bounds of the transparent asset; updated with the selected image.
INK_RECT = (144, 187, 1948, 379)
LOGO_ASPECT = INK_RECT[2] / INK_RECT[3]


@lru_cache(maxsize=1)
def _logo_texture():
  if not ASSETS_DIR.joinpath(LOGO_ASSET).is_file():
    return None
  try:
    texture = gui_app.texture(LOGO_ASSET)
    return texture if texture.id and texture.width > 0 and texture.height > 0 else None
  except (OSError, ValueError, RuntimeError):
    return None


@lru_cache(maxsize=1)
def _logo_shader():
  # Render the supplied alpha silhouette; the original PNG remains byte-identical.
  vertex = GL_VERSION + """
in vec3 vertexPosition;
in vec2 vertexTexCoord;
in vec4 vertexColor;
uniform mat4 mvp;
out vec2 fragTexCoord;
out vec4 fragColor;
void main() {
  fragTexCoord = vertexTexCoord;
  fragColor = vertexColor;
  gl_Position = mvp * vec4(vertexPosition, 1.0);
}
"""
  fragment = (
    GL_VERSION
    + """
in vec2 fragTexCoord;
in vec4 fragColor;
uniform sampler2D texture0;
out vec4 finalColor;
void main() {
  float alpha = smoothstep(0.035, 0.98, texture(texture0, fragTexCoord).a);
  finalColor = vec4(1.0, 1.0, 1.0, alpha * fragColor.a);
}
"""
  )
  try:
    shader = rl.load_shader_from_memory(vertex, fragment)
    return shader if shader.id else None
  except (OSError, ValueError, RuntimeError, TypeError):
    return None


def draw_logo(rect):
  texture = _logo_texture()
  if texture is not None:
    target = contain((rect.x, rect.y, rect.width, rect.height), INK_RECT[2] / INK_RECT[3])
    shader = _logo_shader()
    if shader is not None:
      rl.begin_shader_mode(shader)
      try:
        rl.draw_texture_pro(texture, rl.Rectangle(*INK_RECT), rl.Rectangle(*target), rl.Vector2(0, 0), 0, rl.WHITE)
      finally:
        rl.end_shader_mode()
    else:
      # A missing GPU effect must not hide the identity during startup.
      rl.draw_rectangle_rec(rl.Rectangle(*target), rl.WHITE)
      rl.draw_texture_pro(texture, rl.Rectangle(*INK_RECT), rl.Rectangle(*target), rl.Vector2(0, 0), 0, rl.WHITE)
  elif rect.width > 0 and rect.height > 0:
    rl.draw_text_ex(gui_app.font(), "xpilot", rl.Vector2(rect.x, rect.y), min(48, rect.height * 0.8) / FONT_SCALE, 0, rl.WHITE)


class LogoLabel(Widget):
  """Keep mici's original version/footer layout and touch routing."""

  font_size = 108

  def __init__(self):
    super().__init__()
    self.set_rect(rl.Rectangle(0, 0, 480, 108))
    self.set_enabled(False)

  def _render(self, rect):
    draw_logo(rl.Rectangle(rect.x, rect.y + 16, rect.width, 88))
