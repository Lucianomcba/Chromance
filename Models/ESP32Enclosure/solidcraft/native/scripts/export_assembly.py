"""Export one edited native assembly into production and matching quick prints.

All geometry comes from that saved SolidCraft design. No original Python CAD or
reference STEP is used. Print poses and the low fit-frame extraction preserve the
established manufacturing/fit-test conventions.
"""
from pathlib import Path
import argparse,json,subprocess,sys,hashlib
from fuse_exports import PACKAGE,physical_parts,leaves
from cad_mesh import export_print_mesh
from build_native import PARTS
from validate_project import healthy
from build123d import Compound,Pos,Rot,Box,Align,export_step,import_step
from fdm_cad.build import print_layout
sys.path.insert(0,str(PACKAGE/'solidcraft/scripts'))
from validate import mesh_check

def case_parts(parts,p):
 return {n:(s if n=='desk_bracket' else Pos(0,0,p['mount_ceiling'])*Rot(X=180)*s) for n,s in parts.items()}

def print_parts(local,p):
 result={}
 for name,shape in local.items():
  if name in ('body','button_fit_frame'):pass
  elif name=='lid':shape=Pos(0,0,p['lid_top'])*Rot(X=180)*shape
  elif name=='desk_bracket':shape=Pos(0,0,p['plate_height']+p['bracket_plate_thickness'])*Rot(X=180)*shape
  elif name.startswith('pcb_clamp_'):shape=Pos(0,0,-p['clamp_height'])*shape
  else:
   which='reset' if name.startswith('reset_') else 'boot'
   if name.endswith('_moving_magnet_keeper'):shape=Pos(0,0,-p[which+'_moving_magnet_bottom']-.1)*shape
   elif name.endswith('_rear_keeper'):shape=Pos(0,0,-(p['button_face']-14.2))*Rot(Y=-90)*shape
   elif name.endswith('_frame'):shape=Pos(0,0,-(p['button_face']-11.8))*Rot(Y=-90)*shape
   elif name.endswith('_slider'):shape=Pos(0,0,p[which+'_arm_base']+7.8+p['finger_pad_extension'])*Rot(Y=180)*shape
   else:raise ValueError('Unknown print pose: '+name)
  shape.label=name;result[name]=shape
 return result

def save_set(parts,stem,p,printable=True):
 stem.parent.mkdir(parents=True,exist_ok=True)
 flat={}
 for name,shape in parts.items():
  if not shape.is_valid or len(shape.solids())!=1:raise AssertionError('Invalid physical solid: '+name)
  solid=shape.solids()[0];solid.label=name;flat[name]=solid
 parts=flat
 step=stem.with_suffix('.step');export_step(Compound(children=list(parts.values())),step)
 if not printable:return {'step':str(step),'physical_parts':len(parts)}
 mesh=stem.with_suffix('.3mf');reopened={s.label:s for s in leaves(import_step(step))}
 export_print_mesh(reopened,mesh,p)
 return {'step':str(step),'mesh':str(mesh),'checks':mesh_check(mesh,step,len(parts))}

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('design',type=Path);parser.add_argument('--groups',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);a=parser.parse_args();dest=a.output.resolve()
 if dest.exists():raise ValueError('Choose a fresh export directory')
 dest.mkdir(parents=True);script=dest/'inspect.json';script.write_text(json.dumps({'commands':[{'command':'document.inspect','params':{'measure':True,'sketches':True}}]}))
 raw=dest/'native.step';inspection=dest/'native-state.json'
 done=subprocess.run(['solidcraft-cli','run',str(script),'--in',str(a.design),'--out',str(raw),'--results','--json-out',str(inspection)],capture_output=True,text=True)
 if done.returncode:raise RuntimeError(done.stderr)
 state=json.loads(inspection.read_text())[-1];healthy(state);p={x['name']:x['value'] for x in state['params']};groups=json.loads(a.groups.read_text())
 if set(groups)!=set(PARTS):raise ValueError('This exporter expects the complete mounted 15-part enclosure')
 physical=physical_parts(raw,groups,state);physical={n:physical[n] for n in PARTS};local=case_parts(physical,p);printed=print_parts(local,p)
 report={'status':'running','input_design_sha256':hashlib.sha256(a.design.read_bytes()).hexdigest(),'native_parameters':{n:p[n] for n in ('pcb_width','pcb_length','board_fit_width_extra','button_guide_clearance','usb_fit_clearance')},'physical_fit_tested':False,'outputs':{}}
 report['outputs']['mounted_assembly']=save_set(physical,dest/'assembly',p,False)
 report['outputs']['production_print']=save_set(print_layout(printed),dest/'print-layout',p)
 # Same low crop/window as test009, extracted from the edited native body.
 height=p['clamp_height']+2
 crop=Box(160,140,height,align=(Align.CENTER,Align.CENTER,Align.MIN))
 window=Pos(0,0,-1)*Box(p['pcb_width']-5,p['pcb_length']-4,height+2,align=(Align.CENTER,Align.CENTER,Align.MIN))
 frame=(local['body'] & crop)-window;frame.label='button_fit_frame'
 selected={n:s for n,s in local.items() if n.startswith(('pcb_clamp_','reset_','boot_'))}
 fit={'button_fit_frame':frame}|selected
 report['outputs']['fit_assembly']=save_set(fit,dest/'fit-tests/assembly',p,False)
 report['outputs']['fit_print']=save_set(print_layout(print_parts(fit,p)),dest/'fit-tests/print-layout',p)
 replacements={n:printed[n] for n in ('reset_slider','boot_slider','boot_frame')}
 report['outputs']['replacement_print']=save_set(print_layout(replacements),dest/'fit-tests/replacements-only',p)
 report['status']='passed';(dest/'export-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(str(dest/'print-layout.3mf'));print(str(dest/'fit-tests/print-layout.3mf'))
if __name__=='__main__':main()
