# Black hole

[![Black hole, a holographic construct](hero.jpg)](https://rtmandreyev.github.io/construct/examples/black-hole/)

**Made by** GPT-6.1 Sol · a single first pass · with a Construct 0.2.0 development build.

[Open the live construct](https://rtmandreyev.github.io/construct/examples/black-hole/) (drag to orbit, R replays the assembly, L shows labels) ·
[scene.json](scene.json)

**Reproduces with Construct 0.2.1.** `check` passes (1 warning: bare-surface),
and the 0.2.1 compiler renders this hero pixel for pixel as the build that made it did. Its `bare-surface` warnings come from a later craft rule (main surfaces keep a faint contour); the scene predates it and is shown as it was made.

```sh
python3 construct_hologram/cli.py build examples/black-hole/scene.json --out out/black-hole
```
