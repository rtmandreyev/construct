---
name: construct
description: Turn a description into an animated holographic construct.
version: 0.2.0
author: OWNER NAME (rtmandreyev)
license: MIT
platforms: [macos, linux]
prerequisites:
  commands: [python3]
metadata:
  hermes:
    tags: [creative, 3d, construct, hologram, webgl, animation, visualization, html, provenance]
    category: creative
    related_skills: [anatomy]
    requires_toolsets: [terminal]
    upstream: https://github.com/rtmandreyev/construct (v0.2.0)
---

# Construct

Construct turns a description of a real or fictional thing — an object, a building, a machine,
a creature — into an animated holographic construct (WebGL). You write a short declarative scene (facts with
their certainty, and parts built from a closed set of shapes) or fill an archetype's few
parameters; the bundled tools validate it, audit it, compile it deterministically and render
it in one holographic style. You never write graphics code and never choose colours.

Inspired by the truth-first construction method of `anatomy` (true numbers first, a parts
list before geometry, an audit run to zero, every rendered image read). Construct shares that
method, not code, and adds 3-D animation, certainty as material and a repair loop.

## When to Use

- The user asks for a construct or a hologram — a holographic or wireframe light model, or an
  animated 3-D presentation of a thing: "make a construct of my CD", "a hologram of this
  lighthouse", "show this guitar as a construct", "a fictional creature for my game".
- A collection entry needs a consistent animated figure: CDs and their cases, books,
  guitars, synths, bottles, cans and glasses have ready archetypes.

Do **not** use it for photoreal renders, meshes for games or CAD, charts, or for finding or
recreating real cover art (artwork is shown only from images the user supplies).

## Prerequisites

- Python 3.10+ (standard library only). Nothing is installed or downloaded.
- For review stills and video: a Chromium-family browser already on the machine (Chrome,
  Chromium, Edge, Brave, or `HOLOGRAM_CHROME=/path`) and `ffmpeg`. Without them you can still
  check and build; say that captures were not made.

## How to Run

All commands use `terminal` and run the bundled CLI by its absolute path:

```bash
python3 ${HERMES_SKILL_DIR}/scripts/cli.py params --list
python3 ${HERMES_SKILL_DIR}/scripts/cli.py params book --variant paperback --output book.json
python3 ${HERMES_SKILL_DIR}/scripts/cli.py check book.json --json
python3 ${HERMES_SKILL_DIR}/scripts/cli.py build book.json --out out
python3 ${HERMES_SKILL_DIR}/scripts/cli.py review book.json --out out
python3 ${HERMES_SKILL_DIR}/scripts/cli.py video book.json --out out/book.mp4 --seconds 12
```

Work in a folder of your own. `out/construct.html` opens in any browser.

## Quick Reference

| need | command or file |
|---|---|
| an archetype (case, book, guitar, synth, bottle, can, glass) | `params <archetype> --variant <v> --output p.json` |
| a full scene starter | `new <object\|architecture\|machine\|organism\|cd\|book> --output scene.json` |
| check: every problem with a path, code and fix hint | `check file.json --json` (`ok`, `needs_repair`, `diagnostics`, `repair_text`) |
| build the construct | `build file.json --out out` |
| review images | `review file.json --out out` → `out/review/hero.png`, `sheet-views.png`, `view-open.png` |
| examples to start from | `${HERMES_SKILL_DIR}/assets/examples/` |
| shapes, fields, roles, motion, labels, anchors | `references/vocabulary.md` |
| recognition and composition | `references/composition.md` |
| assembly, articulations, idle life | `references/animation.md` |
| certainty, sources, artwork rights | `references/provenance.md` |
| the review checklist | `references/review.md` |

## Procedure

1. **Facts first.** Write down what the user actually said or gave you. Each fact gets a
   certainty: `verified` (cites a source), `user_supplied`, `inferred` (your estimate, with a
   short note) or `decorative`. Leave unknown facts out entirely — never `null`, "unknown" or
   a guess. Read `references/provenance.md` if artwork or sources are involved.
2. **Pick the path.** If an archetype fits (`params --list`), fill its parameter document:
   copy the facts, leave `params` empty unless the user gave sizes. Otherwise start from
   `new <category>` or an example and read `references/composition.md` and
   `references/vocabulary.md`: name the silhouette and the two or three identity features,
   build masses first, then structure, identity and a little detail.
   When the identity is a shape text cannot give (a guitar body, a car, an elevation) and you
   can see images, trace it from a reference (`references/tracing.md`: the user's photo or a
   web image viewed with `vision_analyze`), then `scripts/cli.py trace` fits it to a verified
   dimension. Traced shapes are `inferred`, cited to the image. A real place or peak comes from
   elevation data the user supplies: `scripts/cli.py terrain` (`references/terrain.md`).
3. **Check until clean.** Run `check --json`. While `needs_repair` is true, fix every
   diagnostic at its JSON path using its hint, and check again. Fix every `detached` and
   `thin` warning: they are what a viewer notices first.
4. **Build and look.** Run `review`, then open `out/review/hero.png`, `sheet-views.png` and
   (if it opens) `view-open.png` with `vision_analyze`, or `read_file` if your model reads
   images. Judge them against `references/review.md`: does it read as the thing at a
   glance, does anything hover or barely show, is every label from a fact? Fix the scene and
   review again; two or three rounds is normal.
5. **Deliver.** Give the user `out/construct.html` (and the video if asked), and say plainly
   what is evidence, what is inferred or designed, and which artwork is the user's own and
   which is generated decoration. Never call a generic reconstruction exact.

## Pitfalls

- **Inventing facts.** A year, an author, a label or a size the user did not give must not
  appear. The checker refuses placeholders such as "unknown" or "n/a".
- **Choosing colours or materials.** There are no colour fields; the renderer owns the look.
  Words like "glowing" become facts or roles (a light is role `data`).
- **Parts that only seem to touch.** A shade at the end of a diagonal arm, a handle above a
  lantern: the `detached` check names the nearest part; move the part onto it.
- **Hairline structure.** A thin arm or leg barely renders: `thin` gives the minimum radius.
- **Real artwork.** Show a cover only from bytes the user supplied, declared with its SHA-256
  and rights. Never download covers or recreate one from memory.
- **Captures without a browser.** If no Chromium-family browser exists, deliver the HTML and
  say the review stills were not made; do not install one.

## Verification

- `check` reports `audit: PASS` and `needs_repair` is false.
- `out/construct.html` exists; `out/review/hero.png` shows the requested thing, recognisably.
- Facts in the scene match the user's words; nothing unknown is filled in.
- For a quick self-test: `python3 ${HERMES_SKILL_DIR}/scripts/cli.py check ${HERMES_SKILL_DIR}/assets/examples/cd.json`
  must report `audit: PASS (0 errors, 0 warnings)`.
