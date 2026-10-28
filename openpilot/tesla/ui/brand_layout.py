"""Pure geometry for the user-supplied Xpilot brand; no graphics or vehicle IO."""


def contain(rect, aspect):
  x, y, w, h = map(float, rect)
  if w <= 0 or h <= 0 or aspect <= 0:
    return (x, y, 0.0, 0.0)
  width = min(w, h * aspect)
  height = width / aspect
  return (x + (w - width) / 2, y + (h - height) / 2, width, height)


def spinner_layout(width, height, lines=0):
  big = width >= 1000
  logo = 260.0 if big else 86.0
  ring = 64.0 if big else 22.0
  gap = 30.0 if big else 10.0
  font = 72.0 if big else 28.0
  line_height = 82.0 if big else 34.0
  status = max(14.0 if big else 7.0, lines * line_height)
  total = logo + ring + 2 * gap + status
  scale = min(1.0, max(1.0, height - 16) / total)
  logo *= scale
  ring *= scale
  gap *= scale
  status *= scale
  total *= scale
  top = (height - total) / 2
  return dict(
    logo=(width * 0.08, top, width * 0.84, logo),
    spinner=((width - ring) / 2, top + logo + gap, ring, ring),
    status=(width * 0.1, top + logo + gap + ring + gap, width * 0.8, status),
    font=max(10, int(font * scale)),
  )


def saver_size(width, height, small, aspect=4.2):
  w = min(220.0 if small else 860.0, max(1.0, width - 32), max(1.0, height - 32) * aspect)
  return w, w / aspect
