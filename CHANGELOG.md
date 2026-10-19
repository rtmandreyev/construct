# Changelog

## 0.2.0 — 2026-10-19 (unreleased; the product name is provisional)

First standalone release, extracted from the Tessera project's `hologram-skill` branch with its
history (`git subtree split` of `tools/hologram`: the toolkit's files only, one author).

- Relicensed under MIT by its author (previously Apache-2.0 inside Tessera).
- The product's name lives in `hologram_studio/product.py` and `pyproject.toml`;
  `scripts/rename.py` applies a final name.
- Layout: the package in `hologram_studio/`; the contract, README, licence and notices at the
  root. Removed: the Tessera branch's handoff and working notes and the v0.1
  `create-hologram` skill (superseded by `hologram_studio/skill`).
- Contract `tessera.hologram/0.2` (accepted by Tessera, with the `open` view): scenes with
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
