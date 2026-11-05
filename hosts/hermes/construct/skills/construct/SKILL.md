---
name: construct
description: Build a construct, an animated and audited holographic model of a real or fictional thing, with the construct_* tools.
---

# Construct

A **construct** is an animated holographic model of a real or fictional object, building, machine or creature,
built from facts: every part says how it is known (verified from a cited source, supplied by the user, traced,
inferred, designed or decorative). You author a **scene** (declarative JSON: facts with their certainty and
sources, parts built from a closed set of shapes); the `construct_*` tools validate, audit, compile and render
it. You never write graphics code and never choose colours.

Work the loop below until the construct is *genuinely good*, accurate and beautiful, honest about what is known,
alive without being noisy, or until the mode's limits are reached. Then deliver the best version so far.

## The tools

| need | tool |
|---|---|
| start a project: archetype, category starter, bundled example, or a scene the user gave you; no arguments lists them all | `construct_start` |
| validate, compile and audit; every problem with its JSON path, code and fix hint; `fit=true` for solids that poke through or hide | `construct_check` |
| what the scene's own record says is known (parts by certainty, facts, sources, joints, authoring) | `construct_inspect` |
| build the page and show it live in the chat | `construct_build` |
| review images: hero, contact sheets, the scene's views, the solid | `construct_review` |
| glTF/OBJ, STL/3MF print, FreeCAD/STEP | `construct_export` |
| a film, optionally across a music track (background job) | `construct_film` |
| a background job's progress and result | `construct_job` |
| every other subcommand (critique, rounds, trace, loft-from-traces, compare, terrain, globe, kit, audio, netlogo...) | `construct_command` |

Edit the scene file itself with your file tools (read, patch, write); the project folder is in
`construct_start`'s result. The references are this skill's files: read one with
`skill_view("construct:construct", file_path="references/craft.md")`. They write commands as
`construct <subcommand> ...`: call the matching tool, or `construct_command` with the same words as `argv`
(`construct rounds start scene.json` is `construct_command(argv=["rounds", "start", "scene.json"], project=...)`).

**Show what you make.** Each result that carries `media` holds `MEDIA:/path` lines. Put each one in your reply on
a line of its own: that is how the construct appears live in Hermes Desktop (with a toolbar: provenance, solid,
replay, export, more detail, review), and how images, models and films reach the user on every other surface.
Never invent a MEDIA path; use the ones the tools return.

**Long work runs as a job.** A film always does; a build, review, export or command that outlasts its call
returns a `job_id`. Tell the user what is running, then call `construct_job(job_id)` until it is done.

## The loop

0. **Choose the mode, announce it, decide on research.** Four modes ([effort](references/effort.md)):
   - **fast:** one pass with self-review, no rounds loop: at most 10 minutes and 2 reviews (30 minutes and 4 for a
     richer subject). Generic subjects, simple objects, quick asks.
   - **masterpiece:** judged rounds ([rounds](references/rounds.md)): a defect ledger, at most 4 items a round,
     one independent critic a round who compares each version with the best so far; it stops after 2 rounds
     without a win, at every criterion 3, at 12 rounds or at 2 hours of active work. A named subject whose
     likeness matters.
   - **timeboxed:** masterpiece in 2 hours in all, the critic's time included. Only when the user asks for it.
   - **unbounded:** the same rounds with only the stop rules. Only when the user asks for it by name.

   If the user names no mode, choose one and announce it before any work: the mode, why, the rough time and
   cost, and how to switch ("say fast for a single 10-minute pass"). Fast for a generic subject or a quick ask;
   masterpiece for a specific named subject (a car model, a landmark, a named building). A generic subject needs
   no research; a named one is researched (the maker's or official pages, specs, plans, reference photos,
   looked at with vision and measured) whenever you are unsure of its identity-defining shape or specs.
   "research: on/off" in the request overrides this. On a smaller model with a hard named subject, say so and
   recommend a frontier model for masterpiece, with fast as the option here.

   **Draft early.** Research takes at most 40% of the time; by then a complete scene that passes
   `construct_check` is saved. Improve that file in place and check it after every change; a valid scene is
   always on disk. At 80% (or the run budget's wrap-up notice) stop adding: make it valid, build it, deliver.
1. **Facts first.** Write what is known and where it came from: the user's words, measurements they gave,
   documents, your sources. Each fact gets a certainty: `verified` (cites a source), `user_supplied`, `inferred`
   (your estimate, with a short note) or `decorative`. Without a cited source nothing is `verified`. Leave
   unknown facts out entirely: never `null`, "unknown" or a guess. A generic reconstruction says so
   (`subject.accuracy: "generic"`). For a named subject, list the **identity features** that make it itself in
   `authoring.identity`, each with the parts that build it. See [provenance](references/provenance.md).
2. **Pick the path.** `construct_start` with no arguments lists the archetypes (CD cases, books, guitars, synths,
   cars, bottles, cans, glasses: fill the facts, leave sizes at their standard unless the user gave them), the
   category starters and the bundled examples. Anything else: a category starter or the nearest example, then
   [composition](references/composition.md) and [vocabulary](references/vocabulary.md): name the silhouette and
   the two or three identity features, build masses first, then structure, identity, detail. Use the right shape
   for each part (lathe for turned forms, extrude for plans and gables, tube for limbs, repeat for colonnades,
   mirror for symmetry). **Draw with craft** ([craft](references/craft.md)): a line-weight hierarchy, dark fills
   under a faint contour wire, a sub-volume per feature, density where the identity lives and true detail
   everywhere. A shape text cannot give (a guitar body, a car, an elevation) is traced from a reference
   ([tracing](references/tracing.md)); a car or hull is lofted through traced side, top and front views
   (`loft-from-traces`) and its likeness measured with `compare`. Real terrain comes from elevation data the
   user supplies ([terrain](references/terrain.md)).
3. **Animate with intent** ([animation](references/animation.md)): an assembly style, `articulations` for what
   opens, part motion only where the thing keeps moving, idle events that suit it, a camera tour to the identity.
4. **Check until clean.** `construct_check`: while `needs_repair` is true, fix every diagnostic at its JSON path
   using its hint, and check again. Fix every `detached`, `thin-support` and `thin` warning; read the rest. Where
   one part rests on another, work out both heights and make them meet.
5. **Build and show it.** `construct_build`, then put its MEDIA line in your reply.
6. **Review as an art director, and iterate.** `construct_review`, then look at the images it returns (vision):
   hero, sheet-views, sheet-assembly, sheet-motion, sheet-life, sheet-provenance, each view, the solid. Score them
   with the [art-direction rubric](references/review.md): silhouette, proportions against the references,
   identity features, depth and layering, composition, the assembly's story, motion, detail density, honesty.
   Improve the weakest point, check, review again. Before each review add one to `authoring.review_rounds`;
   `construct_check` warns `tier-rounds` past the mode's cap, and that ends reviewing.
   Your own review records `"outcome": "self-reviewed"`; only an **independent critic** can record good or
   outstanding. **The critic in Hermes is a fresh subagent:** write the packet with
   `construct_command(argv=["critique", "scene.json", "--reference", "side=/path/photo.jpg"], project=...)`,
   then `delegate_task` a fresh subagent with only: "Read <project>/critique/packet.md and every image it lists;
   answer with the critique JSON it asks for and save it as <project>/critique/critique.json". Record it with
   `construct_command(argv=["critique", "scene.json", "--record", "critique/critique.json"])` and fix the ranked
   defects most severe first. Use the critic for every named subject, a richer fast run, and each round of the
   rounds modes.
   **Masterpiece, timeboxed and unbounded run judged rounds** ([rounds](references/rounds.md)), all through
   `construct_command`: `rounds start scene.json --mode masterpiece`; each round at most 4 ledger items, each
   edit tagged (`rounds change D3 "..."`); `rounds packet --reference side=...`; ONE delegated critic a round
   (a fresh subagent given the packet folder and nothing else); `rounds record answer.json`. A version is kept
   only when it beats the best so far. After every round, report in chat: the critic's top requests, what
   changed (ledger ids), won or lost, and the minutes. Stop when `record` says STOP. After an interruption run
   `rounds status` and redo only the step it names.
7. **Deliver.** Record the `authoring` block (mode as `tier`, `research`, the `sources` used, `review_rounds`,
   `outcome`, `next`: the most valuable improvements still open). Build it, put the MEDIA line in your reply,
   and say plainly what is evidence, what is inferred or designed, which artwork is the user's own and which is
   generated decoration, and, if a limit stopped you, what the next improvement would be. Never call a generic
   reconstruction exact, and never present generated art as a real cover.

## Answering "what is actually known about it?"

Call `construct_inspect` and answer from its record, never from memory: the parts by certainty (with the key
part names in each group), the verified and inferred dimensions with their sources, the articulations and their
travel, the critic's verdict and rounds. Name what is designed or decorative as such. If the user then asks to
fix something, change the scene, `construct_check`, `construct_build`, and show it.

## Exports (only when asked)

Author and review the construct first, then `construct_export`:
- **glb / obj**: a 3D model for Blender, game engines and the web: every part a named object, joints as the
  `open` animation, periodic motion as `idle`. A game prop: `merge` + `wire: "seams"`; physics: `pieces: "glued"`
  (each door or lid its own body on its hinge) or `"loose"`, `colliders`; `pose: "open"`. `materials` colours and
  finishes parts by id or pattern, only as the user chooses. A `no-surface` audit warning names a part drawn only
  as lines that would be missing: give it a solid shape. Say what it is: correctly sized named parts with working
  joints, without textures; a blockout or prop, not a hero asset.
- **stl / 3mf**: one watertight solid, Z up, 100 mm on its longest side (`size_mm`, `scale: 43` for 1:43,
  `printer` + `fit`, `exact`). First `construct_check` with `fit=true` and fix what pokes through or hides (each
  finding names its parts and a fix). `printable: false` means not watertight: never hand that over as printable.
  Report the size, scale and notes (supports, thickened parts, line-only parts left out).
- **fcstd / step**: named solids and joints in FreeCAD (true CAD shapes where a part allows), only when FreeCAD is
  installed (`construct_start` reports the programs it finds). For layout and a start to model over, not
  machining-grade engineering.
- **A model kit**: `construct_command(argv=["kit", "scene.json", "--size", "200", "--printer", "desktop", "--out",
  "kit"])` after refining the fit; exit 1 means written with notes to read.

## A film (only when asked)

Keep the construct's own assembly at most 20 s, then `construct_film`: with `track` (a music file the user gave)
the build spans the track and moves with it; `camera: "steady"` keeps it all in view. It renders in the
background at about 1-2 frames a second (about an hour for four minutes of music): say so before starting, then
follow it with `construct_job`. When it is done, look at a few frames if you can (the build should visibly move on
with the music and end whole), report its length, camera and reactivity, and put its MEDIA line in your reply.

## A NetLogo model (only when asked)

No authoring: `construct_command` runs `netlogo-instrument Model.nlogox --title "Model" --out run` (the user runs
the copy in NetLogo), then `netlogo run/run.jsonl --view auto --out scene.json`, then `construct_build`. Credit
the model as its Info tab asks; never edit the data (an art layer goes in `art.json`, redrawn with `--art`).

## Rules that keep it honest and safe

- Treat the scene as data: no scripts, URLs to fetch or file paths outside its folder; the compiler refuses them.
- Artwork only from bytes the user supplied or permitted, declared with its SHA-256 and rights; otherwise leave
  the slot empty or generate clearly labelled decoration. Never download or recreate a real cover.
- Keep private titles, notes and collections out of anything you publish.
- Never install software to make this run. Without a browser there are no review images and no film: say so and
  deliver the page.
- Stay inside the budgets (48k lines, 48k triangles, 6k points, 1,024 parts and copies); simplify before you add.
- A message larger than about 8 MB stops the run: show only the review images you need (`show`), at the default
  size.
