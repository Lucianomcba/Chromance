# Revision 016: shallow finger cups

Both RESET and BOOT sliders have a **7 mm diameter, 0.6 mm deep spherical dish**
in the exposed finger face. A flat rim and the existing 0.5 mm outer chamfer
remain. The spherical radius is derived from diameter and depth, so both inputs
stay editable in the native feature history. Earlier revisions are preserved.

- [Editable SolidCraft assembly](enclosure.solidcraft) / [plain JSON history](enclosure.json)
- [Assembly STEP](enclosure.step)
- [Two replacement sliders, printable 3MF](replacement-sliders.3mf)
- [Quick feel/finish samples, printable 3MF](fit-tests/finger-cup-samples.3mf)
- [Actual finger-face preview](finger-faces.png)
- [Individual slider STEP/3MF files](parts/)
- [All 15 parts, print layout](print-layout.3mf)
- [Validation report](validation.json)

Only the exposed pad surface is cut. Guide surfaces, rear lug, magnet pockets,
contact insert/boss, nylon-adjuster axis, pad shoulders, stops and mounting
geometry are unchanged. Slider stroke remains 0.8 mm. Reuse the existing frames,
keepers and hardware with the two new sliders; follow the existing
[button assembly guide](../../../assembly-guides/014-buttons/README.md), including
contact adjustment and release checks. New contact inserts can be fitted using
the same M3×5 interface. Do not assume physical comfort or return has been tested.

## Printing and quick iteration

The two replacement sliders keep their established print pose, with the finger
face toward the bed. The cup introduces a small 7 mm recess to bridge; underside
finish and bed adhesion are printer-dependent. The small test set checks that
surface directly before spending material on full sliders. It also includes one
cup-up comparison. A smoother cup-up sample does not validate flipping the entire
slider: arm orientation, guide fit and supports must be checked separately.
Retain the existing slider support strategy around other overhangs; keep guide,
magnet and contact fits free of support scars. No printer/filament/support profile
is embedded in these geometry-only 3MF files.

The sample pieces are actual 3 mm thick caps extracted from the native slider
states, preserving the real pad outline, edge chamfer and cup. They are feel and
finish coupons; they cannot be installed in the guide and do not check the full
mechanism. See the [sample instructions](fit-tests/README.md).

The new favourite parameters are `finger_cup_depth` (0.4–0.8 mm, default 0.6 mm)
and `finger_cup_diameter` (6.5–7.5 mm, default 7 mm). Test one new input at a time
from defaults. Existing parameters retain their earlier validation scope; this
revision does not re-certify every combination of old and new inputs.

## Geometry checks

Every native state must have clean parameters/features and all sketches solved
at zero degrees of freedom. Low → high → default edits for both new inputs run
in one native session, exporting every state. An independent sphere subtraction
must match each edited slider to within 0.001 mm³. Removed volume is also checked
against the analytic spherical-cap volume. Every other physical part must match
revision 015 exactly. STEP/3MF checks require valid, connected solids and closed,
consistently wound, manifold meshes in millimeters. The native file must reopen
without external references.

The changed sliders contain no added material: they are subsets of the prior
sliders at identical poses. Therefore their rigid motion cannot create a new
interference in the assembly. The removed caps are outside the guide and stop
surfaces. This geometric proof does not establish magnetic force, friction,
physical switch travel or comfort. Existing USB interference at permitted board
offsets remains unresolved. The barrel holder is unchanged; its axis alignment
remains paused/provisional as requested.

Rebuild into a fresh directory by changing `OUT` in the authoring script first:

```bash
uv run --locked python solidcraft/native/scripts/add_finger_cups.py
uv run --locked python solidcraft/native/scripts/check_finger_cups.py
```

The checker imports the same `BASE`/`OUT`. Native STEP/state files from the six
parameter states are retained losslessly in `parameter-checks/verification-artifacts.zip`.
Physical fit/comfort testing is pending.
