## What this changes

## Why

## How it was verified

- [ ] `python3 -m unittest discover -s construct_hologram -t . -p 'test_*.py'` (paste the final line)
- [ ] Every example and golden still passes `check`
- [ ] A visual change: `review` run and the images read; a before/after still attached
- [ ] Prompts regenerated if `prompts.py` changed (`python3 construct_hologram/cli.py prompts --out construct_hologram/prompts`)
- [ ] No third-party dependency added
- [ ] Docs and CHANGELOG updated where behaviour changed

## Anything deliberately not done
