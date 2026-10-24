# Patek Philippe 5320G

[![Patek Philippe 5320G, a holographic construct](hero.jpg)](https://rtmandreyev.github.io/construct/examples/patek-philippe-5320g/)

**Made by** GPT-6.1 Sol · research first, standard (10 minutes) · with a Construct 0.2.0 development build.

[Open the live construct](https://rtmandreyev.github.io/construct/examples/patek-philippe-5320g/) (drag to orbit, R replays the assembly, L shows labels) ·
[scene.json](scene.json)

**Reproduces with Construct 0.2.1.** `check` passes (11 warnings: bare-surface),
and the 0.2.1 compiler renders this hero pixel for pixel as the build that made it did. Its `bare-surface` warnings come from a later craft rule (main surfaces keep a faint contour); the scene predates it and is shown as it was made.

```sh
python3 construct_hologram/cli.py build examples/patek-philippe-5320g/scene.json --out out/patek-philippe-5320g
```
