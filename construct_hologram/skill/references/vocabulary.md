# Scene vocabulary (format `construct-scene` version 2)

Metres, **Y up, the front faces +Z** (a viewer's yaw 0 looks at the front). Angles in
degrees. Rotations apply X, then Y, then Z, about the part's own origin. Unknown keys are
errors: the closed vocabulary is the safety boundary.

## Skeleton

```json
{
  "format": "construct-scene", "version": 2,
  "id": "lowercase-id", "title": "Human title",
  "subject": {"category": "object", "summary": "one or two sentences", "accuracy": "generic", "synthetic": false},
  "units": "m", "seed": 7,
  "sources": [{"id": "request", "kind": "user_request", "title": "The user's request", "rights": "user_private"}],
  "facts":   [{"key": "height", "value": 0.42, "unit": "m", "certainty": "inferred", "source": "request", "note": "why"}],
  "assets":  [],
  "parts":   [ ... ],
  "articulations": [ ... ], "labels": [ ... ], "anchors": { ... },
  "annotations": [ ... ],
  "presentation": { ... },
  "animation": { ... }
}
```

- `subject.category`: `architecture, object, machine, vehicle, organism, fictional, cd, book, artwork-carrier, other`.
- `subject.accuracy`: `generic` (a typical example), `approximate` (based on this particular thing, imprecise), `documented` (its key parts cite evidence; the audit enforces it). `check` prints "evidence-backed key parts: n of m": how many key parts (mass and identity) are themselves verified or user-supplied; 0 is normal for a generic reconstruction.
- `subject.synthetic`: `true` only for examples and demonstrations; a real request is `false`, its `request` source `user_private`.
- Facts hold known values only. **An unknown fact is absent**: never `null`, never a guess.
- Colour is the renderer's. `presentation.style_hint {palette, identity}` is an optional hint a host may ignore: palettes `violet, cyan, amber, green, ice, rose`; identity tints `none, warm-wood, stone, steel, brass, bio, ember, ice, paper`. Leave it out when a host (Tessera) owns the look.

## Parts

```json
{"id": "tower", "label": "Tower", "role": "mass", "certainty": "inferred", "stage": 1,
 "basis": ["tower.height"], "source": null,
 "shape": {"type": "lathe", "profile": [[3.6, 0], [2.8, 20]]},
 "at": [0, 0, 0], "rotate": [0, 0, 0], "scale": 1,
 "look": {"fill": "glass"}, "repeat": null, "mirror": null, "motion": null, "floating": false}
```

| field | values |
|---|---|
| `role` | `mass` silhouette/primary volume · `structure` supporting construction · `detail` small/repeated (fades first) · `identity` the recognisable features (identity tint, glow) · `data` emphasised point/light (accent, strong glow) · `ornament` atmosphere (motes, sparkle) · `ground` survey/base lines · `artwork` a face carrying an image |
| `certainty` | `verified` (needs `source` or a verified basis fact) · `user_supplied` · `inferred` · `decorative`. A feature the user asked for whose size you chose: a `user_supplied` fact ("three blades") as `basis`, the part `inferred` |
| `stage` | 0–7, assembly order (foundation first) |
| `basis` | fact keys the part's dimensions come from |
| `look` | `tone` (`accent, bright, hairline, structure, dust, identity, data, faint`), `line` (`auto, solid, dashed, dotted, none`), `fill` (`auto, none, glass, dark`), `glow` 0–1, `weight` 0.25–3, `alpha` 0.05–1 — use sparingly: role and certainty already set the look |
| `floating` | `true` for things that truly hover (a beam of light, a halo, a creature's bell, motes); everything else must rest on something |
| `anchor` (box, sphere) | `center` (default) or `base` (sits on `at`) |
| `artwork` | `{"slot": "cover-front", "asset": "cover", "face": "front", "mask": "rect"}` — see Artwork |

### Shapes

| type | parameters | use for |
|---|---|---|
| `box` | `size [w,h,d]`, `ribs` 0–32 (panel lines), `anchor` | plinths, cases, rooms, boards |
| `cylinder` | `radius, height`, `segments` 6–96, `ribs` (vertical lines), `rings` (horizontal), `caps` | columns, feet, platters, knobs (base at `at`, along +Y) |
| `cone` | `radius_bottom, radius_top, height` (+ cylinder options) | lampshades, spires, beams, funnels |
| `sphere` | `radius` or `radii [x,y,z]`, `lat` 2–24, `lon` 3–48, `anchor` | heads, domes, bodies, ellipsoids |
| `torus` | `major, minor`, `segments, sides, rings` | rails, rims, tyres, rings |
| `lathe` | `profile [[radius, y], ...]` revolved about Y, `segments`, `meridians` | towers, bottles, vases, lamps, bells, records (flat profile = grooves) |
| `extrude` | `profile [[u,v], ...]` (simple polygon), `height`, `axis` `y` (footprint in XZ, rises) · `z` (front elevation in XY, runs back) · `x`, `ribs` | building plans, gabled houses, book spines, brackets |
| `tube` | `path [[x,y,z], ...]` (Catmull-Rom smoothed), `radius` or one per point (taper), `sides` 3–24, `samples`, `longitudinal`, `ring_every`, `caps` | limbs, tentacles, tonearms, pipes, cables, branches |
| `curve` | `points`, `smooth`, `closed` | edges, paths, outlines, shine strokes |
| `plane` | `size [w,h]` facing +Z, `divisions` | doors, windows, signs, artwork faces |
| `grid` | `size [w,d]`, `divisions` | ground plans, decks |
| `points` | `count` ≤ 2000, `region` `{"box":[w,h,d]}` · `{"sphere": r}` · `{"shell": r}`, `sprite` `disc, ring, square, soft`, `size_px` | dust, spores, stars, sparks |
| `marker` | `sprite`, `size_px` | one emphasised point |

### Repeat and mirror

- `"repeat": {"count": 2-64, "step": {"at": [dx,dy,dz], "rotate": [rx,ry,rz]}}` — copies
  stepped from the first (rotate is about each copy's own `at`).
- `"repeat": {"count": n, "radial": {"axis": "y", "center": [x,y,z], "span": 360}}` —
  copies around an axis (railings, petals, spokes, tentacles).
- `"phase_step": 0.083` — offsets each copy's motion phase (a ripple).
- `"mirror": "x"` — adds the reflection across the plane x = 0 (bilateral symmetry).

### Motion (object-relative)

The pivot is a **world point** and the axis a **world direction** for the first copy
(default pivot: the part's `at`); repeat and mirror copies carry them along.

| type | fields | example |
|---|---|---|
| `spin` | `axis, rpm` (±120), `pivot` | platter 33.33, fan, rotating beam |
| `swing` | `axis, degrees` (≤ 90), `period`, `pivot`, `phase` | hinge, tonearm drift, tentacle sway, pendulum |
| `bob` | `axis` (direction), `distance`, `period`, `phase` | floating, piston, breathing body |
| `pulse` | `period, amount` (0–1) | heart, lamp, glowing core |

## Articulations (one-shot opening)

Lids, boards, doors, drawers, a disc lifted from its tray: things that open once and hold.

```json
"articulations": [
  {"id": "lid-open", "type": "hinge", "parts": ["lid", "booklet"], "axis": [0, -1, 0], "pivot": [-0.071, 0.0625, 0.0052], "amount": 108, "order": 0},
  {"id": "booklet-out", "type": "slide", "parts": ["booklet"], "axis": [1, 0, 0], "amount": 0.07, "order": 1},
  {"id": "disc-lift", "type": "lift", "parts": ["disc"], "axis": [0, 0, 1], "amount": 0.03, "order": 1},
  {"id": "disc-turn", "type": "turn", "parts": ["disc"], "axis": [0, 0, 1], "pivot": [0.003, 0.0625, 0.0004], "amount": 360, "order": 2}
]
```

`hinge` (degrees, ±180, needs `pivot`), `turn` (degrees, ±1080, needs `pivot`), `slide` and
`lift` (metres along `axis`; lift defaults to up). Axes and pivots are world values in the
**closed** pose. List every part that moves with it: a booklet inside a lid is in the lid's
hinge too. Later `order`s ride on earlier ones (the booklet slides out of the opened lid).
Positive rotation follows the right-hand rule about `axis`: a lid hinged on its left edge
(front +Z) opens towards the viewer with `axis [0, -1, 0]` and a positive amount.
`presentation.still_pose`: `open` (default) or `closed` for the still frame.

## Labels (text the renderer sets from facts)

```json
"labels": [
  {"id": "spine-title", "part": "tray", "face": "left", "field": "title", "role": "title",
   "orientation": "vertical-down", "region": [0, 0.04, 1, 0.58]}
]
```

`field` names a fact (the label shows its value and inherits its certainty); `text` is
decorative literal text instead. `face` (box: `front back left right top bottom`; plane:
`front back`; cylinder/lathe: `top bottom`; default front/top), `region [u0, v0, u1, v1]`
(0..1 across the face, v downwards), `orientation` `horizontal | vertical-down` (spines,
reading top to bottom) `| vertical-up`, `role` `title | creator | meta | catalog | body |
decorative`, `align` `left | center | right`. Never put text in geometry; never label a fact
you do not know (the compiler refuses a label whose fact is missing).

## Anchors

`"anchors": {"front": {"part": "lid", "face": "front"}, "spine": {"part": "tray", "face": "left"},
"grip": {"part": "handle"}, "base": {"point": [0, 0, 0], "up": [0, 1, 0]}}` — all optional. They
tell a host which face to show face-out, which face a rack shows, where it rests and where it
is held. Unstated ones come from the bounds (front +Z, spine −X, base bottom centre). Give
`front` and `spine` for every CD, book and other shelved object.

## Annotations

`{"id": "lantern", "text": "Lantern room", "part": "lantern", "offset": [0, 1, 0]}` — short
review labels with a leader line. The anchor is the **top centre of the part's first copy's
box**, plus `offset` (metres); it follows the part when it opens. Shown with `labels=1` or
the L key. Mark inferred or decorative content in the text ("Beam (decorative)").

## Presentation

```json
"presentation": {
  "framing": {"yaw": 30, "pitch": 18, "fit": 1.0, "target": null},
  "views": [{"id": "detail", "label": "Detail", "yaw": 20, "pitch": 8, "distance": 1.5, "target": "lantern"}],
  "atmosphere": {"haze": 0.7, "scanlines": true, "vignette": true, "grid": true, "projector": false, "motes": 0.4},
  "occlusion": "xray", "certainty_style": "subtle", "background": "deep", "float": 0
}
```

Built-in views: `hero, front, side, back, top, three-quarter`. A view with `target` frames
that part alone; `distance` multiplies the distance fitted to that target (or to the whole
object without one), so a small target with `distance: 1` is already a close-up — raise it
(1.5–3) to keep context. `review` captures each of your views as `view-<id>.png`. A view named
`open` is the one that best shows the opened pose; give one whenever the object has
articulations. `projector` draws an emitter with
light rays and rising motes under small objects; `float` drops the survey ground below a
hovering subject; `certainty_style: "explicit"` dashes everything inferred.

## Animation

```json
"animation": {
  "assembly": {"style": "ceremony", "seconds": 6, "interference": true},
  "idle": {"life": "alive", "events": ["scan", "sweep", "shimmer"], "cadence": [5, 11], "strength": 0.6},
  "camera": {"drift": 6, "breathe": 0.03, "tour": [{"view": "detail", "at": 14, "fly": 3}, {"view": "hero", "at": 22, "fly": 3.5}]},
  "reduced_motion": "still"
}
```

Details and choices: [animation](animation.md).

## Artwork

```json
"assets": [{"id": "cover", "path": "assets/cover.png", "sha256": "<64 hex>", "media_type": "image/png",
            "rights": "user_private", "provenance": "authentic", "source": "user-photo"}]
```

and on a part with a face (box, plane, cylinder, lathe):
`"artwork": {"slot": "cover-front", "asset": "cover"}`. Slots name the place an image belongs:
`cover-front, cover-back, inlay, disc, label, booklet-page-1 … 64`, each once. Leave `asset`
out for an empty slot a host fills later. `face` as for labels; `mask` `rect` or `circle`
(with `inner_radius` in metres for a disc's hole); `region` a part of the face.
`provenance`: `authentic` (the real artwork: needs `permitted`/`user_private` rights and a
cited source), `user_photo`, `synthetic`, `generated-decorative`. Paths are relative to the scene's folder. The build
embeds only bytes whose hash matches; anything else is an empty slot. Compute the hash
with `shasum -a 256 file` (or Python's `hashlib`).

## Budgets

256 parts, 1,024 copies, 32 moving copies, 16 articulations, 48 labels, 24,000 lines,
24,000 triangles, 6,000 points, coordinates within ±500 m. Over budget: lower `segments`, `meridians`, `ribs`, `lat/lon`,
repeat counts, or drop fills (`"fill": "none"`) on thin parts.
