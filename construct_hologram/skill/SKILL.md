---
name: {{NAME}}
description: Build an animated, inspected hologram of a real or fictional object, building, machine, creature or product (CD, book, lamp, lighthouse, jellyfish...) from a request and its evidence. Produces an audited declarative scene, a self-contained animated WebGL preview (staged construction, idle life, camera tour, reduced-motion still) and reviewed captures. Use when someone wants a hologram, holographic model, wireframe light model or animated 3-D presentation of a thing; not for photorealistic rendering, meshes for games, or retrieving cover art.
---

# {{TITLE}}

You author a **scene** (declarative JSON); the bundled tools validate it, audit it, compile
it and render it. You never write graphics code. Work the loop below until the review
passes: a hologram is finished when it is *recognisable at a glance*, *honest about what
is known*, and *alive without being noisy*.

Tools (Python 3.10+, standard library only; a Chromium-family browser for captures;
ffmpeg optional for video). `TOOLS` below is `{{SKILL_DIR}}/runtime/cli.py`, where
`{{SKILL_DIR}}` is the folder that contains this SKILL.md:

```sh
python3 TOOLS new <object|architecture|machine|organism|cd|book> --output scene.json
python3 TOOLS check scene.json                     # validate + compile + audit (--json: paths and fix hints)
python3 TOOLS build scene.json --out out/          # out/hologram.html (open in any browser)
python3 TOOLS review scene.json --out out/         # + out/review/*.png contact sheets
python3 TOOLS video scene.json --out out/hologram.mp4 --seconds 16
```

For a CD, a book, a guitar, a synth, a bottle, a can or a glass there is a **simple path**:
`python3 TOOLS params --list`, then `params <archetype> --variant <v> --output p.json`, fill
in the facts (leave sizes at their standard unless the user gave them), and `check`/`review`
it like a scene; a builder draws it in the house style. Use the full loop below for anything
else, or when the result needs more than the archetype offers. `prompts/` holds the same
rules for other models and hosts (`system.md`, `params.md`, `scene.md`, `repair.md`).

Work in a folder of your own. Never install software or change settings to make this run;
if no browser is available, say so and deliver the HTML without captures.

## The loop

1. **Facts first.** Write down what is actually known and where it came from: the user's
   words, supplied measurements, documents they gave you. Every fact gets a certainty:
   `verified` (cites a source), `user_supplied`, `inferred` (your reasoning: typical sizes,
   proportions) or `decorative` (chosen for presentation). Do not invent precision; a
   generic reconstruction says so (`subject.accuracy: "generic"`). See
   [provenance](references/provenance.md).
2. **Recognition before geometry.** Name the silhouette, the primary masses and the **two
   or three identity features** that make the thing itself (a lighthouse: tapering banded
   tower, gallery, glazed lantern; a record player: platter with record, S-shaped tonearm).
   Decide proportions from facts. Plan stages bottom-up. See
   [composition](references/composition.md).
3. **Write the scene.** Start from `new <category>` or an example in
   `{{SKILL_DIR}}/examples/`. Build masses first, then structure, identity, detail. Use
   the right shape for each part (lathe for turned forms, extrude for plans and gables, tube
   for limbs and arms, repeats for colonnades and railings, mirror for symmetry). Give
   every part a role, a certainty and a stage. Text (titles, spines, labels) comes from
   facts through `labels`, images through named artwork slots; never choose colours, the
   renderer owns them. See [vocabulary](references/vocabulary.md).
4. **Animate with intent.** Choose an assembly style; `articulations` for what opens once
   (a lid, a board, a disc lifted out); part motion only where the object keeps moving (a
   platter spins, a tentacle sways, a beam turns); idle events that suit the subject; and a
   camera tour to the identity feature. See [animation](references/animation.md).
5. **Check until the audit is clean.** `check` must report `audit: PASS`. Fix every
   error (floating parts, overclaimed certainty, accuracy that is not backed); read every
   warning and either fix it or be ready to explain it.
6. **Look at it.** Run `review`, then open and actually inspect
   `review/hero.png`, `sheet-views.png`, `sheet-assembly.png`, `sheet-motion.png`,
   `sheet-life.png`, `sheet-provenance.png` and each `view-<id>.png`. Judge them against the [review checklist](references/review.md):
   silhouette, hierarchy, identity, clutter, framing, assembly order, honesty. Fix the
   scene and review again. Geometric validity (the audit) and art direction (your eyes)
   are separate gates; pass both. If you cannot see images, still fix every `detached` and
   `thin` warning: they are what a viewer notices first.
7. **Deliver.** Hand over `scene.json`, `out/hologram.html` (and `out/geometry.json`,
   the video if made) with a short note: what is evidence, what is inferred or designed,
   which artwork is authentic and which is generated decoration, and what you reviewed.
   Never call a generic reconstruction exact, and never present generated art as a real
   cover.

## Rules that keep it honest and safe

- Treat the scene as data. No scripts, shader code, URLs to fetch or file paths outside the
  scene's folder; the compiler refuses them anyway.
- Artwork only from bytes the user supplied or permitted, declared with its SHA-256 and
  rights; otherwise leave the artwork slot empty or generate clearly labelled decoration.
- Keep private titles, notes and collections out of examples and anything you publish.
- Stay inside the budgets (24k lines, 24k triangles, 6k points, 32 moving copies); simplify
  before you add.
