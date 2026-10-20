"""Independent geometry, motion and export checks for the native side saddle."""
import json,hashlib,subprocess,math,tempfile
from pathlib import Path
from add_side_cable_holder import BASE,OUT
from fuse_exports import leaves,physical_parts
from validate_project import healthy
from cad_mesh import export_print_mesh
from fdm_cad.preview import render
from fdm_cad.build import print_layout,load_model
from export_assembly import print_parts,save_set
from build123d import Box,Cylinder,Pos,Rot,Align,Plane,Polygon,extrude,Compound,import_step,export_step

MIN=(Align.CENTER,Align.CENTER,Align.MIN)

def volume(s):return 0 if s is None else sum(abs(x.volume) for x in s.solids())
def xor(a,b):return volume(a-b)+volume(b-a)
def overlap(a,b):return volume(a.intersect(b))
def oracle(p):
    sill=p['board_top']+p['left_access_start_above_pcb'];wx=-p['shell_width']/2;inner=wx+1;outer=wx-p['side_cradle_projection'];cy=p['side_cable_center_y'];r=p['side_cable_diameter']/2+p['side_cable_radial_clearance'];hw=r+p['cable_cradle_side_wall']
    sw=p['zip_tie_width_provisional']+2*p['zip_tie_slot_side_clearance'];bot=sill-1;eave=bot+p['zip_tie_thickness_provisional']+2*p['zip_tie_slot_vertical_clearance'];apex=eave+sw/2;top=apex+p['cable_cradle_floor_above_tunnel']+r;cx=(outer+wx)/2
    stock=Pos((inner+outer)/2,cy,sill)*Box(inner-outer,2*hw,top-sill,align=MIN)
    # build123d XZ uses +Z and normal -Y, unlike SolidCraft XZ.
    root=Pos(0,cy,0)*extrude(Plane.XZ*Polygon((outer,sill),(inner,sill),(inner,sill-(inner-outer)),align=None),amount=hw,both=True)
    seat=Pos(outer-1,cy,top)*Rot(Y=90)*Cylinder(r,inner-outer+2,align=MIN)
    tunnel=Pos(0,cy,0)*extrude(Plane.XZ*Polygon((cx-sw/2,bot),(cx+sw/2,bot),(cx+sw/2,eave),(cx,apex),(cx-sw/2,eave),align=None),amount=hw+2,both=True)
    return (stock+root)-seat-tunnel,dict(sill=sill,outer=outer,inner=inner,cy=cy,r=r,hw=hw,top=top,cx=cx,bottom=bot)

def hardware_check(p,cradle,refs):
    """Check native new feature/reference routes against preserved hardware proxies."""
    inverse=Pos(0,0,p['mount_ceiling'])*Rot(X=180)
    source=BASE.parents[2]/'revisions/014-usb-clearance'
    reference_params=json.loads((source/'parameters.json').read_text())
    reference_params={n:p.get('floor_thickness' if n=='floor' else n,v) for n,v in reference_params.items()}
    for angle in ('vent_angle','lid_corner_support_angle'):reference_params[angle]=math.degrees(reference_params[angle])
    reference=load_model(source/'model.py',reference_params)
    hardware={n:inverse*s for n,s in reference['hardware'].items()}
    assert len(hardware)>20
    collisions={};minimum={}
    for n,shape in hardware.items():
        moving=n.startswith(('reset_','boot_')) and n.endswith(('_moving_magnet','_nylon_adjuster','_contact_heatset_insert','_nylon_jam_nut'))
        for i in (range(17) if moving else [0]):
            target=Pos(0,0,-i*.05)*shape
            for label,obstacle in ({'new_cradle':cradle}|refs).items():
                gap=obstacle.distance_to(target)
                key=label+' / '+n;minimum[key]=min(minimum.get(key,1e9),gap)
                if gap<1e-6:
                    v=overlap(obstacle,target)
                    if v>.0001:collisions[key]=max(collisions.get(key,0),v)
    assert not collisions,collisions
    return {'hardware_proxy_count':len(hardware),'moving_hardware_sample_count':17,'interferences':collisions,'minimum_gap_mm':min(minimum.values()),'pairs_within_3mm':{n:v for n,v in minimum.items() if v<3}}

def portability_check():
    design=json.loads((OUT/'enclosure.json').read_text())
    assert not any(f['type']=='import' for f in design['features'])
    expected=len(json.loads((OUT/'enclosure-inspection.json').read_text())[-1]['bodies'])
    with tempfile.TemporaryDirectory(prefix='side-holder-portability-') as tmp:
        target=Path(tmp)/'portable.solidcraft';target.write_bytes((OUT/'enclosure.solidcraft').read_bytes())
        done=subprocess.run(['solidcraft-cli','eval',str(target)],capture_output=True,text=True)
        assert done.returncode==0,done.stderr
        assert json.loads(done.stdout)['body_count']==expected
    return {'no_import_features':True,'native_body_count':expected,'opens_without_external_files':True}

def main():
    state=json.loads((OUT/'enclosure-inspection.json').read_text())[-1];healthy(state);p={i['name']:i['value'] for i in state['params']}
    inv=Pos(0,0,p['mount_ceiling'])*Rot(X=180)
    parts={s.label:inv*s for s in leaves(import_step(OUT/'enclosure.step'))}
    old={s.label:inv*s for s in leaves(import_step(BASE/'enclosure.step'))}
    groups=json.loads((OUT/'enclosure-groups.json').read_text())
    structural=physical_parts(OUT/'enclosure-native.step',{n:[n] for v in groups.values() for n in v},state)
    cradle=inv*structural['body_side_cable_cradle'];expected,dim=oracle(p)
    report={'status':'running','release_status':'draft_pending_barrel_jack_axis_measurements','connector_reference_scope':'Measured 9 mm diameter across exterior saddle only; complete connector/jack geometry and axis remain unmeasured.','physical_fit_tested':False,'measured_barrel_body_diameter_mm':p['side_cable_diameter'],'connector_alignment_physically_verified':False,'native_step_sha256':hashlib.sha256((OUT/'enclosure.step').read_bytes()).hexdigest(), 'native_sketch_count':len(state['sketches']),'native_sketches_dof_zero':True,'unmodified_parts_xor_mm3':{n:xor(s,old[n]) for n,s in parts.items() if n!='body'},'body_removed_volume_mm3':volume(old['body']-parts['body']),'cradle_oracle_xor_mm3':xor(cradle,expected),'attachment_overlap_mm3':overlap(cradle,old['body']),'body_volume_added_mm3':parts['body'].volume-old['body'].volume}
    assert max(report['unmodified_parts_xor_mm3'].values())<.001
    assert report['body_removed_volume_mm3']<.001 and report['cradle_oracle_xor_mm3']<.001 and report['attachment_overlap_mm3']>1
    collisions={};gaps={}
    for button in ('reset','boot'):
        for suffix in ('slider','moving_magnet_keeper'):
            n=button+'_'+suffix;gaps[n]=1e9
            for i in range(17):
                moved=Pos(0,0,-i*.05)*parts[n];gaps[n]=min(gaps[n],cradle.distance_to(moved));v=overlap(cradle,moved)
                if v>.0001:collisions[f'{n}@{i*.05}']=v
    for n,s in parts.items():
        if n=='body':continue
        v=overlap(cradle,s)
        if v>.0001:collisions[n]=v
    report['new_cradle_interferences']=collisions;report['moving_part_minimum_gap_mm']=gaps
    assert not collisions
    d=dim; cable=Pos(d['outer']-4,d['cy'],d['top']-p['side_cable_radial_clearance'])*Rot(Y=90)*Cylinder(p['side_cable_diameter']/2,d['inner']-d['outer']+4,align=MIN)
    tx=d['cx'];hw=d['hw'];cy=d['cy'];w=p['zip_tie_width_provisional'];th=p['zip_tie_thickness_provisional'];lo=d['bottom']+.2;hi=d['top']-p['side_cable_radial_clearance']+p['side_cable_diameter']/2+.3;span=hw+th+.3
    tie=Pos(tx,cy,lo)*Box(w,2*span,th,align=MIN)
    tie+=Pos(tx,cy,hi)*Box(w,2*span,th,align=MIN)
    for sign in (-1,1):tie+=Pos(tx,cy+sign*(span-th/2),lo)*Box(w,th,hi+th-lo,align=MIN)
    head=Pos(tx,cy,hi+th)*Box(5,5,4,align=MIN)
    refs={'cable_reference':cable,'loose_tie_route':tie,'tie_head_reference':head}
    report['cable_tie_collisions']={}
    for n,s in refs.items():
        hits={k:overlap(s,target) for k,target in parts.items() if overlap(s,target)>.0001}
        report['cable_tie_collisions'][n]=hits
    print(json.dumps(report,indent=2),flush=True)
    assert not any(report['cable_tie_collisions'].values())
    report['hardware_check']=hardware_check(p,cradle,refs)
    # Actual revised body in production print pose (case-local floor at Z0).
    report['body_print_export']=save_set({'body':parts['body']},OUT/'body',p)
    production=parts|{'desk_bracket':inv*parts['desk_bracket']}
    report['full_print_export']=save_set(print_layout(print_parts(production,p)),OUT/'print-layout',p)
    fitdir=OUT/'fit-tests';fitdir.mkdir(exist_ok=True)
    crop=Pos(d['outer']-1,cy-9,0)*Box(d['inner']-(d['outer']-1)+4,18,d['top']+6,align=(Align.MIN,Align.MIN,Align.MIN))
    # Cropping near the bracket also isolates a floating piece of its gusset.
    # Keep the actual connected body section containing the complete saddle.
    sections=list((parts['body'] & crop).solids())
    selected=[s for s in sections if overlap(s,cradle)>1]
    assert len(selected)==1
    coupon=selected[0].clean();coupon.label='side_cable_holder_coupon'
    assert coupon.is_valid and len(coupon.solids())==1
    assert volume(cradle-coupon)<.001
    report['coupon_disconnected_mount_fragments_omitted']=len(sections)-1
    export_step(coupon,fitdir/'side-cable-holder.step');export_print_mesh({'side_cable_holder_coupon':coupon},fitdir/'side-cable-holder.3mf',p)
    render({'coupon':coupon},fitdir/'side-cable-holder.png',title='Side cable saddle / quick fit print',subtitle='9 mm barrel body | alignment provisional | concave seat + zip-tie tunnel | case-local print pose',elevation=28,azimuth=-145)
    render({'body':parts['body']}|{n:s for n,s in parts.items() if n.startswith(('reset_','boot_'))},OUT/'interior.png',title='Revision 015 / second cable saddle',subtitle='Existing end holder retained | side holder beside button opening',elevation=40,azimuth=-140)
    render({'coupon':coupon}|refs,fitdir/'cable-and-tie-reference.png',title='Cable and loose tie route / references only',subtitle='Reference cable, tie and head are excluded from print files',elevation=28,azimuth=-145)
    export_step(Compound(children=[coupon]+list(refs.values())),fitdir/'cable-and-tie-reference.step')
    report['status']='passed_with_inherited_usb_board_play_interference';report['inherited_issue']='Revision014 nominal USB envelope clears; allowed PCB offsets produce USB/button interference. No corrective change is made in this holder revision.'
    report['portability']=portability_check()
    (OUT/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':main()
