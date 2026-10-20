# Revision 017: spherical dish across the full rectangular top

The entire rectangular finger face of both sliders is now spherical. The sphere
covers the pad corners, and the existing pad/chamfer clips its outline. There is
no circular inset or flat border on the original top plane. Center depression is
0.6 mm relative to the original flat face. The existing outer chamfer remains.
Earlier revisions are preserved.

- [Editable SolidCraft assembly](enclosure.solidcraft) / [JSON history](enclosure.json)
- [Close-up of the finger face](finger-face-detail.png) / [complete sliders](finger-faces.png)
- [Two replacement sliders, printable 3MF](replacement-sliders.3mf) / [editable SolidCraft layout](replacement-sliders.solidcraft)
- [Quick feel samples: 0.5 / 0.6 / 0.8 mm](fit-tests/finger-cup-samples.3mf)
- [Assembly STEP](enclosure.step)
- Editable individual sliders: [RESET](parts/reset_slider.solidcraft) / [BOOT](parts/boot_slider.solidcraft)
- [Individual slider STEP/3MF files](parts/)
- [Full print layout, 3MF](print-layout.3mf) / [editable SolidCraft layout](print-layout.solidcraft)
- [Geometry and mesh validation](validation.json) / [native document verification](native-document-validation.json)

The existing spherical-cut features are edited through their native parameters.
`finger_cup_depth` is the adjustable input (0.5–0.8 mm, default 0.6 mm).
`finger_cup_diameter` is now a derived construction value: pad diagonal plus
1 mm, giving 0.5 mm radial coverage beyond the corners and avoiding a tangent
cut. It is not an independently sized circular recess. Sphere radius follows
that construction diameter and the center depth. A 0.4 mm variant stalled
native recomputation and is outside this revision's validated range.

## Printing

**Print these sliders cup-side up.** Their guide-key base is on Z0 and the arm
lies parallel to the bed, keeping filament paths along the arm. Use slicer
supports under the raised arm/contact boss and rear lug where needed. Keep
bearing faces, magnet pockets and insert fits clear of support scars. The cup
should remain upward and free of supports for a clean finger surface. Review
support access and removal in the slicer; no printer/filament/support profile is
embedded in the geometry-only 3MF files. Physical finish, fit and strength remain
untested. Reuse your established material/process settings for the quick samples.

The old cup-down pose loses broad flat bed contact once the dish spans the whole
top. This revision deliberately changes the manufacturing pose without changing
the mounted assembly pose. Use this revision's exporter for later edits; the
older generic exporter retains its earlier slider orientation.

Print the [small samples](fit-tests/README.md) first to choose a feel. They are
caps extracted from the real native geometry. For a working mechanism test, use
the two replacement sliders with the existing frames, keepers and hardware.
Follow the [button assembly guide](../../../assembly-guides/014-buttons/README.md)
for inserts, magnet orientation, nylon tips, adjustment and release checks.

## Checks and limits

Independent OCCT sphere subtraction must match the native sliders to within
0.001 mm³ at low → high → default depth edits in one native session. All other
parts must match revision 016 exactly. The checks also require zero remaining
flat area on the original finger-top plane and the specified center depth on
the actual spherical face. Native histories must have zero sketch degrees of
freedom and no feature/parameter errors or warnings. STEP and 3MF exports must
have the intended connected part count, valid closed solids/meshes and mm units.
The saved native assembly must reopen without external files.

Each slider is contained within the original uncupped revision-015 slider. At
its default setting it is also contained within revision 016. Removing material
at the finger face cannot add interference at any prior rigid-motion pose.
Guide surfaces, stops and hardware interfaces are outside the cut. This does
not establish physical friction, magnetic return, switch travel or comfort.
Existing USB/board-play interference remains unresolved. The barrel holder is
unchanged and its jack-axis alignment remains paused/provisional as requested.

To rebuild, select a fresh `OUT` in the authoring script, then run:

```bash
uv run --locked python solidcraft/native/scripts/rectangular_finger_cups.py
uv run --locked python solidcraft/native/scripts/check_rectangular_cups.py
uv run --locked python solidcraft/native/scripts/export_rectangular_cups.py
```

The scripts share the same `BASE`/`OUT`.
Run `uv run --locked python solidcraft/native/scripts/package_current_native.py`
to generate the matching individual-slider and print-layout native documents.
Their terminal remove/move features isolate parts and set the manufacturing pose
while preserving the full editable source history. The nominal plate positions
are fixed layout placements; regenerate the layout after large dimension edits.
The `*-groups.json` sidecars support export through the existing fusion helper.
The packager refuses to overwrite existing native documents. Choose a fresh
revision/destination when rebuilding them. Actual native parameter-state STEP and
inspection files are kept in a hash-verified ZIP under `parameter-checks/`.
Existing unrelated parameter ranges and combinations are not re-certified here.
