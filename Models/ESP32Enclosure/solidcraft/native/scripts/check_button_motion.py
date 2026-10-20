"""Sample actual native STEP button motion against printed parts and hardware.

No design changes. OCCT Boolean intersections and distances, 0.05 mm samples.
Electronics are measured USB and flat PCB proxies; switch/adjuster model is provisional.
"""
import hashlib,itertools,json
from fuse_exports import PACKAGE,leaves
from fdm_cad.build import load_model
from build123d import import_step,Pos

TOL=1e-4
BOUNDS={}

def bounds(shape):
    key=id(shape)
    if key not in BOUNDS:BOUNDS[key]=(shape,shape.bounding_box())
    return BOUNDS[key][1]

def near(a,b,margin=2):
    aa,bb=bounds(a),bounds(b)
    return all(max(a0,b0)-min(a1,b1)<margin for a0,b0,a1,b1 in zip(aa.min,bb.min,aa.max,bb.max))

def overlap(a,b):
    if not near(a,b,0):return 0.
    shape=a.intersect(b)
    return 0. if shape is None else sum(abs(s.volume) for s in shape.solids())

def main():
    native=PACKAGE/'solidcraft/native/revision-014/enclosure.step'
    p=json.loads((PACKAGE/'revisions/014-usb-clearance/parameters.json').read_text())
    print('Building reference electronics/hardware',flush=True)
    ref=load_model(PACKAGE/'fit-tests/009-usb-clearance/model.py',p)
    full=ref['full_model'];inverse=full['mount_transform'].inverse()
    printed={s.label:inverse*s for s in leaves(import_step(native))}
    assert len(printed)==15
    hardware={n:inverse*s for n,s in full['hardware'].items()}
    # Include the four short side inserts missing from the production hardware STEP.
    hardware.update({n:s for n,s in ref['hardware'].items() if '_body_insert_' in n})
    result={'native_step_sha256':hashlib.sha256(native.read_bytes()).hexdigest(),
        'method':'OCCT intersections and minimum distances on translated native STEP solids; discrete sampling, not continuous collision detection',
        'stroke_mm':p['button_stroke'],'sample_spacing_mm':.05,'physical_fit_tested':False,
        'limitations':['No native assembly joints or contact solver are created by this check.',
        'Actual switch height/travel, magnetic return force, friction, tolerances and flexible wiring are not verified.',
        'PCB is a flat substrate proxy; USB is a measured rectangular envelope. Other electronic components are not detailed.'],
        'buttons':{},'usb_board_positions':[]}
    for button in ('reset','boot'):
        names=[button+'_slider',button+'_moving_magnet_keeper']
        hnames=[button+'_'+s for s in ('moving_magnet','nylon_adjuster','contact_heatset_insert','nylon_jam_nut')]
        movers={n:printed[n] for n in names}|{n:hardware[n] for n in hnames}
        fixed={n:s for n,s in printed.items() if n not in names}|{n:s for n,s in hardware.items() if n not in hnames}|{'reference_pcb':ref['reference_pcb'],'reference_usb':ref['reference_usb']}
        for x,y,z in itertools.product((-.65,.65),(-.4,.4),(0,.2)):
            fixed[f'usb_shift_{x}_{y}_{z}']=Pos(x,y,z)*ref['reference_usb']
        records={};collisions={}
        for i in range(17):
            t=round(i*.05,8)
            for name,original in movers.items():
                shape=Pos(0,0,-t)*original
                assert abs(shape.bounding_box().min.Z-original.bounding_box().min.Z+t)<1e-5
                for other,target in fixed.items():
                    if not near(shape,target):continue
                    key=name+' / '+other
                    dist=shape.distance_to(target)
                    row=records.setdefault(key,{'minimum_gap_mm':float('inf'),'at_travel_mm':t})
                    if dist<row['minimum_gap_mm']:row.update(minimum_gap_mm=dist,at_travel_mm=t)
                    v=overlap(shape,target)
                    if v>TOL:
                        hit=collisions.setdefault(key,{'first_sample_mm':t,'last_sample_mm':t,'maximum_overlap_mm3':0})
                        hit.update(last_sample_mm=t,maximum_overlap_mm3=max(v,hit['maximum_overlap_mm3']))
            print(button,t,flush=True)
        result['buttons'][button]={'moving_parts':list(movers),'sample_count':17,'nearby_pair_minimum_distances':records,'interferences':collisions}
    targets=printed|hardware
    for x,y,z in itertools.product((-.65,0,.65),(-.4,0,.4),(0,.2)):
        usb=Pos(x,y,z)*ref['reference_usb'];hits={};gaps={}
        for name,target in targets.items():
            if not near(usb,target):continue
            d=usb.distance_to(target);gaps[name]=d
            v=overlap(usb,target)
            if v>TOL:hits[name]=v
        result['usb_board_positions'].append({'board_shift_mm':[x,y,z],'intersections_mm3':hits,'nearby_gaps_mm':gaps})
    result['provisional_switch_contact']={'idle_gap_mm':p['button_stroke']-p['modeled_switch_depression'], 'modeled_depression_at_stop_mm':p['modeled_switch_depression']}
    result['summary']={'centered_board_sampled_motion_clear':all(not any('usb_shift' not in k for k in b['interferences']) for b in result['buttons'].values()),'nominal_usb_minimum_gap_mm':.2,'adjuster_head_lid_minimum_gap_mm':.4,'usb_board_position_cases':len(result['usb_board_positions']),'usb_board_position_cases_with_interference':sum(bool(x['intersections_mm3']) for x in result['usb_board_positions']),'physical_fit_tested':False}
    out=PACKAGE/'solidcraft/native/revision-014/button-motion-validation.json'
    out.write_text(json.dumps(result,indent=2)+'\n')
    print(out)
    print(json.dumps({b:r['interferences'] for b,r in result['buttons'].items()},indent=2))
    print(json.dumps([r for r in result['usb_board_positions'] if r['intersections_mm3']],indent=2))
if __name__=='__main__':main()
