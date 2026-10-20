"""Export verified rectangular cups upright for a smooth, accessible finger face."""
import hashlib,json,tempfile,zipfile
from pathlib import Path
from copy import deepcopy
from rectangular_finger_cups import BASE,OUT
from fuse_exports import leaves,physical_parts
import cad_mesh
from export_assembly import print_parts,save_set
from fdm_cad.build import print_layout
from fdm_cad.preview import render
from build123d import import_step,Pos,Rot,Box,Align,GeomType
NAMES=('reset_slider','boot_slider')
def bed(shape):return Pos(0,0,-shape.bounding_box().min.Z)*shape

def main():
    # Shallow, thin coupons need finer tessellation to preserve cup volume.
    cad_mesh.LINEAR=.005
    state=json.loads((OUT/'enclosure-inspection.json').read_text())[-1];p={i['name']:i['value'] for i in state['params']}
    report=json.loads((OUT/'validation.json').read_text());assert report['status'].startswith('passed')
    inverse=Pos(0,0,p['mount_ceiling'])*Rot(X=180)
    mounted={s.label:s for s in leaves(import_step(OUT/'enclosure.step'))};local={n:(s if n=='desk_bracket' else inverse*s) for n,s in mounted.items()}
    printed=print_parts(local,p)
    report['flat_bed_contact_area_mm2']={}
    for n in NAMES:
        printed[n]=bed(local[n])
        area=sum(f.area for f in printed[n].faces() if f.geom_type==GeomType.PLANE and abs(f.bounding_box().min.Z)<1e-5 and abs(f.bounding_box().max.Z)<1e-5)
        assert area>25,(n,area)
        report['flat_bed_contact_area_mm2'][n]=area
    partsdir=OUT/'parts';partsdir.mkdir(exist_ok=True)
    for n in NAMES:report[n+'_export']=save_set({n:printed[n]},partsdir/n,p)
    report['replacement_sliders_export']=save_set(print_layout({n:printed[n] for n in NAMES}),OUT/'replacement-sliders',p)
    report['full_print_export']=save_set(print_layout(printed),OUT/'print-layout',p)
    dest=OUT/'parameter-checks';archive=dest/'verification-artifacts.zip';cups={}
    groups=json.loads((OUT/'enclosure-groups.json').read_text());single={n:[n] for v in groups.values() for n in v}
    with tempfile.TemporaryDirectory(prefix='rectangular-cup-samples-') as tmp,zipfile.ZipFile(archive) as z:
        states=[s for s in json.loads(z.read('states.json')) if isinstance(s,dict) and 'bodies' in s and 'timeline' in s]
        for case,s in zip(report['parameter_cases'],states):
            data=z.read(case['step']);assert hashlib.sha256(data).hexdigest()==report['parameter_archive_members_sha256'][case['step']]
            raw=Path(tmp)/case['step'];raw.write_bytes(data);native=physical_parts(raw,single,s);q={x['name']:x['value'] for x in s['params']}
            slider=inverse*native['reset_slider'];top=q['reset_arm_base']+7.8+q['finger_pad_extension'];cx=q['button_face']-7.1;cy=q['reset_housing_y']
            cap=slider & (Pos(cx,cy,top-3)*Box(12,14,4,align=(Align.CENTER,Align.CENTER,Align.MIN)))
            assert cap.is_valid and len(cap.solids())==1
            name=f"cup_{round(q['finger_cup_depth']*100):03}_up";cap=bed(deepcopy(cap.solids()[0]));cap.label=name;cups[name]=cap
    cups={n:cups[n] for n in ('cup_050_up','cup_060_up','cup_080_up')}
    fit=OUT/'fit-tests';fit.mkdir(exist_ok=True)
    report['finger_cup_samples_export']=save_set(print_layout(cups),fit/'finger-cup-samples',p)
    for shape in list(cups.values())+[local[n] for n in NAMES]:shape.tessellate(.003,.03)
    render({'default_finger_face':cups['cup_060_up']},OUT/'finger-face-detail.png',title='Full rectangular spherical finger face',subtitle='Actual slider top section | 0.6 mm center depression | original edge chamfer',elevation=32,azimuth=-60)
    render(print_layout(cups),fit/'finger-cup-samples.png',title='Full rectangular spherical cups / quick feel samples',subtitle='Left to right: 0.5, 0.6, 0.8 mm center depth | all cups face up',elevation=38,azimuth=-65)
    render(print_layout({n:local[n] for n in NAMES}),OUT/'finger-faces.png',title='Revision 017 / full rectangular spherical finger faces',subtitle='Spherical dish clipped by the full top rectangle | 0.6 mm center depth',elevation=62,azimuth=-55)
    report['print_orientation']='Sliders and feel coupons cup-side up (case-local +Z), rebased to Z0. Slicer supports under raised arm/contact boss and rear lug; protect guide/magnet fits. Process settings and physical finish remain unverified.'
    (OUT/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(OUT,flush=True)
if __name__=='__main__':main()
