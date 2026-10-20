"""The authoring package for any model: prompts and a parameter schema, generated from the
toolkit's own tables so they never drift from the validator.

    python3 cli.py prompts --out prompts/

Files:
  system.md          rules every author follows (any model, any host)
  params.md          the simple path: fill a parameter document (recommended for small models)
  scene.md           the full path: write a scene (capable models)
  repair.md          the loop a host or runner drives: check, send the repair text, retry
  vision-review.md   an optional self-review of the renders for models that can see images
  trace.md           the vision step that traces a shape from a reference image (construct trace)
  params.schema.json JSON Schema of a parameter document, for hosts that can constrain output
"""

import json
from pathlib import Path

from . import params as params_mod
from . import product
from . import scene as scene_mod
from . import tiers

HERE = Path(__file__).resolve().parent
CONTRACT = product.CONTRACT

SYSTEM = """# Construct authoring rules ({contract})

You describe one physical object (or a fictional one) so a renderer can draw it as a holographic construct.
You write data, never code.

1. Answer with exactly one JSON object: no prose, no comments, no code fences.
2. Describe what the object is: its parts, real sizes in metres (Y up, the front faces +Z),
   and facts. Never describe how it looks: no colours, materials, glow, effects, fonts or
   camera code. The renderer owns the look, so every entry matches the others on the shelf.
   Appearance words in a request ("glowing", "mossy", "red") become facts or roles, not
   colours: a fact `{{"key": "lantern", "value": "glowing", ...}}`, a light as role `data`.
3. Every fact has a certainty:
   - "verified": a cited source says so (give its "source" id);
   - "user_supplied": the user said or gave it;
   - "inferred": your reasoned estimate (add a short "note" with the reason);
   - "decorative": chosen only for the picture.
4. Unknown stays unknown. If you do not know a value (a year, an edition, a size, a name),
   leave that fact out entirely. Never write null, "unknown" or a plausible guess.
5. Words on the object (titles, spines, label text) come only from facts. If the fact is
   absent, there is no text.
6. Images come only from files the user supplied, by their asset id and a named slot.
   Never invent or describe artwork as if it were the real one.
7. If you get back a list of problems, fix every one and send the whole corrected object
   again. Each problem names a JSON path and says what to write instead.

## Research (optional; the request decides)

- A generic subject ("a watch", "a desk lamp", "a fictional moss snail"): no research. Build
  a typical, well-proportioned example from general knowledge: `subject.accuracy` "generic",
  facts `inferred` or `decorative`; record `"research": "not_needed"`.
- A concrete, named subject (a brand and model, a named place or building, a species, a
  specific artwork or vehicle): when you are unsure of its identity-defining shape or specs
  and the host gives you web search, research it first: the official or maker's pages,
  manuals, specs and plans, and reference photos. Look at the references (any model that
  can see images: Claude, GPT, Gemini, DeepSeek...) and measure silhouette and proportions;
  trace the identity shape (`trace.md`). Each value is then documented (`verified`, citing
  the source), traced (`inferred`, citing the reference image) or invented (`inferred` with
  a note, or `decorative`). Only then write parts. Record `"research": "done"` and the ids of
  the sources you used.
- Confident without looking: record `"skipped"`. Nothing can be `verified` without a cited
  source, so facts are `inferred` and accuracy is `approximate` at most.
- No web tool in the host: record `"unavailable"`, mark accuracy honestly, and list in
  `next` what research would improve.
- The user overrides either way ("research: on" / "research: off"); "off" is recorded as
  `"off"`.

## Effort: aim for genuinely good, always within the tier's limits

{tiers}

{clock}

Work silhouette, then proportions, then the two or three identity features, then secondary
detail. Put effort where it shows: nothing smaller than about 0.5% of the object's largest
size. Stop at whichever comes first: the review judges the construct genuinely good (accurate
and beautiful: something you would put in a launch video), or any limit of the tier is
reached. Then deliver the best version so far. The host and user pick the tier (default
standard) and may override single limits; hosts add hard limits of their own on top.

For a named subject, turn research into an identity checklist before the first part: the
features that make it itself (a Countach: the low wedge, NACA ducts, the periscope roof
channel, trapezoid wheel arches, scissor doors), each later mapped to the parts that build it
(`authoring.identity`). An independent critic checks every item.

Only an independent critic (a fresh context: `critic.md`) can call a construct "good" or
"outstanding"; your own review records "self-reviewed". The masterpiece tier, on explicit
request for hard subjects, has no time or round cap: improve the critic's top defects round
after round, saving a checkpoint each time, until the critic scores every criterion 3.

Record how it was made, in the scene (or parameter document):
`"authoring": {{"tier": "standard", "research": "done", "sources": ["maker-specs", "ref-front"],
"identity": [{{"feature": "periscope roof channel", "parts": ["roof-channel"], "source": "ref-top"}}],
"next": ["what the next improvement would be"]}}` — `research` is one of {research}; `sources`
are ids from the scene's sources; `next` lists, most valuable first, what you would improve
with more time.
"""

PARAMS_INTRO = """# The simple path: a parameter document

Fill this document for the object; a builder draws it. Choose the archetype and variant
that match, copy the user's facts with their certainty, and leave `params` empty unless the
user gave sizes (then give them in metres and say how certain they are in `param_certainty`).

```json
{template}
```

Archetypes, variants, standard sizes and artwork slots:

{describe}

Fact keys the builder sets as text when they exist: `title`, and the first of
`artist`, `author`, `creator`, `composer`, `brewery`, `maker` (the creator line); vessels
also `style`; guitars and synths `maker` and `model`. A missing fact simply has no line
(no author known: no author line). Other facts are kept as evidence:
use plain keys such as `year`, `label`, `publisher`, `abv` (with `"unit": "%"`), `volume`
(with `"unit": "ml"`), `discs`.

`params` stays empty (`{{}}`) unless the user gave a size or the item differs from the
standard: then give only what differs, in metres, and say in `param_certainty` whether the
user gave it (`user_supplied`) or you derived it (`inferred`). Common sizes: cans of 330 ml
are 0.115 m tall, 440 ml 0.147 m, 500 ml 0.168 m (all 0.066 m wide); a 500 ml bottle is
about 0.25 m tall; a hardcover is about 0.16 x 0.24 m, a mass-market paperback 0.11 x 0.18 m.
Leave out `sources`: a `request` source is added for you. Example of a stated size:
`"params": {{"height": 0.147}}, "param_certainty": {{"height": "inferred"}}` (a 440 ml can).
`"synthetic": false` for real requests; `true` only for examples and tests.

`artwork` maps a slot to the id of an asset in `assets` (only images the user supplied:
`{{"id", "path", "sha256", "media_type", "rights", "provenance", "source"}}`). Leave a slot out
when there is no image; the renderer shows its designed face.

A complete example (synthetic):

```json
{example}
```
"""

SCENE_INTRO = """# The full path: a scene

Use this when no archetype fits. A scene lists facts and parts built from a closed set
of shapes; the compiler checks everything.

Skeleton:

```json
{{"format": "construct-scene", "version": 2, "id": "lowercase-id", "title": "Name",
 "subject": {{"category": "object", "accuracy": "generic", "synthetic": false, "summary": "one sentence"}},
 "units": "m", "seed": 7,
 "sources": [{{"id": "request", "kind": "user_request", "title": "The request", "rights": "user_private"}}],
 "facts": [{{"key": "height", "value": 0.42, "unit": "m", "certainty": "inferred", "note": "typical"}}],
 "parts": [], "articulations": [], "labels": [], "anchors": {{}}}}
```

`subject.category`: {categories}. `subject.accuracy`: `generic` (a typical example;
the usual choice), `approximate` (this particular thing, imprecisely) or `documented`
(its key parts cite evidence). A fictional subject is category `fictional`.

Parts: `{{"id", "role", "certainty", "stage" (0..7), "shape", "at" [x,y,z],
"rotate" [deg x,y,z], "basis" [fact keys], "repeat", "mirror", "floating", "artwork"}}`.
Stages build from what holds things up: legs and feet before the body that rests on them,
walls before roofs, a base before an arm. Parts that hover (a halo, a beam) are `floating`.
A part the user named but whose size you chose is `inferred` (cite the user's fact in
`basis`). To take a shape from a picture, trace it: `trace.md` gives the measuring step and
`construct trace` fits the outline to a documented dimension. A spec page verifies dimensions (a scale length, a height), never a shape: an outline,
profile or path is `inferred` — or traced from a reference image (`construct trace`) — unless a
cited drawing, measurement or dataset gives its coordinates; the parts of a fictional design are `inferred` too (designed from the request).
`decorative` is only for atmosphere. The request source is `"rights": "user_private"`
(`"synthetic"` only for examples and tests).

- Roles: {roles}. Two or three `identity` parts are what make it recognisable.
- Default orientations: cylinders, cones, lathes and tori stand on `at` around the +Y axis
  (a torus lies flat); boxes and spheres are centred on `at`; a plane faces +Z; a tube
  follows its path. Keep detail parts to under half of the lines.
- Shapes ({shapes}):
  box `size [w,h,d]` (centred on `at`; `anchor: base` stands it on `at`); cylinder `radius,
  height` (its base is at `at`, it rises along +Y); cone `radius_bottom, radius_top, height`
  (a lampshade is wider at the bottom; tilt any part with `rotate`, degrees about X, then Y,
  then Z); sphere `radius` or `radii`;
  torus `major, minor`; lathe `profile [[radius, y], ...]` (turned forms); extrude
  `profile [[u, v], ...], height, axis y|z|x` (plans, elevations); loft `sections [[z,
  half_width, y_bottom, y_top(, half_width_top)], ...]` back to front along +Z, `round` 0..1
  (car bodies, glasshouses, hulls: plan and side profile together); tube `path [[x,y,z],...],
  radius` (limbs, cables); curve `points`; plane `size [w,h]` facing +Z; grid; points; marker;
  architecture kit (each stands on y = 0): tower `radius, height, sides (0 round), roof
  cone|pyramid|spire|onion|flat|none, roof_height, taper, profile straight|parabolic, eave,
  windows [rows, per_row]`; roof
  `size [w,d], height, style gable|hip, ridge x|z, overhang, courses`; dormer `width, height,
  depth`; facade `size [w,h], rows, cols, arch round|pointed|flat|none, kind windows|arcade`
  (a wall facing +Z; `outline: false` on a box face); battlements `radius` or `path [[x,z],...],
  height, merlon, gap, thickness`; buttress `width, depth, height, steps`; shell `span,
  height, reach, bulge, ribs` (a ribbed sail rising back from a base edge: concert-hall roofs);
  terrain `size [w,d], heights [[...rows back to front...]]` — real relief comes from
  `construct terrain` and elevation data (MEASURED TERRAIN, verified); a small hand-made grid
  is `inferred` (SKETCHED TERRAIN).
- Copies: `"repeat": {{"count": n, "step": {{"at": [dx,dy,dz]}}}}` or
  `{{"count": n, "radial": {{"axis": "y", "center": [x,y,z]}}}}`; `"mirror": "x"`.
- Everything rests on something (the ground, another part) unless `"floating": true`.
- Opening once: `articulations: [{{"id", "type": hinge|slide|lift|turn, "parts", "axis",
  "pivot" (hinge/turn), "amount" (degrees or metres), "order"}}]`, values in the closed pose.
- Text from facts: `labels: [{{"id", "part", "face" (box: front back left right top bottom),
  "field": fact key, "role": title|creator|meta, "orientation": horizontal|vertical-down,
  "region": [u0, v0, u1, v1]}}]`.
- Images: on a part, `"artwork": {{"slot": "cover-front", "asset": "id", "mask": "rect"}}`.
- Shelving: `"anchors": {{"front": {{"part", "face"}}, "spine": {{"part", "face"}}}}`.
- Budgets: 256 parts, 24,000 lines, 24,000 triangles, 32 moving copies.

Vehicles are never a box, and never an outline of thin tubes (they render as wire, not a
body): trace the side silhouette and the plan outline first (from references for a named
model), loft the body through them with a narrow, rounded nose, a narrower glasshouse,
wheels on the ground in arches; then smooth section `curve`s across the body at the main
stations and along the arch lips. Or start from the `vehicle` archetype (wedge, coupe, sedan).

Work in this order: the overall size and silhouette (`mass`), the structure, the
identity features, then a little detail. Fewer, truer parts beat many guesses.
Connecting parts (an arm, a handle, a stem, a leg) must read clearly next to the big
volumes: give them a real radius (about 1.5% of the object or more) and the `identity`
role when they carry the silhouette; end them inside the part they join.

Leave out `presentation` and `animation` (the host owns camera, colour and timing), except
`presentation.views` (never `style_hint`: colour is the renderer's, one house palette for
everyone): give a view named `"open"` (yaw, pitch in degrees) when the object
opens, so a host can turn to what opening reveals. `look` only to hide a part that just
carries text (`{{"line": "none", "fill": "none"}}`).

An example (synthetic):

```json
{example}
```
"""

REPAIR = """# The check-and-repair loop (for hosts and runners)

1. Send `system.md`, then `params.md` (small models) or `scene.md` (capable models), then
   the user's request with any facts and supplied images.
2. Check the answer: `python3 cli.py check draft.json --json` (or `diagnose.diagnose_text`).
   The report: `ok`, `errors`, `warnings`, `diagnostics[]` (`severity, code, path, message,
   hint`) and `repair_text`.
3. While `needs_repair` is true (errors, or a part that is detached or a hairline), send
   `repair_text` back as the next user message and check again.
   Stop at the tier's check rounds; if a full scene still fails, ask the same model for the parameter
   document instead (`params.md`), which almost always validates.
4. When `ok` is true: `build` (geometry, preview, audit) and, if a browser is available,
   `review` for images a person or a vision model can judge. Other warnings are allowed;
   pass them on with the proposal.
5. For models that can see images: send `vision-review.md` with `review/hero.png`,
   `sheet-views.png`, `sheet-assembly.png` (and `view-open.png` when it opens) and the
   original request. While the verdict is "improve", ask for the fix to the weakest point,
   check it again, and review again.
6. Every loop is bounded by the effort tier (`system.md`): check rounds, review rounds and
   wall clock, plus any token or cost ceiling the host sets. Stop at whichever comes first,
   the verdict "good" or a limit, and deliver the best draft so far with its `authoring`
   record (`tier`, `outcome`, `next`). `construct author --tier ... --vision` runs exactly this.

Codes a model will meet: json, duplicate-key, unknown-key, missing-key, type, range,
choice, id, reference, certainty, unknown-fact, style, path, budget, floating,
stage-order, overclaim, accuracy, decorative-identity, no-mass, no-identity, clutter,
duplicates, tiny, invisible, no-open-view, detached, thin, shape-overclaim, research,\ntier-budget, authoring.

A host that supports constrained output can hold a small model to `params.schema.json`.
No step needs an API key from this toolkit; the model and its key live in the host.
"""


VISION = """# Art-direction review of your construct (for models that can see images)

Here are the renders of your construct: `hero.png` (the finished object), `sheet-views.png`
(hero, front, side, back, top, three-quarter), `sheet-assembly.png` (how it builds) and, when
it opens, `view-open.png`. Judge the pictures against the request and your references, not
the JSON. The question is not "is it recognisable?" but "is it genuinely good: accurate and
beautiful, something you would put in a launch video?"

Score each criterion 0-3 (0 missing, 1 weak, 2 good, 3 striking):

- `silhouette`: it reads instantly as this thing, from the hero and in every view;
- `proportions`: right against the facts and references (heights, widths, spacing);
- `identity`: the two or three identity features are rendered with care, in proportion;
- `depth`: masses, structure, detail and ornament layer clearly; nothing equally loud;
- `composition`: strong hero framing, nothing cut off, good use of the frame;
- `assembly`: the build order tells the object's story (foundations first, the reveal last);
- `motion`: articulations and idle life bring it alive without noise (judge from the
  assembly sheet and what moves);
- `density`: rich detail that never clutters; no hairlines, nothing hovering or poking through;
- `honesty`: labels come only from facts; inferred and decorative parts look it.

Answer with one JSON object:

```json
{{"verdict": "good", "scores": {{"silhouette": 3, "proportions": 2, "identity": 2, "depth": 2,
 "composition": 3, "assembly": 2, "motion": 2, "density": 2, "honesty": 3}},
 "weakest": "the criterion to improve first",
 "fix": "the concrete change to the scene that improves it most",
 "next": ["further improvements, most valuable first"]}}
```

`verdict` is "good" only when every score is 2 or more and you would show it as it is;
otherwise "improve". Be a demanding art director: a construct that is merely correct is not
yet good. You will then be asked to apply the fix and send the whole corrected scene.
"""


CRITIC = """# Independent critique of a construct

You are an independent critic with fresh eyes. You did not make this construct, and you owe
its author nothing but an exact account. You get the request, the identity checklist written
from research, reference photos of the real subject, and renders of the construct taken from
the same views. Judge the construct against the real thing, view by view: put each reference
beside its render and measure (length to height, wheelbase to length, where the roofline
peaks, tower heights against each other, how far the nose narrows).

Score each criterion 0-3:

- 3 outstanding: someone who knows the subject names it exactly at a glance; silhouette and
  proportions match the reference within a few percent; finished, polished, impressive,
  exhibition quality. Rare: most first versions are 1 or 2.
- 2 good: clearly right; deviations show only beside the reference.
- 1 weak: the right kind of thing, wrong in ways an owner notices at once (boxy where it is
  curved, missing towers, a rectangle where the nose tapers).
- 0 missing or wrong.

Criteria: `silhouette`, `proportions`, `identity` (the checklist features, rendered with
care), `depth` (masses, structure, detail and ornament layered), `composition` (hero framing),
`assembly` (the build tells the story), `motion` (alive without noise), `density` (rich, never
cluttered), `honesty` (labels from facts; inferred parts look it).

Answer with one JSON object, no prose:

```json
{{"format": "construct-critique", "version": 1, "scene_sha256": "copy it from the packet",
 "scores": {{"silhouette": 1, "proportions": 1, "identity": 2, "depth": 2, "composition": 2, "assembly": 2,
            "motion": 2, "density": 1, "honesty": 3}},
 "checklist": [{{"feature": "as listed", "present": true, "quality": 2, "comment": "what is right or wrong"}}],
 "defects": [{{"rank": 1, "severity": "critical", "criterion": "proportions", "parts": ["body"], "view": "side",
              "problem": "what is wrong, measured against the reference",
              "fix": "the concrete change to the scene: which part, which shape, which numbers"}}],
 "verdict": "improve"}}
```

- `checklist`: every listed feature, plus any feature of the real subject you find missing.
- `defects`: ranked by how much they cost the likeness, most severe first; `critical` (the
  subject is not recognisable because of it), `major` (an owner would notice), `minor`.
- `verdict`: "outstanding" only when every score is 3 and nothing critical or major remains;
  "good" when every score is at least 2 and nothing is critical; otherwise "improve". It is
  recomputed from your scores, so score honestly rather than kindly.
"""


TRACE = """# Trace a reference image (for models that can see)

You are measuring a shape, not copying a picture. Look at the attached image — the user's own
photo, or an image you are viewing on the web — and answer with one JSON object:

```json
{{"format": "construct-trace", "version": 1,
 "reference": {{"id": "ref-front", "title": "who made the image, what it shows", "ref": "the URL, or user photo",
               "rights": "reference_only", "view": "front"}},
 "image": {{"width": 1200, "height": 1600}},
 "outline": [[x, y], [x, y], ...],
 "features": {{"name": [x, y]}}}}
```

- `image`: the image's size in pixels as you see it; every point is in those pixels, x to the
  right, y down.
- `outline`: the silhouette edge of the one thing you were asked to trace, once around, 40 to
  120 points, denser where the edge curves (horns, cutaways, waists). Only the outer edge: no
  holes, no inner details, no shadow or background.
- `features`: the named points you were asked for (for example a guitar's `nut`, `bridge`,
  `neck-joint`), each where its centre is.
- `reference.rights`: `user_private` when the user gave you their own photo, otherwise
  `reference_only` — the image is looked at, never kept or reproduced.
- Never transcribe logos, text, colours or artwork from the image.

The outline is then scaled to a documented dimension (`construct trace --fit nut:bridge=0.648`)
and becomes `inferred` geometry cited to this image.
"""


def params_schema():
    """JSON Schema of a parameter document (structure; the validator checks the rest)."""
    slots = sorted({s for v in params_mod.VARIANTS.values() for (_, _, ss, _) in v.values() for s in ss})
    props = {}
    for k, (lo, hi, integer, help_) in params_mod.PARAMS.items():
        props[k] = {"type": "integer" if integer else "number", "minimum": lo, "maximum": hi, "description": help_}
    for k, options in params_mod.CHOICES.items():
        props[k] = {"enum": list(options)} if not all(isinstance(o, bool) for o in options) else {"type": "boolean"}
    cert = {"enum": ["verified", "user_supplied", "inferred", "decorative"]}
    variants = {a: sorted(v) for a, v in params_mod.VARIANTS.items()}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "construct/0.2/params.schema.json",
        "title": "Construct parameter document (construct-params v1)",
        "type": "object", "additionalProperties": False,
        "required": ["format", "version", "archetype", "variant", "id", "title", "facts"],
        "properties": {
            "format": {"const": params_mod.FORMAT}, "version": {"const": params_mod.VERSION},
            "archetype": {"enum": sorted(variants)},
            "variant": {"enum": sorted({v for vs in variants.values() for v in vs})},
            "id": {"type": "string", "pattern": "^[a-z0-9][a-z0-9._-]{0,63}$"},
            "title": {"type": "string", "minLength": 1, "maxLength": 200},
            "summary": {"type": "string", "maxLength": 600},
            "synthetic": {"type": "boolean"},
            "sources": {"type": "array", "maxItems": 64, "items": {
                "type": "object", "additionalProperties": False, "required": ["id", "kind", "title", "rights"],
                "properties": {"id": {"type": "string"}, "kind": {"enum": list(scene_mod.SOURCE_KINDS)},
                               "title": {"type": "string"}, "rights": {"enum": list(scene_mod.SOURCE_RIGHTS)},
                               "ref": {"type": "string"}}}},
            "facts": {"type": "array", "maxItems": 160, "items": {
                "type": "object", "additionalProperties": False, "required": ["key", "value", "certainty"],
                "properties": {"key": {"type": "string", "maxLength": 120},
                               "value": {"type": ["string", "number", "boolean"]},
                               "unit": {"type": "string", "maxLength": 24}, "certainty": cert,
                               "source": {"type": "string"}, "note": {"type": "string", "maxLength": 600}}}},
            "assets": {"type": "array", "maxItems": 32, "items": {
                "type": "object", "additionalProperties": False,
                "required": ["id", "path", "sha256", "media_type", "rights", "provenance"],
                "properties": {"id": {"type": "string"}, "path": {"type": "string"},
                               "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                               "media_type": {"enum": list(scene_mod.MEDIA_TYPES)},
                               "rights": {"enum": list(scene_mod.ASSET_RIGHTS)},
                               "provenance": {"enum": list(scene_mod.ASSET_PROVENANCE)}, "source": {"type": "string"}}}},
            "artwork": {"type": "object", "additionalProperties": False,
                        "properties": {s: {"type": "string"} for s in slots}},
            "params": {"type": "object", "additionalProperties": False, "properties": props},
            "param_certainty": {"type": "object", "additionalProperties": {"enum": ["verified", "user_supplied", "inferred"]}},
            "authoring": tiers.authoring_schema(),
        },
        "x-variants": variants,
    }


def build():
    """Every file of the package, as {name: text}."""
    golden = json.loads((HERE / "examples" / "v2" / "case-jewel.params.json").read_text())
    scene_example = json.loads((HERE / "examples" / "v2" / "book.json").read_text())
    # the example shows what an author writes: no host-owned presentation or timing
    scene_example["presentation"] = {"views": scene_example["presentation"]["views"]}
    scene_example.pop("animation", None)
    template = params_mod.template("book", "paperback")
    return {
        "system.md": SYSTEM.format(contract=CONTRACT, tiers=tiers.table(), clock=tiers.clock_rule(),
                                   research=", ".join('"%s"' % r for r in tiers.RESEARCH_RECORD)),
        "params.md": PARAMS_INTRO.format(template=json.dumps(template, indent=2), describe=params_mod.describe(),
                                         example=json.dumps(golden, indent=2, ensure_ascii=False)),
        "scene.md": SCENE_INTRO.format(roles=", ".join(scene_mod.ROLES), shapes=", ".join(scene_mod.SHAPE_TYPES),
                                       categories=", ".join(scene_mod.CATEGORIES),
                                       example=json.dumps(scene_example, indent=1, ensure_ascii=False)),
        "repair.md": REPAIR,
        "vision-review.md": VISION.format(),
        "trace.md": TRACE.format(),
        "critic.md": CRITIC.format(),
        "params.schema.json": json.dumps(params_schema(), indent=1) + "\n",
    }


def write(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for name, text in build().items():
        (out / name).write_text(text, encoding="utf-8")
    return sorted(build())


if __name__ == "__main__":
    import sys
    target = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else str(HERE / "prompts")
    for name in write(target):
        print(name)
