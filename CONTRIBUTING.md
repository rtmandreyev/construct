# Contributing to Construct

Thanks for looking. Construct is a small, single-author project, and this file is short on
purpose.

## Setup

```sh
git clone https://github.com/rtmandreyev/construct.git
cd construct
python3 construct_hologram/cli.py check construct_hologram/examples/v2/lighthouse.json
```

Python 3.10 or newer. **No third-party packages**; please keep it that way. The viewer is plain
WebGL2 with no dependencies either.

## Running the tests

```sh
python3 -m unittest discover -s construct_hologram -t . -p 'test_*.py'
```

A Chromium-family browser enables the capture tests (review stills, critic packets); without
one, or with `HOLOGRAM_SKIP_CAPTURE=1`, they are skipped. CI runs the suite on every push and
pull request with the captures skipped, so run them locally when you change the viewer or the
renderer.

## Principles

- **Truth first.** Facts carry their certainty and sources; nothing unknown is guessed. Every
  example says how well it is known (generic, approximate or documented, and synthetic where it
  is), and a named subject cites the public references it was made from. No private data, real artwork or reference photographs in the repository.
- **One style.** A scene describes what a thing is; the compiler and viewer decide how it looks.
  Changes to the look go into the viewer and the compiler's style rows, never into scenes.
- **Determinism.** The same scene compiles to the same bytes. Keep randomness seeded.
- **The audit runs to zero.** Every skill example and golden passes `check` with no errors, and a
  test enforces it; any warning left is one you can explain.
- **Look at it.** Run `review` and read the images before calling a visual change done; attach a
  before/after still to the pull request.

## Common changes

- **A new shape or field:** `scene.py` (validation and compiler), the JSON Schema
  (`construct_hologram/geometry.schema.json`) if the output changes,
  `skill/references/vocabulary.md`, the prompts (`prompts.py`, then
  `python3 construct_hologram/cli.py prompts --out construct_hologram/prompts`) and tests. An
  output change is a contract change: bump the contract version in `product.py` and document it
  in `CONTRACT.md` and the changelog.
- **A new archetype:** `params.py` (a builder and its variants), a golden document in
  `construct_hologram/examples/v2/`, a row in `docs/ARCHETYPES.md`; review its renders.
- **A new audit check:** `audit.py`, a hint in `diagnose.py`, the code in the repair list in
  `prompts.py`, and a failing and a passing test.
- **An example construct:** see [examples/README.md](examples/README.md) and
  [PUBLISHING.md](PUBLISHING.md).

## Pull requests

The pull request template lists the checks. Keep a change to one concern, and say in the
description what you deliberately did not do.

## Credit and licence

By contributing you agree that your work is released under the [MIT licence](LICENSE).
Construct's method is inspired by Anatomy's truth-first construction
([wheresryan22/anatomy](https://github.com/wheresryan22/anatomy)); do not copy code, assets or
text from Anatomy or any other project into this one.
