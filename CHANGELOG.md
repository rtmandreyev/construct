# Changelog

## 0.2.0 — Construct (unreleased)

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
