"""Native, dimension-driven feature definitions for Chromance revision014."""
from native_builder import E,expr,val,sqrt,atan2,tan,maximum,minimum

def dimensions(b):
 p=b.p;d=b.derived
 rw=d('retention_width',p['pcb_width']+p['board_fit_width_extra'])
 cw=d('cavity_width',rw+2*p['side_margin']);cl=d('cavity_length',p['pcb_length']+2*p['end_margin'])
 ow=d('shell_width',cw+2*p['wall']);ol=d('shell_length',cl+2*p['wall'])
 bottom=d('board_bottom',p['floor']+p['solder_clearance']);top=d('board_top',bottom+p['pcb_thickness'])
 height=d('case_height',top+p['component_clearance']);cz=d('clamp_height',top+p['board_vertical_play'])
 d('lid_top',height+p['lid_thickness']);d('plate_height',height+p['bracket_clearance_above_body'])
 d('mount_ceiling',p['plate_height']-p['desk_gap_above_case_floor'])
 d('mount_interface',p['mount_ceiling']-(height-5))
 d('lug_y',ol/2-11);d('lug_x',ow/2+6)
 d('clamp_screw_x',rw/2+p['pcb_clamp_screw_offset_from_edge'])
 d('clamp_inner',p['pcb_width']/2-p['board_edge_overlap']);d('clamp_outer',rw/2+8)
 d('clamp_width',p['clamp_outer']-p['clamp_inner']);d('clamp_center',(p['clamp_inner']+p['clamp_outer'])/2)
 d('button_face',-ow/2-3.6);d('button_tip_x',-p['pcb_width']/2+p['button_inset_from_left_pcb_edge'])
 return p

def clamp(b,name,sx,sy):
 p=b.p;z=p['clamp_height']
 b.box(name+'_blank',p['clamp_width'],8,2,sx*p['clamp_center'],sy*p['clamp_y'],z,body=name,op='new')
 b.cylinder(name+'_clearance',p['m3_clearance']/2,3,sx*p['clamp_screw_x'],sy*p['clamp_y'],z-.5,body=name)
 return name,z

def button(b,which,part):
 p=b.p;name=f'{which}_{part}';prefix=name+'_';d=lambda n,x,unit='mm':b.derived(which+'_'+n,x,unit=unit)
 face=p['button_face'];y=p[which+'_housing_y'];tx=p['button_tip_x'];ty=d('tip_y',p[which+'_button_from_bottom']-p['pcb_length']/2)
 a=d('arm_base',p['board_top']+p['button_arm_height_above_pcb']);dz=a-19.2;stroke=p['button_stroke'];gap=p['button_guide_clearance']
 rear=face-14.2;ir=face-11.8;front=face-2.4;sx0=ir+gap;sx1=front-gap
 width=d('slider_width',sx1-sx0);mx=d('magnet_x',face-7.2);center=(sx0+sx1)/2
 gf=d('guide_floor',11.2+dz);sb=d('slider_bottom',13+dz);st=a+4.8;pad=st
 fixed=d('fixed_magnet_bottom',8.2+dz);moving=d('moving_magnet_bottom',sb+.8)
 boss_bottom=a-.8;boss_top=d('boss_top',maximum(a+4.8,boss_bottom+p['button_contact_insert_length']+1.4))
 elbow=face+p['button_arm_elbow_inset']
 if part=='frame':
  b.box(prefix+'stock',11.8,14,a+6.4-2.4,(ir+face)/2,y,2.4,body=name,op='new')
  b.box(prefix+'guide_channel',9.5,8.6,30,ir+4.65,y,gf,body=name,op='cut')
  b.box(prefix+'arm_sill',12.2,11.2,30,face-5.9,y,a-stroke,body=name,op='cut')
  for sign in (-1,1):b.box(prefix+f'pad_stop_{sign}',9.5,3,20,ir+4.65,y+sign*5.8,pad-stroke,body=name,op='cut')
  for i,dy in enumerate((-3,3)):
   b.cylinder(prefix+f'mount_hole_{i}',1.7,15,rear-.2,y+dy,5,body=name,axis='X')
  b.box(prefix+'fixed_magnet_channel',mx+2.15-ir+.2,4.3,2.2,(mx+2.15+ir-.2)/2,y,fixed,body=name,op='cut')
  ux=-p['pcb_width']/2;uy=-p['pcb_length']/2+p['usb_center_from_bottom'];uz=p['board_top']+p['usb_plug_underside_above_pcb'];c=p['usb_fit_clearance']
  lo=[ux-p['usb_plug_projection']-c,uy-p['usb_plug_width']/2-c,uz-c]
  hi=[ux+c,uy+p['usb_plug_width']/2+c,maximum(uz+p['usb_plug_thickness']+c,a+6.4)+.1]
  # RESET cutter misses by design. Keep only an actual cut feature when it intersects.
  if which=='boot':b.box(prefix+'usb_open_rail',hi[0]-lo[0],hi[1]-lo[1],hi[2]-lo[2],(hi[0]+lo[0])/2,(hi[1]+lo[1])/2,lo[2],body=name,op='cut')
  return name,2.4
 if part=='rear_keeper':
  b.box(prefix+'plate',2.4,14,a+4-2.4,rear+1.2,y,2.4,body=name,op='new')
  b.box(prefix+'magnet_tongue',mx-2.15-ir+.05,4.1,2,(ir+mx-2.15-.05)/2,y,fixed+.1,body=name)
  for i,dy in enumerate((-3,3)):b.cylinder(prefix+f'mount_hole_{i}',1.7,3,rear-.2,y+dy,5,body=name,axis='X')
  b.box(prefix+'stop_lug_window',3,6.6,2+stroke,rear+1.2,y,a+.8-stroke,body=name,op='cut')
  return name,2.4
 if part=='moving_magnet_keeper':
  b.box(prefix+'plug',mx-2.15-sx0-.1,4.1,2,(sx0+mx-2.15)/2,y,moving+.1,body=name,op='new')
  return name,moving+.1
 if part!='slider':raise ValueError(part)
 # Native straight tongue and overlapping round elbow, followed by a dimensioned dogleg.
 arm_body=name
 b.box(prefix+'straight_tongue',elbow-mx+.5,8.4,4.8,(mx+elbow)/2,y,a,body=arm_body,op='new')
 b.cylinder(prefix+'elbow',4.2,4.8,elbow,y,a,body=arm_body,op='join')
 length=d('dogleg_length',sqrt((tx-elbow)**2+(ty-y)**2))
 angle=d('dogleg_angle',atan2(ty-y,tx-elbow),unit='deg')
 tool=prefix+'dogleg_tool'
 b.box(prefix+'dogleg_blank',length+.5,8.4,4.8,0,0,a,body=tool,op='new')
 b.move(prefix+'dogleg_direction',tool,axis=[0,0,1],angle=angle)
 b.move(prefix+'dogleg_position',tool,translation=[(elbow+tx)/2,(y+ty)/2,0])
 b.combine(prefix+'dogleg',arm_body,[tool])
 b.cylinder(prefix+'contact_boss',4.5,boss_top-boss_bottom,tx,ty,boss_bottom,body=arm_body,op='join')
 b.box(prefix+'guide_key',width,8.6-2*gap,st-sb,center,y,sb,body=name)
 b.box(prefix+'extended_finger_pad',width,12,3+p['finger_pad_extension'],center,y,pad,body=name)
 b.chamfer(prefix+'pad_chamfer',name,[(center,y-6,pad+3+p['finger_pad_extension']),(center,y+6,pad+3+p['finger_pad_extension']),(center-width/2,y,pad+3+p['finger_pad_extension']),(center+width/2,y,pad+3+p['finger_pad_extension'])],.5)
 b.box(prefix+'rear_stop_lug',sx0-rear-.2,6,2,(sx0+rear+.2)/2,y,a+.8,body=name)
 b.box(prefix+'moving_magnet_channel',mx+2.15-sx0+.2,4.3,2.2,(mx+2.15+sx0-.2)/2,y,moving,body=name,op='cut')
 b.cylinder(prefix+'contact_through_hole',1.7,boss_top-boss_bottom+1,tx,ty,boss_bottom-.5,body=name)
 depth=p['button_contact_insert_length']+.4
 b.cylinder(prefix+'contact_heatset_pilot',p['button_contact_insert_pilot_diameter']/2,depth+.2,tx,ty,boss_top-depth,body=name)
 direction=-1 if which=='reset' else 1
 b.box(prefix+'low_collar_flat',9.2,20,a-boss_bottom+.1,tx,ty+direction*p['button_contact_collar_flat_offset']+direction*10,boss_bottom-.1,body=name,op='cut')
 ux=-p['pcb_width']/2;uy=-p['pcb_length']/2+p['usb_center_from_bottom'];uz=p['board_top']+p['usb_plug_underside_above_pcb'];c=p['usb_fit_clearance']
 lo=[ux-p['usb_plug_projection']-c,uy-p['usb_plug_width']/2-c,minimum(uz-c,sb)-.1]
 hi=[ux+c,uy+p['usb_plug_width']/2+c,uz+p['usb_plug_thickness']+c+stroke]
 b.box(prefix+'usb_loading_relief',hi[0]-lo[0],hi[1]-lo[1],hi[2]-lo[2],(hi[0]+lo[0])/2,(hi[1]+lo[1])/2,lo[2],body=name,op='cut')
 return name,sb

def print_orientation(b,name,kind,which=None):
 p=b.p
 if kind=='clamp':b.move(name+'_on_bed',name,translation=[0,0,-p['clamp_height']])
 elif kind in ('frame','rear_keeper'):
  b.move(name+'_print_rotation',name,axis=[0,1,0],angle='-90 deg')
  b.move(name+'_on_bed',name,translation=[0,0,-(p['button_face']-14.2 if kind=='rear_keeper' else p['button_face']-11.8)])
 elif kind=='moving_magnet_keeper':
  z=p[which+'_moving_magnet_bottom']+.1;b.move(name+'_on_bed',name,translation=[0,0,-z])
 elif kind=='slider':
  b.move(name+'_print_rotation',name,axis=[0,1,0],angle='180 deg')
  b.move(name+'_on_bed',name,translation=[0,0,p[which+'_arm_base']+7.8+p['finger_pad_extension']])
 elif kind=='lid':
  b.move(name+'_print_rotation',name,axis=[1,0,0],angle='180 deg');b.move(name+'_on_bed',name,translation=[0,0,p['lid_top']])
 elif kind=='bracket':
  b.move(name+'_print_rotation',name,axis=[1,0,0],angle='180 deg');b.move(name+'_on_bed',name,translation=[0,0,p['plate_height']+p['bracket_plate_thickness']])

def shell_body(b,name='body',fit=False):
 members=[name]
 p=b.p;cw,cl,ow,ol,h=(p[k] for k in ('cavity_width','cavity_length','shell_width','shell_length','case_height'));f=p['floor'];r=p['corner_radius'];bevel=p['edge_bevel']
 if fit:h=p['clamp_height']+2
 v=p['belt_projection'];bz=p['belt_bottom'];bh=p['belt_height']
 # Six adjoining analytic segments avoid coincident curved-surface unions.
 # Their taper profiles are the exact original bottom chamfer and belt envelope.
 sections=[('base_bevel',ow-2*bevel,ol-2*bevel,r-bevel,0,bevel,45),
           ('lower_wall',ow,ol,r,bevel,bz-bevel,0),
           ('belt_lower_transition',ow,ol,r,bz,v,45),
           ('belt_center',ow+2*v,ol+2*v,r+v,bz+v,bh-2*v,0),
           ('belt_upper_transition',ow+2*v,ol+2*v,r+v,bz+bh-v,v,-45),
           ('upper_wall',ow,ol,r,bz+bh,h-bz-bh,0)]
 for i,(suffix,width,length,radius,z,depth,taper) in enumerate(sections):
  b.rounded_profile_extrude(name+'_'+suffix,width,length,radius,z,depth,name,op='new' if i==0 else 'join',taper=taper)
 b.box(name+'_electronics_cavity',cw,cl,h,z=f,body=name,op='cut')
 for sy in (-1,1):b.box(name+f'_board_end_stop_{sy}',12,2,p['board_bottom']+p['pcb_thickness']/2-f,0,sy*(p['pcb_length']/2+1.4),f,body=name)
 if not fit:
  for sx in (-1,1):
   for sy in (-1,1):
    tag=f'{name}_mount_{sx}_{sy}';x=sx*p['lug_x'];y=sy*p['lug_y'];inner=sx*(ow/2-.3);outer=sx*(ow/2+12)
    b.box(tag+'_ear',12.3,14,5,sx*(ow/2+5.85),y,h-5,body=name)
    for i,dy in enumerate((-5.8,5.8)):
     b.polygon(tag+f'_ear_rib_{i}',[(inner,-(h-17.3)),(outer,-(h-5)),(inner,-(h-5))],2.4,body=name,plane='XZ',offset=y+dy,symmetric=True)
    b.cylinder(tag+'_screw_hole',p['m3_clearance']/2,6,x,y,h-5.5,body=name)
 access=p['board_top']+p['left_access_start_above_pcb']
 b.box(name+'_usb_side_opening',p['wall']+1,p['left_access_length'],h+2,-ow/2+p['wall']/2,0,access,body=name,op='cut')
 if not fit:
  b.box(name+'_end_cable_opening',p['end_cable_width'],p['wall']+1,p['end_cable_height']+2,0,ol/2-p['wall']/2,h-p['end_cable_height'],body=name,op='cut')
  for i,y in enumerate((-17.4,-11.6,-5.8,0,5.8,11.6,17.4)):
   b.slot_cut(name+f'_side_vent_{i}',9,2.4,p['wall']+1,cw/2-.5,y,p['board_top']+10.5,E('90 deg',90)-p['vent_angle'],body=name,plane='YZ')
 for sx in (-1,1):
  for i,dy in enumerate((-2.5,2.5)):
   b.box(name+f'_floor_tie_slot_{sx}_{i}',1.8,3.2,f+1,sx*(p['end_cable_width']/2+3),p['pcb_length']/2+dy,-.5,body=name,op='cut')
 # Uniform support stock joins the floor before the capture-step cuts.
 for sx in (-1,1):
  for sy in (-1,1):
   tag=f'{name}_pcb_{sx}_{sy}';tool=tag+'_support';x=sx*p['clamp_screw_x'];y=sy*p['clamp_y'];cz=p['clamp_height'];radius=p['pcb_clamp_boss_diameter']/2
   outside=p['clamp_screw_x']+radius+.8
   b.box_circle(tag+'_support_stock',outside-p['clamp_inner'],8,cz-f+2,sx*(outside+p['clamp_inner'])/2,y,f-1,x,y,radius,body=tool,op='new')
   outer=outside+.1
   inner=p['clamp_inner']-.1
   b.box(tag+'_top_height',outer-inner,2*radius+.2,1.2,sx*(outer+inner)/2,y,cz,body=tool,op='cut')
   outer=p['retention_width']/2+.4
   inner=p['clamp_inner']-.1
   b.box(tag+'_pcb_capture_step',outer-inner,8.2,cz-p['board_bottom']+1.2,sx*(outer+inner)/2,y,p['board_bottom'],body=tool,op='cut')
   if sx<0:
    x0=-outside;x1=-cw/2+.5
    outline=[(x0,y-4),(x1,y-4),(x1,y+4),(x0,y+4)]
    b.cavity(tag+'_outer_access_notches',outline,[],[(x,y,radius)],p['board_bottom'],cz-p['board_bottom']+1.2,tool,points=[(x0+.1,y)])
   b.cylinder(tag+'_insert_pilot',p['pcb_insert_pilot_diameter']/2,p['pcb_insert_bore_depth']+.1,x,y,cz-p['pcb_insert_bore_depth'],body=tool)
   members.append(tool)
 if not fit:
  proj=p['lid_corner_projection'];ov=p['lid_corner_wall_overlap'];pad=h-p['lid_corner_pad_height'];root=pad-proj*tan(p['lid_corner_support_angle']);w=proj+ov;center=(ov-proj)/2
  for sx in (-1,1):
   for sy in (-1,1):
    tag=f'{name}_lid_corner_{sx}_{sy}';tool=tag+'_support'
    b.box(tag+'_pad',w,w,h-pad,sx*(cw/2+center),sy*(cl/2+center),pad,body=tool,op='new')
    b.polygon(tag+'_x_rib',[(sx*(cw/2-proj),-(pad+1)),(sx*(cw/2+ov),-(pad+1)),(sx*(cw/2+ov),-root),(sx*cw/2,-root),(sx*(cw/2-proj),-pad)],w,body=tool,plane='XZ',offset=sy*(cl/2+center),symmetric=True)
    b.polygon(tag+'_y_rib',[(sy*(cl/2-proj),pad+1),(sy*(cl/2+ov),pad+1),(sy*(cl/2+ov),root),(sy*cl/2,root),(sy*(cl/2-proj),pad)],w,body=tool,plane='YZ',offset=sx*(cw/2+center),symmetric=True)
    b.cylinder(tag+'_heatset_pilot',p['lid_insert_pilot_diameter']/2,p['lid_insert_bore_depth']+.1,sx*(cw/2-4),sy*(cl/2-4),h-p['lid_insert_bore_depth'],body=tool)
    members.append(tool)
 for which in ('reset','boot'):
  face=p['button_face'];y=p[which+'_housing_y'];tool=f'{name}_{which}_mounting_pad'
  # Rounded pad is modeled as its own native feature group before joining.
  b.box(tool+'_stock',4.6,14,9.3,face+2.3,y,0,body=tool,op='new')
  b.fillet(tool+'_rounds',tool,[(face+2.3+sx*2.3,y+sy*7,4.65) for sx in (-1,1) for sy in (-1,1)],.8)
  members.append(tool)
  for i,dy in enumerate((-3,3)):
   targets=[(tool,'pad'),(name,'wall')]
   if which=='boot' and i==1:targets.append((name+'_pcb_-1_-1_support','embedded_stock'))
   for target,label in targets:b.cylinder(tool+f'_{label}_heatset_pilot_{i}',p['button_insert_pilot_diameter']/2,p['button_insert_bore_depth']+.01,face-.01,y+dy,5,body=target,axis='X')
 cable=cradle(b,name);members.append(cable)
 if fit:
  # Crop the same native body history to the production clamp top, then open its floor.
  height=p['clamp_height']+2
  tool=name+'_cradle_crop_tool'
  b.box(name+'_cradle_crop_volume',160,140,height,0,0,0,body=tool,op='new')
  b.combine(name+'_cradle_crop',cable,[tool],op='intersect')
  b.box(name+'_quick_floor_window',p['pcb_width']-5,p['pcb_length']-4,height+2,0,0,-1,body=name,op='cut')
 return members

def cradle(b,body):
 p=b.p;tag=body+'_cable_cradle';stock=tag+'_stock'
 cy=p['pcb_length']/2+p['end_margin'];sill=p['case_height']-p['end_cable_height'];proj=p['cable_saddle_projection'];ov=p['cable_saddle_wall_overlap'];r=p['cable_diameter_provisional']/2+p['cable_cradle_radial_clearance'];hw=r+p['cable_cradle_side_wall']
 y0=cy-proj;y1=cy+ov;ty=(y0+cy)/2;sw=p['zip_tie_width_provisional']+2*p['zip_tie_slot_side_clearance'];bottom=sill-p['zip_tie_slot_floor_below_sill'];eave=bottom+p['zip_tie_thickness_provisional']+2*p['zip_tie_slot_vertical_clearance'];apex=eave+sw/2
 groove_bottom=apex+p['cable_cradle_floor_above_tunnel'];top=groove_bottom+r;root=sill-proj
 b.box(tag+'_upper',2*hw,y1-y0,top-sill,0,(y0+y1)/2,sill,body=stock,op='new')
 b.polygon(tag+'_root',[(y0,sill),(y1,sill),(y1,root),(cy,root)],2*hw,body=stock,plane='YZ',symmetric=True)
 b.cylinder(tag+'_concave_cable_seat',r,y1-y0+2,0,y0-1,top,body=stock,axis='Y')
 b.polygon(tag+'_zip_tie_tunnel',[(ty-sw/2,bottom),(ty+sw/2,bottom),(ty+sw/2,eave),(ty,apex),(ty-sw/2,eave)],2*(hw+2),body=stock,op='cut',plane='YZ',symmetric=True)
 return stock

def lid(b,name='lid'):
 p=b.p;cw,cl,ow,ol,h=(p[k] for k in ('cavity_width','cavity_length','shell_width','shell_length','case_height'));t=p['lid_thickness'];depth=p['lid_skirt_depth'];fit=p['lid_fit_clearance']
 skirt=name+'_skirt_body';sw=cw-2*fit;sl=cl-2*fit
 b.box(name+'_skirt_stock',sw,sl,depth,0,0,h-depth,body=skirt,op='new')
 b.box(name+'_skirt_inner_cut',sw-2.4,sl-2.4,depth+1,0,0,h-depth-.5,body=None,op='cut')
 for sx in (-1,1):
  for sy in (-1,1):
   tag=f'{name}_corner_{sx}_{sy}';x=sx*(cw/2-4);y=sy*(cl/2-4)
   b.cylinder(tag+'_skirt_clearance',4.8,depth+1,x,y,h-depth-.5,body=None)
   w=p['lid_corner_projection']+p['lid_corner_wall_overlap'];center=(p['lid_corner_wall_overlap']-p['lid_corner_projection'])/2
   b.box(tag+'_skirt_trim',w+2*fit,w+2*fit,depth+.2,sx*(cw/2+center),sy*(cl/2+center),h-depth-.1,body=None,op='cut')
 b.box(name+'_skirt_usb_opening',p['wall']+4,p['left_access_length']+.6,depth+1,-cw/2,0,h-depth-.5,body=None,op='cut')
 b.box(name+'_skirt_cable_opening',p['end_cable_width']+.6,p['wall']+4,depth+1,0,cl/2,h-depth-.5,body=None,op='cut')
 skirt_fragments=b.existing_bodies()
 b.rounded_box(name+'_plate',ow,ol,t,p['corner_radius'],h,name)
 b.chamfer(name+'_exterior_bevel',name,b.rounded_loop_points(ow,ol,p['corner_radius'],h+t),p['edge_bevel'])
 b.combine(name+'_locating_skirt',name,skirt_fragments)
 for sx in (-1,1):
  for sy in (-1,1):b.cylinder(name+f'_lid_screw_{sx}_{sy}',p['m3_clearance']/2,t+1,sx*(cw/2-4),sy*(cl/2-4),h-.5,body=name)
 for i,y in enumerate(range(-24,25,6)):b.slot_cut(name+f'_diagonal_vent_{i}',29,p['lid_vent_width'],t+1,4,y,h-.5,-p['vent_angle'],body=name)
 for i,x in enumerate((-23,-20)):b.slot_cut(name+f'_accent_rail_{i}',45,.8,p['accent_depth']+.5,x,0,h+t-p['accent_depth'],E('90 deg',90),body=name)
 return name

def bracket(b,name='desk_bracket'):
 p=b.p;ow=p['shell_width'];plate=p['plate_height'];inter=p['mount_interface'];t=p['bracket_plate_thickness'];leg=p['bracket_leg_width_y'];ix=ow/2+p['belt_projection']+p['bracket_belt_clearance'];ox=ow/2+12
 b.box(name+'_desk_spine',10,2*p['lug_y']+14,t,0,0,plate,body=name,op='new')
 for sy in (-1,1):b.box(name+f'_crossbar_{sy}',ow+44,14,t,0,sy*p['lug_y'],plate,body=name)
 for sx in (-1,1):
  for sy in (-1,1):
   x=sx*p['lug_x'];y=sy*p['lug_y'];tag=f'{name}_leg_{sx}_{sy}'
   b.box(tag,ox-ix,leg,plate-inter+.05,sx*(ix+ox)/2,y,inter,body=name)
   projection=(14-leg)/2-.2
   for i,direction in enumerate((-1,1)):
    edge=y+direction*leg/2
    b.polygon(tag+f'_root_rib_{i}',[(edge,plate-p['bracket_root_gusset_height']),(edge,plate+.05),(edge+direction*projection,plate+.05)],ox-ix,body=name,plane='YZ',offset=sx*(ix+ox)/2,symmetric=True)
   b.cylinder(tag+'_heatset_pilot',p['button_contact_insert_pilot_diameter']/2,p['button_contact_insert_length']+.41,x,y,inter-.01,body=name)
 for sx in (-1,1):
  for sy in (-1,1):b.cylinder(name+f'_desk_screw_{sx}_{sy}',p['desk_screw_clearance']/2,t+1,sx*(ow/2+17),sy*p['lug_y'],plate-.5,body=name)
 return name
