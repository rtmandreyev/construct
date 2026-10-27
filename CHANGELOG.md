# Changelog

## Unreleased (toward 1.0.0, [roadmap](docs/ROADMAP.md))

- **3D export** ([EXPORT.md](docs/EXPORT.md)): `construct export scene.json --out model.glb|.obj`,
  the MCP tool `construct_export`, and a step in the skill.
  - glTF 2.0 (.glb): every part a named node under its stage, with its role, certainty and source;
    surfaces with smoothed normals and a material per role (or from `--materials map.json`); the
    line art as edges, thin tubes (`--wire tubes`) or nothing; the articulations as the `open`
    animation (and `open:<id>` for each), nested so a chain still rides; spin, swing and bob as
    the looping `idle` animation; each vertex's build phase as `_PHASE`.
  - OBJ with its MTL: the same surfaces and edges in one pose (`--pose`, `--frame z-up`).
  - The export reads a solid compile (`compile_scene(scene, solid=True)`), which keeps every
    shape's surfaces; the hologram's own compile is unchanged.
  - Checked against the compiler: every vertex of an opened joint or a spinning part lands where
    the compiler puts it, in a pure-Python glTF evaluator and in Blender 5.2's importer.
- **Construct for Blender** ([hosts/blender](hosts/blender/README.md)): an add-on (a Blender
  extension, 4.2 and later) built by `scripts/build_blender_extension.py`. File → Import →
  Construct reads a scene or a `.glb`; the construct gets three controls, **Build**, **Open** and
  **Light ↔ Metal**, plus the line thickness and an operator that keyframes a reveal. The controls
  are custom properties driving the joints, materials and line art, so a .blend works without the
  add-on. In Blender 5.2 the opened joints land exactly where the compiler puts them.
- **From light to metal** ([examples/light-to-metal](examples/light-to-metal/README.md)), under
  Beyond objects in the gallery: four gallery constructs (the FJ62, the James Webb Space Telescope,
  the Revox A77 and the MiniFreak) as their exported files, lit live with three.js: a scan line
  from the hologram to the solid model, the build, the joints, an exploded view with each part's
  name, role, certainty and size, and a download of each file. The site build exports the files
  (`exports` in `examples/beyond.json`); a beyond card may name its own buttons.
- **Finished models:** a material map's rules take a `finish` (paint, brushed, chrome, wood, rubber,
  plastic, glass, light), exported with standard glTF extensions (clear coat, transmission and IOR,
  emissive strength) and kept in `extras.construct.finish`. The Blender add-on adds a **Plain ↔
  Finished** control, reads `<scene>.materials.json` beside a scene (or a map chosen on import),
  and makes wood, brushed metal and rubber procedural. The example page gains the same control and
  material maps for its four constructs; its hero shows the hologram, the plain model and the
  finished one in one Blender render.
- **Seams, not wireframes:** on the solid and finished model, a part's construction lines (the
  edges of its own surfaces) fade, faint on the plain model and gone on the finished one; parts
  drawn as lines (seams, creases, outlines) stay as seams. In the add-on and on the example page.
- **Fixed in the Blender add-on:** the line art's tubes rendered with Blender's default material
  (geometry made by a modifier carries none); each tone now has a node group that sets it.
- **Game-ready export:** `--merge` merges every part that does not move into one mesh per material
  (the FJ62 goes from about 300 draw calls to 27, its tailgate still opening); `--wire seams` makes
  tubes of the design lines only, in a dark seam material, for a finished model; surfaces carry
  box-projected texture coordinates (also in OBJ); a part named for its glazing gets glass, and
  glass also carries a translucent base colour for engines without transmission. Checked in
  Godot 4.7.2 (`CONSTRUCT_GODOT`).
- **Audit:** `no-surface` warns when a main or structural part is drawn only as lines, so it would
  be missing from a 3D export.

## 0.3.0 — 2026-10-24

- **Film mode** ([FILM.md](docs/FILM.md)): a construct can assemble across a whole track of
  music, and you can see the music in it.
  - `construct audio` measures a track per video frame: loudness, brightness, attacks
    (`onset`), the moments it changes section, and a voice stem if you have one. Each track is
    measured against its own range by default (`--scale fixed` keeps one fixed window).
  - `video --assembly S --audio features.json --sound track.wav` renders an assembly of S
    seconds with the track in the MP4. The build nearly pauses in quiet passages and surges in
    loud ones, the light swells and dims (60–140%), strong attacks flare the build front, and
    each new section starts a new stage of the construct. `--reactivity` (0..2, default 1) sets
    how strongly; 0 is an even build.
  - `--camera tour|steady|still` chooses the camera; a scene's own tour keeps its place in a
    longer assembly.
  - Scenes may set an assembly of up to 1200 seconds, with a `long-assembly` warning above 20.
  - The skill knows the film workflow, for requests like "a construct of X that assembles
    across this track".
  - Strictly optional: film mode is its own script (`viewer/film.js`), embedded only with
    `build --film` or a film option to `video`. Without it Construct writes exactly what 0.2.1
    wrote: the viewer is the 0.2.1 viewer, byte for byte, and `check`, `build`, `review` and
    `video` give identical files for stock examples.
  - An optional three.js loader for filmmakers ships in `construct_hologram/film/`.
- **Docs for people new to Construct:** [How a construct is made](docs/HOW-IT-IS-MADE.md) (with a
  construct improving round by round), [The Measured Light style](docs/STYLE.md) (with annotated
  pictures), [Troubleshooting](docs/TROUBLESHOOTING.md), a docs index with a short glossary, and
  release notes. USING is rewritten for users, and the contributor material moved to
  [DEVELOPMENT.md](docs/DEVELOPMENT.md).
- **A README in the house style**: a plain opening, the three most complex examples assembling,
  how it works as a flowchart, then install, quick start, modes, models and requirements.
- **Repository furniture:** a test workflow on every push and pull request, issue and pull
  request templates, and SECURITY.md.
- **The gallery's construct pages** are built without the round history, so no published page
  shows the round timeline, whatever its URL.
- **Tests that need a browser** now skip cleanly as a class when none is available (or with
  `HOLOGRAM_SKIP_CAPTURE=1`); before, the skip marker sat on a helper that compile-only tests
  also use.

## 0.2.1 — 2026-10-23

Construct 0.2.1 makes long runs pay off and makes the result easy to choose and to trust: three
modes, a masterpiece loop judged by an independent critic, drawing rules that keep constructs
detailed, and a gallery of 24 examples made by AI agents.

### Three modes, and the skill picks one

- **fast:** one pass with self-review, about 10 minutes (30 for a richer subject). For generic
  subjects, simple objects and quick requests; cheaper models such as DeepSeek V4.1 Flash do these well.
- **masterpiece:** rounds judged by an independent critic, each new version compared with the
  best so far. It stops after two rounds without a win, at 12 rounds, or after 2 hours of active
  work. For a named car, landmark or building whose likeness matters.
- **unbounded:** the same rounds without the cap or the time limit, only when you ask for it.
  The critic finds an improvement almost every round, so it can run for hours at a high token
  cost; every round is reported, so you can stop it at any time.
- When you name no mode, the skill picks one and tells you before it starts: which mode, why,
  roughly how long and what it costs, and how to switch. It never picks unbounded. A smaller
  model asked for a hard named subject says so and recommends GPT-6.1 Sol or Claude Opus 5.5.
- The old tier names still work: quick, standard and showcase are fast, masterpiece is
  masterpiece. `--mode`, `mode:` in a request, the MCP `construct_limits` tool and the Claude
  Code budget hook all accept them.

### The masterpiece loop (`construct rounds`)

- **One fresh critic a round, in three parts:** it judges the new version on its own, then
  picks the better of the new version and the best so far (unlabelled, in random order, from the
  same views, beside the references), then updates the list of open defects.
- **The pairwise pick decides.** A version that wins is kept and its regressions are repaired
  next; one that loses is reverted. Scores are recorded, but every score below 3 must name the
  defect that holds it back.
- **Small rounds:** at most four defects worked on per round, each edit tagged with the defect
  it addresses, so it is clear what helped.
- **What the renderer cannot draw** (hidden lines showing faintly through solids, tinted glass,
  an opening in a still) is known from the start and never sent back as work.
- **Fair timing:** active time is measured from the run folder's own activity; the critic's
  time is logged separately, and `rounds pause` marks a break.
- **A record you can read and resume:** a short report in chat after every round, `rounds.md`,
  a checkpoint per round, `rounds status` after any interruption, and the round timeline in
  `construct.html`.

### Drawing that reads

- **A drawing-craft guide** (`references/craft.md`): a line-weight hierarchy, dark fills under
  a faint contour wire, a sub-volume per feature, density where the identity lives, and a
  critic round answered by a refine pass, with excerpts from the strongest constructs.
- **Main surfaces keep their contour.** A body, roof or tower drawn as a flat dark shape reads
  as cardboard; `check` now warns `bare-surface`, and the critic is told that faint surface
  contours are form, not clutter.
- **Detail everywhere:** one clear object at full view, and something true to find in every
  region up close. A bare face or an empty corner is unfinished work.

### An independent critic, and likeness you can measure

- `construct critique` writes a packet for a fresh model (instructions, the request, an identity
  checklist, renders beside the reference photos) and records its answer bound to the scene's
  hash. Only the critic can call a construct "good" or "outstanding".
- `authoring.identity`: the features that make the subject itself, each mapped to the parts
  that build it.
- `construct compare` measures the construct's silhouette against a traced reference outline,
  and `construct loft-from-traces` builds a body from side, top and front traces.

### New shapes

- A `loft` shape and a `vehicle` archetype, so cars come out as cars; an architecture kit
  (`tower`, `roof`, `dormer`, `facade`, `battlements`, `buttress`), parabolic towers and ribbed
  `shell` roofs; measured terrain as a building's site; a cleaner globe from dense coastline data.

### Examples

- **24 example constructs** in `examples/`, each with its scene, a hero image, its mode and
  the model that made it, and a live gallery built from them (`scripts/build_site.py`). All of
  them build with this release.
- Six new skill examples drawn with the craft guide: a Leica M3, an open-reel tape recorder, a
  sea cliff at dusk, a Jackson Juggernaut ET7, a Porsche 911 (964) and the Sagrada Família.

### Fixes

- The packaged skills ship the examples and prompts that `critique`, `author` and `prompts`
  read; they crashed from an install before.
- `compare` leaves ornament out of the silhouette, fills a tyre drawn as a wire torus, and finds
  a plan trace drawn in any orientation.
- `check` warns when a car's outline is drawn with thin tubes (`tube-outline`) and when a run
  passes its review rounds (`tier-rounds`); an opt-in Claude Code hook enforces the limits.

## 0.2.0 — Construct (2026-10-19)

The first release as **Construct**, an independent MIT-licensed project.

- **Name and ids.** Skill, MCP server and command `construct`; Python distribution
  `construct-hologram`, import package `construct_hologram`. Contract `construct/0.2` with
  formats `construct-scene` v2, `construct-geometry` v2 and `construct-params` v1. The previous
  ids (`tessera.hologram/0.2`, `tessera-hologram`, `tessera-hologram-params`,
  `tessera-hologram-geometry`) are read for one release with a `legacy-format` warning and are
  never written.
- **Any-model authoring:** `construct author` drafts with any OpenAI-compatible endpoint, checks
  and repairs until clean (the key comes from an environment variable and is never stored).
- **"Construct" is the noun.** What Construct makes is a *construct* ("build a construct of a
  lighthouse"; "holographic" still describes the look). MCP tools are `construct_diagnose`,
  `construct_params_template`, `construct_expand_params` and `construct_compile`; the pre-release
  names `hologram_diagnose`, `hologram_params_template`, `hologram_expand_params` and
  `hologram_compile_scene` still answer for one release (unlisted). `build` writes
  `construct.html` (was `hologram.html`; `review` and `video` still read an old `hologram.html`).
  The tagline is "Holographic constructs any agent can build — from a description, honestly."
- **Research and effort, bounded.** Research is optional and decided by the request: none for
  a generic subject; for a concrete, named one, preferred whenever the model is unsure of its
  identity-defining shape — the maker's pages, specs and reference photos first, viewed and
  measured with vision (any model that can see, DeepSeek V4.1 Flash included), then authoring; the user can
  say "research: on/off". Three effort tiers — quick, standard (default), showcase — with
  wall-clock, check-round, review-round and research limits. The aim is genuinely good
  (an art-direction rubric in `references/review.md` and `prompts/vision-review.md`: silhouette,
  proportions, identity, depth, composition, assembly, motion, density, honesty); the run stops
  at whichever comes first, a "good" verdict or any limit, and delivers the best version so far.
  An optional `authoring` record (tier, research, sources, review rounds, outcome, next
  improvements) is validated, audited and carried into the geometry's provenance.
  Draft early: research takes at most 40% of the time and ends in a complete, valid scene saved
  to disk, improved in place after that; at 80% nothing new is added.
  `construct author` saves every new best valid draft at once and enforces the limits (`--tier`, `--vision` review rounds, `--max-seconds`,
  `--max-images`, `--max-total-tokens`, `--max-cost`); MCP hosts read them from
  `construct_limits`.
- **The review hero is the whole object.** `hero.png` is taken in the hero view's fitted
  framing with the camera held still (`?camera=still`), so a camera tour or drift can no longer
  crop it to a detail.
- **Measured globe.** A `globe` shape (longitude/latitude paths on a sphere, a graticule, glass
  faces) and `construct globe`, which draws GeoJSON coastlines the user supplies (Natural Earth,
  public domain) simplified only as far as the line budget needs, with the axis at the cited
  axial tilt and a slow spin, labelled MEASURED COASTLINES with its scale and data credit.
- **Terrain that looks its part.** Contours about three dozen levels deep with bold index
  contours on round heights (every 100 m at 50 m spacing); the ridgelines that fall from the
  summit traced from the data and lit as identity, with a summit marker; no survey grid on a
  massif or range; closer hero framing. `--dem` takes several tiles or a folder, reads only the
  area thinned to the sampling (twenty 2 m swissALTI3D tiles in about 5 s and 35 MB), reports the
  data's true extremes, and caps the grid at 100 cells per side so the output always fits the
  triangle budget.
- **Measured terrain.** A `terrain` shape (a heightfield of up to 128×128: contours, a survey
  grid, a skirt, glass) and `construct terrain`, which samples an ESRI ASCII grid or XYZ export
  the user supplies (LV95, UTM or degrees), scales it by the ladder (spot, site, valley, massif,
  range), drapes a GPX route, places markers and labels the construct MEASURED TERRAIN with its
  scale and data attribution; a hand-made relief is SKETCHED TERRAIN. Pulled forward from 0.3.
- **Likeness from references.** `construct trace` fits a traced outline (`construct-trace`,
  measured by a model that can see, from the user's photo or a web image viewed and never
  kept) to a documented dimension: an `extrude` profile, features in metres, a `reference_image`
  source, an `inferred` part. `construct trace-image` runs the vision step on any
  OpenAI-compatible vision model; `author --reference` attaches images. `shape-overclaim`
  warns when a free-form shape is verified without a drawing, measurement or dataset.
- **One house palette.** Every construct renders in the house palette whatever the model wrote:
  a scene's `presentation.style_hint` is ignored (warning `style-hint-ignored`). Only a person
  chooses another colour, through a host option (`build --palette`, `--identity`, or the viewer's
  `?palette=`). The examples no longer carry colour hints.
- **Legibility:** thin or small mass and structure parts get a minimum visual weight.
- **Docs:** README with pictures, `docs/ABOUT.md` (what it is, the Anatomy and NODE credits, how
  to talk about it), `docs/USING.md` (every entry point, a worked example, costs and times),
  `docs/ARCHETYPES.md`, `docs/EVALUATION.md`, `CONTRIBUTING.md`; `scripts/docs_media.py` and
  `scripts/release_video.py` render the pictures and the release video.

## 0.2.0-pre — as hologram-studio (2026-10-19)

From the first live runs (Hermes with DeepSeek V4.1 Flash and GPT-6.1 Sol), which passed the audit with
visible defects:

- `detached`: a part whose real surfaces and segments come within 1% of the object's size of
  no other part (and not the ground) is flagged with its nearest part, beyond what bounding
  boxes can see (a shade floating off a diagonal arm). `floating: true` is the exception.
- `thin`: a mass or structure part thinner than 0.6% of the object's largest size (a tube, a
  curve, a long cylinder or box, a torus) gets a minimum radius.
- Both set the report's `needs_repair`, and lead `repair_text`, so the repair loop continues
  until they are fixed.
- `prompts/vision-review.md`: an optional self-review of `hero.png` against the request for
  models that can see images.
- Fixed in the examples by these checks: the jellyfish's oral arms now hang from the bell,
  the can has a lid under its tab, the lighthouse rail is detail, the organism starter's eye
  sits on its body.

First standalone release, extracted from the Tessera project's `hologram-skill` branch with its
history (`git subtree split` of `tools/hologram`: the toolkit's files only, one author).

- Relicensed under MIT by its author (previously Apache-2.0 inside Tessera).
- The product's name lives in `construct_hologram/product.py` and `pyproject.toml`.
- Layout: the package in `construct_hologram/`; the contract, README, licence and notices at the
  root. Removed: the Tessera branch's handoff and working notes and the v0.1
  `create-hologram` skill (superseded by `construct_hologram/skill`).
- Contract `construct/0.2` (accepted by Tessera, with the `open` view): scenes with
  facts and certainty, a closed shape vocabulary, roles, stages, periodic motion, one-shot
  articulations, labels from facts, artwork slots and masks, anchors, views; compiled
  geometry with `geometry.schema.json`.
- Diagnostics with JSON paths, codes, hints and `repair_text`; every problem in one round;
  placeholder values are unknown facts.
- The simple path: parametric archetypes for cases, books, guitars, a synth and vessels, with
  15 synthetic golden documents.
- Any-model prompts and `params.schema.json`; read-only v2 MCP tools; Hermes and Claude Code
  skill packages; a synthetic cross-model evaluation and its scorer.
- WebGL2 viewer: staged construction, idle life, articulations and the `open` view, labels
  set from facts, masks, provenance mode, reduced-motion still; headless review captures and
  video.

## 0.1.0

The construction-sheet prototype (`hologram.py`, `schema.json`, the v0.1 CLI and MCP tools),
kept as a legacy layer.
