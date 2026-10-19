"""Walk actual saved SolidCraft parameters low -> high -> default in one session.

Exports every state for independent OCCT comparison with the original Python
model. Native creation never uses this oracle or imports any resulting geometry.
"""
from pathlib import Path
import argparse,json,subprocess,sys,hashlib,zipfile
from build_native import PACKAGE
from native_builder import NATIVE_NAMES
from parameter_ranges import RANGES
from validate_project import healthy
from fuse_exports import normalize
sys.path.insert(0,str(PACKAGE/'src'))
from fdm_cad.build import load_model
from build123d import export_step,Compound,CenterOf
sys.path.insert(0,str(PACKAGE/'solidcraft/scripts'))
from validate import compare

def archive_parameter_artifacts(directory,design=None,groups=None):
 """Losslessly retain large check outputs in a verified ZIP, then remove copies."""
 directory=Path(directory);report_path=directory/'validation.json';report=json.loads(report_path.read_text())
 if report['status']!='passed':raise AssertionError('Archive only completed checks')
 states=[s for s in json.loads((directory/'states.json').read_text()) if isinstance(s,dict) and 'timeline' in s and 'bodies' in s]
 if len(states)!=len(report['cases']):raise AssertionError('Native state/report count differs')
 defaults=json.loads((PACKAGE/'revisions/014-usb-clearance/parameters.json').read_text())
 for case,state in zip(report['cases'],states):
  healthy(state);values={p['name']:p['value'] for p in state['params']}
  for name in RANGES:
   expected=case['value_mm'] if name==case['parameter'] else defaults[name]
   if abs(values[NATIVE_NAMES.get(name,name)]-expected)>1e-8:raise AssertionError('Native walk input differs from its reported case')
 archive=directory/'verification-artifacts.zip'
 if archive.exists():raise ValueError('Verification archive already exists')
 files=sorted(list(directory.glob('*.step'))+[directory/'states.json'])
 hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
 with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as output:
  for path in files:output.write(path,path.name)
 with zipfile.ZipFile(archive) as saved:
  if saved.testzip() is not None:raise AssertionError('Archive CRC failed')
  for name,expected in hashes.items():
   if hashlib.sha256(saved.read(name)).hexdigest()!=expected:raise AssertionError('Archive did not preserve '+name)
 report['artifacts_archive']=archive.name;report['archive_sha256']=hashlib.sha256(archive.read_bytes()).hexdigest();report['archive_members_sha256']=hashes
 if design:report['native_design_sha256']=hashlib.sha256(Path(design).read_bytes()).hexdigest()
 if groups:report['native_groups_sha256']=hashlib.sha256(Path(groups).read_bytes()).hexdigest()
 report_path.write_text(json.dumps(report,indent=2)+'\n')
 for path in files:path.unlink()
 return archive

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--document',default='enclosure.json');p.add_argument('--parameters',nargs='*');p.add_argument('--output',type=Path);p.add_argument('--archive',action='store_true');a=p.parse_args();root=a.directory.resolve();dest=a.output.resolve() if a.output else root/'parameter-checks'/Path(a.document).with_suffix('');dest.mkdir(parents=True,exist_ok=False)
 defaults=json.loads((PACKAGE/'revisions/014-usb-clearance/parameters.json').read_text());commands=[];cases=[]
 for name,(low,high) in RANGES.items():
  if a.parameters and name not in a.parameters:continue
  for label,value in [('low',low),('high',high),('default',defaults[name])]:
   tag=name+'-'+label;path=dest/(tag+'-native.step')
   commands += [{'command':'parameters.change','params':{'name':NATIVE_NAMES.get(name,name),'expression':f'{value} mm'}},{'command':'file.export','params':{'path':str(path)}},{'command':'document.inspect','params':{'measure':True,'sketches':True}}]
   cases.append({'parameter':name,'value_mm':value,'position':label,'raw_step':path.name,'step':tag+'.step'})
 script=dest/'walk.json';script.write_text(json.dumps({'commands':commands},indent=2)+'\n');results=dest/'states.json'
 done=subprocess.run(['solidcraft-cli','run',str(script),'--in',str(root/a.document),'--results','--json-out',str(results)],capture_output=True,text=True)
 if done.returncode:raise RuntimeError(done.stderr)
 inspections=[s for s in json.loads(results.read_text()) if isinstance(s,dict) and 'timeline' in s and 'bodies' in s]
 if len(inspections)!=len(cases):raise AssertionError(('inspection count',len(inspections),len(cases)))
 for state in inspections:healthy(state)
 report={'status':'running','document':a.document,'sequence':'low -> high -> default, each input separately in one native session','cases':[],'physical_fit_tested':False}
 cache={}
 groups=json.loads((root/Path(a.document).with_name(Path(a.document).stem+'-groups.json')).read_text())
 for case,state in zip(cases,inspections):
  normalize(dest/case['raw_step'],groups,dest/case['step'],state=state)
  name=case['parameter'];value=case['value_mm'];key=(name,value) if value!=defaults[name] else ('default',0)
  if key not in cache:
   params=defaults|{name:value};data=load_model(PACKAGE/'revisions/014-usb-clearance/model.py',params)
   shapes=data['assembly'] if a.document=='enclosure.json' else {Path(a.document).stem:data['parts'][Path(a.document).stem]}
   reference=dest/('oracle-'+case['step']);export_step(Compound(children=list(shapes.values())),reference)
   cache[key]=(reference,shapes)
  reference,shapes=cache[key];r=compare(dest/case['step'],reference,1e-3)
  measured={}
  for n,s in shapes.items():
   box=s.bounding_box();measured[n]={'volume_mm3':float(s.volume),'area_mm2':float(s.area),'center_of_mass':list(s.center(CenterOf.MASS)),'bbox':{'min':list(box.min),'max':list(box.max)}}
  entry=case|{'comparison':r,'frozen_reference':measured,'all_sketches_dof_zero':True,'timeline_clean':True}
  report['cases'].append(entry);(dest/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print('WALK PASSED '+name+' '+case['position'],flush=True)
 report['status']='passed';(dest/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
 if a.archive:archive_parameter_artifacts(dest,root/a.document,root/Path(a.document).with_name(Path(a.document).stem+'-groups.json'))
if __name__=='__main__':main()
