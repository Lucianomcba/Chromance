"""Author native feature-history documents; build_project.py saves/exports them."""
from pathlib import Path
from native_builder import Builder
from enclosure_features import dimensions,clamp,button,print_orientation,shell_body,lid,bracket
PACKAGE=Path(__file__).resolve().parents[3]

def add_part(b,name,placement='print'):
 kind=None;which=None;members=[name]
 if name=='body':members=shell_body(b)
 elif name=='button_fit_frame':members=shell_body(b,name=name,fit=True)
 elif name=='lid':lid(b);kind='lid'
 elif name=='desk_bracket':bracket(b);kind='bracket'
 elif name.startswith('pcb_clamp_'):
  clamp(b,name,-1 if 'left' in name else 1,-1 if 'front' in name else 1);kind='clamp'
 else:
  which='reset' if name.startswith('reset_') else 'boot';kind=name[len(which)+1:]
  button(b,which,kind)
 if placement=='print' and kind:print_orientation(b,name,kind,which)
 elif placement=='mounted' and name!='desk_bracket':
  b.move(name+'_mounted_rotation',members,axis=[1,0,0],angle='180 deg')
  b.move(name+'_mounted_height',members,translation=[0,0,b.p['mount_ceiling']])
 b.part_bodies[name]=members
 return members

PARTS=['body','lid','desk_bracket','pcb_clamp_left_front','pcb_clamp_left_rear','pcb_clamp_right_front','pcb_clamp_right_rear','reset_frame','reset_slider','reset_rear_keeper','reset_moving_magnet_keeper','boot_frame','boot_slider','boot_rear_keeper','boot_moving_magnet_keeper']

def model(defaults,name):
 b=Builder(defaults);dimensions(b)
 if name=='enclosure':
  # The skirt is cut before the other bodies exist; later operations name targets.
  for part in ['lid']+[p for p in PARTS if p!='lid']:add_part(b,part,'mounted')
 elif name=='fit_assembly':
  add_part(b,'button_fit_frame','local')
  for part in PARTS:
   if part.startswith(('pcb_clamp_','reset_','boot_')):add_part(b,part,'local')
 else:add_part(b,name)
 return b
