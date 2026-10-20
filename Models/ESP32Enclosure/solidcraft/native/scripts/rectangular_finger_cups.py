"""Expand existing native spherical cups to the full rectangular pad face."""
import json,subprocess
from fuse_exports import PACKAGE,normalize
from validate_project import healthy
BASE=PACKAGE/'solidcraft/native/revision-016-finger-cups'
FLAT=PACKAGE/'solidcraft/native/revision-015-side-cable-holder'
OUT=PACKAGE/'solidcraft/native/revision-017-rectangular-cups'
def main():
    if OUT.exists():raise ValueError('Preserve revisions; select a fresh output directory')
    OUT.mkdir(parents=True)
    cmds=[{'command':'document.inspect','params':{'measure':False,'sketches':False}},
          {'command':'parameters.change','params':{'name':'finger_cup_diameter','expression':'sqrt(reset_slider_width^2 + (12 mm)^2) + 1 mm','comment':'Derived sphere footprint spans the full pad diagonal with 0.5 mm radial margin, avoiding corner-tangent Boolean geometry. The pad clips the spherical surface; no independent circular cup boundary. Face length is the existing fixed 12 mm.','favorite':False}},
          {'command':'parameters.comment','params':{'name':'finger_cup_depth','comment':'Allowed range 0.5..0.8 mm; default 0.6 mm center depression. Spherical dish spans the complete rectangular top. Physical comfort and print finish pending.'}},
          {'command':'file.save','params':{'path':str(OUT/'enclosure.solidcraft'),'compression':'compact','cache':True,'preview':True}},
          {'command':'document.inspect','params':{'measure':True,'sketches':True}}]
    script=OUT/'expand-cups.json';script.write_text(json.dumps({'commands':cmds},indent=2)+'\n')
    run=subprocess.run(['solidcraft-cli','run',str(script),'--in',str(BASE/'enclosure.json'),'--save',str(OUT/'enclosure.json'),'--out',str(OUT/'enclosure-native.step'),'--results','--json-out',str(OUT/'enclosure-inspection.json')],capture_output=True,text=True)
    if run.returncode:raise RuntimeError(run.stderr[-4000:])
    state=json.loads((OUT/'enclosure-inspection.json').read_text())[-1];healthy(state)
    groups=json.loads((BASE/'enclosure-groups.json').read_text());(OUT/'enclosure-groups.json').write_text(json.dumps(groups,indent=2)+'\n')
    normalize(OUT/'enclosure-native.step',groups,OUT/'enclosure.step',state=state);print(OUT,flush=True)
if __name__=='__main__':main()
