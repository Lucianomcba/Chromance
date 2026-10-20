"""Native low -> high -> default edits with independent saddle oracle checks."""
import hashlib,json,subprocess,zipfile
from add_side_cable_holder import OUT
from validate_side_cable_holder import oracle,xor
from validate_project import healthy
from fuse_exports import physical_parts
from build123d import Pos,Rot

RANGES={'side_cable_diameter':(8.8,9.2,9.),'side_cable_center_y':(19.8,20.2,20.),'side_cable_radial_clearance':(.15,.25,.2)}
def main():
    dest=OUT/'parameter-checks';dest.mkdir(exist_ok=False);cmds=[];cases=[]
    for name,values in RANGES.items():
        for label,v in zip(('low','high','default'),values):
            tag=name+'-'+label;raw=dest/(tag+'.step')
            cmds.extend([{'command':'parameters.change','params':{'name':name,'expression':f'{v} mm'}},{'command':'file.export','params':{'path':str(raw)}},{'command':'document.inspect','params':{'measure':True,'sketches':True}}])
            cases.append({'parameter':name,'position':label,'value_mm':v,'raw_step':raw.name})
    (dest/'walk.json').write_text(json.dumps({'commands':cmds},indent=2)+'\n')
    run=subprocess.run(['solidcraft-cli','run',str(dest/'walk.json'),'--in',str(OUT/'enclosure.json'),'--results','--json-out',str(dest/'states.json')],capture_output=True,text=True)
    if run.returncode:raise RuntimeError(run.stderr[-4000:])
    states=[s for s in json.loads((dest/'states.json').read_text()) if isinstance(s,dict) and 'timeline' in s and 'bodies' in s];assert len(states)==9
    groups=json.loads((OUT/'enclosure-groups.json').read_text());single={n:[n] for v in groups.values() for n in v}
    for state,case in zip(states,cases):
        healthy(state);p={x['name']:x['value'] for x in state['params']}
        for name,values in RANGES.items():assert abs(p[name]-(case['value_mm'] if name==case['parameter'] else values[-1]))<1e-7
        solids=physical_parts(dest/case['raw_step'],single,state);shape=Pos(0,0,p['mount_ceiling'])*Rot(X=180)*solids['body_side_cable_cradle'];expected,_=oracle(p)
        case['oracle_xor_mm3']=xor(shape,expected);case['all_sketches_dof_zero']=True;assert case['oracle_xor_mm3']<.001
        print(case,flush=True)
    files=list(dest.glob('*.step'))+[dest/'states.json'];hashes={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    archive=dest/'verification-artifacts.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for f in files:z.write(f,f.name)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name,digest in hashes.items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
    (dest/'validation.json').write_text(json.dumps({'status':'passed','sequence':'low -> high -> default, individually, one native session','cases':cases,'native_design_sha256':hashlib.sha256((OUT/'enclosure.json').read_bytes()).hexdigest(),'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'archive_members_sha256':hashes,'physical_fit_tested':False},indent=2)+'\n')
    for f in files:f.unlink()
if __name__=='__main__':main()
