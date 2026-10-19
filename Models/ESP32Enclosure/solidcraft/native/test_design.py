"""Frozen original-CAD regression checks for native SolidCraft documents.

Expected measurements come from revision014's preserved Python/OCCT geometry.
Tolerance covers tessellated native measurements; independent exact STEP XOR
checks in validation.json use the stricter 0.001 mm³ limit.
"""
from pathlib import Path
import json,math,subprocess,sys,tempfile,hashlib
import pytest
ROOT=Path(__file__).parent/'revision-014'
MANIFEST=json.loads((ROOT/'manifest.json').read_text())
sys.path.insert(0,str(ROOT.parent/'scripts'))
from fuse_exports import physical_parts

@pytest.mark.parametrize('doc',MANIFEST['documents'],ids=lambda d:d['path'])
def test_native_history_and_frozen_geometry(doc):
 design=json.loads((ROOT/doc['path']).read_text())
 types={f['type'] for f in design['features']}
 assert 'import' not in types
 assert {'sketch','extrude'}<=types
 assert design['params'] and design['favorites']
 done=subprocess.run(['solidcraft-cli','eval',str(ROOT/doc['path'])],capture_output=True,text=True)
 assert done.returncode==0,done.stderr
 state=json.loads(done.stdout);bodies={b['name']:b for b in state['bodies']}
 assert set(bodies)==set(doc['native_body_names'])
 assert hashlib.sha256((ROOT/doc['path']).read_bytes()).hexdigest()==doc['design_sha256']
 groups=json.loads((ROOT/doc['groups']).read_text())
 if any(len(names)>1 for names in groups.values()):
  with tempfile.TemporaryDirectory(prefix='native-regression-') as tmp:
   raw=Path(tmp)/'actual.step'
   exported=subprocess.run(['solidcraft-cli','run','--in',str(ROOT/doc['path']),'--out',str(raw)],capture_output=True,text=True)
   assert exported.returncode==0,exported.stderr
   physical=physical_parts(raw,groups,state)
  bodies={}
  from build123d import CenterOf
  for name,shape in physical.items():
   box=shape.bounding_box();bodies[name]={'volume_mm3':float(shape.volume),'area_mm2':float(shape.area),'center_of_mass':list(shape.center(CenterOf.MASS)),'bbox':{'min':list(box.min),'max':list(box.max)}}
 for name,expected in doc['frozen_reference'].items():
  actual=bodies[name];tol=max(1e-3,1.5e-4*math.dist(expected['bbox']['min'],expected['bbox']['max']))
  assert actual['volume_mm3']==pytest.approx(expected['volume_mm3'],rel=5e-4)
  assert actual['area_mm2']==pytest.approx(expected['area_mm2'],rel=5e-4)
  assert actual['center_of_mass']==pytest.approx(expected['center_of_mass'],abs=tol)
  assert actual['bbox']['min']==pytest.approx(expected['bbox']['min'],abs=tol)
  assert actual['bbox']['max']==pytest.approx(expected['bbox']['max'],abs=tol)
 states=json.loads((ROOT/doc['inspection']).read_text())[-1]
 assert not any(f.get('error') or f.get('warning') for f in states['timeline'])
 assert states['sketches'] and all(s['dof']==0 and s['status']=='solved' for s in states['sketches'])

def test_independent_export_and_range_reports():
 report=json.loads((ROOT/'validation.json').read_text())
 assert report['status']=='passed'
 assert len(report['documents'])==len(MANIFEST['documents'])==21
 for d in report['documents']:
  assert d['exact_reference']['xor_mm3']<=1e-3
  assert d['native_opens_without_external_files']
 walk=json.loads((ROOT/'parameter-checks/enclosure/validation.json').read_text())
 assert walk['status']=='passed'
 assert len(walk['cases'])==33
 if walk.get('artifacts_archive'):
  archive=ROOT/'parameter-checks/enclosure'/walk['artifacts_archive']
  assert hashlib.sha256(archive.read_bytes()).hexdigest()==walk['archive_sha256']
  assert walk['native_design_sha256']==hashlib.sha256((ROOT/'enclosure.json').read_bytes()).hexdigest()
 for c in walk['cases']:
  assert c['comparison']['xor_mm3']<=1e-3
  assert c['all_sketches_dof_zero'] and c['timeline_clean']
