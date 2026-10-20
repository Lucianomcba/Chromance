"""Check native cups against independent spherical caps; export real test pieces."""
import hashlib,json,math,subprocess,tempfile,zipfile
from pathlib import Path
from copy import deepcopy
from add_finger_cups import BASE,OUT
from fuse_exports import leaves,physical_parts
from validate_project import healthy
from export_assembly import print_parts,save_set
from fdm_cad.build import print_layout
from fdm_cad.preview import render
from build123d import import_step,Pos,Rot,Sphere,Box,Align

NAMES=('reset_slider','boot_slider')

def volume(shape):return 0 if shape is None else sum(abs(s.volume) for s in shape.solids())
def xor(a,b):return volume(a-b)+volume(b-a)
def params(state):return {x['name']:x['value'] for x in state['params']}
def cup(p,which):
    h=p['finger_cup_depth'];r=(p['finger_cup_diameter']**2/4+h*h)/(2*h)
    top=p[which+'_arm_base']+7.8+p['finger_pad_extension']
    return Pos(p['button_face']-7.1,-p[which+'_housing_y'],p['mount_ceiling']-top-r+h)*Sphere(r)
def compare(parts,baseline,p):
    result={};h=p['finger_cup_depth'];r=(p['finger_cup_diameter']**2/4+h*h)/(2*h);expected_loss=math.pi*h*h*(r-h/3)
    for n,s in parts.items():
        if n not in NAMES:
            error=xor(s,baseline[n]);assert error<.001,(n,error);result[n]={'unchanged_xor_mm3':error};continue
        expected=baseline[n]-cup(p,n.split('_')[0]);error=xor(s,expected)
        loss=baseline[n].volume-s.volume;added=volume(s-baseline[n]);assert error<.001 and added<.001 and abs(loss-expected_loss)<.001,(n,error,loss,expected_loss,added)
        result[n]={'oracle_xor_mm3':error,'added_volume_mm3':added,'removed_volume_mm3':loss,'analytic_spherical_cap_volume_mm3':expected_loss}
    return result

def main():
    state=json.loads((OUT/'enclosure-inspection.json').read_text())[-1];healthy(state);p=params(state)
    groups=json.loads((OUT/'enclosure-groups.json').read_text())
    baseline={s.label:s for s in leaves(import_step(BASE/'enclosure.step'))}
    mounted={s.label:s for s in leaves(import_step(OUT/'enclosure.step'))};default_check=compare(mounted,baseline,p)
    report={'status':'running','physical_comfort_tested':False,'physical_fit_tested':False,'default_cup_diameter_mm':p['finger_cup_diameter'],'default_cup_depth_mm':p['finger_cup_depth'],'default_geometry':default_check,'motion_evidence':'Each changed slider is an exact subset of the prior slider, with only the analytic finger-face spherical cap removed. All other parts match exactly. Pure subtraction cannot introduce new interference at any prior rigid-motion pose. Guides and stops are outside the removed cap. Prior USB/board-play collisions remain unresolved.','barrel_holder_status':'Unchanged from revision015; jack-axis alignment remains paused/provisional.'}
    dest=OUT/'parameter-checks';dest.mkdir(exist_ok=True);cmds=[];cases=[]
    for n,values in {'finger_cup_depth':(.4,.8,.6),'finger_cup_diameter':(6.5,7.5,7.)}.items():
        for tag,value in zip(('low','high','default'),values):
            path=dest/(n+'-'+tag+'.step');cases.append({'parameter':n,'position':tag,'value_mm':value,'step':path.name})
            cmds.extend([{'command':'parameters.change','params':{'name':n,'expression':f'{value} mm'}},{'command':'file.export','params':{'path':str(path)}},{'command':'document.inspect','params':{'measure':True,'sketches':True}}])
    script={'commands':cmds}
    if (dest/'walk.json').exists():assert json.loads((dest/'walk.json').read_text())==script
    (dest/'walk.json').write_text(json.dumps(script,indent=2)+'\n')
    if not (dest/'states.json').exists():
        run=subprocess.run(['solidcraft-cli','run',str(dest/'walk.json'),'--in',str(OUT/'enclosure.json'),'--results','--json-out',str(dest/'states.json')],capture_output=True,text=True)
        if run.returncode:raise RuntimeError(run.stderr[-4000:])
    states=[s for s in json.loads((dest/'states.json').read_text()) if isinstance(s,dict) and 'bodies' in s and 'timeline' in s];assert len(states)==6
    cups={};inv=Pos(0,0,p['mount_ceiling'])*Rot(X=180)
    for case,s in zip(cases,states):
        healthy(s);q=params(s)
        assert abs(q[case['parameter']]-case['value_mm'])<1e-8
        other='finger_cup_diameter' if case['parameter']=='finger_cup_depth' else 'finger_cup_depth';assert abs(q[other]-p[other])<1e-8
        actual=physical_parts(dest/case['step'],groups,s);case['geometry']=compare(actual,baseline,q);case['timeline_clean']=True;case['sketches_dof_zero']=True
        if case['parameter']=='finger_cup_depth':
            local=inv*actual['reset_slider'];top=q['reset_arm_base']+7.8+q['finger_pad_extension'];cx=q['button_face']-7.1;cy=q['reset_housing_y']
            cap=local & (Pos(cx,cy,top-3)*Box(12,14,4,align=(Align.CENTER,Align.CENTER,Align.MIN)))
            assert cap.is_valid and len(cap.solids())==1
            cap=cap.solids()[0]
            down=Pos(0,0,top)*Rot(Y=180)*deepcopy(cap);down.label=f"cup_{round(q['finger_cup_depth']*100):03}_down";cups[down.label]=down
            if case['position']=='default':
                up=Pos(0,0,-top+3)*deepcopy(cap);up.label='cup_060_up';cups[up.label]=up
        print('PASSED',case['parameter'],case['position'],flush=True)
    report['parameter_cases']=cases
    inverse=Pos(0,0,p['mount_ceiling'])*Rot(X=180)
    local={n:(s if n=='desk_bracket' else inverse*s) for n,s in mounted.items()}
    printed=print_parts(local,p);partsdir=OUT/'parts';partsdir.mkdir(exist_ok=True)
    for n in NAMES:report[n+'_export']=save_set({n:printed[n]},partsdir/n,p)
    report['replacement_sliders_export']=save_set(print_layout({n:printed[n] for n in NAMES}),OUT/'replacement-sliders',p)
    report['full_print_export']=save_set(print_layout(printed),OUT/'print-layout',p)
    fit=OUT/'fit-tests';fit.mkdir(exist_ok=True)
    cups={n:cups[n] for n in ('cup_040_down','cup_060_down','cup_080_down','cup_060_up')}
    report['finger_cup_samples_export']=save_set(print_layout(cups),fit/'finger-cup-samples',p)
    render(print_layout(cups),fit/'finger-cup-samples.png',title='Finger cups / quick feel and print-finish samples',subtitle='Left to right: 0.4, 0.6, 0.8 mm cup down; 0.6 mm cup up | 7 mm cup diameter',elevation=28,azimuth=-65)
    # Show the actual finger faces upward for inspection; this is a viewing pose.
    view={n:Pos(0,0,-p[n.split('_')[0]+'_arm_base'])*local[n] for n in NAMES}
    render(print_layout(view),OUT/'finger-faces.png',title='Revision 016 / shallow spherical finger cups',subtitle='7 mm diameter | 0.6 mm depth | actual slider geometry, finger faces shown upward',elevation=62,azimuth=-55)
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
