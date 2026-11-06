# Trace a reference image (for models that can see)

You are measuring a shape, not copying a picture. Look at the attached image — the user's own
photo, or an image you are viewing on the web — and answer with one JSON object:

```json
{"format": "construct-trace", "version": 1,
 "reference": {"id": "ref-front", "title": "who made the image, what it shows", "ref": "the URL, or user photo",
               "rights": "reference_only", "view": "front"},
 "image": {"width": 1200, "height": 1600},
 "outline": [[x, y], [x, y], ...],
 "features": {"name": [x, y]}}
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
