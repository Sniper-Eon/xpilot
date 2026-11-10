"""Maneuver glyphs for the Amap HUD arrow.

The installed navassist overlay draws this arrow, and today that draw is one
left turn or one right turn. The phone resolves Amap's icon integer before
publishing pluginMsg kind ``nav.state``; the payload carries a wire name, never
the raw code. This module paints the matching glyph into the same icon box
after that overlay, so a system update changes the arrow without a plugin
release. The box and the distance text stay where the overlay put them.
Drawing an integer here would mix two incompatible namespaces, so an unexpected
value falls back to a plain arrow instead of being treated as an icon id.

AMap SDK IconType (NavigationMappers.maneuver, NaviInfo.iconType):
  0, 1                 none            no icon / car icon
  2                    turn_left       左转
  3                    turn_right      右转
  4                    slight_left     左前方
  5                    slight_right    右前方
  6                    sharp_left      左后方
  7                    sharp_right     右后方
  8                    u_turn_left     左转掉头
  9, 20                straight        直行 / 顺行
  10, 13, 14, 16       none            途经点 / 服务区 / 收费站 / 隧道
  11, 12, 17, 18, 21-28 roundabout     进入/驶出环岛，含左右侧通行的小环岛
  15                   destination     到达目的地
  19                   u_turn_right    右转掉头
  65                   merge_left      靠左
  66                   merge_right     靠右
  anything else        unknown
SDK road type then rewrites a directional maneuver, same file:
  RoadType 9 (exit)                 -> exit_left / exit_right
  RoadType 6, 8, 10, 56, 58 (ramp)  -> ramp_left / ramp_right
Straight, roundabout, destination, none and unknown are left unchanged.

AMap Auto broadcast ICON (AmapAutoBroadcast.autoManeuver). This namespace is
not SDK IconType; ICON 1 is straight there and the car icon in the SDK table.
  1                    straight
  4                    merge_left on ROAD_TYPE 0 or 6, otherwise slight_left
  5                    merge_right on ROAD_TYPE 0 or 6, otherwise slight_right
  9                    u_turn_right
  10                   keep_left
  11                   keep_right
  12, 13               roundabout
  anything else        the SDK table above
keep_left / keep_right exist only on that Auto path (SDK has no separate keep).

The icon box the HUD passes in is unchanged. The glyph is ARROW_SCALE of that
box, centered, so the distance text stays on the same row. The previous stroke
filled the box (scale 1). 0.80 is 20% smaller: a 200 px box draws a 160 px
glyph, and the side column's max(40, min(width-28, height*0.50)) box draws
four fifths of that. Lane ticks pass scale 1 because they are already small.
"""
import math


ARROW_SCALE = 0.80

# Shown in the route list. none/unknown are not instructions.
DISPLAY_MANEUVERS = frozenset((
  'straight', 'slight_left', 'slight_right', 'turn_left', 'turn_right',
  'sharp_left', 'sharp_right', 'u_turn_left', 'u_turn_right', 'keep_left',
  'keep_right', 'merge_left', 'merge_right', 'exit_left', 'exit_right',
  'ramp_left', 'ramp_right', 'roundabout', 'destination',
))


def _loop(cx, cy, radius, steps=28):
  return [
    (cx + radius * math.cos(2 * math.pi * i / steps),
     cy + radius * math.sin(2 * math.pi * i / steps))
    for i in range(steps + 1)
  ]


def _mirror(strokes):
  return [([(1 - x, y) for x, y in pts], head) for pts, head in strokes]


# (points in 0..1 with y down, arrowhead on the last segment). The head marks the
# path being followed; a stroke without one is the road that continues or is not taken.
_LEFT = {
  'slight_left': [(((0.70, 0.88), (0.26, 0.14)), True)],
  'turn_left': [(((0.64, 0.92), (0.64, 0.32), (0.12, 0.32)), True)],
  'sharp_left': [(((0.68, 0.90), (0.68, 0.30), (0.16, 0.74)), True)],
  'u_turn_left': [(((0.72, 0.86), (0.72, 0.38), (0.50, 0.18), (0.28, 0.38), (0.28, 0.72)), True)],
  'keep_left': [
    (((0.50, 0.52), (0.84, 0.30)), False),
    (((0.50, 0.90), (0.50, 0.52), (0.16, 0.14)), True),
  ],
  'merge_left': [
    (((0.32, 0.90), (0.32, 0.12)), False),
    (((0.86, 0.78), (0.40, 0.22)), True),
  ],
  'exit_left': [
    (((0.62, 0.92), (0.62, 0.10)), False),
    (((0.62, 0.58), (0.14, 0.14)), True),
  ],
  'ramp_left': [
    (((0.66, 0.92), (0.66, 0.16)), False),
    (((0.66, 0.58), (0.44, 0.40), (0.14, 0.14)), True),
  ],
}


GLYPHS = {
  'straight': [(((0.50, 0.90), (0.50, 0.18)), True)],
  'roundabout': [
    # Closed ring plus a counterclockwise head. One wire value covers every
    # SDK/Auto roundabout icon, so the exit clock-position is not drawn.
    (_loop(0.50, 0.40, 0.22), False),
    (((0.50, 0.96), (0.50, 0.62)), False),
    (((0.62, 0.36), (0.74, 0.16), (0.84, 0.36)), False),
  ],
  'destination': [
    (_loop(0.50, 0.32, 0.16), False),
    (((0.36, 0.42), (0.50, 0.88)), False),
    (((0.64, 0.42), (0.50, 0.88)), False),
  ],
}
for _name, _strokes in _LEFT.items():
  GLYPHS[_name] = _strokes
  GLYPHS[_name.replace('_left', '_right')] = _mirror(_strokes)


def resolve_maneuver(direction):
  """Wire name, or a plain turn when the text only tells us a side."""
  name = str(direction or '').strip().lower().replace(' ', '_').replace('-', '_')
  if name in GLYPHS:
    return name
  if 'left' in name:
    return 'turn_left'
  if 'right' in name:
    return 'turn_right'
  return 'straight'


def _head(prev, tip):
  dx, dy = tip[0] - prev[0], tip[1] - prev[1]
  mag = math.hypot(dx, dy) or 1.0
  ux, uy = dx / mag, dy / mag
  px, py = -uy, ux
  length = min(0.22, mag * 0.70)
  wing = length * 0.64
  base = (tip[0] - ux * length, tip[1] - uy * length)
  return (
    (base[0] + px * wing, base[1] + py * wing),
    tip,
    (base[0] - px * wing, base[1] - py * wing),
  )


def glyph_polylines(direction, x, y, size, scale=ARROW_SCALE):
  """Pixel polylines and stroke width for the glyph centered in the icon box."""
  kind = resolve_maneuver(direction)
  glyph = float(size) * float(scale)
  ox = x + (size - glyph) / 2
  oy = y + (size - glyph) / 2
  stroke = max(3.0, glyph * 0.065)
  lines = []
  for pts, head in GLYPHS[kind]:
    lines.append([(ox + px * glyph, oy + py * glyph) for px, py in pts])
    if head and len(pts) >= 2:
      lines.append([(ox + px * glyph, oy + py * glyph) for px, py in _head(pts[-2], pts[-1])])
  return lines, stroke


def arrow(x, y, size, direction, color, scale=ARROW_SCALE):
  """Vector arrow. Unknown directions use resolve_maneuver and never raise."""
  import pyray as rl
  lines, stroke = glyph_polylines(direction, x, y, size, scale)
  radius = stroke / 2
  for pts in lines:
    vecs = [rl.Vector2(px, py) for px, py in pts]
    for start, end in zip(vecs, vecs[1:], strict=True):
      rl.draw_line_ex(start, end, stroke, color)
    for point in vecs:
      rl.draw_circle_v(point, radius, color)


def maneuver_to_draw(nav):
  """Maneuver the Amap HUD would currently paint, or None when it draws no arrow."""
  if not isinstance(nav, dict):
    return None
  maneuver = nav.get('maneuver')
  if maneuver in (None, '', 'none'):
    return None
  active = bool(nav.get('valid') or (
    nav.get('linked') and not nav.get('stale', True) and nav.get('routeActive')
    and nav.get('mode') == 'realtime' and maneuver != 'unknown'))
  return maneuver if active else None


def side_icon_origin(zones):
  """Icon box of the side HUD, matching NavAssistOverlay._draw_side. None if that layout is not used."""
  view, left, right = zones.get('view'), zones.get('left'), zones.get('right')
  if view is None or left is None or right is None:
    return None
  zone = right if right.width >= left.width else left
  if zone.width < 160 or view.height < 220:
    return None
  pad = 14
  size = max(40.0, min(zone.width - 2 * pad, view.height * 0.50))
  # The overlay's rect starts at the drive view, not at the top of the side strip.
  return zone.x + (zone.width - size) / 2, view.y + pad, size


def bottom_icon_origin(zones):
  """Icon box of the bottom HUD, matching hud.floating_layout. None if that strip is too small."""
  bottom = zones.get('bottom')
  if bottom is None:
    return None
  width = max(0.0, bottom.width - 32)
  height = max(0.0, bottom.height - 32)
  if width < 1000 or height < 180:
    return None
  side = min(200.0, height - 72)
  return bottom.x + 32, bottom.y + 62, side


def _fresh_nav():
  from openpilot.tesla.plugins import PluginMsgs
  if _fresh_nav.msgs is None:
    _fresh_nav.msgs = PluginMsgs()
  for payload in _fresh_nav.msgs.fresh('nav.state').values():
    if maneuver_to_draw(payload):
      return payload
  return None


_fresh_nav.msgs = None


def displayed_maneuver(fallback):
  """nav.state maneuver when the Amap HUD is live, otherwise the caller's own text."""
  try:
    maneuver = maneuver_to_draw(_fresh_nav())
  except Exception:
    return fallback
  return fallback if maneuver is None else maneuver


def repaint_guidance_arrow(zones, covered):
  """Replace the overlay's left/right arrow. ``covered`` means the host nav panel owns that column."""
  try:
    maneuver = maneuver_to_draw(_fresh_nav())
    if maneuver is None or not zones:
      return
    side = side_icon_origin(zones)
    if side is not None:
      if covered:
        return
      box = side
    else:
      box = bottom_icon_origin(zones)
    if box is None:
      return
    import pyray as rl
    x, y, size = box
    left, top = math.floor(x), math.floor(y)
    rl.draw_rectangle(left, top, math.ceil(x + size) - left, math.ceil(y + size) - top, rl.BLACK)
    arrow(x, y, size, maneuver, rl.Color(78, 224, 255, 255))
  except Exception:
    if not repaint_guidance_arrow.logged:
      repaint_guidance_arrow.logged = True
      from openpilot.common.swaglog import cloudlog
      cloudlog.exception('guidance arrow')


repaint_guidance_arrow.logged = False
