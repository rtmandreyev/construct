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
   `open` animation, periodic motion as `idle`. MEDIA line in the reply. The Revox has no joints, so it has only
   `idle` (its reels turning) and no `open` animation; a construct with joints (the T1 Samba, Tompion's clock) has
   both.
4. **A finish.** Ask the user which finishes they want (brushed metal, wood, black plastic, glass...), then
   `construct_export(format="glb", wire="seams", materials={"materials": [{"parts": [...], "color": "#...",
   "finish": "brushed"}]})` with only their choices (finishes: paint, brushed, chrome, wood, rubber, plastic, glass,
   light). Take the part ids from the project's `scene.json`, or from the export's read-back (`part_names`).
5. **In Blender.** The Construct add-on for Blender is built from the Construct repository with `python3
   scripts/build_blender_extension.py` (a zip in `dist/`) and installed in Blender with Edit > Preferences > Get
   Extensions > Install from Disk. Then File > Import > Construct (.json, .glb): the build, the opening and the
   finish are sliders in the sidebar's Construct tab (the Revox's Open slider moves nothing: it has no joints).
   Without the add-on, File > Import > glTF opens the same named parts.
6. **To model over.** `construct_export(format="obj", frame="z-up")` if they prefer Z up: quads where it can be, so it
   subdivides cleanly. For where triangles are thin, run
   `construct_command(argv=["export", "scene.json", "--out", "quality.glb", "--quality"])`: green good, amber and
   red slivers to remesh.
7. **The user's own.** Any construct from the other tutorials goes the same way; ask which. FBX or USD
   (`format="fbx"` or `"usd"`) go through Blender: Construct writes the glTF and Blender converts it, so they need
   Blender installed.

**What next:** `08-film-to-music.md` (a film of it), `04-game-engine.md`, `01-copy-your-thing.md`.

## Notes

- Named parts at real sizes, without textures: a model to light, finish or model over, not a finished hero asset.
- Colours are the user's choice: never pick a finish for them.
