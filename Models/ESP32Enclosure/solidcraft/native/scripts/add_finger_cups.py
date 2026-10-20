"""Append parametric spherical finger cups to both native slider pads."""
import json,subprocess
from native_builder import Builder,E
from fuse_exports import PACKAGE,normalize
from validate_project import healthy

BASE=PACKAGE/'solidcraft/native/revision-015-side-cable-holder'
OUT=PACKAGE/'solidcraft/native/revision-016-finger-cups'

def main():
    if OUT.exists():raise ValueError('Preserve revisions; choose a fresh output directory')
    OUT.mkdir(parents=True)
    state=json.loads((BASE/'enclosure-inspection.json').read_text())[-1]
    b=Builder({});b.p={p['name']:E(p['name'],p['value']) for p in state['params']};p=b.p
    depth=b.parameter('finger_cup_depth',.6,comment='Allowed range 0.4..0.8 mm, one new input at a time from defaults. Shallow spherical dish; physical comfort and finish pending.')
    diameter=b.parameter('finger_cup_diameter',7.,comment='Allowed range 6.5..7.5 mm, one new input at a time. Fits within the chamfered 7.8 mm-wide pad face.')
    for name in ('finger_cup_depth','finger_cup_diameter'):b.cmd('parameters.favorite',name=name,favorite=True)
    radius=b.derived('finger_cup_radius',(diameter*diameter/4+depth*depth)/(2*depth))
    for which in ('reset','boot'):
        top=p[which+'_arm_base']+7.8+p['finger_pad_extension']
        center=[p['button_face']-7.1,-p[which+'_housing_y'],p['mount_ceiling']-(top+radius-depth)]
        b.cmd('solid.sphere',radius=radius,center=center,operation='cut',targets=[which+'_slider'],name=which+'_spherical_finger_cup')
    b.cmd('file.save',path=str(OUT/'enclosure.solidcraft'),compression='compact',cache=True,preview=True)
    b.finish(OUT/'append-finger-cups.json')
    result=subprocess.run(['solidcraft-cli','run',str(OUT/'append-finger-cups.json'),'--in',str(BASE/'enclosure.json'),'--save',str(OUT/'enclosure.json'),'--out',str(OUT/'enclosure-native.step'),'--results','--json-out',str(OUT/'enclosure-inspection.json')],capture_output=True,text=True)
    if result.returncode:raise RuntimeError(result.stderr[-4000:])
    state=json.loads((OUT/'enclosure-inspection.json').read_text())[-1];healthy(state)
    groups=json.loads((BASE/'enclosure-groups.json').read_text());(OUT/'enclosure-groups.json').write_text(json.dumps(groups,indent=2)+'\n')
    normalize(OUT/'enclosure-native.step',groups,OUT/'enclosure.step',state=state)
    print(OUT,flush=True)
if __name__=='__main__':main()
