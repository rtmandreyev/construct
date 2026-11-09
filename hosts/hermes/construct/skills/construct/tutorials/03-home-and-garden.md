---
title: Plan a change at home
summary: Your shed, room or garden as a model, then the deck, shelves or extension you have in mind added to a copy of it first.
group: Everyday
example: garden-shed-planned
needs: browser
time: about 20 minutes, then an hour or two for your own
status: ready
---

## Prompt

Teach me to plan a change to my home or garden on a copy first, with Construct, step by step, one step at a time and waiting for me between steps. Follow the Construct tutorial: skill_view("construct:construct", file_path="tutorials/03-home-and-garden.md"). Start by showing me the garden shed and its planned version.

## Steps

1. **Show the shed, then the plan.** `construct_start(example="garden-shed")` and `construct_build`, then
   `construct_start(example="garden-shed-planned")` and `construct_build`; both MEDIA lines in the reply. Say: a shed
   from one photo and no measurements, then the same shed with a planned lean-to log store and a deck with a step.
   Ask the user to press Replay (**R**) on the shed: the door opens after the assembly. Then **P** on the plan: the
   new parts stand apart from the shed that is there, as *designed · to a requirement*.
2. **How the sizes were found.** `construct_inspect` on the shed: every size is inferred from the photo (a shed door
   is usually about 1.8 to 1.9 m tall; the window, the cladding boards and the pots give a scale), and each says so.
3. **Gather the user's own.** Ask for: photos from every side they can reach (one is enough to start); a few
   measurements (a wall's length, a door's height: each one improves every other size); plans or drawings if they
   have them; and the change they have in mind. Wait.
4. **The place as it is.** `construct_start(title=..., category="architecture")`. Facts first: their measurements
   `user_supplied`, estimates from the photos `inferred` with how they were estimated, each photo a source with its
   credit. Named parts a builder would recognise (base, floor, wall frames, cladding, door on its hinges, window,
   roof). `construct_check(fit=true)` until clean, so every part rests on what holds it. Build, review; masterpiece
   rounds with a critic if the user wants them.
5. **The planned version, on a copy.** `construct_start(from_path=<project>/scene.json, title="... planned")`, then
   `construct_edit` to add the change as facts first: each planned size a fact with `"requirement": true` and the
   user's request as its `source` (`add_source` with kind `user_request` if the scene has none). Then each new part,
   its label starting `Planned:`, certainty `inferred`, no `source`, the requirement facts it realises as its
   `basis`, and a note that it is designed, not built, sized to fit what is there. Check with `fit=true`, build,
   MEDIA line; ask them to press **P**: the planned parts show as *designed · to a requirement*, apart from the shed
   read from the photos.
6. **Try variations.** "Make the deck a metre deeper", "move the log store to the other side": `construct_edit` by
   part id (the ids are in the project's `scene.json`), check, build. "List the planned parts with their sizes":
   answer from `construct_inspect`.
7. **For whoever builds it.** With FreeCAD installed, `construct_export(format="fcstd", step=true)` on the planned
   project: named solids grouped in build order, and STEP for any CAD program. Or a kit at 1:20
   (`07-a-kit-of-your-own.md`).

**What next:** `06-cad-and-step.md`, `07-a-kit-of-your-own.md`.

## Notes

- A planning model, not a survey: good for seeing, deciding and explaining, not for ordering materials or for
  planning permission. Whoever builds it measures first.
- A room works the same way, from photos of its walls and a floor plan.
