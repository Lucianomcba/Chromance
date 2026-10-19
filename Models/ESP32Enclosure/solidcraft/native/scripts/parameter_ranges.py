"""Conservative edit envelope for the first native parametric port, millimeters.

Only one input is varied at a time from the reference. These limits are not a
claim that arbitrary simultaneous combinations are physically compatible.
"""
RANGES={
 'pcb_width':(48.8,49.2),
 'pcb_length':(70.0,70.5),
 'wall':(2.3,2.5),
 'board_fit_width_extra':(.4,.6),
 'lid_fit_clearance':(.25,.35),
 'pcb_insert_pilot_diameter':(3.9,4.1),
 'button_contact_insert_pilot_diameter':(3.9,4.1),
 'button_guide_clearance':(.25,.35),
 'usb_fit_clearance':(.2,.25),
 'finger_pad_extension':(6.8,7.2),
 'cable_cradle_radial_clearance':(.15,.25),
}
NATIVE_NAMES={'floor':'floor_thickness'}
