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

The card occupies that same icon box (the slot left after the arrow was drawn
at 0.80 of the original stroke). The ring and the distance sit inside it, so
the card does not grow past the slot. On the C3 side column the slot is 272 px;
on the bottom strip it is 200 px. ``card_layout`` is the exact split.
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


def _samples(p0, p1, n):
  return [(p0[0] + (p1[0] - p0[0]) * i / n, p0[1] + (p1[1] - p0[1]) * i / n) for i in range(n + 1)]


def _cubic(p0, p1, p2, p3, n=28):
  """Cubic Bezier. Enough segments that a 122 px glyph has no visible facets."""
  pts = []
  for i in range(n + 1):
    t = i / n
    u = 1 - t
    pts.append((u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
                u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1]))
  return pts


def _arc(cx, cy, radius, a0, a1, n=32):
  """Screen arc. Angle 0 is east, increasing clockwise because y grows downward."""
  return [(cx + radius * math.cos(a0 + (a1 - a0) * i / n),
           cy + radius * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


def _chain(*parts):
  pts = list(parts[0])
  for part in parts[1:]:
    if pts and part and abs(pts[-1][0] - part[0][0]) < 1e-6 and abs(pts[-1][1] - part[0][1]) < 1e-6:
      pts.extend(part[1:])
    else:
      pts.extend(part)
  return pts


def _mirror(strokes):
  return [([(1 - x, y) for x, y in pts], dim, head) for pts, dim, head in strokes]


def _turn(side):
  """Rounded L. side +1 bends right, matching the reference right turn."""
  cx, cy, radius = 0.50, 0.50, 0.22
  stem = _samples((cx - side * radius, 0.88), (cx - side * radius, cy), 8)
  # Enter the west point heading up and leave the north point heading right (or the mirror).
  a0, a1 = (math.pi, math.pi * 1.5) if side > 0 else (0.0, -math.pi * 0.5)
  bend = _arc(cx, cy, radius, a0, a1, 28)
  tip = (cx + side * 0.36, cy - radius)
  return [_chain(stem, bend, _samples(bend[-1], tip, 6))]


def _u_turn(side):
  """Rounded hook. side +1 is the reference shape mirrored: arrow returns downward."""
  cx, cy, radius = 0.50, 0.42, 0.20
  stem = _samples((cx + side * radius, 0.84), (cx + side * radius, cy), 8)
  a0, a1 = (0.0, -math.pi) if side > 0 else (math.pi, math.pi * 2)
  bend = _arc(cx, cy, radius, a0, a1, 32)
  tip = (cx - side * radius, 0.80)
  return [_chain(stem, bend, _samples(bend[-1], tip, 6))]


# Each stroke is (points in 0..1 with y down, dim, filled head on the last point).
# dim marks the road not taken. Curves are sampled; nothing is a sharp elbow.
def _bright(pts, head=True):
  return (pts, False, head)


def _dim(pts, head=False):
  return (pts, True, head)


_RIGHT = {
  'slight_right': [_bright(_cubic((0.38, 0.90), (0.40, 0.52), (0.58, 0.28), (0.78, 0.14)))],
  'turn_right': [_bright(path) for path in _turn(1)],
  'sharp_right': [_bright(_cubic((0.28, 0.88), (0.28, 0.26), (0.58, 0.12), (0.84, 0.62)))],
  'keep_right': [
    _dim(_cubic((0.50, 0.62), (0.50, 0.44), (0.34, 0.30), (0.22, 0.20))),
    _bright(_chain(_samples((0.50, 0.90), (0.50, 0.62), 6),
                   _cubic((0.50, 0.62), (0.50, 0.40), (0.66, 0.22), (0.82, 0.14)))),
  ],
  'merge_right': [
    _dim(_samples((0.68, 0.90), (0.68, 0.14), 8)),
    _bright(_cubic((0.16, 0.74), (0.34, 0.58), (0.56, 0.30), (0.68, 0.14))),
  ],
  'exit_right': [
    _dim(_samples((0.40, 0.90), (0.40, 0.12), 8), head=True),
    _bright(_cubic((0.40, 0.66), (0.40, 0.42), (0.64, 0.30), (0.88, 0.30))),
  ],
  'ramp_right': [
    _dim(_samples((0.38, 0.90), (0.38, 0.12), 8), head=True),
    _bright(_cubic((0.38, 0.72), (0.38, 0.46), (0.60, 0.38), (0.86, 0.58))),
  ],
}


def _ring(cx, cy, radius):
  return _arc(cx, cy, radius, 0.0, math.tau, 40)


GLYPHS = {
  'straight': [_bright(_samples((0.50, 0.88), (0.50, 0.14), 8))],
  'roundabout': [
    # Dim ring and the crossing roads; one bright exit. The wire value has no clock position.
    _dim(_ring(0.46, 0.52, 0.16)),
    _dim(_samples((0.14, 0.52), (0.30, 0.52), 4)),
    _dim(_samples((0.62, 0.52), (0.78, 0.52), 4)),
    _dim(_samples((0.46, 0.20), (0.46, 0.36), 4)),
    _dim(_samples((0.46, 0.68), (0.46, 0.86), 4)),
    _bright(_samples((0.62, 0.52), (0.90, 0.52), 6)),
  ],
  'destination': [],
  'u_turn_left': [_bright(path) for path in _u_turn(1)],
}
GLYPHS['u_turn_right'] = _mirror(GLYPHS['u_turn_left'])
for _name, _strokes in _RIGHT.items():
  GLYPHS[_name] = _strokes
  GLYPHS[_name.replace('_right', '_left')] = _mirror(_strokes)


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


def _approach(pts, dist=0.07):
  """A point far enough back that a dense curve still has a stable heading."""
  tip = pts[-1]
  prev = pts[0]
  for point in reversed(pts[:-1]):
    if math.hypot(tip[0] - point[0], tip[1] - point[1]) >= dist:
      return point
  return prev


def _soften_corner(corner, toward_a, toward_b, radius):
  """Two edge points and one midpoint. The tip of the arrow is never passed through here."""
  def step(target):
    dx, dy = target[0] - corner[0], target[1] - corner[1]
    mag = math.hypot(dx, dy) or 1.0
    dist = min(radius, mag * 0.45)
    return (corner[0] + dx / mag * dist, corner[1] + dy / mag * dist)
  a, b = step(toward_a), step(toward_b)
  mid = (a[0] * 0.42 + b[0] * 0.42 + corner[0] * 0.16, a[1] * 0.42 + b[1] * 0.42 + corner[1] * 0.16)
  return a, mid, b


def _head_pixels(prev, tip, stroke):
  """Sharp isosceles head. Length and width are multiples of the stroke.

  The shaft ends inside the base so a round cap cannot bulge out behind it.
  Only the two back corners are eased; the tip is a single point.
  """
  dx, dy = tip[0] - prev[0], tip[1] - prev[1]
  mag = math.hypot(dx, dy) or 1.0
  ux, uy = dx / mag, dy / mag
  px, py = -uy, ux
  length = 2.0 * stroke
  half = 1.32 * stroke  # full width 2.64 before the back corners are eased
  base = (tip[0] - ux * length, tip[1] - uy * length)
  left = (base[0] + px * half, base[1] + py * half)
  right = (base[0] - px * half, base[1] - py * half)
  l_tip, l_mid, l_base = _soften_corner(left, tip, right, 0.16 * stroke)
  r_base, r_mid, r_tip = _soften_corner(right, left, tip, 0.16 * stroke)
  polygon = [tip, l_tip, l_mid, l_base, r_base, r_mid, r_tip]
  shaft = (base[0] + ux * 0.70 * stroke, base[1] + uy * 0.70 * stroke)
  return polygon, shaft, base, (ux, uy)


HUD_CYAN = (78, 224, 255)  # the overlay's existing cyan; #4DE0FF is 77, 224, 255


DIM_ALPHA = 0.40  # the road not taken, same hue as the bright cyan


def _pin(cx, cy, radius, tip):
  """Teardrop: the upper bulb, then a sharp point. The hole is drawn separately."""
  # From the lower right, the long way over the top, to the lower left.
  arc = _arc(cx, cy, radius, math.pi * 0.22, math.pi * 0.22 - math.pi * 1.56, 36)
  return arc + [tip]


def glyph_polylines(direction, x, y, size, scale=ARROW_SCALE, weight=1.0):
  """Pixel strokes, filled heads, and stroke width. A stroke is ``(points, dim)``.

  ``weight`` thickens the stroke. Heads are sized from that stroke: about 2.4
  widths across and 2.0 widths long, with a sharp tip. ``fills`` and ``holes``
  are the destination pin.
  """
  kind = resolve_maneuver(direction)
  glyph = float(size) * float(scale)
  ox = x + (size - glyph) / 2
  oy = y + (size - glyph) / 2

  def pix(pt):
    return (ox + pt[0] * glyph, oy + pt[1] * glyph)

  stroke = max(3.0, glyph * 0.065 * weight)
  strokes, heads = [], []
  for pts, dim, head in GLYPHS[kind]:
    if head and len(pts) >= 2:
      polygon, shaft, _base, _axis = _head_pixels(pix(_approach(pts)), pix(pts[-1]), stroke)
      axis = _axis
      kept = []
      for point in (pix(p) for p in pts[:-1]):
        along = (point[0] - shaft[0]) * axis[0] + (point[1] - shaft[1]) * axis[1]
        if along <= 0:
          kept.append(point)
      kept.append(shaft)
      strokes.append((kept, dim))
      heads.append((polygon, dim))
    else:
      strokes.append(([pix(p) for p in pts], dim))
  fills, holes = [], []
  if kind == 'destination':
    fills.append([pix(p) for p in _pin(0.50, 0.34, 0.18, (0.50, 0.86))])
    holes.append([pix(p) for p in _arc(0.50, 0.32, 0.075, 0.0, math.tau, 28)])
  return strokes, heads, stroke, fills, holes


def _color_dim(color, dim):
  import pyray as rl
  alpha = getattr(color, 'a', 255)
  if not dim:
    return color
  return rl.Color(color.r, color.g, color.b, max(1, int(alpha * DIM_ALPHA)))


def _fan(points, color):
  """Filled polygon. Both windings, because a 2D triangle can be culled."""
  import pyray as rl
  vecs = [rl.Vector2(px, py) for px, py in points]
  for i in range(1, len(vecs) - 1):
    rl.draw_triangle(vecs[0], vecs[i], vecs[i + 1], color)
    rl.draw_triangle(vecs[0], vecs[i + 1], vecs[i], color)


def arrow(x, y, size, direction, color, scale=ARROW_SCALE, weight=1.0):
  """Vector arrow. Unknown directions use resolve_maneuver and never raise.

  A round cap is only the tail start. The shaft stops inside the head, so no
  circle sits under the tip. Curves are sampled finely enough to stay smooth.
  """
  import pyray as rl
  strokes, heads, stroke, fills, holes = glyph_polylines(direction, x, y, size, scale, weight)
  radius = stroke / 2
  for dim in (True, False):
    paint = _color_dim(color, dim)
    for pts, is_dim in strokes:
      if is_dim != dim or len(pts) < 2:
        continue
      vecs = [rl.Vector2(px, py) for px, py in pts]
      for start, end in zip(vecs, vecs[1:], strict=True):
        rl.draw_line_ex(start, end, stroke, paint)
      rl.draw_circle_v(vecs[0], radius, paint)
    for polygon, is_dim in heads:
      if is_dim != dim:
        continue
      _fan(polygon, paint)
  for polygon in fills:
    _fan(polygon, color)
  hole = rl.Color(6, 10, 16, 255)
  for polygon in holes:
    _fan(polygon, hole)


def card_layout(box):
  """Split one icon-box slot into card, ring, glyph and distance sizes, in px.

  The card is the slot itself. The ring sits above a single distance line, with
  padding so the thicker stroke stays inside the ring. No road name.
  """
  box = float(box)
  pad = max(8.0, round(box * 0.07))
  text_h = max(16.0, round(box * 0.16))
  gap = max(4.0, round(box * 0.03))
  ring = min(box - 2 * pad, box - pad - gap - text_h - pad)
  if ring < 12:
    pad, text_h, gap = 4.0, max(10.0, box * 0.22), 2.0
    ring = max(12.0, box - 2 * pad - gap - text_h)
  thick = max(4.0, round(ring * 0.055))
  glyph = max(24.0, round(ring - 2 * thick - ring * 0.22))
  number = max(22.0, round(text_h * 0.92))
  unit = max(14.0, round(number * 0.62))
  return {
    'card': box, 'pad': pad, 'gap': gap, 'text_h': text_h,
    'ring': ring, 'ring_thick': thick, 'glyph': glyph,
    'number': number, 'unit': unit,
  }


def distance_parts(meters):
  """``('200', 'm')`` or ``('1.2', 'km')``. Missing values are a dash and no unit."""
  if isinstance(meters, bool) or not isinstance(meters, (int, float)) or not math.isfinite(meters) or meters < 0:
    return '--', ''
  if meters >= 1000:
    return f'{meters / 1000:.1f}', 'km'
  return f'{meters:.0f}', 'm'


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


def side_hud_rect(zones):
  """The rectangle NavAssistOverlay paints black and then draws into. None when that layout is unused."""
  view, left, right = zones.get('view'), zones.get('left'), zones.get('right')
  if view is None or left is None or right is None:
    return None
  zone = right if right.width >= left.width else left
  if zone.width < 160 or view.height < 220:
    return None
  return zone.x, view.y, zone.width, view.height


def _fill(x, y, w, h):
  """Opaque black over the overlay's own black panel, so its arrow and distance cannot show through glass."""
  import pyray as rl
  rl.draw_rectangle(int(math.floor(x)), int(math.floor(y)), int(math.ceil(w)), int(math.ceil(h)), rl.BLACK)


def draw_nav_card(x, y, box, maneuver, meters):
  """Frosted card: cyan ring, bold maneuver glyph, distance centered under the ring."""
  import pyray as rl
  from openpilot.system.ui.lib.application import FontWeight
  from openpilot.tesla.ui.tile import text, text_w
  spec = card_layout(box)
  rect = rl.Rectangle(x, y, spec['card'], spec['card'])
  rl.draw_rectangle_rounded(rect, 0.16, 12, rl.Color(8, 14, 22, 108))
  # Sheen only in the top padding, above the ring, so it does not stripe the glyph.
  rl.begin_scissor_mode(int(x), int(y), int(spec['card']), int(spec['pad'] + 6))
  rl.draw_rectangle_rounded(rect, 0.16, 12, rl.Color(255, 255, 255, 36))
  rl.end_scissor_mode()
  inset = 2.0
  inner = rl.Rectangle(x + inset, y + inset, spec['card'] - 2 * inset, spec['card'] - 2 * inset)
  rl.draw_rectangle_rounded_lines_ex(inner, 0.16, 12, 5, rl.Color(*HUD_CYAN, 32))
  rl.draw_rectangle_rounded_lines_ex(rect, 0.16, 12, 1.5, rl.Color(255, 255, 255, 64))
  ring = spec['ring']
  cx = x + spec['card'] / 2
  cy = y + spec['pad'] + ring / 2
  center = rl.Vector2(cx, cy)
  rl.draw_ring(center, ring / 2 - 1, ring / 2 + 11, 0, 360, 48, rl.Color(*HUD_CYAN, 28))
  rl.draw_ring(center, ring / 2 - 1, ring / 2 + 5, 0, 360, 48, rl.Color(*HUD_CYAN, 56))
  rl.draw_ring(center, ring / 2 - spec['ring_thick'], ring / 2, 0, 360, 64, rl.Color(*HUD_CYAN, 255))
  glyph = spec['glyph']
  arrow(cx - glyph / 2, cy - glyph / 2, glyph, maneuver, rl.Color(*HUD_CYAN, 255), scale=1, weight=1.85)
  number, unit = distance_parts(meters)
  num_size, unit_size = int(spec['number']), int(spec['unit'])
  number_w = text_w(FontWeight.BOLD, number, num_size)
  unit_w = text_w(FontWeight.BOLD, unit, unit_size) if unit else 0
  gap = 6 if unit else 0
  text_x = cx - (number_w + gap + unit_w) / 2
  text_y = cy + ring / 2 + spec['gap']
  text(FontWeight.BOLD, number, text_x, text_y, num_size, rl.WHITE)
  if unit:
    text(FontWeight.BOLD, unit, text_x + number_w + gap, text_y + (num_size - unit_size) * 0.82, unit_size,
         rl.Color(255, 255, 255, 230))


def repaint_guidance_arrow(zones, covered):
  """Cover the installed overlay's arrow and distance, then draw the glass card.

  ``covered`` means the host route panel already owns the side column. The
  overlay cannot be changed from here (its repo is not writable), so the card
  is painted after it. The overlay fills its panel with opaque black first;
  this pass fills that same panel again, which removes the old arrow, the old
  distance, and any road-name line, then draws only the card.
  """
  try:
    nav = _fresh_nav()
    maneuver = maneuver_to_draw(nav)
    if maneuver is None or not zones:
      return
    side = side_hud_rect(zones)
    if side is not None:
      if covered:
        return
      _fill(*side)
      origin = side_icon_origin(zones)
      draw_nav_card(*origin, maneuver, nav.get('distanceM'))
      return
    bottom = zones.get('bottom')
    origin = bottom_icon_origin(zones)
    if bottom is None or origin is None:
      return
    _fill(bottom.x, bottom.y, bottom.width, bottom.height)
    draw_nav_card(*origin, maneuver, nav.get('distanceM'))
  except Exception:
    if not repaint_guidance_arrow.logged:
      repaint_guidance_arrow.logged = True
      from openpilot.common.swaglog import cloudlog
      cloudlog.exception('guidance arrow')


repaint_guidance_arrow.logged = False
