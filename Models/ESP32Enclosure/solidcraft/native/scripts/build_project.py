"""Rebuild the complete native feature-history project in a fresh directory.

Only command authoring and CLI execution happen here. The prior conversion's
frozen source measurements specify default print-plate placement and regression
expectations; no STEP or mesh is loaded into a SolidCraft design.
"""
from pathlib import Path
import argparse,concurrent.futures,hashlib,json,subprocess
from build_native import PACKAGE,model,add_part
from native_builder import Builder
from enclosure_features import dimensions
from fuse_exports import normalize

BASE=PACKAGE/'solidcraft/revision-014'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def run(args):
 done=subprocess.run([str(x) for x in args],capture_output=True,text=True)
 if done.returncode:raise RuntimeError(done.stderr[-2000:])
 return done

def layout(defaults,doc,manifest):
 b=Builder(defaults);dimensions(b)
 refs={d['body_names'][0]:d['frozen_reference'][d['body_names'][0]] for d in manifest['documents'] if len(d['body_names'])==1}
 # Match the established source layout at defaults. These are arrangement moves,
 # not mechanical dimensions; their eight millimetre gaps permit modest edits.
 x=y=row=0.;moves={}
 for name in doc['body_names']:
  box=refs[name]['bbox'];lo,hi=box['min'],box['max'];w=hi[0]-lo[0];d=hi[1]-lo[1]
  if x and x+w>220:x=0.;y+=row+8;row=0.
  moves[name]=[x-lo[0],y-lo[1],-lo[2]];x+=w+8;row=max(row,d)
 order=doc['body_names']
 if 'lid' in order:order=['lid']+[n for n in order if n!='lid']
 for name in order:
  add_part(b,name);b.move(name+'_plate_position',b.part_bodies[name],translation=moves[name])
 return b

def build_one(output,defaults,doc,manifest):
 relative=doc['path'];dest=output/relative;dest.parent.mkdir(parents=True,exist_ok=True)
 stem=Path(relative).stem
 if stem in ('replacements-only','print-layout'):b=layout(defaults,doc,manifest)
 else:b=model(defaults,'fit_assembly' if relative=='fit-tests/assembly.json' else stem)
 # Explicit output commands preserve the evaluated native history in one session.
 b.cmd('file.save',path=str(dest.with_suffix('.solidcraft').resolve()),compression='compact',cache=True,preview=True)
 script=dest.with_name(stem+'-build.json');b.finish(script)
 inspect=output/doc['inspection']
 raw=dest.with_name(stem+'-native.step')
 run(['solidcraft-cli','run',script,'--save',dest,'--out',raw,'--results','--json-out',inspect])
 state=json.loads(inspect.read_text())[-1]
 issues=[f for f in state['timeline'] if f.get('error') or f.get('warning')]
 if issues:raise RuntimeError(f'{relative}: {[(f["name"],f.get("error"),f.get("warning")) for f in issues]}')
 if any(s['dof'] or s['status']!='solved' for s in state['sketches']):raise RuntimeError('Unsolved sketch: '+relative)
 if set(x['name'] for x in state['bodies'])!={n for names in b.part_bodies.values() for n in names}:raise RuntimeError('Body names changed: '+relative)
 entry={k:v for k,v in doc.items() if k not in ('design_sha256','native_sha256','step_sha256','reference_sha256','reference_step','measurement')}
 entry['build_script']=str(script.relative_to(output));entry['reference_step']=str((BASE/doc['reference_step']).relative_to(PACKAGE))
 groups=dest.with_name(stem+'-groups.json');groups.write_text(json.dumps(b.part_bodies,indent=2)+'\n')
 entry['groups']=str(groups.relative_to(output));entry['raw_step']=str(raw.relative_to(output));entry['native_body_names']=[n for names in b.part_bodies.values() for n in names];entry['expected_native_body_count']=len(entry['native_body_names'])
 for key,hash_key in [('path','design_sha256'),('native','native_sha256')]:entry[hash_key]=sha(output/entry[key])
 entry['sketch_count']=len(state['sketches']);entry['feature_count']=len(state['timeline']);entry['all_sketches_dof_zero']=True
 print('BUILT '+relative+f': {len(state["bodies"])} bodies, {len(state["sketches"])} solved sketches',flush=True)
 return entry

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);p.add_argument('--workers',type=int,default=2);p.add_argument('--only',nargs='*');a=p.parse_args();output=a.output.resolve()
 if output.exists():raise ValueError('Use a fresh output directory; existing designs are preserved')
 defaults=json.loads((PACKAGE/'revisions/014-usb-clearance/parameters.json').read_text());original=json.loads((BASE/'manifest.json').read_text())
 docs=[d for d in original['documents'] if not a.only or d['path'] in a.only]
 manifest={'schema':2,'conversion_kind':'native constrained sketches and parametric feature history','parametric_feature_history_rebuilt':True,'source_revision':'014-usb-clearance','quick_test':'009-usb-clearance','geometry_changes_intended':False,'units':'mm','source_files':original['source_files'],'documents':[],'physical_fit_tested':False,'native_shell_strategy':'Editable structural bodies; export-only OCCT union produces one solid per printed part. No imported features.'}
 output.mkdir(parents=True)
 with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
  futures=[pool.submit(build_one,output,defaults,d,original) for d in docs]
  for f in futures:
   entry=f.result()
   normalize(output/entry['raw_step'],json.loads((output/entry['groups']).read_text()),output/entry['step'],output/entry['mesh'] if entry.get('mesh') else None,json.loads((output/entry['inspection']).read_text())[-1])
   entry['step_sha256']=sha(output/entry['step']);entry['raw_step_sha256']=sha(output/entry['raw_step']);entry['groups_sha256']=sha(output/entry['groups'])
   if entry.get('mesh'):
    entry['mesh_sha256']=sha(output/entry['mesh']);mesh=Path(entry['mesh']);entry['mesh_report']=str(mesh.with_name(mesh.stem+'-mesh-report.json'))
   manifest['documents'].append(entry);(output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 manifest['generation_source_files']={str(path.relative_to(PACKAGE)):sha(path) for path in Path(__file__).parent.glob('*.py')}
 manifest['status']='built_pending_validation';(output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
if __name__=='__main__':main()
