# Animation semantics

Everything is a pure function of time `t` and the scene's hash: any frame can be
reproduced (`hologram.html?t=12.5`). The page also honours the reduced-motion preference.

## Assembly (staged construction)

The hologram is *constructed*, not faded in. Each part's `stage` (0–7) orders the build;
within a stage lines grow bottom-up, each with a bright moving tip.

- `ceremony`: the whole object appears as a faint, unstable ghost (signal acquired), collapses,
  is rebuilt stage by stage over `seconds`, then stabilises with a short glow. For the
  first presentation of something important.
- `build`: only the staged build and a short settle. For quick previews and many objects.
- `cut`: complete at once.

Stage rules: foundation and ground first; then the primary mass; then structure and roof;
landmarks and identity; detail; light, data and decorative effects last. Nothing should
appear before what holds it up (the audit warns: `stage-order`).

## Articulations (opening once)

After assembly the object opens, one `order` group after another, and holds: a lid hinges
open, a booklet slides out, a disc lifts and turns once, a book's board opens to the title
page. Use articulations for anything that opens or is taken out; a host drives them with
an opening from 0 to 1 and owns the timing. `?open=0` / `?open=1` freezes a pose. Keep the
sequence short (2–3 groups) and the still pose informative (`still_pose: open`).

## Part motion

Only where the real object keeps moving, or where a fictional one would breathe:

- turning things `spin` (platter 33⅓ rpm, rotor, light beam at a few rpm);
- hinged or hanging things `swing` (tonearm drift ±2–3°, tentacles 5–8° with `phase_step`,
  pendulum, door);
- floating or reciprocating things `bob`;
- lights and hearts `pulse`.

Keep amplitudes small and periods long (4–60 s): the presentation is ambient. Moving
copies are limited to 32. A part has one periodic motion; it can also be articulated (a
disc that lifts and then spins). Nested periodic motion (a fan head oscillating while its
blades spin) is not available yet: show the more characteristic one.

## Idle life (host-optional)

After assembly the hologram stays alive with occasional events (`idle.events`), seeded so
captures repeat. Hosts may play none of them; never make recognition depend on one:

| event | look | suits |
|---|---|---|
| `scan` | a bright band climbs the object | anything; buildings, devices |
| `sweep` | energy crosses along a horizontal axis | long objects, machines |
| `wave` | a breath rises, pushing outward slightly | organisms, soft forms |
| `shimmer` | scattered lines twinkle | everything, quietly |
| `propagate` | a front expands from the identity feature | lights, cores, emitters |
| `glitch` | a slice loses registration (stepped) | sparingly: machines, sci-fi |
| `brownout` | half the object dims and recovers | sparingly |
| `tear` | a height band jitters | sparingly |
| `burst` | motes thrown out and gathered back | creatures, magic, energy |

`life`: `alive` (events at `cadence`), `calm` (half as often, softer), `off`. Choose 2–4
events that suit the subject; avoid the unstable ones for calm or documentary subjects.

## Camera (host-optional)

`drift` (degrees per minute) slowly orbits after assembly; `breathe` varies the distance
by a few percent. A `tour` flies to named views at given times (`fly` seconds, eased, with a
small lift) — use it to visit the identity feature and return to the hero. Interaction
(drag, wheel, keys 1–6) takes over; the presentation resumes after a pause.

## Still state

`reduced_motion: "still"`: assembly complete, no events, no part motion, no drift. Shown
for `?motion=reduced`, the M key, or when the system asks for reduced motion. Check
`review/still-reduced-motion.png`: the still must stand on its own.

## Video

`video scene.json --out clip.mp4 --seconds 20` renders frame-exact (24 fps) from `t = 0`;
use `--start` to skip the assembly, `--view` to hold another view. Needs ffmpeg; without
it, the frames are kept.
