---
title: Your vehicle
summary: Your car, bike or scooter from published sizes and your photos, your parts told apart: try wheels or colour, plan a restoration.
group: Everyday
example: vespa-gs150
needs: browser
time: about 20 minutes, then an hour or two for your own
status: ready
---

## Prompt

Teach me to make a construct of my own vehicle to customise or restore it, step by step, one step at a time and waiting for me between steps. Follow the Construct tutorial: skill_view("construct:construct", file_path="tutorials/10-your-vehicle.md"). Start by showing me the Vespa GS 150 example.

## Steps

1. **Show the example.** `construct_start(example="vespa-gs150")` and `construct_build`; MEDIA line in the reply.
   Say: an owner's 1960 Vespa GS 150 from two photos and its published sizes. Ask the user to press **L** for the
   labels (the owner's whitewalls, chrome bars, rack, spare wheel and badges say they are theirs, not the
   factory's) and **P** (how each part is known). Replay it: the cowls lift off, the handlebar steers, the stand
   folds.
2. **What is known.** `construct_inspect`: the parts by certainty, the published dimensions with their sources. The
   published sizes set the scale; the outlines are read from the photos.
3. **Gather the user's own.** Ask for: photos from every side (front, back, both sides, three-quarters; engine and
   interior if they want them); exactly what it is (maker, model, year, version); and what is theirs, not the
   factory's (wheels, rack, badges, paint). Wait.
4. **Facts, then parts.** Cars and bikes are the hardest subjects: masterpiece mode, an hour or two, on the
   strongest model available. Research the published dimensions (length, width, height, wheelbase, wheel size),
   each a fact with its source. `construct_start(title=..., category="machine")`, or the nearest example (the FJ62 or
   the T1 Samba for a car). Named parts a restorer would recognise; each owner's part its own part, labelled as theirs. What opens,
   steers or folds as articulations. `construct_check(fit=true)` until clean; build; review; rounds with a critic.
5. **Try it on the copy.** For a change, keep the original: `construct_start(from_path=<project>/scene.json,
   title="... as it left the factory")`, then `construct_edit` (remove the owner's parts; or resize the wheels), check,
   build. A colour or finish goes into an export: `construct_export(format="glb", materials={...})` with the paint,
   chrome and tyres the user names.
6. **For a restoration.** "List my parts that are not the factory's": answer from `construct_inspect` and the
   labels. A model to show a restorer: `construct_export(format="step")` with FreeCAD installed.

**What next:** `07-a-kit-of-your-own.md` (a kit of it), `05-blender.md` (render it), `01-copy-your-thing.md`.

## Notes

- A reference model, not a measurement: bodywork is read from photos. Before making or ordering a part, measure the
  real one.
