---
title: Into Blender
summary: A construct in Blender with its build, joints and finish on sliders, ready to light, render or model over.
group: Makers and creators
example: revox-a77
needs: blender
time: about 15 minutes
status: ready
---

## Prompt

Teach me to take a construct into Blender, step by step, one step at a time and waiting for me between steps. Follow the Construct tutorial: skill_view("construct:construct", file_path="tutorials/05-blender.md"). Start by showing me the Revox A77 example.

## Steps

1. **Show the example.** `construct_start(example="revox-a77")` and `construct_build`; MEDIA line in the reply.
   Ask the user to press **S** (the solid): that is roughly what Blender will receive as a plain model.
2. **Check the solid first.** `construct_check(project=<id>, fit=true)`. Explain each finding (a part that pokes
   through another, or hides inside it) and fix the ones that would show in a render.
3. **A plain model.** `construct_export(format="glb", wire="seams")`: every part a named object, the joints as the
   `open` animation, periodic motion as `idle`. MEDIA line in the reply.
4. **A finish.** Ask the user which finishes they want (brushed metal, wood, black plastic, glass...), then
   `construct_export(format="glb", wire="seams", materials={"materials": [{"parts": [...], "color": "#...",
   "finish": "brushed"}]})` with only their choices (finishes: paint, brushed, chrome, wood, rubber, plastic, glass,
   light). Use part ids from `construct_inspect`.
5. **In Blender.** With the Construct add-on for Blender (from the Construct repository, `hosts/blender/`):
   File > Import > Construct, and the build, the opening and the finish are sliders. Without it, File > Import >
   glTF opens the same named parts.
6. **To model over.** `construct_export(format="obj", frame="z-up")` if they prefer Z up: quads where it can be, so it
   subdivides cleanly. For where triangles are thin, run
   `construct_command(argv=["export", "scene.json", "--out", "quality.glb", "--quality"])`: green good, amber and
   red slivers to remesh.
7. **The user's own.** Any construct from the other tutorials goes the same way; ask which.

**What next:** `08-film-to-music.md` (a film of it), `04-game-engine.md`, `01-copy-your-thing.md`.

## Notes

- Named parts at real sizes, without textures: a model to light, finish or model over, not a finished hero asset.
- Colours are the user's choice: never pick a finish for them.
