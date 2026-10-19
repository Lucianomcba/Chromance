"""Check migrated SolidCraft documents against preserved STEP and mesh geometry."""
from __future__ import annotations
import argparse,hashlib,json,math,subprocess,sys,tempfile
from pathlib import Path
import numpy as np
from scipy.optimize import linear_sum_assignment
PACKAGE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(PACKAGE/'src'))
import fdm_cad.build  # initialize OCCT font configuration before importing build123d
from fdm_cad.geometry import load_mesh_instances
import build123d as bd


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def box(shape):
    b=shape.bounding_box();return np.array([list(b.min),list(b.max)])

def cut_volume(a,b):
    result=a-b
    if result is None:return 0.0
    members=[result] if hasattr(result,'solids') else list(result)
    return sum(max(0,float(s.volume)) for m in members for s in m.solids())

def pair_solids(actual,expected):
    if len(actual)!=len(expected):raise AssertionError(('solid count',len(actual),len(expected)))
    # Position and dimensions identify duplicate fasteners/clamps too; volume only ranks ties.
    costs=np.array([[np.max(np.abs(box(a)-box(b)))+abs(float(a.volume)-float(b.volume))/max(float(b.volume),1) for b in expected] for a in actual])
    rows,cols=linear_sum_assignment(costs)
    return [(actual[i],expected[j]) for i,j in zip(rows,cols)]

def compare(actual,expected,tolerance):
    a,b=bd.import_step(actual),bd.import_step(expected)
    for path,shape in ((actual,a),(expected,b)):
        if not shape.is_valid or not shape.solids() or any(not s.is_valid or float(s.volume)<=0 for s in shape.solids()):raise AssertionError(f'Invalid STEP solid in {path}')
    results=[]
    for left,right in pair_solids(list(a.solids()),list(b.solids())):
        only_left=cut_volume(left,right);only_right=cut_volume(right,left)
        results.append({'actual_volume_mm3':float(left.volume),'expected_volume_mm3':float(right.volume),'only_actual_mm3':only_left,'only_expected_mm3':only_right,'xor_mm3':only_left+only_right,'bounds_max_difference_mm':float(np.max(np.abs(box(left)-box(right))))})
    total=sum(x['xor_mm3'] for x in results)
    if total>tolerance:raise AssertionError(f'{actual.name}: xor {total:g} mm3 exceeds {tolerance:g}')
    return {'status':'passed','solid_count':len(results),'xor_mm3':total,'tolerance_mm3':tolerance,'bodies':results}


def mesh_check(path,step,expected_count):
    entries=load_mesh_instances(path)
    bodies=[b for _,mesh in entries for b in mesh.split(only_watertight=False)]
    if len(bodies)!=expected_count:raise AssertionError((str(path),'connected bodies',len(bodies),expected_count))
    if any(not b.is_volume or not b.is_watertight or not b.is_winding_consistent for b in bodies):raise AssertionError(f'Invalid mesh: {path}')
    solids=list(bd.import_step(step).solids())
    costs=np.array([[np.max(np.abs(m.bounds-box(s))) for s in solids] for m in bodies])
    rows,cols=linear_sum_assignment(costs)
    maximum=max(float(costs[i,j]) for i,j in zip(rows,cols))
    if maximum>.05:raise AssertionError(f'Mesh bounds drifted {maximum:g} mm in {path}')
    if any(not math.isclose(float(bodies[i].volume),float(solids[j].volume),rel_tol=.005) for i,j in zip(rows,cols)):raise AssertionError(f'Mesh volume drifted in {path}')
    if any(float(b.bounds[0,2]) < -.05 for b in bodies):raise AssertionError(f'Mesh below print bed: {path}')
    return {'status':'passed','units':'mm','connected_bodies':len(bodies),'watertight':True,'maximum_step_bounds_difference_mm':maximum,'bounds_tolerance_mm':.05,'volume_relative_tolerance':.005}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--xor-tolerance',type=float,default=1e-3)
    args=p.parse_args();root=args.directory.resolve();manifest=json.loads((root/'manifest.json').read_text())
    if args.xor_tolerance<=0:raise ValueError('Positive XOR tolerance required')
    report={'status':'running','solidcraft_version':'0.16.2','conversion_kind':manifest['conversion_kind'],'parametric_feature_history_rebuilt':False,'parameter_walk':'not applicable: imported geometry has no driving SolidCraft parameters','source_files_unchanged':True,'physical_fit_tested':False,'documents':[]}
    for name,expected_hash in manifest['source_files'].items():
        if sha(PACKAGE/name)!=expected_hash:raise AssertionError('Preserved source changed: '+name)
    for doc in manifest['documents']:
        print('CHECK '+doc['path'],flush=True)
        for key,hash_key in [('path','design_sha256'),('native','native_sha256'),('step','step_sha256'),('reference_step','reference_sha256')]:
            if sha(root/doc[key])!=doc[hash_key]:raise AssertionError('Artifact changed: '+doc[key])
        inspections=json.loads((root/doc['inspection']).read_text())
        for inspection in inspections:
            if any(f.get('error') or f.get('warning') for f in inspection['timeline']):raise AssertionError('Timeline error/warning: '+doc['path'])
            if any(s.get('dof') or s.get('status')!='solved' for s in inspection.get('sketches',[])):raise AssertionError('Underconstrained sketch: '+doc['path'])
        entry={'path':doc['path'],'native':doc['native'],'named_bodies':doc['body_names'],'exact_named_reference':compare(root/doc['step'],root/doc['reference_step'],args.xor_tolerance)}
        if doc.get('original_step'):entry['exact_preserved_original']=compare(root/doc['step'],PACKAGE/doc['original_step'],args.xor_tolerance)
        if doc.get('mesh'):entry['mesh']=mesh_check(root/doc['mesh'],root/doc['step'],doc['expected_body_count'])
        # Move the native document away from every reference and verify it still opens.
        with tempfile.TemporaryDirectory(prefix='solidcraft-portability-') as temp:
            relocated=Path(temp)/'relocated.solidcraft';relocated.write_bytes((root/doc['native']).read_bytes())
            result=subprocess.run(['solidcraft-cli','eval',str(relocated)],capture_output=True,text=True)
            if result.returncode:raise AssertionError(result.stderr)
            state=json.loads(result.stdout)
            if state['body_count']!=doc['expected_body_count']:raise AssertionError('Relocated native body count changed')
        entry['native_reopens_without_external_files']=True
        report['documents'].append(entry)
        (root/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    report['status']='passed';report['document_count']=len(report['documents'])
    (root/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':'passed','documents':len(report['documents']),'report':str(root/'validation.json')}))

if __name__=='__main__':main()
