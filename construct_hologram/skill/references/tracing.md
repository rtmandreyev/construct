# Likeness from references: tracing

Spec pages give dimensions; they never give a shape. When a thing's identity is its outline (a
guitar body, a car's profile, a building's elevation, a bottle), measure the shape from a
picture instead of inventing it — and never copy the picture.

## The steps

1. **Find a reference.** Best: the user's own photo (rights-clean for their collection).
   Otherwise an image you can view on the web (the maker's product photo, a straight-on view).
   You look at it; you never download it into the scene, embed it or reproduce it.
2. **Trace it** (you need to see images). Follow `prompts/trace.md`: answer a
   `construct-trace` JSON with the image's pixel size, the silhouette as 40–120 points (pixels,
   y down) and the named features you need (`nut`, `bridge`, `neck-joint`; `roof-ridge`;
   `wheel-front`...). Check it: `check trace.json` reports a self-crossing or too-short outline.
3. **Fit it to a documented dimension:**

   ```bash
   python3 TOOLS trace trace.json --fit nut:bridge=0.648 --out body.json
   ```

   `--fit` takes the distance between two traced features (best: a verified spec such as a scale
   length), or `height=` / `width=` of the outline. `--origin bottom-center` (default), `center`
   or `feature:<name>`.
4. **Use it.** `body.json` holds an `extrude` profile in metres (front elevation, axis `z`), the
   features in metres (place pickups, the bridge, horns from them), a `source` of kind
   `reference_image` to add to the scene's sources, and a `part` stub: certainty `inferred`,
   cited to the image, with a note. The dimension facts stay `verified`; the traced shape is
   `inferred` — measured, not documented (the audit's `shape-overclaim` keeps it honest).
5. **Look again.** Review the construct against the reference.

## Enabling vision in hosts

- **Hermes:** use a vision-capable main model (GPT-6.1 Sol, Claude, Gemini; DeepSeek-flash is
  text-only) and attach the photo (`/paste`, or an image path), or let the agent call
  `vision_analyze` on the image file with the `trace.md` instructions as its question (set
  `auxiliary.vision` to a capable model).
- **Claude Code:** the agent reads image files directly; put the user's photo in the working
  folder.
- **Any OpenAI-compatible vision model:** `construct trace-image photo.jpg --what "the guitar
  body outline, front view" --features nut,bridge --fit nut:bridge=0.648 --base-url ...
  --model ... --key-env ... --out body.json` (local photos are sent as data; https images by URL,
  viewed and not kept). `construct author --reference photo.jpg ...` attaches references to a
  whole draft.
