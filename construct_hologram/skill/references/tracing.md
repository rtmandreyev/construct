# Likeness from references: tracing

Spec pages give dimensions; they never give a shape. When a thing's identity is its outline (a
guitar body, a car's profile, a building's elevation, a bottle), measure the shape from a
picture instead of inventing it — and never copy the picture.

## The steps

1. **Find a reference.** Best: the user's own photo (rights-clean for their collection).
   Otherwise an image you can view on the web (the maker's product photo, a straight-on view),
   found during research ([effort](effort.md)) and counted against the tier's reference images.
   You look at it; you never download it into the scene, embed it or reproduce it.
2. **Trace it** (any model that can see images). Follow `prompts/trace.md`: answer a
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

## Bodies from three views (cars, hulls, fuselages)

A car is recognisable by its exact silhouette from the side and from above, and by how its
cabin narrows towards the roof. Trace all three, then loft through them:

1. Trace the **side** (nose left or right: note which), the **top** (plan; nose up or down)
   and, if you can, the **front**: one `construct-trace` each, the whole outline including
   the cabin.
2. `python3 TOOLS loft-from-traces --side side.json --top top.json --front front.json
   --length 4.14 --height 1.07 --width 1.89 --nose-side left --nose-top up --out body.json`
   reconciles them into 24 loft stations (crowded at the nose and tail): bottoms and tops
   from the side, half-widths from the plan, and from the front how wide the body still is
   at each station's top, so the cabin narrows and the bonnet stays wide. It reports the
   traced height and width against the documented ones; a mismatch over a few percent means
   a trace is off.
3. Put it into a scene: `--into car.json --part body --drop glasshouse` (the traced side
   already includes the cabin). Start from `params vehicle` for the wheels, arches and
   lights, then move the wheels to the traced wheelbase.
4. Add the identity features on top (ducts, the roof channel, door lines) as curves and thin
   parts on the body.

## Measure the likeness

`python3 TOOLS compare car.json --trace side.json --view side --overlay side.png` projects the
construct's silhouette from the view (from the geometry, no browser) and measures it against
the traced outline: IoU (1 = identical) and how far apart the outlines are, as a share of the
view's width. Vehicles need IoU 0.88 and outlines within 1.2%; landmark buildings 0.82 and 2%.
A trace may face any way: a plan tries every quarter turn and mirror, and the result says which
was used and warns when a trace was drawn across the view (draw plans nose-up, sides nose-left).
Tyres count as solid discs, and ornament (a shadow ring, motes) is left out of the silhouette.
The overlay shows the reference amber, the construct violet, both white: fix where the colours
show. `--record` writes the result into `authoring.compare` (bound to the scene's hash). An
outstanding vehicle or landmark needs a passing comparison: the critic's "outstanding" is held
at "good" without one.

## Enabling vision in hosts

Tracing works with any model that can see images: Claude, GPT, Gemini and DeepSeek among them.

- **Hermes:** with the vision toolset enabled, attach the photo (`/paste`, or an image path)
  or let the agent call `vision_analyze` on the image, with the `trace.md` instructions as its
  question. Both DeepSeek and GPT models describe and trace images this way.
- **Claude Code:** the agent reads image files directly; put the user's photo in the working
  folder.
- **Any OpenAI-compatible vision model:** `construct trace-image photo.jpg --what "the guitar
  body outline, front view" --features nut,bridge --fit nut:bridge=0.648 --base-url ...
  --model ... --key-env ... --out body.json` (local photos are sent as data; https images by URL,
  viewed and not kept). `construct author --reference photo.jpg ...` attaches references to a
  whole draft.
