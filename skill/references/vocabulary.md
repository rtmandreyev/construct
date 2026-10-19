# Scene vocabulary (format `tessera-hologram` version 2)

Metres, **Y up, the front faces +Z** (a viewer's yaw 0 looks at the front). Angles in
degrees. Rotations apply X, then Y, then Z, about the part's own origin. Unknown keys are
errors: the closed vocabulary is the safety boundary.

## Skeleton

```json
{
  "format": "tessera-hologram", "version": 2,
  "id": "lowercase-id", "title": "Human title",
  "subject": {"category": "object", "summary": "one or two sentences", "accuracy": "generic", "synthetic": false},
  "units": "m", "seed": 7,
  "sources": [{"id": "request", "kind": "user_request", "title": "The user's request", "rights": "user_private"}],
  "facts":   [{"key": "height", "value": 0.42, "unit": "m", "certainty": "inferred", "source": "request", "note": "why"}],
  "assets":  [],
  "style":   {"palette": "violet", "identity": "brass"},
  "parts":   [ ... ],
  "annotations": [ ... ],
  "presentation": { ... },
  "animation": { ... }
}
```

- `subject.category`: `architecture, object, machine, vehicle, organism, fictional, cd, book, artwork-carrier, other`.
- `subject.accuracy`: `generic` (a typical example), `approximate` (based on this particular thing, imprecise), `documented` (its key parts cite evidence; the audit enforces it).
- `style.palette`: `violet, cyan, amber, green, ice, rose`. `style.identity` (a low-chroma material tint for `identity` parts): `none, warm-wood, stone, steel, brass, bio, ember, ice, paper`.

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
| `certainty` | `verified` (needs `source` or a verified basis fact) · `user_supplied` · `inferred` · `decorative` |
| `stage` | 0–7, assembly order (foundation first) |
| `basis` | fact keys the part's dimensions come from |
| `look` | `tone` (`accent, bright, hairline, structure, dust, identity, data, faint`), `line` (`auto, solid, dashed, dotted, none`), `fill` (`auto, none, glass, dark`), `glow` 0–1, `weight` 0.25–3, `alpha` 0.05–1 — use sparingly: role and certainty already set the look |
| `floating` | `true` for things that truly hover (a beam of light, a halo, a creature's bell, motes); everything else must rest on something |
| `anchor` (box, sphere) | `center` (default) or `base` (sits on `at`) |

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

## Annotations

`{"id": "lantern", "text": "Lantern room", "part": "lantern", "offset": [0, 1, 0]}` — short
labels anchored above a part (shown with `labels=1` or the L key). Mark inferred or
decorative content in the text when it matters ("Beam (decorative)").

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
that part; `distance` multiplies the fitted distance. `projector` draws an emitter with
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

and on a `plane` part: `"artwork_asset_id": "cover"`. `provenance`: `authentic` (the real
artwork: needs `permitted`/`user_private` rights and a cited source), `user_photo`,
`synthetic`, `generated-decorative`. Paths are relative to the scene's folder. The build
embeds only bytes whose hash matches; anything else is an empty slot. Compute the hash
with `shasum -a 256 file` (or Python's `hashlib`).

## Budgets

256 parts, 1,024 copies, 32 moving copies, 24,000 lines, 24,000 triangles, 6,000 points,
coordinates within ±500 m. Over budget: lower `segments`, `meridians`, `ribs`, `lat/lon`,
repeat counts, or drop fills (`"fill": "none"`) on thin parts.
