"""Verify that converted print layouts preserve the published quick/full plates."""
from pathlib import Path
import argparse,json,sys
import numpy as np
from scipy.optimize import linear_sum_assignment
PACKAGE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(PACKAGE/'src'))
from fdm_cad.geometry import load_mesh_instances

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);a=p.parse_args();root=a.directory.resolve()
    cases=[('print-layout.3mf',PACKAGE/'revisions/014-usb-clearance/print-layout.3mf'),('fit-tests/print-layout.3mf',PACKAGE/'fit-tests/009-usb-clearance/print-layout.3mf'),('fit-tests/replacements-only.3mf',PACKAGE/'fit-tests/009-usb-clearance/replacements-only.3mf')]
    report={'status':'running','units':'mm','cases':[]}
    for current,previous in cases:
        actual=[m for _,scene in load_mesh_instances(root/current) for m in scene.split(only_watertight=False)]
        expected=[m for _,scene in load_mesh_instances(previous) for m in scene.split(only_watertight=False)]
        if len(actual)!=len(expected):raise AssertionError((current,'body count'))
        costs=np.array([[np.max(np.abs(x.bounds-y.bounds)) for y in expected] for x in actual])
        rows,cols=linear_sum_assignment(costs);worst=max(float(costs[i,j]) for i,j in zip(rows,cols))
        if worst>.05:raise AssertionError((current,'placement drift',worst))
        volume=max(abs(float(actual[i].volume)-float(expected[j].volume))/float(expected[j].volume) for i,j in zip(rows,cols))
        if volume>.005:raise AssertionError((current,'volume drift',volume))
        report['cases'].append({'converted':current,'preserved_original':str(previous.relative_to(PACKAGE)),'body_count':len(actual),'maximum_bounds_difference_mm':worst,'maximum_relative_volume_difference':volume,'bounds_tolerance_mm':.05,'volume_relative_tolerance':.005})
    report['status']='passed';(root/'mesh-placement-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
