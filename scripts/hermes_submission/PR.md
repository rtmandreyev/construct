# Add `construct` optional skill (creative): honest, animated constructs from a description

> DRAFT — not submitted. Before opening: the owner confirms, and re-runs the checks below on a
> current Hermes checkout.

## What it does

`construct` turns a description of a real or fictional thing into an animated holographic construct (WebGL).
The agent writes a short declarative scene — facts with a certainty each (`verified` with a
source, `user_supplied`, `inferred`, `decorative`) and parts from a closed set of shapes — or
fills an archetype's parameters (CD cases, books, guitars, a synth, bottles, cans, glasses).
The bundled stdlib-only scripts validate it, audit it (every problem comes back with a JSON
path, a code and a fix hint), compile it deterministically and render one self-contained HTML
construct, plus review stills and video when a browser and ffmpeg are present. Film mode
(new in 0.3.0) renders a construct assembling across a piece of music, its pace, light and
sections following the track.

It is inspired by the truth-first method of the existing `anatomy` optional skill (true
numbers first, a parts list before geometry, an audit run to zero, read every rendered image)
and shares no code with it; `related_skills: [anatomy]`.

Upstream: https://github.com/rtmandreyev/construct (MIT, v0.3.0).

## Why optional-skills

It is niche (constructs of objects and creatures) and its review stills need a local
Chromium-family browser (and ffmpeg for video), like `hyperframes` and `scrollcraft`. Without
them it still checks and builds the construct's HTML page.

## Files

- `optional-skills/creative/construct/SKILL.md` — the standard sections (When to Use,
  Prerequisites, How to Run, Quick Reference, Procedure, Pitfalls, Verification)
- `references/` — vocabulary, composition, animation, review, provenance, method
- `scripts/` — `cli.py` and the `construct_hologram` package (Python stdlib only) with the
  WebGL viewer
- `assets/examples/` — eleven example scenes the references cite (synthetic objects, an archetype
  and agent-made constructs) and two generated (labelled) cover images
- `tests/skills/test_construct_skill.py` — stdlib + pytest; no network, no browser
- `website/docs/reference/optional-skills-catalog.md`, `website/sidebars.ts` and
  `website/docs/user-guide/skills/optional/creative/creative-construct.md`, written by
  `website/scripts/generate-skill-docs.py` (the catalog test requires them)

## Checklist (For New Skills)

- [ ] Broadly useful to most users — **no**: submitted to `optional-skills`, not `skills/`.
- [x] SKILL.md follows the standard format: frontmatter (`name` = directory, 58-character
      description ending in a period, version, author, license, platforms, tags,
      `related_skills: [anatomy]`), trigger conditions, steps, pitfalls, verification.
- [x] No external dependencies beyond what is available: Python standard library; an already
      installed browser and ffmpeg are optional and never installed by the skill.
- [x] Tested end to end through Hermes 0.22 (one-shot, toolsets terminal+file+skills) on five
      synthetic tasks: DeepSeek V4.1 Flash (`deepseek-flash`) 15/15, $0.038 total, 258 s; GPT-6.1 Sol
      15/15, 357 s; no invented facts. To re-run:
      `hermes --toolsets skills -q "Use the construct skill to make a construct of a desk lamp with a weighted base and a conical shade"`

## Security scan

`tools/skills_guard.py` (`scan_skill(path, source="community")`, Hermes 0.22.5) on the draft:
verdict **safe**. Its notices, all informational:

- `python_subprocess` ×3: the scripts start a local headless browser (DevTools on 127.0.0.1) for
  review stills and call ffmpeg for video and film audio. They make no other network calls, read
  no secrets and bind no public ports.
- `shell_rc_mod` ×4: the word "profile" in scene-validation messages (a lathe's profile), not a
  shell startup file.
- `python_environ_get_secret` ×1: the optional critic reads the name of an API-key variable the
  user chooses (`--key-env`), for a second-model critic; nothing is read unless asked.
- `string_reversal` ×1: reversing a traced polygon's winding (`poly[::-1]`).
- `too_many_files`: 56 files against a guideline of 50: the stdlib runtime (28 modules and the
  viewer), the references and eleven example scenes the references cite. Happy to trim the
  examples if reviewers prefer.

The programmatic authoring standards (fields, name = directory, description ≤ 60 characters with
a period and no marketing words, no machine-local paths, size, paste-safe shell blocks) pass, and
`tests/skills/test_construct_skill.py` passes (15 tests, including film mode). Installed into a
clean Hermes profile, the skill lists as enabled and its CLI checks, builds and renders a film-mode
video from the installed location. No inline-shell snippets, no binaries.

## Lint (to discuss before opening)

Hermes's tests pass with the skill and its generated docs in place (1,731 in `tests/skills/` and
`tests/website/test_generate_skill_docs.py`, the authoring standards and the catalog contract
included), and `check-windows-footguns.py` is clean. `scripts/check` is not: the bundled runtime is
Construct's own stdlib code, written in its upstream style, so ruff reports 565 findings (523 of them
UP031, `%` formatting) and the code-health ratchet flags a dozen long functions (the scene compiler and
the audit among them). Before opening, ask the maintainers whether they would take an optional skill
with a sizeable bundled runtime (with a lint exclusion for its `scripts/` folder, or after a restyle),
or would rather see it on the Skills Hub: `hermes skills install rtmandreyev/construct/skills/construct`.

## Credits

Author: Artyom Andreyev (rtmandreyev). Method inspired by Anatomy by Ryan (wheresryan22), MIT.
