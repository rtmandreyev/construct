# Hologram contract `tessera.hologram/0.2`

Status: draft 1 for review by Tessera main, 2026-10-19. Owner: the hologram toolkit
(`tools/hologram/`). Changes after review bump the version and are announced.

Two documents cross the boundary:

| Document | Format id | Who writes it | Who reads it |
|---|---|---|---|
| **Scene** (authoring input) | `"format": "tessera-hologram", "version": 2` | an agent or a person | the toolkit's compiler |
| **Geometry** (compiled output) | `"format": "tessera-hologram-geometry", "version": 2`, `"contract": "tessera.hologram/0.2"` | the compiler only | renderers (the portable viewer, Tessera native) |

A renderer consumes **geometry**, never scenes: everything is already explicit (line
segments, triangles, sprites, styles, phases, motion slots). No renderer needs to
interpret shapes, run code or fetch anything. Keep the source scene next to its geometry;
`scene_sha256` binds them. The v1 `tessera-geometry` segment list remains available
(`build --v1`, `scene.to_v1`) for the existing native study.

## Frame and units

Metres. Authoring and default output frame: **Y up, the front faces +Z** (glTF's
convention; v1 compatible). `geometry.frame` states it. Consumers with a Z-up object frame
use `build --frame z-up` (or `scene.reframe(g, "z-up")`): `(x, y, z) → (x, −z, y)`, a proper
rotation applied to positions, motion pivots/axes, artwork corners, anchors and bounds;
`frame.up` then reads `+z`. Never mix frames inside one document.

## 1. Facts and sources

`provenance.sources[]`: `{id, kind, title, rights, ref?}`; kinds `user_request |
user_supplied | document | measurement | observation | dataset | generated`; rights
`synthetic | user_private | permitted | public_domain | reference_only`. `ref` is citation
text, never fetched.

`provenance.facts[]`: `{key, value (scalar), unit?, certainty, source?, note?}`.
Certainty is one of **`verified | user_supplied | inferred | decorative`**. `verified`
must cite a source id (the compiler refuses otherwise). `subject.accuracy` is
`generic | approximate | documented`; `subject.synthetic` marks example content.

## 2. Parts

`parts[]` (index = the part number used by styles):
`{id, label, role, certainty, basis[], source, stage, floating, shape, instances[], motion}`.
`id` is stable and unique; `basis` lists fact keys the geometry rests on; `instances` are
the copies after repeat/mirror, each `{min, max, motion_slot}` (an axis-aligned box in the
output frame and its motion slot or −1).

Roles (the hierarchy), with the names main proposed:

| role | meaning | main's term |
|---|---|---|
| `mass` | primary volume and silhouette | structure (primary) |
| `structure` | supporting construction | structure |
| `detail` | small repeated detail; fades first with distance | detail |
| `identity` | the two or three features that make it recognisable | surface/identity |
| `data` | emphasised information (a lamp, a measured point, a label) | — |
| `ornament` | decorative atmosphere (motes, sparkle) | — |
| `ground` | survey/ground reference | — |
| `artwork` | an artwork carrier face | label/artwork carrier |

## 3. Geometry

Packed, renderer-ready arrays (numbers rounded to 10 µm):

- `lines` stride 9: `ax ay az bx by bz style phase_a phase_b` — draw each as an
  anti-aliased screen-space line; `phase_*` are build phases (below).
- `fills` stride 5 per vertex, three vertices per triangle: `x y z style phase` —
  translucent glass or dark occluders (style field `occluder`).
- `points` stride 7: `x y z size_px style sprite phase`; sprite `0 disc, 1 ring,
  2 square, 3 soft`.
- `counts`, `bounds {min, max, center, radius}`.

Budgets: ≤ 24,000 lines, ≤ 24,000 triangles, ≤ 6,000 points, ≤ 256 parts, ≤ 1,024
instances, ≤ 32 moving instances. Authoring shapes (box, cylinder, cone, sphere, torus,
lathe/revolve, extrude, tube/sweep, curve with Catmull-Rom smoothing, plane, grid, points,
marker; repeat, radial repeat, mirror) are compiled away.

## 4. Material roles

`styles[]` rows: `tone, alpha, width_px, glow_px, dash, fade, part, motion_slot, occluder`.

- `tone` index: `0 accent, 1 bright, 2 hairline, 3 structure, 4 dust, 5 identity, 6 data,
  7 faint` — palette slots, never colours. `style.palette` (`violet | cyan | amber | green |
  ice | rose`) and `style.identity` (a low-chroma material tint: `warm-wood, stone, steel,
  brass, bio, ember, ice, paper, none`) choose the colours.
- `dash`: `0 solid, 1 dashed, 2 dotted` (world-space pattern).
- `fade`: `0..3` how strongly depth fog thins it.
- Certainty is the material: verified/user-supplied crisp, inferred a step back (dashed in
  `presentation.certainty_style: "explicit"`), decorative dotted and faint. A renderer may
  restyle within this meaning but must keep the four certainties distinguishable and must
  offer a provenance view.
- No shader code, scripts or URLs exist anywhere in either document.

## 5. Artwork

Declared in `provenance.assets[]`: `{id, path (relative, inside the asset folder), sha256,
media_type (png/jpeg/webp), rights, provenance, source?}` with provenance
**`authentic | synthetic | generated-decorative | user_photo`**. Authentic art needs
`permitted` or `user_private` rights and a cited source. `artwork[]`:
`{part, asset_id, corners[4] (top-left, top-right, bottom-right, bottom-left), uv[4], phase}`,
the face of a `plane` (or the +Z face of a box). A renderer displays bytes only after
verifying the hash under an explicit asset root (the portable build does this and embeds
nothing else); a missing or mismatched asset is an empty, labelled slot. Generated
decoration must be labelled as such wherever it is shown.

## 6. Animation

**Assembly (staged construction).** `parts[].stage` is an ordered integer 0..7;
`stages[]` lists the stages used. Every vertex carries a build phase in 0..1: stage order
first, then bottom-up height within the stage. At build progress `b`, draw what has
`phase ≤ b`; a line whose phases differ grows from its lower end, with a brightening tip.
`animation.assembly`: `style` `ceremony` (signal ghost ≈0.9 s, collapse ≈0.35 s, build
`seconds`, stabilise ≈1.1 s glow) | `build` (build + short settle) | `cut` (complete at once).

**Object-relative motion.** `motions[]` slots referenced by `styles[].motion_slot`:
`{type, axis, pivot, rpm, degrees, distance, period, amount, phase, part}` in the output
frame.

| type | meaning | bounds | main's term |
|---|---|---|---|
| `spin` | rotate about `axis` through `pivot` at `rpm` | ±120 rpm | spin |
| `swing` | oscillate `degrees` about `axis`, period `period` | ≤ 90°, 0.2–120 s | hinge |
| `bob` | translate ± `distance` along `axis` | ≤ 50 m | slide |
| `pulse` | brightness ×(1 + amount·(1+sin)/2) | amount ≤ 1 | — |

`phase` (0..1) offsets copies (a ripple through tentacles). "Reveal" is the assembly
above, not a motion. All motion is a pure function of time `t`.

**Idle life.** `animation.idle`: `life` `off | calm | alive`, `events` from `scan, sweep,
wave, shimmer, glitch, brownout, propagate, tear, burst`, `cadence [min, max]` seconds,
`strength 0..1`. Events start after assembly; the schedule is seeded from `scene_sha256`
so a frame at time `t` is reproducible.

**Still state.** `animation.reduced_motion: "still"`: assembly complete, no events, no part
motion, no camera drift or tour. A renderer must provide it (and honour the platform's
reduce-motion preference).

## 7. Camera hints

`bounds`; `presentation.framing {yaw, pitch, fit, target}` (the hero); `presentation.views[]
{id, label, yaw, pitch, distance (× the fitted distance), target (part id)}`; built-in views
`hero, front (yaw 0), side (90), back (180), top, three-quarter`; `animation.camera {drift
(°/min), breathe, tour[] {view, at, fly}}`. Yaw 0 looks at the front (+Z); pitch is
elevation. Fitting: frame every part's instance boxes (excluding decorative point clouds)
inside the field of view with margin. `presentation.float` lifts the survey ground below a
hovering subject. `presentation.atmosphere {haze, scanlines, vignette, grid, projector,
motes}`, `occlusion` (`xray` | `none`), `background` (`deep` | `transparent`) are
presentation preferences a host may override.

## Out of scope

Regions, world/atlas navigation and its camera, catalog state, selection and application
UI stay in Tessera. The contract describes one object.

## Versioning

`contract` changes on any field addition (minor) or semantic change (major). Readers must
refuse an unknown major, and may ignore unknown fields within the same major. The geometry
`version` integer tracks the major.
