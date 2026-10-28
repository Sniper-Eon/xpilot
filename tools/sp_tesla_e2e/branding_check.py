#!/usr/bin/env python3
"""Failures first: branding remains text/old spinner; wide logo is stretched or
cropped; status/progress overlaps it; mici labels cover footer controls; missing
asset crashes boot; device GLES links a default vertex shader of another version.
Exercise actual layout and drawing with fake GPU calls,
then validate the bundled PNG header. No vehicle, settings or live publisher.
"""

import ast, json, struct, sys
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace as N

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from openpilot.tesla.ui.brand_layout import contain, spinner_layout, saver_size


def main():
  for width, height in ((536, 240), (2160, 1080), (1920, 1080)):
    for lines in (0, 1, 2):
      layout = spinner_layout(width, height, lines)
      boxes = [layout[k] for k in ("logo", "spinner", "status")]
      for x, y, w, h in boxes:
        assert x >= 0 and y >= 0 and x + w <= width + 0.01 and y + h <= height + 0.01, (width, height, lines, layout)
      assert layout["logo"][1] + layout["logo"][3] <= layout["spinner"][1]
      assert layout["spinner"][1] + layout["spinner"][3] <= layout["status"][1]
    w, h = saver_size(width, height, width < 1000)
    assert 0 < w <= width and 0 < h <= height
  for rect in ((0, 0, 480, 88), (164, 22, 330, 70), (0, 0, 1200, 250)):
    x, y, w, h = contain(rect, 4.2)
    assert abs(w / h - 4.2) < 1e-6 and x >= rect[0] and y >= rect[1]
  assert contain((0, 0, 0, 0), 4.2) == (0.0, 0.0, 0.0, 0.0)
  path = ROOT / "openpilot/tesla/ui/branding.py"
  tree = ast.parse(path.read_text())
  nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ("_logo_texture", "_logo_shader", "draw_logo")]
  calls = []
  fallback = []

  def load_shader(vertex, fragment):
    assert isinstance(vertex, str) and vertex.startswith("#version 300 es"), "Device shader must provide a matching GLES vertex stage"
    assert fragment.startswith("#version 300 es")
    return N(id=1)

  rl = N(
    ffi=N(NULL=object()),
    Rectangle=lambda *v: N(x=v[0], y=v[1], width=v[2], height=v[3]),
    Vector2=lambda *v: v,
    WHITE="white",
    draw_texture_pro=lambda *a: calls.append(a),
    draw_text_ex=lambda *a: fallback.append(a),
    load_shader_from_memory=load_shader,
    begin_shader_mode=lambda *a: None,
    end_shader_mode=lambda: None,
    draw_rectangle_rec=lambda *a: None,
  )
  app = N(texture=lambda *a: N(id=1, width=2048, height=512), font=lambda *a: "font")
  ns = dict(
    rl=rl,
    gui_app=app,
    contain=contain,
    lru_cache=lru_cache,
    ASSETS_DIR=N(joinpath=lambda *a: N(is_file=lambda: True)),
    GL_VERSION="#version 300 es\nprecision highp float;\n",
    LOGO_ASSET="branding/xpilot.png",
    INK_RECT=(0, 0, 2048, 512),
    FONT_SCALE=1.0,
  )
  exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), str(path), "exec"), ns)
  ns["draw_logo"](rl.Rectangle(0, 0, 480, 88))
  assert len(calls) == 1 and not fallback

  def missing(*args):
    raise OSError("missing asset")

  app.texture = missing
  ns["_logo_texture"].cache_clear()
  ns["draw_logo"](rl.Rectangle(0, 0, 480, 88))
  assert fallback
  image = ROOT / "openpilot/selfdrive/assets/branding/xpilot.png"
  data = image.read_bytes()
  assert data[:8] == b"\x89PNG\r\n\x1a\n"
  width, height, depth, color = struct.unpack("!IIBB", data[16:26])
  assert width >= 1000 and height > 0 and color == 6, (width, height, color)
  print(json.dumps({"layouts": 9, "containment": True, "draw_and_fallback": True, "asset_RGBA": [width, height], "vehicle_io": False}))


if __name__ == "__main__":
  main()
