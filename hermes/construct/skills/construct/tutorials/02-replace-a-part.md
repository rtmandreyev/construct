---
title: Make a missing part
summary: A knob, bracket or cover drawn to the thing it fits, as a print file or a STEP file someone can make.
group: Everyday
example: braun-sk4-knob
needs: browser
time: about 20 minutes, then an hour for your own
status: ready
---

## Prompt

Teach me to make a replacement for a missing or broken part with Construct, step by step, one step at a time and waiting for me between steps. Follow the Construct tutorial: skill_view("construct:construct", file_path="tutorials/02-replace-a-part.md"). Start by showing me the Braun SK 4 and its replacement knob.

## Steps

1. **Show the thing and the part.** `construct_start(example="braun-sk4")` and `construct_build`, then
   `construct_start(example="braun-sk4-knob")` and `construct_build`; put both MEDIA lines in your reply. Say: a
   1956 Braun SK 4 from three photos, and a replacement for its missing control knob, 35 mm across, as its own
   construct at real size. Ask the user to press **S** on the knob (the solid) and **P** (how each size is known).
2. **Read the knob's record.** `construct_inspect` on the knob project. Point out that the bore for the shaft is
   marked *designed*: it was drawn to fit, and the owner measures the real shaft before printing.
3. **A print of the example.** `construct_check(project=<knob>, fit=true)`, then
   `construct_export(project=<knob>, format="3mf", scale=1, exact=true)` for real size. Report `printable`, the size
   and the notes. Tell the user to open it in their slicer (PrusaSlicer, Bambu Studio, Cura) and look at the bore
   from below: it must be open through the skirt.
4. **Gather the user's own.** Ask for: photos of the thing, and of a matching part if there is one (the other knob,
   the bracket on the other side); the maker and model; and a measurement of what the part fits onto (the shaft's
   diameter and its flat, the hole spacing), if they can. Wait.
5. **The part as its own construct.** Optionally the whole thing first, for context (see `01-copy-your-thing.md`).
   Then `construct_start(title="... knob", category="object")`: the part at real size, modelled to print, as named
   parts (body, grip, indicator, bore). Each size says how it is known: published, read from the photos, the user's
   measurement (`user_supplied`), or designed to fit (`inferred`, with a note). Check with `fit=true` until clean.
6. **Print file and STEP.** `construct_export(format="3mf", scale=1, exact=true)`; if a hole is closed, the usual
   causes are a skirt drawn as a solid disc, or an outline that stops at the top of the hole instead of running
   down its wall: make the skirt a ring and close the outline, check, export again. With FreeCAD installed,
   `construct_export(format="step")` for anyone with CAD or a print service.
7. **Adjust to the measurement.** When the user measures the shaft ("6 mm across, 4.5 mm across the flat"),
   `construct_edit` the bore by part id with a little clearance (0.2 mm), mark it `user_supplied`, check, export.

**What next:** `06-cad-and-step.md` (CAD in more depth), `01-copy-your-thing.md` (the whole thing, from photos).

## Notes

- Fit is the one thing a model from photos cannot promise. Print a test in cheap plastic and try it on first.
- Every size marked *designed* or *inferred* is one to measure on the real thing before the final print.
