# Ferrari F40

[![Ferrari F40, a holographic construct](hero.jpg)](https://rtmandreyev.github.io/construct/examples/ferrari-f40/)

**Made by** GPT-6.1 Sol · masterpiece · with a Construct 0.2.1 development build.

[Open the live construct](https://rtmandreyev.github.io/construct/examples/ferrari-f40/) (drag to orbit, R replays the assembly, L shows labels) ·
[scene.json](scene.json)

**Reproduces with Construct 0.2.1.** `check` passes (3 warnings: bare-surface, critic-stale),
and the 0.2.1 compiler renders this hero pixel for pixel as the build that made it did. Its `bare-surface` warnings come from a later craft rule (main surfaces keep a faint contour); the scene predates it and is shown as it was made. Its `critic-stale` warning is honest: the critic's last verdict was for an earlier version of the scene.

```sh
python3 construct_hologram/cli.py build examples/ferrari-f40/scene.json --out out/ferrari-f40
```
