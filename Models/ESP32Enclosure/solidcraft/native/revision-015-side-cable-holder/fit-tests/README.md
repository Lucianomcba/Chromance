# Side cable saddle: quick iterative fit print

Print [side-cable-holder.3mf](side-cable-holder.3mf) first. It is an actual local
section cropped from the revised body, with its wall/floor attachment, concave
seat and tie passage. Print floor down, as the full body is oriented. Match your
intended material and settings; the file contains geometry, not a slicer profile.
The 45-degree root and tunnel roof are intended to avoid supports. Slicing and
physical testing must confirm that intent.

Measured incoming barrel body diameter is 9 mm; groove diameter is 9.4 mm. Use the
actual cable and zip tie. This coupon does not test the complete board, buttons,
USB plug, lid, bracket, full-case stiffness or warping.

1. Check the cylindrical cut is open and the cable seats without force or jacket
   damage. Record cable diameter and any needed fit allowance.
2. Thread the actual tie through the passage and around the cable; confirm the
   tunnel prints open. Put the head above the cable as shown in the
   [reference preview](cable-and-tie-reference.png), then tighten only enough to
   retain it. Verify access to trim and cut/replace the tie.
3. Check the root and wall print cleanly and remain attached. Check jacket grip
   gently by hand. No load rating is established by this test.
4. Before printing the full body, check actual cable routing/connector height
   against the Z17.5 cable-center assumption. After assembly, check free button
   return, USB fit and lid/bracket clearance with the cable and tie installed.

The [empty preview](side-cable-holder.png) shows printable geometry. Cable, tie
and head in `cable-and-tie-reference.step` and its preview are references only
and are excluded from printable exports. The loose rectangular tie route does
not simulate flexible bending or installed tension.

Record printer, filament, nozzle, layer height, support settings and fit results
against revision 015 before changing the production dimensions. Physical test
status: **pending**.
