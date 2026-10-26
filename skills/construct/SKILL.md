---
name: construct
description: Turn a description into an animated holographic construct.
version: 0.3.0
author: Artyom Andreyev (rtmandreyev)
license: MIT
platforms: [macos, linux]
prerequisites:
  commands: [python3]
metadata:
  hermes:
    tags: [creative, 3d, construct, hologram, webgl, animation, visualization, html, provenance, video, music]
    category: creative
    related_skills: [anatomy]
    requires_toolsets: [terminal]
    upstream: https://github.com/rtmandreyev/construct (v0.3.0)
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
  guitars, synths, bottles, cans, glasses and cars have ready archetypes.
- The user wants a video of a construct assembling across a piece of music ("make a construct
  of X that assembles across this track"): film mode, step 7 below.

Do **not** use it for photoreal renders, meshes for games or CAD, charts, or for finding or
recreating real cover art (artwork is shown only from images the user supplies).

## Prerequisites

- Python 3.10+ (standard library only). Nothing is installed or downloaded.
- Optional: the `web` and `vision` toolsets, for researching a named subject and looking at
  references and captures. Any model that can see images works (tested: DeepSeek V4.1 Flash,
  GPT-6.1 Sol). Without them, the construct is built from general knowledge and labelled so.
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
| an archetype (case, book, guitar, synth, bottle, can, glass, car) | `params <archetype> --variant <v> --output p.json` |
| a full scene starter | `new <object\|architecture\|machine\|organism\|cd\|book> --output scene.json` |
| check: every problem with a path, code and fix hint | `check file.json --json` (`ok`, `needs_repair`, `diagnostics`, `repair_text`) |
| build the construct | `build file.json --out out` |
| review images | `review file.json --out out` → `out/review/hero.png`, `sheet-views.png`, `view-open.png` |
| examples to start from | `${HERMES_SKILL_DIR}/assets/examples/` |
| shapes, fields, roles, motion, labels, anchors | `references/vocabulary.md` |
| recognition and composition | `references/composition.md` |
| masterpiece rounds: ledger, pairwise gate, stop rules, resume | `references/rounds.md` |
| drawing craft: weights, fills, sub-volumes, refine rounds | `references/craft.md` |
| assembly, articulations, idle life | `references/animation.md` |
| certainty, sources, artwork rights | `references/provenance.md` |
| a car body from traced side, top, front views | `loft-from-traces --side s.json --top t.json --front f.json --length 4.14 --into car.json --part body --drop glasshouse` |
| measure likeness against a traced reference | `compare car.json --trace side.json --view side --record` |
| an independent critic (fresh subagent or second call) | `critique scene.json --reference side=photo.jpg`, then `--record critique.json` |
| the art-direction rubric | `references/review.md` |
| the modes (fast, masterpiece, unbounded), research policy and limits | `references/effort.md` |
| film mode: measure a track, then render the construct assembling across it | `audio track.wav --out audio.json`, then `video scene.json --out film.mp4 --assembly <seconds> --audio audio.json --sound track.wav --camera steady` |

## Procedure

1. **Mode and research.** Three modes (`references/effort.md`); the user can just say one:
   - **fast:** one pass with self-review, no rounds loop: at most 10 minutes, 2 review rounds,
     5 searches, 3 sources, 3 reference images (30 minutes and 4 reviews for a richer
     subject). Generic subjects, simple objects, quick asks; DeepSeek V4.1 Flash is fine here.
   - **masterpiece:** judged rounds (below), stopping after 2 rounds without a win, at every
     criterion 3, at 12 rounds or at 2 hours of active work. A named subject whose likeness
     matters. Frontier-model token cost.
   - **unbounded:** the same rounds with only the stop rules, no round cap and no time
     ceiling: many rounds and hours at a high token cost, stoppable after any round. Only
     when the user asks for it by name.

   Quick, standard and showcase still work and mean fast. **If the user names no mode, choose
   one and announce it before any work:** the mode, why, the rough time and cost, and how to
   switch. Fast for generic subjects, simple mechanical objects and quick asks; masterpiece
   for a specific named subject whose likeness matters (a car model, a landmark, a named
   building); never unbounded. On a smaller or cheaper model with a hard named subject, say so
   and recommend GPT-6.1 Sol or Claude Opus 5.5 (or a model of that class) for masterpiece, with fast as the option here. A
   generic subject ("a desk lamp") needs no research. For a concrete, named one (a brand and
   model, a named building or peak, a species) research first whenever you are unsure of its
   shape or specs: the maker's or official pages, specs and reference photos, looked at with
   `vision_analyze` and measured. "research: on/off" in the request overrides this.
   **Draft early.** Research takes at most 40% of the time; by then a complete scene that
   passes `check` is saved in your folder. Improve that file in place, checking and saving
   after every round. At the run budget's wrap-up notice (80%), stop adding: make the saved
   scene valid, build it and deliver.
2. **Facts.** Write down what the user said or gave you and what your sources say. Each fact
   gets a certainty: `verified` (cites a source), `user_supplied`, `inferred` (your estimate
   or a traced measurement, with a short note) or `decorative`. Without a cited source
   nothing is `verified`. Leave unknown facts out entirely — never `null`, "unknown" or a
   guess. Read `references/provenance.md` if artwork or sources are involved.
3. **Pick the path.** If an archetype fits (`params --list`), fill its parameter document:
   copy the facts, leave `params` empty unless the user gave sizes. Otherwise start from
   `new <category>` or an example and read `references/composition.md` and
   `references/vocabulary.md`: name the silhouette and the two or three identity features,
   build masses first, then structure, identity and a little detail. Draw with craft
   (`references/craft.md`): a line-weight hierarchy, dark depth-writing fills under a faint
   contour wire (never a main surface with `line: "none"`), a sub-volume per feature, density
   where the identity lives and true detail everywhere (one clear object at hero scale,
   something true in every region up close), and a critic round answered by a refine pass; the
   examples in `assets/examples/` show all five.
   When the identity is a shape text cannot give (a guitar body, a car, an elevation) and you
   can see images, trace it from a reference (`references/tracing.md`: the user's photo or a
   web image viewed with `vision_analyze`), then `scripts/cli.py trace` fits it to a verified
   dimension. Traced shapes are `inferred`, cited to the image. A real place or peak comes from
   elevation data the user supplies: `scripts/cli.py terrain`, and Earth from coastline data
   (GeoJSON): `scripts/cli.py globe` (`references/terrain.md`).
4. **Check until clean.** Run `check --json`. While `needs_repair` is true, fix every
   diagnostic at its JSON path using its hint, and check again. Fix every `detached` and
   `thin` warning: they are what a viewer notices first.
5. **Review as an art director.** Run `review`, then open `out/review/hero.png`,
   `sheet-views.png`, `sheet-assembly.png` and (if it opens) `view-open.png` with
   `vision_analyze`. Score them with the rubric in `references/review.md` (silhouette,
   proportions, identity, depth, composition, assembly, motion, density, honesty). The aim
   is genuinely good — something you would put in a launch video — not merely
   recognisable: improve the weakest point, check, review again. Your own review records
   `self-reviewed`; for a named subject run the independent critic: `scripts/cli.py critique
   scene.json --reference side=photo.jpg`, then delegate `critique/packet.md` to a fresh
   subagent (or add `--base-url --model --key-env` for a second model call) and record its
   answer with `--record` (`references/review.md`). Before each review add
   one to `authoring.review_rounds` and save; `check` warns `tier-rounds` past the cap. Stop when every criterion
   is good, or when the tier's review rounds or time run out, whichever comes first.
   **Masterpiece and unbounded run judged rounds** (`references/rounds.md`): `scripts/cli.py
   rounds start scene.json --mode masterpiece` (or `unbounded`). Each round, work on at most 4 ledger items and tag each edit (`rounds change
   D3 "..."`). Then `rounds packet --reference ...`, with ONE delegated critic a round (or
   `rounds run --base-url ...`), and `rounds record answer.json`. A version is kept only when
   it beats the best so far, and its regressions lead the next round. After every round,
   report its summary in chat. Stop when `record` says STOP: two rounds without a win, every
   criterion at 3, or, in masterpiece, 12 rounds or 2 hours of active work. After an interruption run
   `rounds status` and redo only the step it names.
6. **Deliver.** Record `authoring` in the scene (tier, research, sources used, outcome,
   `next` improvements). Give the user `out/construct.html` (and the video if asked), and say
   plainly what is evidence, what is inferred or designed, which artwork is the user's own
   and which is generated decoration, and — if a limit stopped you — what the next
   improvement would be. Never call a generic reconstruction exact.
7. **Film mode (only when asked).** For a construct that assembles across a piece of music,
   author the construct as above (keep its own assembly at most 20 s), then:
   `scripts/cli.py audio track.wav --out audio.json` (add `--voice vocals.wav` for a vocal stem)
   and `scripts/cli.py video scene.json --out film.mp4 --assembly <track seconds - 1.25>
   --audio audio.json --sound track.wav --camera steady --size 1920x1080 --fps 24` (the 1.25 s is
   the ceremony opening; use the full length for another assembly style). `--camera steady`
   keeps the whole construct in view; `tour` plays the scene's own camera flights. Leave
   `--reactivity` at its default unless the user asks for a calmer (0.5) or stronger (1.5) film.
   It renders about a frame or two a second, so say how long it will take before starting.
   Review it by sampling frames (`ffmpeg -i film.mp4 -vf fps=1/10 frame-%02d.png`) and look at
   them with `vision_analyze`: the build should visibly move with the music and end whole.

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
- **Running unbounded, or writing at the end.** The tier's limits are ceilings; Hermes's own
  run budget applies on top. A scene held only in context is lost when the budget ends: save a
  valid draft by 40% and keep it valid. When a limit is reached, deliver the saved version
  with its `next` notes.
- **A masterpiece critic that stops after two rounds.** In a one-shot run (`hermes chat -q`),
  Hermes lets a session start only two helper agents by default (`delegation.oneshot_max_children`),
  and the critic is a fresh helper each round. Tell the user to raise it in `config.yaml`
  (14 covers a masterpiece run; `0` means no limit), to run interactively, or use a second model
  as the critic (`rounds run --base-url ... --model ... --key-env ...`).
- **Messages that are too large.** A message larger than about 8 MB stops the run. Do not attach
  several full-size review stills at once: ask for smaller ones (`review --size 1280x800`) and
  only the sheets you need (`--sheets assembly,views`). The saved scene survives the stop.
- **Captures without a browser.** If no Chromium-family browser exists, deliver the HTML and
  say the review stills were not made; do not install one.

## Verification

- `check` reports `audit: PASS` and `needs_repair` is false.
- `out/construct.html` exists; `out/review/hero.png` shows the requested thing, recognisably.
- Facts in the scene match the user's words and the cited sources; nothing unknown is filled in.
- `authoring` records the tier, whether research was done, the outcome and what comes next.
- For a quick self-test: `python3 ${HERMES_SKILL_DIR}/scripts/cli.py check ${HERMES_SKILL_DIR}/assets/examples/cd.json`
  must report `audit: PASS (0 errors, 0 warnings)`.
