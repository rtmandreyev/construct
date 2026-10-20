# Archetypes: the simple path

For common things, a model does not have to write geometry. It fills a short
`construct-params` document — the archetype, a variant, the facts it actually knows, and
sizes only if they differ from the standard — and a deterministic builder draws the object in
the house style, with its labels, artwork slots, opening sequence and anchors. Small models
reach a clean result in one or two rounds this way, and every model's entry looks the same.

```sh
python3 construct_hologram/cli.py params --list                 # every archetype and its standard sizes
python3 construct_hologram/cli.py params case --variant jewel --output cd.json
```

| archetype / variant | standard | artwork slots | opens |
|---|---|---|---|
| `case/jewel` | 142 × 125 × 10.4 mm CD jewel case | cover-front, inlay, disc | lid hinges, booklet lifts out beside the case, disc lifts and turns |
| `case/slim` | 142 × 125 × 5.2 mm slim case | cover-front, cover-back, disc | lid hinges, disc lifts and turns |
| `case/digipak` | 139.5 × 125 × 8 mm two-panel digipak | cover-front, cover-back, inlay, disc | front panel unfolds, disc lifts and turns |
| `case/box` | 145 × 130 mm slipcase of slim cases (`discs`, default 3) | cover-front, cover-back | the cases slide out |
| `book/hardcover` | 156 × 234 × 36 mm | cover-front, cover-back | front board opens to the title page |
| `book/paperback` | 129 × 198 × 25 mm | cover-front, cover-back | cover opens to the title page |
| `object/electric-guitar` | 648 mm scale; `body_style` double-cut, single-cut or offset; strings, frets, pickups, knobs | — | — |
| `object/acoustic-guitar` | dreadnought, 645 mm scale | — | — |
| `object/bass-guitar` | 864 mm scale, 4 strings | — | — |
| `object/synth` | 49 keys; knob rows, screen, wheels | — | — |
| `vessel/bottle` | 330 ml long-neck, 235 mm | label | — |
| `vessel/can` | 330 ml, 115 × 66 mm (440 ml: 147 mm; 500 ml: 168 mm) | label | — |
| `vessel/glass` | pint, tulip or stange; `fill` | — | — |

Text on the object comes from facts: `title`, then the first of `artist`, `author`,
`creator`, `composer`, `brewery`, `maker` (the creator line); vessels add `style`; guitars and
synths `maker` and `model`. A fact that is not there has no text. Sizes become facts:
standard sizes are `inferred` (with the reason), sizes you give are `inferred` unless
`param_certainty` says `user_supplied` or `verified`.

Fifteen synthetic golden documents live in `construct_hologram/examples/v2/*.params.json`;
`prompts/params.md` is the same information written for a model, and
`prompts/params.schema.json` constrains a model's output where the endpoint supports it.

Adding an archetype is code (`params.py`): it is where the visual language grows, so each
new one is designed, rendered and reviewed. See [CONTRIBUTING.md](../CONTRIBUTING.md).
