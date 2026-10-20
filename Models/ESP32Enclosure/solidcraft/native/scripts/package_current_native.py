"""Save current slider/print-layout native documents from the verified master.

All features remain native and editable. Terminal remove/move features isolate
parts and set their manufacturing poses; older revisions are never overwritten.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,subprocess,tempfile
from rectangular_finger_cups import OUT
from native_builder import Builder,E
from fuse_exports import physical_parts,normalize,leaves
from validate_project import healthy
from export_assembly import print_parts
from export_rectangular_cups import bed
from build123d import import_step,Pos,Rot,Compound,export_step
import sys
from fuse_exports import PACKAGE
sys.path.insert(0,str(PACKAGE/'solidcraft/scripts'))
from validate import compare

def main():
    state=json.loads((OUT/'enclosure-inspection.json').read_text())[-1]
    p={x['name']:x['value'] for x in state['params']};groups=json.loads((OUT/'enclosure-groups.json').read_text())
    mounted={s.label:s for s in leaves(import_step(OUT/'enclosure.step'))}
    inverse=Pos(0,0,p['mount_ceiling'])*Rot(X=180)
    local={n:(s if n=='desk_bracket' else inverse*s) for n,s in mounted.items()};printed=print_parts(local,p)
    for n in ('reset_slider','boot_slider'):printed[n]=bed(local[n])
    documents=[('parts/reset_slider',['reset_slider'],False),('parts/boot_slider',['boot_slider'],False),('replacement-sliders',['reset_slider','boot_slider'],True),('print-layout',list(groups),True)]
    jobs=[]
    for stem,names,layout in documents:
        dest=OUT/stem
        dest.with_name(dest.name+'-groups.json').write_text(json.dumps({n:groups[n] for n in names},indent=2)+'\n')
        if dest.with_suffix('.solidcraft').exists() or dest.with_suffix('.json').exists():raise ValueError('Preserve existing native documents: '+stem)
        b=Builder({});b.p={x['name']:E(x['name'],x['value']) for x in state['params']};q=b.p
        keep={v for n in names for v in groups[n]};discard=[v for vs in groups.values() for v in vs if v not in keep]
        if discard:b.cmd('solid.remove',bodies=discard)
        for n in names:
            bodies=groups[n]
            if n!='desk_bracket':
                b.move(n+'_document_case_rotation',bodies,axis=[1,0,0],angle='180 deg');b.move(n+'_document_case_height',bodies,translation=[0,0,q['mount_ceiling']])
            if n in ('reset_slider','boot_slider'):b.move(n+'_upright_print_pose',bodies,translation=[0,0,-q[n.split('_')[0]+'_slider_bottom']])
            elif n=='lid':b.move(n+'_document_print_rotation',bodies,axis=[1,0,0],angle='180 deg');b.move(n+'_document_print_height',bodies,translation=[0,0,q['lid_top']])
            elif n=='desk_bracket':b.move(n+'_document_print_rotation',bodies,axis=[1,0,0],angle='180 deg');b.move(n+'_document_print_height',bodies,translation=[0,0,q['plate_height']+q['bracket_plate_thickness']])
            elif n.startswith('pcb_clamp_'):b.move(n+'_document_on_bed',bodies,translation=[0,0,-q['clamp_height']])
            elif n.endswith(('_frame','_rear_keeper')):
                offset=q['button_face']-(14.2 if n.endswith('_rear_keeper') else 11.8)
                b.move(n+'_document_print_rotation',bodies,axis=[0,1,0],angle='-90 deg');b.move(n+'_document_on_bed',bodies,translation=[0,0,-offset])
            elif n.endswith('_moving_magnet_keeper'):b.move(n+'_document_on_bed',bodies,translation=[0,0,-q[n.split('_')[0]+'_moving_magnet_bottom']-.1])
            elif n!='body':raise ValueError(n)
        if layout:
            target={s.label:s for s in leaves(import_step(dest.with_suffix('.step')))}
            assert set(target)==set(names)
            for n in names:
                before,after=printed[n].bounding_box(),target[n].bounding_box()
                delta=[a-b for a,b in zip(after.min,before.min)]
                b.move(n+'_nominal_plate_position',groups[n],translation=delta)
        b.cmd('file.save',path=str(dest.with_suffix('.solidcraft')),compression='compact',cache=True,preview=True)
        script=dest.with_name(dest.name+'-native-layout.json');b.finish(script)
        jobs.append((stem,names,script,dest))
    def build(job):
        stem,names,script,dest=job
        inspection=dest.with_name(dest.name+'-native-inspection.json');raw=dest.with_name(dest.name+'-native.step')
        done=subprocess.run(['solidcraft-cli','run',str(script),'--in',str(OUT/'enclosure.solidcraft'),'--save',str(dest.with_suffix('.json')),'--out',str(raw),'--results','--json-out',str(inspection)],capture_output=True,text=True,timeout=180)
        if done.returncode:raise RuntimeError(done.stderr[-2000:])
        print('SAVED '+stem,flush=True);return job,inspection,raw
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(build,jobs))
    report={'status':'running','source_native_sha256':hashlib.sha256((OUT/'enclosure.solidcraft').read_bytes()).hexdigest(),'documents':[],'physical_fit_tested':False}
    for (stem,names,script,dest),inspection,raw in results:
        current=json.loads(inspection.read_text())[-1];healthy(current);subset={n:groups[n] for n in names}
        assert {x['name'] for x in current['bodies']}=={v for vs in subset.values() for v in vs}
        actual=physical_parts(raw,subset,current)
        with tempfile.TemporaryDirectory(prefix='current-native-match-') as tmp:
            measured=Path(tmp)/'actual.step';export_step(Compound(children=list(actual.values())),measured)
            match=compare(measured,dest.with_suffix('.step'),.001)
            relocated=Path(tmp)/'portable.solidcraft';relocated.write_bytes(dest.with_suffix('.solidcraft').read_bytes())
            done=subprocess.run(['solidcraft-cli','eval',str(relocated)],capture_output=True,text=True,timeout=90);assert done.returncode==0,done.stderr
            assert json.loads(done.stdout)['body_count']==sum(len(v) for v in subset.values())
        assert not any(f['type']=='import' for f in json.loads(dest.with_suffix('.json').read_text())['features'])
        report['documents'].append({'path':str(dest.with_suffix('.solidcraft').relative_to(OUT)),'native_sha256':hashlib.sha256(dest.with_suffix('.solidcraft').read_bytes()).hexdigest(),'readable_json_sha256':hashlib.sha256(dest.with_suffix('.json').read_bytes()).hexdigest(),'physical_parts':len(names),'native_bodies':sum(len(v) for v in subset.values()),'sketches_dof_zero':len(current['sketches']),'no_import_features':True,'opens_without_external_files':True,'exact_step_match':match})
        (OUT/'native-document-validation.json').write_text(json.dumps(report,indent=2)+'\n');print('VERIFIED '+stem,flush=True)
    report['status']='passed';(OUT/'native-document-validation.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
