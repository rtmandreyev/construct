# Nissan Skyline GT-R R34

[![Nissan Skyline GT-R R34, a holographic construct](hero.jpg)](https://rtmandreyev.github.io/construct/examples/nissan-skyline-gt-r-r34/)

**masterpiece · Claude Opus 5.5**

[Open the live construct](https://rtmandreyev.github.io/construct/examples/nissan-skyline-gt-r-r34/): drag to orbit, R replays the assembly, L shows
labels. The scene it was built from: [scene.json](scene.json).

Build it yourself from a checkout of Construct:

```sh
python3 construct_hologram/cli.py build examples/nissan-skyline-gt-r-r34/scene.json --out out/nissan-skyline-gt-r-r34
```

## Refined for the solid (1.1.2)

The light forgives what a solid does not. Seen as a solid (**S** on the page) and exported to Blender, the first
version showed defects the checks had let through; this version answers them, and every part keeps its name:

- **C-pillar** (`sail-panel`): a fully rounded fin at 36° that stopped short of the rear glass, left a hollow
  between itself and the glass and ran forward through the quarter window. It now closes the pillar from the
  shoulder up under the rear glass and above the quarter window's slanted edge up under the roof.
- **Bumper flanks** (`front-bumper-side`, `-2`): plates 2 cm thick with nothing behind them, an open-sided
  bracket ahead of each front wheel. Each is a closed flank 6 cm deep behind the same outer face.
- **Rear bumper and tail panel**: rounded by 0.9 of their half height (21 cm), a pillow rolling away from the
  quarter panels; now rounded as a moulded bumper is.
- **Sills** (`side-skirt`): their lower edge wandered by 5 cm and their top stood out of the door by up to 3 cm,
  a notched seam; now straight, and flush with the panels above.
- **Diffuser**: square in plan under a bumper rounded in plan, its corners stood out; its strakes hung below it,
  touching nothing. It follows the bumper, and the strakes reach up into it.
- **Wing to cowl** (`fender-front-upper`): its rear end stood 2 cm below the bonnet. It meets it.
- **Tubes**: 37 suspension arms, shafts, pipes and springs were open at both ends; they are capped.

The C-pillar, the sills, the diffuser and its strakes are no longer the tracing, and say so (`inferred`, with a
note); nothing claims more than before. The light is all but unchanged.
