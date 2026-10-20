"""Append a native parametric cable saddle beside the button opening.

Preserves revision014. Source document history remains intact; new features are
appended in case coordinates and transformed to the existing mounted pose.
"""
from pathlib import Path
import json,subprocess,sys
from fuse_exports import PACKAGE,normalize
from native_builder import Builder,E
from validate_project import healthy

BASE=PACKAGE/'solidcraft/native/revision-014'
OUT=PACKAGE/'solidcraft/native/revision-015-side-cable-holder'

def main():
    if OUT.exists():raise ValueError('Output already exists; preserve revisions')
    OUT.mkdir(parents=True)
    state=json.loads((BASE/'enclosure-inspection.json').read_text())[-1]
    b=Builder({});b.p={p['name']:E(p['name'],p['value']) for p in state['params']}
    p=b.p
    def param(n,v,comment):
        b.parameter(n,v,comment=comment);b.cmd('parameters.favorite',name=n,favorite=True);return b.p[n]
    diameter=param('side_cable_diameter',9.,'Measured 9 mm incoming barrel connector body. Allowed range 8.8..9.2 mm, one input at a time; physical fit pending.')
    cy=param('side_cable_center_y',20.,'Case-local position beside RESET end of side opening. Allowed range 19.8..20.2 mm; one input at a time.')
    depth=param('side_cradle_projection',7.,'Projection outside left wall. Nominal only: 7 mm.')
    allowance=param('side_cable_radial_clearance',.2,'Provisional radial fit allowance. Allowed range .15...25 mm; one input at a time.')
    sill=p['board_top']+p['left_access_start_above_pcb'];wallx=-p['shell_width']/2
    inner=wallx+1;outer=wallx-depth;r=diameter/2+allowance;hw=r+p['cable_cradle_side_wall']
    slot=p['zip_tie_width_provisional']+2*p['zip_tie_slot_side_clearance'];bottom=sill-1
    eave=bottom+p['zip_tie_thickness_provisional']+2*p['zip_tie_slot_vertical_clearance'];apex=eave+slot/2
    top=apex+p['cable_cradle_floor_above_tunnel']+r;cx=(outer+wallx)/2
    name='body_side_cable_cradle';b.box(name+'_stock',inner-outer,2*hw,top-sill,(inner+outer)/2,cy,sill,body=name,op='new')
    # XZ sketch uses -Z. A 45-degree root meets both the side wall and floor.
    b.polygon(name+'_root',[(outer,-sill),(inner,-sill),(inner,-(sill-(inner-outer)))],2*hw,body=name,plane='XZ',offset=cy,symmetric=True)
    b.cylinder(name+'_concave_seat',r,inner-outer+2,outer-1,cy,top,body=name,axis='X')
    b.polygon(name+'_tie_passage',[(cx-slot/2,-bottom),(cx+slot/2,-bottom),(cx+slot/2,-eave),(cx,-apex),(cx-slot/2,-eave)],2*(hw+2),body=name,op='cut',plane='XZ',offset=cy,symmetric=True)
    b.move(name+'_mounted_rotation',name,axis=[1,0,0],angle='180 deg')
    b.move(name+'_mounted_height',name,translation=[0,0,p['mount_ceiling']])
    b.cmd('file.save',path=str(OUT/'enclosure.solidcraft'),compression='compact',cache=True,preview=True)
    script=OUT/'append-holder.json';b.finish(script)
    args=['solidcraft-cli','run',str(script),'--in',str(BASE/'enclosure.json'),'--save',str(OUT/'enclosure.json'),'--out',str(OUT/'enclosure-native.step'),'--results','--json-out',str(OUT/'enclosure-inspection.json')]
    run=subprocess.run(args,capture_output=True,text=True)
    if run.returncode:raise RuntimeError(run.stderr[-4000:])
    state=json.loads((OUT/'enclosure-inspection.json').read_text())[-1];healthy(state)
    groups=json.loads((BASE/'enclosure-groups.json').read_text());groups['body'].append(name)
    (OUT/'enclosure-groups.json').write_text(json.dumps(groups,indent=2)+'\n')
    normalize(OUT/'enclosure-native.step',groups,OUT/'enclosure.step',state=state)
    print(OUT,flush=True)
if __name__=='__main__':main()
