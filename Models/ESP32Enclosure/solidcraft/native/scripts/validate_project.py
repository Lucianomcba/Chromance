"""Independently check native history, STEP geometry, meshes and portability."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys,tempfile
from build_native import PACKAGE
sys.path.insert(0,str(PACKAGE/'solidcraft/scripts'))
from validate import compare,mesh_check

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def healthy(state):
 if any(p.get('error') for p in state.get('params',[])):raise AssertionError('Native parameter expression error')
 issues=[f for f in state['timeline'] if f.get('error') or f.get('warning')]
 if issues:raise AssertionError([(f['name'],f.get('error'),f.get('warning')) for f in issues])
 if not state['sketches'] or any(s['dof'] or s['status']!='solved' for s in state['sketches']):raise AssertionError('Sketches must all solve at zero DoF')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);a=p.parse_args();root=a.directory.resolve();m=json.loads((root/'manifest.json').read_text())
 report={'status':'running','conversion_kind':'native parametric feature history','parametric_feature_history_rebuilt':True,'physical_fit_tested':False,'documents':[]}
 for name,h in m['source_files'].items():
  if sha(PACKAGE/name)!=h:raise AssertionError('Original changed: '+name)
 for d in m['documents']:
  design=json.loads((root/d['path']).read_text());types={f['type'] for f in design['features']}
  if 'import' in types or not {'sketch','extrude'}<=types:raise AssertionError('Expected native sketches/extrusions without imports')
  for key,hkey in [('path','design_sha256'),('native','native_sha256'),('step','step_sha256'),('raw_step','raw_step_sha256'),('groups','groups_sha256')]:
   if sha(root/d[key])!=d[hkey]:raise AssertionError('Changed artifact: '+d[key])
  healthy(json.loads((root/d['inspection']).read_text())[-1])
  r={'path':d['path'],'sketches_dof_zero':d['sketch_count'],'feature_count':d['feature_count'],'no_import_features':True,'exact_reference':compare(root/d['step'],PACKAGE/d['reference_step'],1e-3)}
  if d.get('original_step'):r['exact_original']=compare(root/d['step'],PACKAGE/d['original_step'],1e-3)
  if d.get('mesh'):
   if sha(root/d['mesh'])!=d['mesh_sha256']:raise AssertionError('Changed print mesh: '+d['mesh'])
   r['mesh']=mesh_check(root/d['mesh'],root/d['step'],d['expected_body_count'])
   meshing=json.loads((root/d['mesh_report']).read_text())
   if meshing['status']!='passed' or any(not p['watertight'] or p['manifold_check']!='passed' for p in meshing['parts'].values()):raise AssertionError('Meshing report did not pass')
   r['mesh_report']=d['mesh_report']
  with tempfile.TemporaryDirectory(prefix='native-portability-') as tmp:
   relocated=Path(tmp)/'portable.solidcraft';relocated.write_bytes((root/d['native']).read_bytes())
   done=subprocess.run(['solidcraft-cli','eval',str(relocated)],capture_output=True,text=True)
   if done.returncode:raise AssertionError(done.stderr)
   if json.loads(done.stdout)['body_count']!=d['expected_native_body_count']:raise AssertionError('Relocated body count')
  r['native_body_count']=d['expected_native_body_count'];r['printed_part_count']=d['expected_body_count'];r['native_opens_without_external_files']=True;report['documents'].append(r)
  (root/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print('PASSED '+d['path'],flush=True)
 report['status']='passed';report['document_count']=len(report['documents']);(root/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
