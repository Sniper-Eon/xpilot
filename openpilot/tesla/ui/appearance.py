"""Pure parked presentation transform; driving, detail pages and edit mode stay native."""
GLASS_HEADER_H=108
GLASS_SCALE=.86
GLASS_X=(2160-2160*GLASS_SCALE)/2


def park_point(x,y):
  return GLASS_X+x*GLASS_SCALE,GLASS_HEADER_H+y*GLASS_SCALE


def park_inverse(x,y):
  return (x-GLASS_X)/GLASS_SCALE,(y-GLASS_HEADER_H)/GLASS_SCALE


def park_rect(rect):
  x,y,w,h=rect
  a,b=park_point(x,y)
  return a,b,w*GLASS_SCALE,h*GLASS_SCALE
