"""Fuse a physical part's native structural bodies for manufacturing exports.

SolidCraft 0.16.2 has failing curved-shell Booleans. The editable document keeps
its constrained structural bodies. This export-only OCCT step joins their actual
STEP geometry, never imports an oracle, and refuses invalid/disconnected parts.
"""
from pathlib import Path
import argparse,json,sys
PACKAGE=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(PACKAGE/'src'))
import fdm_cad.build
from build123d import Compound,import_step,export_step
from cad_mesh import export_print_mesh

def leaves(shape):
 if shape.children:
  for child in shape.children:yield from leaves(child)
 else:yield shape

def physical_parts(raw_step,groups,state=None):
 raw=import_step(raw_step)
 if any(not s.is_valid or float(s.volume)<=0 for s in raw.solids()):raise AssertionError('Invalid native STEP structural solid')
 by_name={s.label:s for s in leaves(raw)}
 expected={n for names in groups.values() for n in names}
 if set(by_name)!=expected or any(len(v.solids())!=1 for v in by_name.values()):
  if len(groups)==1:by_name={};single_group=list(raw.solids())
  else:single_group=None
  if state is not None:
   import numpy as np
   from scipy.optimize import linear_sum_assignment
   bodies=state['bodies'];solids=list(raw.solids())
   if {b['name'] for b in bodies}!=expected:raise AssertionError('Update physical part groups after adding or renaming native bodies')
   if len(bodies)!=len(solids):raise AssertionError('Native STEP solid count does not match inspection')
   def bounds(shape):
    box=shape.bounding_box();return np.array([list(box.min),list(box.max)])
   solid_bounds=[bounds(s) for s in solids];solid_volumes=[float(s.volume) for s in solids]
   costs=np.array([[np.max(np.abs(np.array([b['bbox']['min'],b['bbox']['max']])-bound))+abs(b['volume_mm3']-volume)/max(volume,1) for bound,volume in zip(solid_bounds,solid_volumes)] for b in bodies])
   rows,cols=linear_sum_assignment(costs)
   if max(costs[i,j] for i,j in zip(rows,cols))>.05:raise AssertionError('Native STEP body assignment is ambiguous or drifted')
   by_name={bodies[i]['name']:solids[j] for i,j in zip(rows,cols)};single_group=None
  elif single_group is None:raise AssertionError('Native STEP omits body labels; supply its inspection')
 else:single_group=None
 result={}
 for name,members in groups.items():
  solids=list(single_group) if single_group is not None else []
  for member in ([] if single_group is not None else members):
   shape=by_name[member]
   if not shape.is_valid:raise AssertionError('Invalid native structural body: '+member)
   solids.extend(shape.solids())
  joined=solids[0]
  for next_solid in solids[1:]:
   candidate=next_solid.fuse(joined).clean()
   if not candidate.is_valid:
    candidate=joined.fuse(next_solid).clean()
   if not candidate.is_valid:raise AssertionError('Invalid export union while assembling '+name)
   joined=candidate
  if not hasattr(joined,'solids') or len(joined.solids())!=1 or not joined.is_valid or float(joined.volume)<=0:raise AssertionError('Physical part must be one valid solid: '+name)
  shape=joined.solids()[0];shape.label=name;result[name]=shape
 return result

def normalize(raw_step,groups,step,mesh=None,state=None):
 parts=physical_parts(raw_step,groups,state);export_step(Compound(children=list(parts.values())),step)
 if mesh:
  reopened=import_step(step);named={p.label:p for p in leaves(reopened)}
  if set(named)!=set(parts):raise AssertionError('Normalized STEP lost physical part names')
  export_print_mesh(named,mesh,{p['name']:p['value'] for p in state.get('params',[]) if p.get('value') is not None} if state else None)
 return parts

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('design',type=Path,help='Saved native .json or .solidcraft');p.add_argument('--groups',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 import subprocess
 dest=a.output.resolve()
 if dest.exists():raise ValueError('Use a new output directory')
 dest.mkdir(parents=True);raw=dest/'native.step'
 script=dest/'inspect.json';script.write_text(json.dumps({'commands':[{'command':'document.inspect','params':{'measure':True,'sketches':True}}]}))
 subprocess.run(['solidcraft-cli','run',str(script),'--in',str(a.design),'--out',str(raw),'--results','--json-out',str(dest/'native-state.json')],check=True,capture_output=True,text=True)
 state=json.loads((dest/'native-state.json').read_text())[-1]
 if any(p.get('error') for p in state.get('params',[])) or any(f.get('error') or f.get('warning') for f in state['timeline']) or any(s['dof'] or s['status']!='solved' for s in state['sketches']):raise AssertionError('Resolve native timeline or sketch issues before exporting')
 normalize(raw,json.loads(a.groups.read_text()),dest/'print.step',dest/'print.3mf',state)
 print(str(dest/'print.3mf'))
if __name__=='__main__':main()
