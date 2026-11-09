---
title: A model kit of your own thing
summary: Your scooter, house or guitar as a kit to print, glue and paint: numbered plates, a booklet and the same steps in 3D.
group: Everyday
example: vespa-gs150
needs: browser
time: about 30 minutes
status: ready
---

## Prompt

Teach me to make a model kit of my own thing with Construct, step by step, one step at a time and waiting for me between steps. Follow the Construct tutorial: skill_view("construct:construct", file_path="tutorials/07-a-kit-of-your-own.md"). Start by showing me the Vespa GS 150 example.

## Steps

1. **Show the example.** `construct_start(example="vespa-gs150")` and `construct_build`; MEDIA line in the reply.
   Say: an owner's 1960 Vespa GS 150 from two photos. It ships with its kit plan: 28 pieces on 2 plates in 22 steps
   at 1:12, 157 mm long (a published kit to open:
   https://rtmandreyev.github.io/construct/examples/vespa-gs150/kit/assembly.html).
2. **A first kit.** `construct_check(project=<id>, fit=true)` first: a kit cannot glue what does not touch. Then
   `construct_command(argv=["kit", "scene.json", "--scale", "12", "--printer", "desktop", "--out", "kit"],
   project=<id>)`. The first kit takes about 10 minutes: say so before starting. Exit 1 means it was written with
   notes to read. Expect many small pieces and slivers on a first kit: a construct is drawn to look right, not to be
   moulded.
3. **A plan.** The Vespa's project already holds its `kit-plan.json`: show it as the model. `{"title": "...",
   "merge": [["monocoque", "floorboard-*", ...], ...]}` merges what a factory would cast as one piece (the body with
   its floor and legshield, each wheel with its tyre and hubcaps, each cowl with its trim). Run the kit again with
   `"--plan", "kit-plan.json"`: 28 pieces on 2 plates in 22 steps. Report pieces, plates and steps, and read the
   remaining notes to the user. For the user's own construct you write its `kit-plan.json` in the project, the part
   ids taken from its `scene.json` or from the first kit's `kit/kit.json` (`pieces[].parts`).
4. **What they get.** In `kit/`: `booklet.html` (to print), `assembly.html` (the steps in 3D), a `.3mf` per plate
   for their slicer, and every piece on its own. Put the files the result lists in the reply.
5. **The user's own thing.** It starts from a construct of it in masterpiece mode: `01-copy-your-thing.md`,
   `10-your-vehicle.md` or `03-home-and-garden.md`. Ask their printer, and choose a scale it takes: 1:12 for a
   scooter or a chair, 1:24 for a car, 1:100 for a house (or `--size` in mm for the longest side). Then steps 2 and 3
   with their parts.
6. **Print one first.** Tell them to print one small sub-assembly before the plates. A piece that comes out wrong:
   `--only 12` (or `--only 'door-glass*'`) writes `only.3mf` with just those pieces. Slightly tight or loose is a
   slicer setting; the wrong shape is fixed in the construct, then the kit made again.

**What next:** `10-your-vehicle.md`, `06-cad-and-step.md`.

## Notes

- A first version: no kit has yet been printed and built by a person. They are made and checked by software and
  AI critics. Pieces are glued, without pins or hinge pins.
- A kit is only as buildable as the construct: parts that do not quite meet come out as slivers or loose pieces.
  For a kit someone will really build, `"--critic"` prints the kit critic's brief: run it as a fresh subagent and
  fix the fit it asks for.
