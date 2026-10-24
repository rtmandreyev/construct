# Porsche 911 (964)

[![Porsche 911 (964), a holographic construct](hero.jpg)](https://rtmandreyev.github.io/construct/examples/porsche-911-964/)

**Made by** GPT-6.1 Sol · masterpiece · with Construct 0.2.0.

[Open the live construct](https://rtmandreyev.github.io/construct/examples/porsche-911-964/) (drag to orbit, R replays the assembly, L shows labels) ·
[scene.json](scene.json)

**Reproduces with Construct 0.2.1.** `check` passes (44 warnings: bare-surface, no-checklist),
and the 0.2.1 compiler renders this hero pixel for pixel as the build that made it did. Its `bare-surface` warnings come from a later craft rule (main surfaces keep a faint contour); the scene predates it and is shown as it was made.

```sh
python3 construct_hologram/cli.py build examples/porsche-911-964/scene.json --out out/porsche-911-964
```
