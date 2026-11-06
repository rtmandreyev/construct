---
title: Invent from real designs
summary: A ship, vehicle or creature that does not exist, designed from real ones with a clear brief, for a game, film or story.
group: Makers and creators
example: kestrel
needs: browser
time: about 20 minutes, then an hour or more for your own
status: ready
---

## Prompt

Teach me to design something that does not exist from real designs with Construct, step by step, one step at a time and waiting for me between steps. Follow the Construct tutorial: skill_view("construct:construct", file_path="tutorials/09-invent-from-real-designs.md"). Start by showing me KESTREL, the ice tug.

## Steps

1. **Show the example.** `construct_start(example="kestrel")` and `construct_build`; MEDIA line in the reply. Say:
   KESTREL is an invented ice tug for a game, built from a brief that borrows reasoning from real space-tug studies
   and the ISS truss, copying nothing. Ask the user to press **P**: every part is designed, none measured, because
   none of it exists. The features the brief asked for are kept as facts.
2. **Change it without breaking it.** `construct_start(example="kestrel-v2")` and `construct_build`. Compare the two
   with `construct_inspect`: v2 asked for more detail for close-ups, keeping every part's name, place and size and
   adding detail as new parts. Explain why: every scene, animation and engine setup that names a part keeps working.
3. **Write the user's brief together.** Ask, one or two at a time: what it is and what it is for; what real designs,
   studies or living things to learn from (their reasoning, not their look); size, units and frame ("about 120 m;
   metres; Y up; nose towards +Z"); the features that must be there, numbered; what may be invented ("design what
   is missing so that it would work"); what it must fit (another construct and the exact place they meet); what
   moves (joints) and what lives (slow motion); pipeline rules (no text in the geometry, nothing random); what to
   deliver. Read the brief back for a yes.
4. **Facts from the brief.** `construct_start(title=..., category="machine")` (or `organism`). The brief's
   requirements become facts (`user_supplied`, the brief as a source); researched references `verified` with their
   source; every designed part says it is designed. Announce masterpiece mode for a design that matters.
5. **Build, check, critic.** Masses, structure, identity, detail; joints as articulations. `construct_check` until
   clean (`fit=true` if it will be exported), `construct_build`, `construct_review`, then the rounds with an
   independent critic as SKILL.md says.
6. **Deliver.** `construct_export(format="glb", pieces="glued")` for Godot, or a glb with a finish for Blender; a
   short film with `construct_film`; and notes of the sizes, the frame and the anchor points.

**What next:** `04-game-engine.md`, `05-blender.md`, `08-film-to-music.md`.

## Notes

- A design, not an engineering study: the layout follows real reasoning, but nobody has checked that it would work.
- The scene records the brief in its sources and facts. To share a design but keep the brief private, share the
  page and pictures, and ask for a copy without the brief.
- What the user makes is theirs.
