---
title: Copy something you own
summary: Your chair, lamp or heirloom in 3D from your photos and the maker's published sizes, saying what was measured and what was guessed.
group: Everyday
example: eames-lounge-chair
needs: browser
time: about 20 minutes, then an hour for your own
status: ready
---

## Prompt

Teach me to copy something I own into a construct, step by step, one step at a time and waiting for me between steps. Follow the Construct tutorial: skill_view("construct:construct", file_path="tutorials/01-copy-your-thing.md"). Start by showing me the Eames Lounge Chair example.

## Steps

1. **Show the example.** `construct_start(example="eames-lounge-chair")`, then `construct_build(project=<id>)`; put
   its MEDIA line in your reply. Say what it is: an Eames Lounge Chair and Ottoman made from two photos and the
   maker's published sizes. Ask the user to drag to turn it, press **P** (how each part is known, in shades of how
   firmly it is held) and **S** (the solid).
2. **What is actually known.** `construct_inspect(project=<id>)`, and answer from it, never from memory: the parts
   by certainty with a few names in each group, the published dimensions and their sources. Point out that a size
   and a shape are known apart: a part can be checked against a published size and still be read from a photo.
3. **Gather the user's own thing.** Ask for: 2 to 10 photos from different sides, in good light, the whole thing in
   each (attached, or paths); what it is as exactly as they know (maker, model, year); and a measurement or two
   (height, width) if they have a tape measure. Wait for them.
4. **Facts first.** Announce the mode (masterpiece for a named piece, about half an hour to an hour; fast for a quick
   pass, recorded in the scene's `authoring.tier` as `standard`). Research the maker's published sizes.
   `construct_start(title=..., category="object")`, or the nearest example. Write the facts before any part: the
   user's measurements `user_supplied`, published sizes `verified` with their source, sizes read from the photos
   `inferred` with a note saying how. Record each photo as a source with its credit. Leave out what nobody knows.
5. **Parts, then check.** Named parts the owner would recognise, masses first, then structure and detail; what
   opens or turns as an articulation. `construct_check(project=<id>, fit=true)` until `needs_repair` is false, and
   fix every `detached`, `thin-support` and `pokes` finding.
6. **Build, review, improve.** `construct_build`, MEDIA line in the reply; `construct_review`, look at the images
   and improve the weakest point. In masterpiece mode run the rounds with an independent critic as SKILL.md says.
   Then ask the user to press **P** again: the parts that rest on their measurements now read as *seen and
   checked*, and `construct_inspect` lists those measurements as supplied by the user.
7. **Change the copy, not the original.** To try something, keep the first version:
   `construct_start(from_path=<project>/scene.json, title="... lower ottoman")`, then `construct_edit` by part id,
   the ids from the project's `scene.json` (resize the ottoman's parts 10 cm lower), check, build. A finish (walnut,
   black leather, polished aluminium) goes into an export, not the page: `construct_export(format="glb",
   materials={...})` with only the user's choices.
8. **Take it with you.** A print: `construct_check(fit=true)` first, then `construct_export(format="3mf",
   size_mm=150, exact=true)`; report `printable` and the notes. `exact=true` keeps the construct's own solids:
   without it the print is made of voxels, far larger and far slower to write. A STEP file needs FreeCAD
   (`construct_export(format="step")`).

**What next:** `05-blender.md` (finish it in Blender), `07-a-kit-of-your-own.md` (a model kit of it),
`02-replace-a-part.md` (a part that is missing).

## Notes

- A careful model, not a measurement. Before making anything to fit, measure the sizes that matter; **P** shows
  which were measured by the user, published by the maker or read from the photos.
- What no photo shows (the underside, the back, the inside) is inferred, and says so.
- Shapes come from the photos: more sides give better shapes.
