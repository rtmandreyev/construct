# Contributing

Thank you for helping Construct grow. A few principles keep it honest and consistent.

## Principles

- **Truth first.** Facts carry certainty and sources; nothing unknown is guessed. Examples are
  synthetic and say so (`"synthetic": true`); no private data, real artwork or personal
  collections in the repository.
- **One style.** Scenes describe what a thing is; the renderer decides how it looks. Changes to
  the look go into the viewer and the compiler's style rows, never into scenes.
- **Determinism.** The same scene compiles to the same bytes. Keep randomness seeded.
- **The audit runs to zero.** Every example and golden must pass `check` with no errors or
  warnings (a test enforces it).
- **Look at it.** Run `review` and read the images before calling a visual change done; include
  a before/after still in your pull request.
- **No new dependencies.** Python standard library only; the viewer is plain WebGL2.

## Setup and tests

```sh
git clone https://github.com/rtmandreyev/construct && cd construct
python3 -m unittest discover -s construct_hologram -t . -p 'test_*.py'
```

A Chromium-family browser enables the capture tests; ffmpeg the video tests.

## Common changes

- **A new shape or field:** `scene.py` (validation, compiler), the JSON Schema
  (`geometry.schema.json`) if the output changes, `skill/references/vocabulary.md`, the
  prompts (`prompts.py`, then `python3 construct_hologram/cli.py prompts --out construct_hologram/prompts`)
  and tests. Output changes are contract changes: bump the contract version in `product.py`,
  document them in `CONTRACT.md` and the changelog.
- **A new archetype:** `params.py` (a builder and its variants), a golden document in
  `examples/v2/`, a row in `docs/ARCHETYPES.md`; review its renders.
- **A new audit check:** `audit.py`, a hint in `diagnose.py`, the code in `prompts.py`'s repair
  list, a failing and a passing test.
- **Docs pictures:** `python3 scripts/docs_media.py`. The release video: `scripts/release_video.py`.

## Credit and licence

By contributing you agree your work is released under the MIT licence. Construct is inspired
by Anatomy's truth-first method (`wheresryan22/anatomy`); do not copy code, assets or text from
Anatomy, NODE or any other project into this one.
