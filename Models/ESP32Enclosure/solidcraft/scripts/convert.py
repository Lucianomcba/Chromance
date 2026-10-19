"""Convert preserved revision014 into named, self-contained SolidCraft documents.

This is an exact-solids migration. Imported features support direct edits in
SolidCraft; they do not reconstruct the original Python sketch/feature history.
"""
from __future__ import annotations
import argparse,hashlib,json,shutil,subprocess,sys,tempfile
from pathlib import Path

PACKAGE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(PACKAGE/'src'))
# Initialize OCCT's font system before build123d, as in the established builder.
from fdm_cad.build import load_model,print_layout
from build123d import Compound,export_step,Location,CenterOf


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def run(args):
    done=subprocess.run([str(x) for x in args],capture_output=True,text=True)
    if done.returncode:raise RuntimeError(f'{args[0]} failed: {done.stderr[-1800:]}')
    return done


def named_compound(parts,label):
    children=[]
    for name,shape in parts.items():
        item=shape.moved(Location())
        item.label=name;children.append(item)
    result=Compound(children=children);result.label=label
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();output=args.output.resolve()
    if output.exists():raise ValueError('Choose a fresh output directory; preserved conversions are never overwritten')
    if not shutil.which('solidcraft-cli'):raise RuntimeError('Install SolidCraft CLI and put it on PATH first')
    full=PACKAGE/'revisions/014-usb-clearance';fit=PACKAGE/'fit-tests/009-usb-clearance'
    full_data=load_model(full/'model.py',json.loads((full/'parameters.json').read_text()))
    fit_data=load_model(fit/'model.py',json.loads((fit/'parameters.json').read_text()))
    output.mkdir(parents=True)
    plans=[]
    def add(name,relative,shapes,reference=None,printable=False):
        plans.append({'name':name,'relative':relative,'shapes':shapes,'reference':reference,'printable':printable})
    add('ESP32 enclosure revision014','enclosure',full_data['assembly'],full/'assembly.step')
    for name,shape in full_data['parts'].items():
        add(name,'parts/'+name,{name:shape},full/'parts'/(name+'.step'),True)
    add('Button fit registration frame','fit-tests/button_fit_frame',{'button_fit_frame':fit_data['parts']['button_fit_frame']},fit/'parts/button_fit_frame.step',True)
    add('Button and USB fit assembly','fit-tests/assembly',fit_data['assembly'],fit/'assembly.step')
    add('Three replacement pieces','fit-tests/replacements-only',print_layout(fit_data['replacement_parts']),None,True)
    add('Complete button fit print layout','fit-tests/print-layout',print_layout(fit_data['parts']),None,True)
    add('Full enclosure print layout','print-layout',print_layout(full_data['parts']),None,True)
    manifest={'schema':1,'conversion_kind':'exact imported solids; direct-editable SolidCraft import features','parametric_feature_history_rebuilt':False,'source_revision':'014-usb-clearance','quick_test':'009-usb-clearance','geometry_changes_intended':False,'units':'mm','documents':[],'source_files':{}}
    for base in (full,fit):
        names=json.loads((base/'source-files.json').read_text())
        for name in names:
            p=base/name;manifest['source_files'][str(p.relative_to(PACKAGE))]=sha(p)
    for plan in plans:
        dest=output/plan['relative'];dest.parent.mkdir(parents=True,exist_ok=True)
        source=output/'references'/(plan['relative']+'.step');source.parent.mkdir(parents=True,exist_ok=True)
        export_step(named_compound(plan['shapes'],plan['name']),source)
        saved=dest.with_suffix('.json');native=dest.with_suffix('.solidcraft');step=dest.with_suffix('.step')
        measurement=dest.parent/(dest.name+'-measurement.json')
        # Document starts from a named reference STEP and embeds it when saved.
        run(['solidcraft-cli','run','--in',source,'--save',saved,'--out',step,'--json-out',measurement])
        inspect_path=dest.parent/(dest.name+'-inspection.json')
        script={'commands':[{'command':'document.inspect','params':{'measure':True,'sketches':True}}]}
        with tempfile.TemporaryDirectory(prefix='solidcraft-inspect-') as temporary:
            command=Path(temporary)/'inspect.json';command.write_text(json.dumps(script))
            command_line=['solidcraft-cli','run',command,'--in',saved,'--save',native,'--results','--json-out',inspect_path]
            if plan['printable']:command_line+=['--out',dest.with_suffix('.3mf')]
            run(command_line)
        inspection=json.loads(inspect_path.read_text())[-1]
        errors=[f for f in inspection.get('timeline',[]) if f.get('error') or f.get('warning')]
        if errors:raise RuntimeError(f'{plan["name"]}: timeline issues: {errors}')
        if inspection.get('sketches'):raise RuntimeError('Exact import unexpectedly created sketches')
        measurements=json.loads(measurement.read_text())
        expected_count=len(plan['shapes'])
        if measurements['body_count']!=expected_count:raise RuntimeError((plan['name'],'body count',measurements['body_count'],expected_count))
        original=plan['reference']
        entry={'name':plan['name'],'path':str(saved.relative_to(output)),'native':str(native.relative_to(output)),'step':str(step.relative_to(output)),'reference_step':str(source.relative_to(output)),'original_step':str(original.relative_to(PACKAGE)) if original else None,'printable':plan['printable'],'expected_body_count':expected_count,'body_names':list(plan['shapes']),'design_sha256':sha(saved),'native_sha256':sha(native),'reference_sha256':sha(source),'step_sha256':sha(step),'inspection':str(inspect_path.relative_to(output)),'measurement':str(measurement.relative_to(output)),'frozen_reference':{}}
        for name,shape in plan['shapes'].items():
            box=shape.bounding_box()
            entry['frozen_reference'][name]={'volume_mm3':float(shape.volume),'area_mm2':float(shape.area),'center_of_mass':list(shape.center(CenterOf.MASS)),'bbox':{'min':list(box.min),'max':list(box.max)}}
        if plan['printable']:entry['mesh']=str(dest.with_suffix('.3mf').relative_to(output))
        manifest['documents'].append(entry)
        (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        print(f'CONVERTED {plan["relative"]}: {expected_count} bodies',flush=True)
    manifest['status']='converted_pending_exact_validation'
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')

if __name__=='__main__':main()
