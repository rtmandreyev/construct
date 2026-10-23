# Changelog

## 0.2.1 (release candidate)

- **Three modes, and the skill chooses** (from the fifth rounds experiment: C2's rounds won
  the owner's blind pick, and the owner saw no visible gain after about round 12):
  - **fast:** one pass with self-review, no rounds loop (the standard tier, or showcase for a
    richer subject). For generic subjects, simple objects and quick asks; DeepSeek-class models
    do these well.
  - **masterpiece:** the rounds loop, stopping after 2 rounds without a pairwise win, at every
    criterion 3, at a default cap of **12 rounds**, or at 2 hours of active work. For a named
    subject whose likeness matters.
  - **unbounded:** the same loop with only its stop rules: no round cap, no time ceiling. Only
    on explicit request: the critic finds a win almost every round, so it can run many rounds
    and hours at a high token cost; the per-round report lets the user stop it.
  - **the old tier names are aliases:** quick, standard and showcase mean fast; masterpiece
    means masterpiece. `--mode` (or `--tier`), `mode:` or `tier:` in a request,
    `CONSTRUCT_TIER` for the Claude Code hook and the MCP `construct_limits` tool all take
    either.
  - **the skill picks when the user says nothing,** and announces it before any work: the
    mode, why, the rough time and cost, and how to switch. Fast for generic and simple
    subjects; masterpiece for a named car, landmark or building; never unbounded
    (`tiers.choose` gives the same answer from the author's judgement of the subject).
  - **model-aware:** a smaller or cheaper model on a hard named subject says so and recommends
    GPT-6.1 Sol or Claude Opus (`construct author` logs the same note).

- **Contours, detail and fair rounds** (build C2, from the fifth rounds experiment: build C's
  rounds won every blind comparison; a later build's renders lost their surface contours):
  - **the contour rule:** main surfaces keep a faint contour wire (weight about 0.4–0.5, alpha
    about 0.5–0.6) over their dark fill; `line: "none"` is for occluders and backings. `check`
    warns `bare-surface` when a visible main surface (role mass, or a large loft or extrude) has
    no lines. The critic is told that faint surface contours give form and are not clutter. The
    911 example's glasshouse and bumpers get their contour back.
  - **the density bar:** at hero scale one clear object; up close every region still has
    something true to find; a bare face or an empty corner is unfinished (`craft.md`, the
    critic). The audit's clutter warning stays for real clutter.
  - **fair timing:** author time comes from the run folder's own activity and stops at the
    packet; the critic's time is logged separately; `rounds pause`.
  - **a blind packet:** the references are copied into it, and the pair's pictures are
    re-encoded and named at random; the header counts the ledger items actually shown.
  - **the medium:** hidden lines showing through, untinted glass and the closed still pose are
    seeded as known limits; an ask the critic files under one never enters the ledger.
  - **a finish-cap log line:** each round says whether a 4-round finish cap would stop there
    (finish starts at the first round with no critical or major silhouette, proportions or
    identity item open). Log only.

- **Masterpiece rounds that keep what is good** (`construct rounds`,
  `references/rounds.md`):
  - **one critic a round, three parts:** this version blind, then against the best so far
    (the same views, unlabelled, in a random A/B order, beside the references), then the
    defect ledger;
  - **the pairwise pick decides:** a version is kept when it wins overall, and its
    regressions lead the next round (repair, don't revert); it is reverted only when it
    loses;
  - **small rounds:** at most 4 ledger items, every edit tagged with its id;
  - **a defect ledger** (`ledger.json`): known limits only from kept rounds without progress,
    or what the tools cannot express, reported as skill gaps;
  - **stop rules:** every criterion at 3, two rounds without a win, or a 2-hour safety stop
    on active time (Masterpiece's new default; interruptions do not count);
  - **a log a person can read and resume:** a chat report after every Masterpiece round
    (Showcase: once, at the end), `rounds.md`, `checkpoints/round-NN/`, `state.json`
    (`rounds status`), and the round timeline in `construct.html` and `review`
    (`rounds.png`).

  A critique's score below 3 must cite a defect of its criterion. The README and USING
  recommend models: Sol or Opus for hard subjects at Masterpiece, DeepSeek for simpler
  objects, and not small free models.

- **Drawing craft** (`references/craft.md`, linked from the authoring recipe and the scene
  prompt): five rules from the strongest constructs: a line-weight hierarchy, dark depth-writing
  fills that hide the construction mesh, a sub-volume per feature, density where the identity
  lives, and a critic round answered by a refine pass, with excerpts of the scripts that drew
  them.
- **Six new examples**: a Leica M3, an open-reel tape recorder, a sea cliff at dusk, a Jackson
  Juggernaut ET7, a Porsche 911 (964) and the Sagrada Família, drawn with that craft. The two
  older scenes are converted to `construct-scene`; hairlines are role `detail`, closing points
  repeated in lathe profiles are dropped, a label carrier is seated on its lens, and a
  comparison record those edits made stale is removed. No reference photos ship.

- **The packaged skill runs critique**: the Claude Code package and the Hermes draft ship the
  two examples the prompts read, and the Hermes draft ships `prompts.py`; `critique`, `author`
  and `prompts` crashed from an install before.
- **`compare` measures the object**: ornament and decorative parts (a shadow ring, motes) are
  left out of the silhouette; a tyre drawn as a wire torus (and the well under its arch) is
  filled as a solid disc, so a car's side is no longer measured with holes in it; a plan trace
  drawn any way round (nose up, down, left or right, mirrored) is found, the result names the
  orientation, and a trace drawn across the view is warned about.

- **Round caps inside any host.** `check` warns `tier-rounds` when `authoring.review_rounds`
  passes the tier's cap; the skill counts rounds in the scene before each review. A Claude Code
  budget hook (`hosts/claude-code/`, opt-in, shipped in the plugin switched off) refuses review
  commands past the rounds and, past the wall clock, every tool but reading, `check` and
  `build`; Hermes runs take `--run-budget` and `--max-turns`.
- **Cars that are cars.** A `loft` shape (rounded sections back to front: plan and side profile
  together) and a `vehicle` archetype (wedge, coupe, sedan): a lofted lower body with a narrow,
  rounded nose and leaning sides, a glasshouse loft, tyres on the ground in arches, lights.
  Car guidance in the prompts and composition reference: trace side and plan first, never a
  box.
- **A clean globe from dense data.** Shared coastline edges are drawn once; when a file is over
  the line budget, islands too small to read are left out first and lines are never simplified
  below about a pixel (no beading). Natural Earth 1:50m now reads as cleanly as 1:110m.

### Milestone 2: the quality bar

- **An independent critic.** `construct critique` writes a packet for a fresh context (the
  critic's instructions, the request, the identity checklist, the scene's hash, renders from
  the views of the reference photos beside them); a subagent, a delegated task or a second
  model call (`--base-url`) answers a `construct-critique` (0–3 scores with strict anchors,
  the checklist checked item by item, defects ranked by severity). `--record` binds it to the
  scene's hash and recomputes the verdict from the scores; only the critic can record "good"
  or "outstanding" (the audit flags `self-graded`, `critic-stale` and `critic-claim`), and the
  author's own review records "self-reviewed".
- **Identity checklist.** `authoring.identity`: the features research says make the subject
  itself, each with the parts that build it (`identity-unbuilt`, `no-checklist`).
- **The masterpiece tier.** For hard subjects on request: no wall clock and no round cap; it
  stops only when the critic scores every criterion 3, at an optional cost ceiling, or when the
  user stops it, and checkpoints every round. `construct author --critic` / `--tier
  masterpiece`; the Claude Code budget hook knows it.

### Milestone 3: likeness, measured

- **`construct compare`**: the construct's silhouette from a named view, projected from the
  geometry (no browser), against a traced reference outline: IoU and the mean distance between
  the outlines (as a share of the view's width), the better of the reference as traced or
  mirrored, and an overlay PNG. Thresholds for vehicles (IoU 0.88, 1.2%) and landmark buildings
  (0.82, 2%). `--record` binds it to the scene (`authoring.compare`); an outstanding vehicle or
  landmark needs a passing comparison (`likeness`, `compare-stale`; the critic's verdict is
  held at "good" without one).
- **`construct loft-from-traces`**: side, top and front traces reconciled into loft stations
  (crowded at the nose and tail; the front sets how the cabin narrows), checked against the
  documented height and width; `--into scene --part body --drop glasshouse` swaps it into an
  archetype.

### Milestone 4: the architecture kit

- New shapes: `tower` (round or polygonal; cone, pyramid, spire, onion or flat roof; taper,
  eave, arched windows in rows), `roof` (gable or hip, either ridge, overhang, tile courses),
  `dormer`, `facade` (window grids with round, pointed or flat heads and mullions, or an
  arcade), `battlements` (round or along a wall path) and `buttress` (stepped). Every
  variant compiles without warnings; `examples/castle.json` uses them all.
- Massing from a traced plan and elevations (`trace` + `extrude`) in the composition guide.
- `construct terrain --into scene.json`: measured terrain at real scale as a building's
  plinth, the ground at the site's centre at `y = 0`.

### From the baseline runs

- `tube-outline`: a vehicle (or a scene without surfaces) whose outline is drawn with long thin
  tubes is warned: they render as glowing wire, not a body (both weak live cars did this).
- The section method for cars in the composition guide and scene prompt: traced side skins,
  filled cross-section slices, smooth section curves (how the best-liked cars were built).
- `tower` `profile: parabolic`: shafts that narrow ever faster towards the top (the Sagrada
  Família's bell towers).
- `shell`: a ribbed sail rising back from a base edge, bulging forward (the Sydney Opera
  House's roofs; pair and turn them with `rotate`).

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
  measured with vision (any model that can see, DeepSeek included), then authoring; the user can
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

From the first live runs (Hermes with DeepSeek and GPT-6.1 Sol), which passed the audit with
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
