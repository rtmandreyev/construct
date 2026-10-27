# The Construct contract `construct/0.2`

Status: **stable** (0.2, 2026-10-19). The documents agents write (scenes, parameter documents)
and apps read (compiled geometry). Any change bumps the version and is recorded in the
changelog.

## Identifiers

| | id | version |
|---|---|---|
| contract | `construct/0.2` | — |
| scene (authoring input) | `construct-scene` | 2 |
| parameter document | `construct-params` | 1 |
| compiled geometry | `construct-geometry` | 2 |

**Legacy ids, read for one release.** The toolkit began inside Tessera, where the same
documents were `tessera.hologram/0.2`, `tessera-hologram` (scene, version 2),
`tessera-hologram-params` and `tessera-hologram-geometry`. Construct 0.2.x reads the legacy
scene and parameter ids (with a `legacy-format` warning) and never writes them; readers of
geometry should accept both geometry ids until 0.3. The v0.1 construction sheets
(`tessera-hologram` version 1, `tessera-geometry`) are a separate legacy format.

| Document | Format id | Written by | Read by |
|---|---|---|---|
| **Scene** (authoring input) | `"format": "construct-scene", "version": 2` | an agent or a person | the toolkit's compiler |
| **Geometry** (compiled output) | `"format": "construct-geometry", "version": 2`, `"contract": "construct/0.2"` | the compiler only | renderers (the portable viewer; apps' native renderers) |

A renderer consumes **geometry**, never scenes: everything in it is explicit (line segments,
triangles, sprites, styles, phases, transform slots, face quads). No renderer needs to
interpret shapes, run code or fetch anything (the one exception is film mode's optional audio
features file, below, in a page built for film). Its structure and budgets are published as
[`geometry.schema.json`](construct_hologram/geometry.schema.json) (JSON Schema 2020-12); a consumer re-validates
structure, budgets and `scene_sha256` itself and never trusts compiler output blindly. Keep
the source scene next to its geometry; `scene_sha256` binds them. The v1 `tessera-geometry`
segment list stays available (`build --v1`, `scene.to_v1`).

## Frame and units

Metres. **Y up, the front faces +Z** is the only default frame (`geometry.frame`). `build
--frame z-up` / `scene.reframe(g, "z-up")` remains a utility, `(x, y, z) → (x, −z, y)` applied
to every position, axis, pivot, quad, anchor and box, for apps with a Z-up world.

## 1. Facts and sources

`provenance.sources[]`: `{id, kind, title, rights, ref?}`; kinds `user_request | user_supplied |
document | drawing | measurement | observation | dataset | reference_image | generated`; rights `synthetic | user_private |
permitted | public_domain | reference_only`. `ref` is citation text, never fetched.

`provenance.facts[]`: `{key, value, unit?, certainty, source?, note?}` with certainty
**`verified | user_supplied | inferred | decorative`**. `verified` must cite a source id.
**An unknown fact is absent**: `value` is a string, number or boolean, never null; the compiler
refuses null, and an author deletes the fact instead of guessing. (An app's "unknown" facts simply do not reach the construct.) `subject.accuracy` is `generic |
approximate | documented`; `subject.synthetic` marks example content.

## 2. Parts

`parts[]` (index = the part number in styles):
`{id, label, role, certainty, basis[], source, stage, floating, shape, motion, joint, instances[]}`.
`instances` are the copies after repeat/mirror: `{min, max, motion_slot, joint, open_min?,
open_max?}` — the rest-pose box, the periodic-motion slot (or −1), the articulation joint (or
−1), and for articulated copies the box they reach fully open.

| role | meaning | also called |
|---|---|---|
| `mass` | primary volume and silhouette | structure (primary) |
| `structure` | supporting construction | structure |
| `detail` | small repeated detail; fades first with distance | detail |
| `identity` | the two or three features that make it recognisable | surface/identity |
| `data` | emphasised information (a lamp, a measured point) | — |
| `ornament` | decorative atmosphere (motes, sparkle) | — |
| `ground` | survey/ground reference | — |
| `artwork` | an artwork carrier face | label/artwork carrier |

## 3. Geometry

Packed, renderer-ready arrays (numbers rounded to 10 µm), all in the rest (closed) pose:

- `lines` stride 9: `ax ay az bx by bz style phase_a phase_b`; per-vertex build phases.
- `fills` stride 5 per vertex, three per triangle: `x y z style phase`.
- `points` stride 7: `x y z size_px style sprite phase`; sprite `0 disc, 1 ring, 2 square, 3 soft`.
- `bounds {min, max, center, radius, open_min, open_max}`; `counts`.

Budgets: ≤ 24,000 lines, ≤ 24,000 triangles, ≤ 6,000 points, ≤ 256 parts, ≤ 1,024 instances,
≤ 32 moving instances, ≤ 16 articulations, ≤ 16 joints, ≤ 48 labels.

## 4. Material roles (the renderer owns colour)

`styles[]` rows: `tone, alpha, width_px, glow_px, dash, fade, part, motion_slot, occluder, joint`.

- `tone` is a slot, never a colour: `0 accent, 1 bright, 2 hairline, 3 structure, 4 dust,
  5 identity, 6 data, 7 faint`. `dash` `0 solid, 1 dashed, 2 dotted`; `fade` 0..3 (how much
  depth thins it); `occluder` 1 for a dark fill that hides what is behind it.
- **Colour belongs to the renderer.** Every construct compiles with the house palette:
  `presentation.style_hint` in the geometry is always `{palette: violet, identity: none}` unless
  a person chose another through a host option (`build --palette`), whatever the scene said.
  A scene's `style_hint` is ignored with a `style-hint-ignored` warning; a scene-level `style`
  is refused. An app with its own palette ignores the field altogether.
- Certainty is the material: verified/user-supplied crisp, inferred a step back, decorative
  dotted and faint. A renderer may restyle within this meaning but keeps the four
  certainties distinguishable and offers a provenance view.
- No shader code, scripts or URLs exist in either document.

## 5. Artwork slots and masks

Assets: `provenance.assets[]` `{id, path, sha256, media_type (png/jpeg/webp), rights,
provenance (authentic | synthetic | generated-decorative | user_photo), source?}`. Authentic
art needs `permitted` or `user_private` rights and a cited source.

`artwork[]`: `{part, slot, asset_id | null, face, corners[4], uv[4], mask, inner_ratio,
certainty, motion_slot, joint, phase}`.

- `slot` names the place, so a pipeline can map images by name: **`cover-front, cover-back,
  inlay, disc, label, booklet-page-1 … booklet-page-64`**, each at most once per scene. An
  empty slot (`asset_id: null`) is valid: the host fills it from its own permitted media, or
  shows its designed no-art face.
- `mask`: `rect` or `circle`; `inner_ratio` is a circle's hole as a fraction of its radius (a
  disc print: 7.5 mm / 60 mm = 0.125).
- A renderer shows bytes only after verifying the hash; generated decoration is labelled.

## 6. Labels: text from facts, set by the host

`labels[]`: `{id, part, face, corners[4], field | null, text, certainty, role, align,
orientation, motion_slot, joint, phase}`.

- `field` is a fact key (`title`, `artist`, `author`, `year`, …); `text` is that fact's value
  as the compiler read it, and the label **inherits the fact's certainty**. The host sets the
  text in its own fonts from the fact (it may re-read the live entry). `field: null` is
  decorative literal text (certainty `decorative`).
- `corners` are top-left, top-right, bottom-right, bottom-left **of the text box**: the first
  edge is the direction the text runs, the last edge points down the letters. `orientation`
  (`horizontal | vertical-down | vertical-up`) is already applied to the corner order and
  stated for information. `role`: `title | creator | meta | catalog | body | decorative`
  (weight/size class; the host decides the type); `align`: `left | center | right`.
- A label referring to a fact that does not exist is refused: an unknown fact has no label.
- A spine is a face plus fields; a title page, a beer label or an inlay the same.

## 7. Anchors (rest pose)

`anchors`: `{base {point, up}, front {corners, part, face}, spine {corners, part, face},
grip {point, part} | null}`, each with `from: scene | bounds`.

- `base`: where the object rests and which way is up (shelf, stand). Default: the bottom
  centre of the bounds, up +Y.
- `front`: the face shown face-out; `spine`: the face a rack shows. Defaults: the bounds' +Z
  and −X faces. Corners as in §6 (seen from outside).
- `grip`: optional handling point.
- A rack can draw thousands of items from `bounds` + `anchors.spine` + the spine labels alone;
  full geometry is for previews and face-out displays (detail roles fade first).

## 8. Animation

**Assembly.** `parts[].stage` 0..7; `stages[]`; every vertex has a build phase 0..1 (stage
order, then bottom-up height within the stage). Draw what has `phase ≤ b`; a line whose
phases differ grows from its lower end. `animation.assembly.style`: `ceremony | build | cut`.

**Articulations (one-shot, host-driven).** `articulations[]` (sorted by `order`):
`{id, type, axis, pivot | null, amount, unit, order, parts[], instances[[part, index]]}`.

| type | moves | amount | unit |
|---|---|---|---|
| `hinge` | rotate about `axis` through `pivot` | −180..180 | deg |
| `turn` | rotate about `axis` through `pivot` (a disc turning once) | −1080..1080 | deg |
| `slide` | translate along `axis` | metres | m |
| `lift` | translate along `axis` (default up) | metres | m |

The host drives each articulation with an opening `u ∈ [0, 1]` (pose = `amount · u`) and owns
timing, easing, sequencing and Reduce Motion; `order` is the suggested sequence. Axes and
pivots are world values **in the rest pose**. `joints[]` lists, per joint slot, the
articulations that move it (indices into `articulations`, ascending order); a vertex's joint
transform is `A[j0](u0) · A[j1](u1) · …` — the first is outermost, so **a later articulation
rides on the earlier ones** (a booklet slides out of a lid that is already hinged open).
Periodic motion (below) is applied before the joint. `presentation.still_pose` (`open |
closed`) is the pose the still state shows. The portable viewer opens after assembly, one
order group at a time (~1.5 s each), and holds; `?open=0..1` freezes a pose.

**Periodic motion.** `motions[]` slots referenced by `styles[].motion_slot`:

| type | meaning | bounds |
|---|---|---|
| `spin` | rotate about `axis` through `pivot` at `rpm` | ±120 rpm |
| `swing` | oscillate `degrees` about `axis` | ≤ 90°, 0.2–120 s |
| `bob` | translate ± `distance` along `axis` | ≤ 50 m |
| `pulse` | brightness × (1 + amount·(1+sin)/2) | amount ≤ 1 |

For things that keep moving (a fan, a beam, a tentacle). Hinges, lids and one-time turns are
articulations, not motions.

**Idle life (host-optional).** `animation.idle {life, events, cadence, strength}` with events
`scan, sweep, wave, shimmer, glitch, brownout, propagate, tear, burst`, seeded from
`scene_sha256`. A host may play none of them (an app may settle to zero frames when idle).

**Still state (required).** Assembly complete, the `still_pose`, no events, no motion, no
camera movement.

## 9. Camera hints (host-optional)

`bounds` (and `open_min/open_max`); `presentation.framing {yaw, pitch, fit, target}`;
`presentation.views[] {id, label, yaw, pitch, distance (× the distance fitted to the view's
target, or to the whole object), target}`; built-in views `hero, front, side, back, top,
three-quarter`; yaw 0 looks at the front, pitch is elevation.

**The `open` view** (minor addition to 0.2): `views[id="open"]` is the view that best shows
the opened pose (the title page, the lifted disc beside its booklet). A host arrives at the
hero (the closed object's best side) and turns to `open` as the articulations play; the
portable viewer does the same when the scene has no tour of its own. The audit warns
(`no-open-view`) when something opens and has no `open` view; the authoring skill picks it
from `review/view-open.png`. `animation.camera {drift,
breathe, tour[]}` and `presentation.atmosphere / occlusion / background / float` are the
portable viewer's preferences; a host that owns its camera and environment ignores them.

## Out of scope

A world or collection around the object (regions, navigation and its camera, catalogue
state, selection, UI) belongs to the app. The contract describes one object.

## Versioning

`contract` changes on any field addition (minor) or semantic change (major). Readers refuse an
unknown major and may ignore unknown fields within a major. Geometry `version` tracks the major.

## Terrain (an addition within 0.2)

A scene may use the shape `terrain` (a heightfield); it compiles to ordinary lines and
triangles, so geometry readers need nothing new. `parts[].shape` is then `"terrain"`: a host
labels the construct **MEASURED TERRAIN** when that part is `verified` or `user_supplied` (its
source a `dataset`), otherwise **SKETCHED TERRAIN**, and shows the scale (fact
`terrain.scale`) and the data attribution (the `dataset` source's title).

## Authoring record: identity, critic, compare (additions within 0.2)

`authoring` may also carry `identity` (the checklist: `{feature, parts, source?}`), `critic`
(`{scene_sha256, verdict, scores, round?, model?, defects?}`: an independent critic's record,
bound to the hash of the scene without its authoring block) and `compare` (`{view, reference,
iou, edge, pass, scene_sha256}`: silhouette comparisons). `outcome` adds `outstanding` and
`self-reviewed`; `tier` adds `masterpiece`. Readers may ignore all of it.

## The architecture kit (additions within 0.2)

Shapes `tower`, `roof`, `dormer`, `facade`, `battlements`, `buttress` and `shell` (fields in the
skill's vocabulary reference) compile to ordinary lines and triangles; readers need nothing new.

## Loft (an addition within 0.2)

The shape `loft` `{sections: [[z, half_width, y_bottom, y_top, half_width_top?], ...],
round?: 0..1}` runs back to front along +Z through rounded trapezoid sections. It compiles to
ordinary lines and triangles.

## Paths (an addition within 0.2)

The shape `paths` `{paths: [[[x, y, z], ...], ...], detail?: bool}` draws up to 4,000 open polylines
(2 to 256 points each, 30,000 in all) in one part: agent tracks, network edges, measured curves. It
compiles to ordinary lines; readers need nothing new. `detail` draws them as detail lines (thinner,
fading first with distance). The NetLogo bridge (`construct netlogo`) writes it.

## Globe (an addition within 0.2)

The shape `globe` `{radius, paths: [[[lon, lat], ...], ...], graticule?: 0|10|15|20|30|45,
faces?: bool}` draws longitude/latitude paths (degrees) on a sphere: north up (+Y), longitude
0 facing the front (+Z). It compiles to ordinary lines and triangles. A host labels a globe
whose `identity` globe part is `verified` (a `dataset` source) **MEASURED COASTLINES**,
otherwise **SKETCHED COASTLINES**, and shows the scale (fact `globe.scale`) and the data
credit. Terrain shapes may also carry `index` (every n-th contour bold) and `grid_every: 0`.

## Authoring record (an addition within 0.2)

A scene or parameter document may carry `authoring`, which compiles to
`provenance.authoring`: `{tier, research, sources?, review_rounds?, outcome?, next?}` — `tier`
`quick | standard | showcase`; `research` `done | not_needed | skipped | unavailable | off`;
`sources` the ids of the scene's sources research used (required when `research` is `done`);
`outcome` `good | limit | unreviewed`; `next` up to 8 improvement notes. It says how the
construct was made so a host can regenerate it at a higher tier; readers may ignore it.

## Film mode (0.3.0, optional)

Film mode lets an assembly span a piece of music, for video. It is strictly optional: it lives in
its own script, `viewer/film.js`, which a page carries only when it is built for film
(`construct build --film`, or `construct video` with a film option). A page built without it is the
stock viewer, byte for byte, and a page built with it behaves exactly like the stock one until a
film parameter is given.

- **Long assemblies.** `animation.assembly.seconds` accepts up to 1200 (20 minutes). Above 20
  seconds the audit warns `long-assembly`: a construct assembles in at most 20 s, and a film
  usually keeps the scene short and sets the length when rendering.
- **Viewer parameters** (a page built for film).
  - `assembly=<seconds>` sets the assembly's length for this view, overriding the scene.
  - `audio=<features.json>` loads audio features (below), and `reactivity=<0..2>` (default 1) sets
    how strongly they show. At reactivity r: each frame of the build advances by
    `exp(4r·(rank − 0.5)) · (0.15 + 0.85·min(1, energy/0.15))^r`, where rank is the frame's energy
    ranked among the build's frames (0..1), smoothed over 2 s and normalised so the build still
    ends exactly on time; at each section boundary inside the build (the strongest first, at most
    one per stage) the build is pinned to the start of a stage; the light scales by
    `1 + 0.4r·(2·energy − 1)`; each onset above `0.75 − 0.2r` gives an accent
    `((onset − floor)/(1 − floor))^1.5`, as does each section boundary (1), decaying with a 0.2 s
    time constant, which lights a scan band at the build front's height, a glow surplus on what is
    built and 10% more light; and while `voice` is above 0.25 the construct shimmers. At r = 0
    the build is even and none of these apply.
  - `camera=steady` flies no tour (neither the scene's nor the automatic turn to its open view) but
    keeps the drift and the breathing; `camera=still` (any page) holds the view with no motion.
  - The camera tour is authored against the scene's own assembly, and each stop keeps its place in
    it: a stop before the build stays; a stop during the build comes when the film's build reaches
    the same progress, its `fly` scaled by the build's ratio (at most 3×, and at most 12 s unless the
    authored `fly` is longer); a stop after the build moves by as much as the assembly's end. A
    flight never runs into the next stop.
- **The features file** (`construct audio`, version 2): `{"format": "construct-audio", "version": 2,
  "fps", "frames", "scale", "energy": [...], "high": [...], "onset": [...], "voice": [...],
  "sections": [{"t", "strength"}], "range_db"}`, one value per frame, each 0..1, indexed by track
  time from the start of the page's clock. `energy` is the music's loudness (each track mapped to
  its own range, or a fixed -40..-10 dBFS window), `high` its brightness and attacks, `onset` the
  strongest attack in the frame (peak-picked rises in three bands, at least 0.2 s apart, relative
  to the track's strong attacks), `voice` a voice stem's level, and `sections` the moments (track
  seconds) where the music changes, from the novelty of its smoothed loudness and brightness, at
  least 10 s apart. Version 1 files (no `onset` or `sections`) still work: no accents and no
  staging.
- **The one fetch.** With `audio=`, the film script fetches that one file, a JSON document of
  numbers beside the page. It fetches nothing else, and a page without film mode fetches nothing.
- **Hosts with their own renderer** can read the same features. `film/construct-three.js` is an
  optional three.js loader that draws compiled geometry in a three.js scene and takes
  `build`, `time`, `energy`, `high` and `voice` every frame; its `makeBuildCurve` is the simpler
  `0.35 + 2.5·energy²` pace and does not stage sections or flare on onsets.

## Planned (not yet in the contract)

Terrain is in already, as the `terrain` shape and the `construct terrain` tool
([TERRAIN.md](docs/TERRAIN.md)). Still planned:

- `terrain` archetype: a heightfield or contour set with `scale.class` (`spot | site | valley |
  massif | range`) and `extent_m`, mapped to a stage size through a logarithmic scale ladder;
  provenance per surface, labelled **MEASURED** (supplied DEM/GPX) vs **SKETCHED** (inferred or
  decorative relief).
- `route`: a polyline draped on a terrain, traced as an articulation-like progress `u`; summit
  markers.
- Hierarchical periodic motion (a head that oscillates while its blades spin), found missing
  by the fresh-agent test.
