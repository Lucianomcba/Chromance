"""Validate the rectangularly clipped native spherical finger faces."""
import hashlib,json,math,subprocess,tempfile,zipfile
from pathlib import Path
from rectangular_finger_cups import BASE,OUT,FLAT
from fuse_exports import leaves,physical_parts
from validate_project import healthy
from build123d import import_step,Pos,Sphere

NAMES=('reset_slider','boot_slider')

def volume(shape):return 0 if shape is None else sum(abs(s.volume) for s in shape.solids())
def xor(a,b):return volume(a-b)+volume(b-a)
def params(state):return {x['name']:x['value'] for x in state['params']}
def cup(p,which):
    h=p['finger_cup_depth'];r=(p['finger_cup_diameter']**2/4+h*h)/(2*h)
    top=p[which+'_arm_base']+7.8+p['finger_pad_extension']
    return Pos(p['button_face']-7.1,-p[which+'_housing_y'],p['mount_ceiling']-top-r+h)*Sphere(r)
def compare(parts,baseline,p):
    from build123d import GeomType
    flat={s.label:s for s in leaves(import_step(FLAT/'enclosure.step'))}
    result={}
    for n,shape in parts.items():
        if n not in NAMES:
            error=xor(shape,baseline[n]);assert error<.001,(n,error)
            result[n]={'unchanged_xor_mm3':error};continue
        which=n.split('_')[0];expected=flat[n]-cup(p,which);error=xor(shape,expected)
        added=volume(shape-flat[n]);assert error<.001 and added<.001,(n,error,added)
        top=p[which+'_arm_base']+7.8+p['finger_pad_extension'];plane=p['mount_ceiling']-top
        flat_area=0.;sphere_max=[]
        for face in shape.faces():
            box=face.bounding_box()
            if face.geom_type==GeomType.PLANE and abs(box.min.Z-plane)<1e-5 and abs(box.max.Z-plane)<1e-5:flat_area+=face.area
            if face.geom_type==GeomType.SPHERE:sphere_max.append(box.max.Z)
        assert flat_area<.0001,(n,'remaining flat top',flat_area)
        assert sphere_max and abs(max(sphere_max)-plane-p['finger_cup_depth'])<.001
        result[n]={'oracle_xor_mm3':error,'added_volume_vs_flat_slider_mm3':added,'removed_volume_mm3':flat[n].volume-shape.volume,'remaining_original_flat_top_area_mm2':flat_area,'measured_center_depth_mm':max(sphere_max)-plane}
    return result

def main():
    state=json.loads((OUT/'enclosure-inspection.json').read_text())[-1];healthy(state);p=params(state)
    groups=json.loads((OUT/'enclosure-groups.json').read_text())
    baseline={s.label:s for s in leaves(import_step(BASE/'enclosure.step'))}
    mounted={s.label:s for s in leaves(import_step(OUT/'enclosure.step'))};default_check=compare(mounted,baseline,p)
    previous_added={n:volume(mounted[n]-baseline[n]) for n in NAMES}
    assert max(previous_added.values())<.001
    report={'default_added_vs_revision016_mm3':previous_added,'status':'running','physical_comfort_tested':False,'physical_fit_tested':False,'derived_sphere_footprint_diameter_mm':p['finger_cup_diameter'],'face_boundary':'complete rectangular top; original chamfer retained','default_cup_depth_mm':p['finger_cup_depth'],'default_geometry':default_check,'motion_evidence':'Each slider is an exact subset of the uncupped revision015 slider, with only a rectangularly clipped spherical dish removed. All other parts match exactly. Pure subtraction cannot introduce new interference at any prior rigid-motion pose. Guides and stops are outside the removed cap. Prior USB/board-play collisions remain unresolved.','barrel_holder_status':'Unchanged from revision015; jack-axis alignment remains paused/provisional.'}
    dest=OUT/'parameter-checks';dest.mkdir(exist_ok=True);cmds=[];cases=[]
    for n,values in {'finger_cup_depth':(.5,.8,.6)}.items():
        for tag,value in zip(('low','high','default'),values):
            path=dest/(n+'-'+tag+'.step');cases.append({'parameter':n,'position':tag,'value_mm':value,'step':path.name})
            cmds.extend([{'command':'parameters.change','params':{'name':n,'expression':f'{value} mm'}},{'command':'file.export','params':{'path':str(path)}},{'command':'document.inspect','params':{'measure':True,'sketches':True}}])
    script={'commands':cmds}
    if (dest/'walk.json').exists():assert json.loads((dest/'walk.json').read_text())==script
    (dest/'walk.json').write_text(json.dumps(script,indent=2)+'\n')
    if not (dest/'states.json').exists():
        run=subprocess.run(['solidcraft-cli','run',str(dest/'walk.json'),'--in',str(OUT/'enclosure.solidcraft'),'--results','--json-out',str(dest/'states.json')],capture_output=True,text=True,timeout=120)
        if run.returncode:raise RuntimeError(run.stderr[-4000:])
    states=[s for s in json.loads((dest/'states.json').read_text()) if isinstance(s,dict) and 'bodies' in s and 'timeline' in s];assert len(states)==3
    for case,s in zip(cases,states):
        healthy(s);q=params(s)
        assert abs(q[case['parameter']]-case['value_mm'])<1e-8
        assert abs(q['finger_cup_diameter']-(math.hypot(q['reset_slider_width'],12)+1))<1e-8
        actual=physical_parts(dest/case['step'],groups,s);case['geometry']=compare(actual,baseline,q);case['timeline_clean']=True;case['sketches_dof_zero']=True
        print('PASSED',case['parameter'],case['position'],flush=True)
    report['parameter_cases']=cases
    with tempfile.TemporaryDirectory(prefix='finger-cups-portability-') as tmp:
        path=Path(tmp)/'portable.solidcraft';path.write_bytes((OUT/'enclosure.solidcraft').read_bytes());run=subprocess.run(['solidcraft-cli','eval',str(path)],capture_output=True,text=True);assert run.returncode==0,run.stderr;assert json.loads(run.stdout)['body_count']==len(state['bodies'])
    assert not any(f['type']=='import' for f in json.loads((OUT/'enclosure.json').read_text())['features'])
    report['opens_without_external_files']=True;report['no_import_features']=True;report['sketches_dof_zero']=len(state['sketches'])
    files=list(dest.glob('*.step'))+[dest/'states.json'];digests={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    with zipfile.ZipFile(dest/'verification-artifacts.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for f in files:z.write(f,f.name)
    with zipfile.ZipFile(dest/'verification-artifacts.zip') as z:
        assert z.testzip() is None
        for n,digest in digests.items():assert hashlib.sha256(z.read(n)).hexdigest()==digest
    report['parameter_archive_members_sha256']=digests
    for f in files:f.unlink()
    report['status']='passed_with_inherited_alignment_and_usb_limitations';(OUT/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(OUT,flush=True)
if __name__=='__main__':main()
