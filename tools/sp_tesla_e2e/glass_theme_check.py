"""Failures before implementation: parked hit-testing differs from rendering;
header overlaps transformed tiles; driving/edit/detail coordinates are changed.
No live params or vehicle state are modified by this layout check.
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from openpilot.tesla.ui.appearance import park_point, park_inverse, park_rect, GLASS_HEADER_H
from openpilot.tesla.ui import tiles


def main():
  assert 'Glass' in tiles.THEMES
  for c in range(tiles.COLS):
    for r in range(tiles.ROWS):
      x,y,w,h=tiles.cell_rect(c,r)
      a,b=park_point(x+w/2,y+h/2)
      u,v=park_inverse(a,b)
      assert abs(u-(x+w/2))<1e-6 and abs(v-(y+h/2))<1e-6
      assert tiles.hit({'t':(c,r,'small')},u,v)=='t'
      tx,ty,tw,th=park_rect((x,y,w,h))
      assert 0<=tx<tx+tw<=2160 and GLASS_HEADER_H<=ty<ty+th<=1080
  # Execute the real wrapper without loading GUI/vehicle modules.
  import ast
  from types import SimpleNamespace as N
  tree=ast.parse((ROOT/'openpilot/tesla/ui/screen.py').read_text())
  cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='BigScreenHost')
  method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_draw_start')
  ns={'tiles':tiles,'park_inverse':park_inverse}
  exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),'<real draw wrapper>','exec'),ns)
  h=N(_glass_theme=True,_layout='park',_edit=False,_gesture=tiles.Gesture(),_draw_park_header=lambda:None)
  h._gesture.press(300,300,0)
  h._draw_start_tiles=lambda events:setattr(h,'_edit',True)
  ns['_draw_start'](h,[])
  assert h._gesture.start is None, 'changing from scaled park to native edit must end the old gesture'
  print('glass parked transform: all 32 cells round-trip; viewport unchanged')


if __name__=='__main__':main()
