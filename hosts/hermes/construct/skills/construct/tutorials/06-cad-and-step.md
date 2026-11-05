---
title: CAD and STEP
summary: A construct as true CAD shapes in FreeCAD with its joints, and a STEP file for any CAD program.
group: Makers and creators
example: tompion-year-going-clock
needs: freecad
time: about 15 minutes
status: ready
---

## Prompt

Teach me to take a construct into CAD as FreeCAD and STEP files, step by step, one step at a time and waiting for me between steps. Follow the Construct tutorial: skill_view("construct:construct", file_path="tutorials/06-cad-and-step.md"). Start by showing me Tompion's year-going clock.

## Steps

1. **Is FreeCAD here?** `construct_start()` with no arguments lists the outside programs it finds. Without FreeCAD,
   say so: there is no FCStd or STEP file without it, and Construct never installs it. FreeCAD is free
   (freecad.org); the user installs it if they want to go on.
2. **Show the example.** `construct_start(example="tompion-year-going-clock")` and `construct_build`; MEDIA line in
   the reply. Ask the user to replay the opening (the hood and the trunk door) and press **S** for the solid.
3. **Fit first.** `construct_check(project=<id>, fit=true)`; explain what each finding means and fix the ones that
   matter, so the solids meet as they should.
4. **FreeCAD and STEP.** `construct_export(project=<id>, format="fcstd", step=true)`. Report what the summary
   says: named solids grouped by build stage, true CAD shapes where a part allows, and its joints. MEDIA line in
   the reply. Tell the user to open the `.FCStd` in FreeCAD and the `.step` in any CAD program (Fusion,
   SolidWorks, Onshape).
5. **The user's own.** Ask which construct they want in CAD (one from another tutorial, or a new one), and for what:
   a layout to measure, a drawing for a builder, a part to send to a print service. Check with `fit=true`, export.
6. **Change, then export again.** `construct_edit` by part id for a size the user corrects (mark it `user_supplied`),
   `construct_check`, export again: the same scene always gives the same files.

**What next:** `02-replace-a-part.md` (one part, for a print or a service), `03-home-and-garden.md`.

## Notes

- For layout, measuring and a start to model over: not machining-grade engineering. Tolerances, threads and
  drafts are the CAD user's work.
- A part drawn only in lines has no solid: give it a solid shape if it must be in the CAD file.
