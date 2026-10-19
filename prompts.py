"""The authoring package for any model: prompts and a parameter schema, generated from the
toolkit's own tables so they never drift from the validator.

    python3 -m hologram.prompts --out prompts/      (or: cli.py prompts --out prompts/)

Files:
  system.md          rules every author follows (any model, any host)
  params.md          the simple path: fill a parameter document (recommended for small models)
  scene.md           the full path: write a scene (capable models)
  repair.md          the loop a host or runner drives: check, send the repair text, retry
  params.schema.json JSON Schema of a parameter document, for hosts that can constrain output
"""

import json
from pathlib import Path

from . import params as params_mod
from . import scene as scene_mod

HERE = Path(__file__).resolve().parent
CONTRACT = "tessera.hologram/0.2"

SYSTEM = """# Hologram authoring rules ({contract})

You describe one physical object (or a fictional one) so a renderer can draw it as a hologram.
You write data, never code.

1. Answer with exactly one JSON object: no prose, no comments, no code fences.
2. Describe what the object is: its parts, real sizes in metres (Y up, the front faces +Z),
   and facts. Never describe how it looks: no colours, materials, glow, effects, fonts or
   camera code. The renderer owns the look, so every entry matches the others on the shelf.
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
also `style`; guitars and synths `maker` and `model`. Other facts are kept as evidence.

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
{{"format": "tessera-hologram", "version": 2, "id": "lowercase-id", "title": "Name",
 "subject": {{"category": "object", "accuracy": "generic", "synthetic": false, "summary": "one sentence"}},
 "units": "m", "seed": 7,
 "sources": [{{"id": "request", "kind": "user_request", "title": "The request", "rights": "user_private"}}],
 "facts": [{{"key": "height", "value": 0.42, "unit": "m", "certainty": "inferred", "note": "typical"}}],
 "parts": [], "articulations": [], "labels": [], "anchors": {{}}}}
```

Parts: `{{"id", "role", "certainty", "stage" (0..7, foundation first), "shape", "at" [x,y,z],
"rotate" [deg x,y,z], "basis" [fact keys], "repeat", "mirror", "floating", "artwork"}}`.

- Roles: {roles}. Two or three `identity` parts are what make it recognisable.
- Shapes ({shapes}):
  box `size [w,h,d]` (`anchor: base` stands it on `at`); cylinder `radius, height` (base at
  `at`, along +Y); cone `radius_bottom, radius_top, height`; sphere `radius` or `radii`;
  torus `major, minor`; lathe `profile [[radius, y], ...]` (turned forms); extrude
  `profile [[u, v], ...], height, axis y|z|x` (plans, elevations); tube `path [[x,y,z],...],
  radius` (limbs, cables); curve `points`; plane `size [w,h]` facing +Z; grid; points; marker.
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

Work in this order: the overall size and silhouette (`mass`), the structure, the
identity features, then a little detail. Fewer, truer parts beat many guesses.

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
3. If `ok` is false, send `repair_text` back as the next user message and check again.
   Stop after 4 rounds; if a full scene still fails, ask the same model for the parameter
   document instead (`params.md`), which almost always validates.
4. When `ok` is true: `build` (geometry, preview, audit) and, if a browser is available,
   `review` for images a person or a vision model can judge. Warnings are allowed; pass them
   on with the proposal.

Codes a model will meet: json, duplicate-key, unknown-key, missing-key, type, range,
choice, id, reference, certainty, unknown-fact, style, path, budget, floating,
stage-order, overclaim, accuracy, decorative-identity, no-mass, no-identity, clutter,
duplicates, tiny, invisible.

A host that supports constrained output can hold a small model to `params.schema.json`.
No step needs an API key from this toolkit; the model and its key live in the host.
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
        "$id": "tessera.hologram/0.2/params.schema.json",
        "title": "Hologram parameter document (tessera-hologram-params v1)",
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
        },
        "x-variants": variants,
    }


def build():
    """Every file of the package, as {name: text}."""
    golden = json.loads((HERE / "examples" / "v2" / "case-jewel.params.json").read_text())
    scene_example = json.loads((HERE / "examples" / "v2" / "book.json").read_text())
    template = params_mod.template("book", "paperback")
    return {
        "system.md": SYSTEM.format(contract=CONTRACT),
        "params.md": PARAMS_INTRO.format(template=json.dumps(template, indent=2), describe=params_mod.describe(),
                                         example=json.dumps(golden, indent=2, ensure_ascii=False)),
        "scene.md": SCENE_INTRO.format(roles=", ".join(scene_mod.ROLES), shapes=", ".join(scene_mod.SHAPE_TYPES),
                                       example=json.dumps(scene_example, indent=1, ensure_ascii=False)),
        "repair.md": REPAIR,
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
