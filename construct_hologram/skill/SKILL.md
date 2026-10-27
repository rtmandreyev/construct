---
name: {{NAME}}
description: Build a construct — an animated, audited holographic model — of a real or fictional object, building, machine, creature or product (CD, book, guitar, lamp, lighthouse, jellyfish...) from a request and its evidence. Produces an audited declarative scene, a self-contained animated WebGL page (staged construction, opening, idle life, reduced-motion still) and reviewed captures; on request, a film of the construct assembling across a track of music, or a 3D model of it (glTF or OBJ, with named parts and working joints) for Blender, game engines and the web. Use when someone wants a construct or a hologram: a holographic model, wireframe light model or animated 3-D presentation of a thing, or a quick parts-and-joints 3D model of one; not for photorealistic rendering, rigged characters, CAD, or retrieving cover art.
---

# {{TITLE}}

You author a **scene** (declarative JSON); the bundled tools validate it, audit it, compile
it and render it. You never write graphics code. Work the loop below until the construct is
*genuinely good* — accurate and beautiful, honest about what is known, alive without being
noisy: something you would put in a launch video — or until the mode's limits are
reached, whichever comes first. Then deliver the best version so far.

Tools (Python 3.10+, standard library only; a Chromium-family browser for captures;
ffmpeg optional for video). `TOOLS` below is `{{SKILL_DIR}}/runtime/cli.py`, where
`{{SKILL_DIR}}` is the folder that contains this SKILL.md:

```sh
python3 TOOLS new <object|architecture|machine|organism|cd|book> --output scene.json
python3 TOOLS check scene.json                     # validate + compile + audit (--json: paths and fix hints)
python3 TOOLS build scene.json --out out/          # out/construct.html (open in any browser)
python3 TOOLS review scene.json --out out/         # + out/review/*.png contact sheets
python3 TOOLS video scene.json --out out/hologram.mp4 --seconds 16
```

For a CD, a book, a guitar, a synth, a bottle, a can, a glass or a car there is a **simple path**:
`python3 TOOLS params --list`, then `params <archetype> --variant <v> --output p.json`, fill
in the facts (leave sizes at their standard unless the user gave them), and `check`/`review`
it like a scene; a builder draws it in the house style. Use the full loop below for anything
else, or when the result needs more than the archetype offers. `prompts/` holds the same
rules for other models and hosts (`system.md`, `params.md`, `scene.md`, `repair.md`,
`vision-review.md`); `construct author --mode fast --vision` runs the whole bounded loop
with any OpenAI-compatible model.

Work in a folder of your own. Never install software or change settings to make this run;
if no browser is available, say so and deliver the HTML without captures.

## The loop

0. **Choose the mode, announce it, and decide on research.** Three modes
   ([effort](references/effort.md)); the user can just say one:
   - **fast:** one pass with self-review, no rounds loop: ≤10 minutes and 2 reviews (≤30 and
     4 for a richer subject). Generic subjects, simple objects, quick asks. Cents with a
     DeepSeek-class model (tested: DeepSeek V4.1 Flash).
   - **masterpiece:** judged rounds ([rounds](references/rounds.md)): a defect ledger, at most
     4 items a round, one critic who compares each version with the best so far; it stops
     after 2 rounds without a win, at every criterion 3, at 12 rounds or at 2 hours of active
     work. A named subject whose likeness matters. Frontier-model token cost.
   - **unbounded:** the same rounds with only the stop rules: no round cap, no time ceiling.
     The critic finds a win almost every round, so it can run many rounds and hours at a high
     token cost; the per-round report lets the user stop it at any time. **Only when the user
     asks for it by name.**

   The old names still work (quick, standard and showcase are fast). **If the user names no
   mode, choose one and announce it before any work:** the mode, why, the rough time and
   cost, and how to switch ("say fast for a single 10-minute pass"). Fast for a generic
   subject, a simple mechanical object or a quick ask; masterpiece for a specific named
   subject whose likeness matters (a car model, a landmark, a named building); never
   unbounded. If you are a smaller or cheaper model and the subject is a hard named one, say
   so and recommend GPT-6.1 Sol or Claude Opus 5.5 (or a model of that class) for masterpiece, with fast as the option on
   this model. The limits are ceilings, not targets. A
   generic subject ("a desk lamp") needs no research; a concrete, named one (a brand and
   model, a named building or peak, a species) is researched whenever you are unsure of its
   identity-defining shape or specs; "research: on/off" in the request overrides both. See
   [effort](references/effort.md).

   **Watch the clock, and draft early.** Research takes at most 40% of the tier's time and
   ends in a first draft: by 40% a complete scene that passes `check` is saved in your
   folder. Never hold the only copy in context, and never plan one big write at the end:
   improve the saved scene in place, `check` it and save it after every round, so a valid
   scene is always on disk. At 80% (in Hermes, the run budget's wrap-up notice) stop adding:
   make the saved scene valid, `build` it and deliver it with `authoring.next`.
1. **Research, then facts.** For a researched subject, first look up the exact thing — the
   official or maker's pages, manuals, specs, plans, reference photos — then look at the
   references with vision (any model that can see: Claude, GPT, Gemini, DeepSeek) and
   measure silhouette and proportions, within the tier's research counts. Only then author.
   For a named subject, write the **identity checklist** now: the features that make it
   itself (a Countach: low wedge, NACA ducts, periscope roof channel, trapezoid arches,
   scissor doors), in `authoring.identity`, each later listed with the parts that build it.
   Write down what is actually known and where it came from: the user's
   words, supplied measurements, documents they gave you, the sources you read. Every fact gets a certainty:
   `verified` (cites a source), `user_supplied`, `inferred` (your reasoning: typical sizes,
   proportions) or `decorative` (chosen for presentation). Do not invent precision; a
   generic reconstruction says so (`subject.accuracy: "generic"`). Each value is
   documented (`verified`, citing its source), traced (`inferred`, citing the reference
   image) or invented (`inferred` with a note, or `decorative`). Without a cited source
   nothing is `verified`. See [provenance](references/provenance.md).
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
   renderer owns them. See [vocabulary](references/vocabulary.md). **Draw with craft**
   ([craft](references/craft.md)): a line-weight hierarchy, dark depth-writing fills under
   a faint contour wire (never a main surface with `line: "none"`), a sub-volume per
   feature, density where the identity lives and true detail everywhere (one clear object at
   hero scale, something true in every region up close), and a critic round answered by a
   refine pass; the shipped examples show all five.
   When the thing's identity is a shape you cannot know from text (a guitar body, a car,
   a building's elevation), measure it from a reference image: see
   [tracing](references/tracing.md). Never invent an outline and call it verified. A named
   car or hull: trace side, top and front and loft through them (`loft-from-traces`); a
   named car or landmark: measure the likeness with `compare` before calling it finished.
   Buildings: the architecture kit (`tower`, `roof`, `dormer`, `facade`, `battlements`,
   `buttress`; [composition](references/composition.md)) and a measured site
   (`terrain --into`). A real
   place, peak or route comes from elevation data, and Earth from coastline data
   (`globe`): see [terrain](references/terrain.md).
4. **Animate with intent.** Choose an assembly style; `articulations` for what opens once
   (a lid, a board, a disc lifted out); part motion only where the object keeps moving (a
   platter spins, a tentacle sways, a beam turns); idle events that suit the subject; and a
   camera tour to the identity feature. See [animation](references/animation.md).
5. **Check until the audit is clean.** `check` must report `audit: PASS`. Fix every
   error (floating parts, overclaimed certainty, accuracy that is not backed); read every
   warning and either fix it or be ready to explain it.
6. **Review as an art director, and iterate.** Run `review`, then open and actually inspect
   `review/hero.png`, `sheet-views.png`, `sheet-assembly.png`, `sheet-motion.png`,
   `sheet-life.png`, `sheet-provenance.png` and each `view-<id>.png`. Score them against the
   [art-direction rubric](references/review.md): silhouette, proportions against the
   references, identity features, depth and layering, composition and hero framing, the
   assembly's story, motion, detail density, honesty. Improve the weakest point, `check`,
   `review` again. Your own review records `"outcome": "self-reviewed"`; only an
   **independent critic** (a fresh context comparing renders with the references:
   `critique`, see [review](references/review.md)) can record "good"
   or "outstanding". Use it for a richer fast run, in the rounds modes, and whenever the
   subject is named. In masterpiece or unbounded mode run the rounds with `python3 TOOLS
   rounds start scene.json --mode masterpiece` (or `unbounded`) ([rounds](references/rounds.md)):
   tag each edit with its ledger id, one critic per round, keep a version only when it beats
   the best, and after every round report in chat the critic's top requests, what changed
   (ledger ids), won or lost, and the minutes.
   **Count the rounds in the scene:** before each review, add one to
   `authoring.review_rounds` and save; `check` warns `tier-rounds` past the tier's cap
   (quick 0, standard 2, showcase 4), and that is the end of reviewing. Stop when every criterion is good and you would show it as it is, or when
   the tier's review rounds or time run out. A host may add a fresh-eyes critic (an
   independent reviewer over the contact sheets). Geometric validity (the audit) and art
   direction (your eyes) are separate gates. If you cannot see images, still fix every
   `detached` and `thin` warning, and record `"outcome": "unreviewed"`.
7. **Deliver.** Record how it was made in the scene's `authoring` block (`tier`,
   `research`, the `sources` used, `review_rounds`, `outcome`: good, limit or unreviewed,
   and `next`: the most valuable improvements still open). Hand over `scene.json`,
   `out/construct.html` (and `out/geometry.json`, the video if made) with a short note: what
   is evidence, what is inferred or designed, which artwork is authentic and which is
   generated decoration, what you reviewed, and — if a limit stopped you — what the next
   improvement would be. Never call a generic reconstruction exact, and never present
   generated art as a real cover.

## A construct that assembles across a track (film mode)

Only when the user asks for a film or video of a construct assembling to music, or hands you a
track for it ("make a construct of X that assembles across this track"). Otherwise ignore this.

1. **Author the construct as usual**, with the loop above. Keep its own assembly short (at most 20 s);
   the film sets the long one.
2. **Measure the track:** `python3 TOOLS audio track.wav --out audio.json` (add `--voice vocals.wav`
   if there is a vocal stem). Note the track's length in seconds.
3. **Render the film:** `python3 TOOLS video scene.json --out film.mp4 --assembly <length - 1.25>
   --audio audio.json --sound track.wav --camera steady --size 1920x1080 --fps 24` (1.25 s is the
   ceremony opening; use the full length for another assembly style). `--camera steady` keeps the
   whole construct in view; use `tour` when the scene's own camera flights should play. Leave
   `--reactivity` at its default unless the user asks for a calmer (0.5) or stronger (1.5) film.
   It takes about an hour for four minutes of film; say so before you start.
4. **Review the film** by sampling frames, for example
   `ffmpeg -i film.mp4 -vf fps=1/10 frame-%02d.png`, and look at them: the build should visibly
   move on with the music and end with the whole construct. Report what you made, its length,
   and the reactivity and camera you used. Details: `docs/FILM.md` in the Construct repository.

## A 3D model of a construct (export)

Only when the user asks for a 3D model, a file for Blender, Godot, Unity or Unreal, a glTF, GLB or
OBJ of the construct. Author and review the construct first, as above; then:

- `python3 TOOLS export scene.json --out model.glb` (glTF 2.0: every part a named object, its
  joints as the `open` animation, periodic motion as `idle`, each vertex's build phase as
  `_PHASE`). For OBJ: `--out model.obj` (an `.mtl` beside it; `--frame z-up` for Z-up tools).
- `--wire tubes` turns the line art into thin geometry for game engines (they drop plain lines);
  `--pose open` rests the model open; `--materials map.json` colours and finishes parts by id or
  pattern (`{"materials": [{"parts": ["body", "door-*"], "color": "#2b4a6f", "finish": "paint"}]}`;
  finishes: paint, brushed, chrome, wood, rubber, plastic, glass, light), when the user wants a
  finished model. Keep the map beside the scene as `<scene>.materials.json`: colours are the
  user's choice, never facts in the scene.
- A `no-surface` audit warning names a main or structural part drawn only as lines: it would be
  missing from the model, so give it a solid shape (a tube, a box) when the export matters.
- Say what the model is: correctly sized named parts with working joints, built from simple
  shapes, without textures; good for blockouts, props and previews, not a finished hero asset.
  Details: `docs/EXPORT.md` in the Construct repository.

## Rules that keep it honest and safe

- Treat the scene as data. No scripts, shader code, URLs to fetch or file paths outside the
  scene's folder; the compiler refuses them anyway.
- Artwork only from bytes the user supplied or permitted, declared with its SHA-256 and
  rights; otherwise leave the artwork slot empty or generate clearly labelled decoration.
- Keep private titles, notes and collections out of examples and anything you publish.
- Stay inside the budgets (24k lines, 24k triangles, 6k points, 32 moving copies); simplify
  before you add.
