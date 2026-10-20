# Revision 015: second cable saddle beside the buttons

**Draft: 9 mm barrel-body size is measured; jack-axis alignment is pending.**

Revision 014 is preserved. This revision appends constrained native sketches and
features to its full enclosure history; it has no imported-solid features.

- [Editable SolidCraft assembly](enclosure.solidcraft)
- [Plain JSON history](enclosure.json)
- [Assembly STEP](enclosure.step)
- [All 15 parts, print layout](print-layout.3mf) / [STEP](print-layout.step)
- [Revised body 3MF](body.3mf) / [STEP](body.step)
- [Quick local fit print](fit-tests/side-cable-holder.3mf)
- [Actual geometry preview](interior.png)
- [Verification report](validation.json)
- [Native parameter edit checks](parameter-checks/validation.json)

The original end saddle remains. The new saddle attaches to the left wall at
case-local Y = 20.0 mm, beside the RESET end of the button opening. It projects
7 mm outside that wall, with a 45-degree root connecting to the wall/floor. Its
open concave seat is cut by a cylinder along X. A passage with a 45-degree roof
lets a zip tie wrap over the cable. Put the tie head above the cable; routing it
toward the end bracket obstructs the mounting structure. Thread and tighten it
with the lid off, leaving slack between retention and the electrical connector.

The incoming barrel connector body is **measured at 9 mm diameter**.
Its axis position is provisional pending the jack centerline measurements. Nominal groove diameter is 9.4 mm (0.2 mm radial allowance), with
2 mm side walls and 2 mm material above the tie tunnel. The tie reference is
2.5 mm wide by 1 mm thick; its provisional head envelope is 5 × 5 × 4 mm.
The cable center is at case-local Z = 17.5 mm, 7.5 mm above the perfboard top.
Its actual routing and connector height have not been measured. The cylindrical
reference covers the exterior holder only; complete connector length, inner
projection and jack geometry remain unmeasured. It does not prove connector
alignment, insertion or removal clearance. This is a cable
retainer, with no verified pull rating or electrical-connector strain-relief claim.

The new favourite parameters are `side_cable_diameter` (8.8–9.2 mm),
`side_cable_center_y` (19.8–20.2 mm), `side_cable_radial_clearance` (0.15–0.25 mm)
and `side_cradle_projection` (nominal 7 mm only). Ranges are checked one input at
a time through low → high → default. Existing revision-014 parameter reports
apply to revision 014; they are not a fresh full-range certification of revision 015.

The saddle is joined to the printable body by the export helper, like the
existing structural bodies. Use this revision's `enclosure-groups.json` when
exporting edited geometry. All other printed parts retain revision-014 geometry
and can be reused. Body print pose remains floor down, opening up; the sloped
root and tunnel roof are intended to print without supports. Material, nozzle,
layer height and slicer settings remain user-specific. Match the actual intended
body settings when printing the coupon; physical fit and strength are pending.

## Checks and limits

Native histories must remain free of errors/warnings, with zero sketch degrees
of freedom. An independent OCCT model checks the added feature, unchanged parts
are compared exactly with revision 014, and body material removal must be zero.
The new saddle is checked against moving sliders/keepers at 0.05 mm intervals
over the complete 0.8 mm stroke, stationary printed parts, and reference cable,
loose tie route and head. STEP and mesh checks do not establish physical fit.
Reference electronics and flexible wire routing are incomplete.

The existing USB limitation is retained: centered-board button motion clears,
but some permitted PCB offsets cause USB/button interference. See the
[revision-014 sampled motion report](../revision-014/button-motion-validation.json).
The new cable saddle does not resolve that interference. Nylon adjuster heads
also retain only 0.4 mm nominal lid clearance at rest; actual switch height,
overtravel, friction and magnetic return need physical testing.

Rebuild in a fresh revision directory, preserving existing output:

```bash
uv run --locked python solidcraft/native/scripts/add_side_cable_holder.py
uv run --locked python solidcraft/native/scripts/validate_side_cable_holder.py
uv run --locked python solidcraft/native/scripts/check_side_holder_parameters.py
```

The authoring script refuses an existing destination. Set its `OUT` to a fresh
path before rebuilding; the validation/check scripts import the same path.
