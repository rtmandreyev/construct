# Add `construct` optional skill (creative): honest, animated constructs from a description

> DRAFT — not submitted. Before opening: the owner fills in the author name, confirms the
> upstream repository is public, and re-runs the checks below on a current Hermes checkout.

## What it does

`construct` turns a description of a real or fictional thing into an animated holographic construct (WebGL).
The agent writes a short declarative scene — facts with a certainty each (`verified` with a
source, `user_supplied`, `inferred`, `decorative`) and parts from a closed set of shapes — or
fills an archetype's parameters (CD cases, books, guitars, a synth, bottles, cans, glasses).
The bundled stdlib-only scripts validate it, audit it (every problem comes back with a JSON
path, a code and a fix hint), compile it deterministically and render one self-contained HTML
construct, plus review stills and video when a browser and ffmpeg are present.

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
- `assets/examples/` — eight synthetic examples and two generated (labelled) cover images
- `tests/skills/test_construct_skill.py` — stdlib + pytest; no network, no browser

## Checklist (For New Skills)

- [ ] Broadly useful to most users — **no**: submitted to `optional-skills`, not `skills/`.
- [x] SKILL.md follows the standard format: frontmatter (`name` = directory, 58-character
      description ending in a period, version, author, license, platforms, tags,
      `related_skills: [anatomy]`), trigger conditions, steps, pitfalls, verification.
- [x] No external dependencies beyond what is available: Python standard library; an already
      installed browser and ffmpeg are optional and never installed by the skill.
- [x] Tested end to end through Hermes 0.22 (one-shot, toolsets terminal+file+skills) on five
      synthetic tasks: DeepSeek (`deepseek-flash`) 15/15, $0.038 total, 258 s; GPT-6.1 Sol
      15/15, 357 s; no invented facts. To re-run:
      `hermes --toolsets skills -q "Use the construct skill to make a construct of a desk lamp with a weighted base and a conical shade"`

## Security scan

`tools/skills_guard.py` (`scan_skill(path, source="community")`) on the draft: verdict
**safe**, 5 medium (informational) findings — `python_subprocess` ×2 (the browser and ffmpeg)
and `shell_rc_mod` ×3. The programmatic authoring standards (fields, name = directory,
description ≤ 60 characters with a period and no marketing words, no machine-local paths,
size, paste-safe shell blocks) pass, and `tests/skills/test_construct_skill.py` passes
(10 tests). Re-run both on a current checkout before opening.
The scripts start a local headless browser through `subprocess` (DevTools on 127.0.0.1) and
ffmpeg; they make no other network calls, read no secrets and bind no public ports. No
inline-shell snippets, no binaries.

## Credits

Author: OWNER NAME (rtmandreyev). Method inspired by Anatomy by Ryan (wheresryan22), MIT.
