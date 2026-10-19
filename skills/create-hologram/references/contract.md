# Construction contract v1

Use the complete schema/examples shipped two levels above the skill directory.
Root fields: `format: tessera-hologram`, `version: 1`, slug `id`, `title`,
`kind` (cd/book/structure/custom), integer `seed`, `units: m`, `facts`, `parts`,
`assets`, `motion`. Seed is reserved; current geometry generation has no randomness.

Facts: `{key, value, certainty, source}`; value is scalar JSON, not a nested object.
Certainties: verified, user_supplied, inferred, decorative. Verified requires a
nonblank source. Do not pass speculative dimensions as verified facts.

Parts: `{id, shape, position, size, rotation, tone, certainty, stage}` with optional
`source`, optional `artwork_asset_id`, and `points` for polyline only.
Positions use metres; rotations are Euler degrees, applied X then Y then Z;
translation follows rotation. Axes: X right, Y up, Z toward the object's front.
Box size is full X/Y/Z dimensions. Disc and ring size is
`[outer_radius, inner_radius, thickness]`, with inner radius below outer radius;
they lie in XY and are extruded along Z. Polylines use a positive XYZ size as a
scale applied to their local `points`, followed by rotation and translation.

Tones: accent, bright, structure, dust, identity, faint. Stages: integers 0–5.
The host owns the palette; construction sheets cannot execute custom shaders.
Artwork is supported only on a box front (+Z face). Declare matching `assets`
entries `{id,path,sha256,media_type,rights}`. PNG/JPEG/WebP supported declarations;
paths must stay relative and inside a user-selected root; no symlinks/traversal/URLs.

Motion: `{assembly_ms, ambient, strength}` with assembly 0–5000 ms, ambient
off/scan/breathe, strength 0–1. These are renderer hints; the study currently uses
its own fixed assembly sequence, so full hint fidelity is not implemented.

Compiled `tessera-geometry` v1 contains segments, bounds, source sheet hash,
fact/part provenance, asset declarations and artwork UV quads. Geometry positions
remain metres; atlas placement/scaling is a separate host concern. A renderable
study scene wraps these objects in user-region data. This is a versioned prototype
contract, not a general mesh interchange format or a faithful universal reconstruction.
