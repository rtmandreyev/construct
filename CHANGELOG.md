# Changelog

## 1.2.0 — 2026-11-06

- **Construct for Hermes, a native plugin** ([hosts/hermes/construct](hosts/hermes/construct/README.md); install with
  `hermes plugins install rtmandreyev/construct#hermes/construct`, built into `hermes/construct/` by `scripts/hermes_plugin.py`). Twelve tools, a
  `/construct` command and the `construct:construct` skill with sixteen tutorials. In Hermes Desktop the construct
  is live in the chat with its own controls (provenance, solid, replay, how to read it); a glTF turns in a 3D viewer
  with its joints; a STEP or FreeCAD file shows its exact shapes; a kit steps through in 3D beside its booklet; a
  NetLogo run plays with its replay bar. Every export is read back from the written file and summarised; work longer
  than Hermes's tool deadline (films, NetLogo runs, large builds and kits) runs as a background job with its progress
  in the chat; a Constructs page keeps every project, build, kit and file. Tested end to end with GPT-6.1 Sol: a
  masterpiece Villa Savoye, its provenance, a solid-fit repair, glTF, STEP and FreeCAD, a 30-piece desktop kit and a
  film, all from the chat. The plugin keeps Construct's version.
- **Villa Savoye, made in Hermes** ([examples/villa-savoye](examples/villa-savoye/README.md);
  [docs/for/hermes-walkthrough.md](docs/for/hermes-walkthrough.md)): the final test's construct joins the gallery
  with its five requests, its research notes, every round, the fit repair, a Blender finish and its 30-piece desktop
  kit (the gallery's fifth). The walkthrough shows each step as it looked in Hermes.
- **KESTREL, an invented ship, start to finish** ([docs/for/invent-from-what-exists.md](docs/for/invent-from-what-exists.md)):
  the invented brief that page used to give as an illustration, run by GPT-6.1 Sol in Codex. The page now follows it
  step by step: the brief, the NASA and ISS studies it reasoned from, the first build, thirteen masterpiece rounds
  and what the critics found in them, a more detailed version that keeps all 256 parts and adds 242, the joints in
  Godot and what it handed back. Both versions join the gallery under Apache-2.0
  ([examples/kestrel](examples/kestrel/), [examples/kestrel-v2](examples/kestrel-v2/)), with their briefs and the
  record of how they were made, and KESTREL takes a place among the constructs at the top of the README.
- **Documentation → product** ([docs/for/documentation-to-product.md](docs/for/documentation-to-product.md)): a new
  use case and a "Find your path" route. A well-documented system as the specification for a physical product,
  followed through one run, a software synthesizer's 354-page manual made into a 61-key instrument concept in a
  64-minute session, with what it showed, what it did not and why it worked. The same page sets out the
  design-freedom continuum, from reconstructing what exists to inventing from requirements, with the gallery's
  examples placed on it and the untested points marked as such; [About](docs/ABOUT.md) gives it in brief.
- **Solids wound outward, and closed:** in Blender's face orientation the R34's whole left side, every tyre, lamp
  and wheel showed inside out. A mirrored copy kept its original's winding (a mirror turns a surface inside out),
  and cylinders, cones, lathes, tori and spheres were wound inward; an extrusion of a clockwise profile and a
  tube's start cap were wound against the rest of their own surface. Every primitive is now wound outward and a
  mirrored copy is wound back, so a 3D export's normals, a modelling program's face orientation and its booleans,
  solidify and recalculated normals agree. A fully rounded loft section (`round` 1 on a narrow section, the R34's
  C-pillar) left corners a rounding apart and an extrusion closed by repeating its first point left an edge of no
  length: both now make one closed surface, and the poles of spheres and lathes no longer leave slivers. The
  light is unchanged; tests in `test_solids.py`.
- **Is it held?** A Red-Blue chair's back board stood on the rear low rail along its bottom edge and leaned back with
  nothing behind it (the upper rail ran on the sitter's side), and `check --fit` passed it. The audit now asks of each
  structural part that stands on something whether its weight is over where it touches, seen from above; a `tips`
  warning names the part, what it stands on, where, and how far its weight lies off it, with the fix (a second hold on
  the side it leans to). A part fixed into the side of another or hung from it is left alone, and so is a rod's end
  joined across its section. Over the gallery's scenes and the bundled examples it finds nothing.
- **Small gaps are detached:** touching meant within 1% of the object's size, 4.6 cm on a car, so a fin 2 cm under a
  floor passed when something near it kept its box in touch. For `detached` a part must come within 5 mm, or 0.3% of
  the object's size on a large one (1.4 cm on a car, half a metre on a cathedral, whose stones are not set to 5 mm).
  It named 57 parts in 12 scenes. Nine were set through another part's face (a piano's pedals and lyre posts through
  its lyre box, a DB5's cross-members through its rails, an F40's rear slats through its wing's end plates, a foyer
  mullion through the Opera House's podium) with no corner, edge midpoint or face centre near a face: an edge through
  a face now touches. The other 48 were real gaps, and the scenes were mended before the check changed (below); over
  the gallery and the bundled examples it now names none.
- **Seated, not floating** (each moved part says so in its `note`; ids, certainty and the light look are kept): the
  Porsche 911's lamp slats now follow their lamp's face, which slants back outboard, and its door handle (9 cm out
  from the body), brake discs (now against their hubs), rocker line, rear arch, front lower edge, roof rails, wipers
  and top demister wire meet the body or glass they lie on; the F40's nose wrap, sill line, door handle, brake
  intakes and a louvre return meet its body; the R34's front duct rims sit on the bumper's face (2 cm proud), the
  FJ62's rear wiper on its liftgate glass, the T1's speedometer pod in its dashboard's face (it floated 10 cm behind
  it). The CFX's bridge stands on its soundboard, its plate just under the treble strings, its bass strings just over
  them and its folded prop against the lid (its turn to the open lid grows from 69 to 71.1 degrees). The Opera House's
  14 foyer mullions stand on the terrace's edge (they began 1.8-2.3 m beyond it, in the air); the nave's clerestory
  oculi rise into their window heads and its rose glazing into the tracery's plane; the castle's gate roof bears on
  the gatehouse's walls, and the sea-cliff lighthouse's (and The Last Light's) lantern cap closes onto the lantern.
- **The stock examples check clean:** the T1's side trims assemble with the body they rest on, its wheel-arch lips
  and wipers are fine trim (`detail`, drawn as before), and the CFX's outcome is "self-reviewed", since no critic
  judged it. Two warnings were the checker's: `duplicates` counted the ring where two parts meet (a knob on its skirt)
  and a lathe closed by repeating its first point drew that ring twice (the Braun knob read 18%), so a lathe now
  draws it once and `duplicates` counts a part overlapping itself; `tube-outline` warned a vehicle with six thin tubes
  however its body was built (the T1's 47 panels, its drip rail and bumpers), and now does when the tubes outnumber
  its body's surfaces. What remains is advice (`tiny`, `clutter`) or the record (`critic-stale` and `compare-stale`
  where a scene changed after its critic and comparisons, `tier-rounds` where the rounds ran past the tier).
- **A flash between samples:** a Fireflies run's landmark said "Most at once: 83%" while 1500 of 1500 flashed
  together from tick 638. A run's reading kept evenly spaced records (every 7th of 2000), and a flash lasts a record,
  so the samples caught the flashes part way and the landmarks were read from them. The pulse's reading now keeps the
  most at once in each group of records, as its rings do; on a 1000-tick run with NetLogo 7.0.4, "All at once" moves
  from tick 957 to 547, the first tick all 1500 flashed.
- **A run is a recorded run:** a NetLogo run's construct was captioned DOCUMENTED RECONSTRUCTION, though nothing in
  it is reconstructed. `subject.accuracy` takes `recorded` (a minor addition to the contract), which `construct
  netlogo` sets and the viewer captions RECORDED RUN; the gallery's six recorded runs say so.
- **The fit, more exact:** `check --fit` left glass out altogether, so a pillar standing through a quarter window
  passed; it now names a solid part that crosses a pane (`crosses-glass`), not what holds the pane's edge. A poke is
  confirmed on its two parts alone at voxels four times finer: on the R34 a 2 cm diffuser was said to poke through
  the strakes it only touches (at 3 cm voxels), and over the gallery about 90 such false pokes go. A solid shape left
  open where it shows, an uncapped tube end or a lathe that stops short of its axis, is named (`open`), with how to
  close it; holes on the ground or inside another part are not.
- **Designed to a requirement:** a designed part could cite nothing it was designed to, so a part the user asked for
  ("two seats") or a documented function ("a 64-slot modulation matrix") looked like free invention. A fact may now
  be a `requirement` (from the user's request or a document, citing it), and a part names it in its `basis` while it
  stays `inferred`, shaded designed. The provenance legend splits DESIGNED into "designed · to a requirement" and
  "designed" and names the requirements' sources; `check` counts them ("designed parts: 2 to a requirement") and warns
  `requirement-unmet` when no part names one. A new design is `subject.accuracy: "original"`, captioned ORIGINAL
  DESIGN instead of APPROXIMATE RECONSTRUCTION. The viewer's pinned copy moves to `testdata/hologram-1.2.0.js`.
- **The critic stands apart:** an audit of a run found an author's rationale in a critic's packet, and a critic that
  had written to the author mid-review changing its blind score. A rounds packet now holds only the renders, the
  reference pictures and the user's request (`--reference` refuses a document; the scene's own summary no longer
  stands in for the request). Once written it is sealed: read-only, its hash in the run's state; `rounds record`
  refuses an answer when the packet changed or is gone, and answers a packet once: a recorded blind verdict is not
  rewritten (its `round.json` is read-only, its hash in the history, and `rounds report` names a round edited
  afterwards). A new answer needs a new packet.
- **Numbers that went stale:** a chair's How to read it still gave an 11.8 deg lean after the fact became 15.2. The
  audit warns `stale-number` when a number with a unit in How to read it or an annotation contradicts the one fact it
  clearly names (every telling word of the key in the same clause, and no fact at all with that value). Over the
  gallery and the bundled examples it finds nothing.
- **Kits: boards lie flat, rails keep their ends:** a Red-Blue chair at 1:6 laid its 2 mm back board, set at a slant,
  on its edge, and each rail's ends standing proud of the leg it passes through came out as 2.5 mm chips of their
  own. A thin board set at a slant now lies on its broad face; a bit the trimming cuts off a part, under 6 mm every
  way, is moulded with the piece that cut it off, and what is left of the part is counted again ("cross-low-rear",
  not "1 of 3"). Plates fill each row before starting a new one (the chair: 30 pieces on 2 plates became 20 on one),
  and a piece every neighbour of which hangs from it no longer starts a second tree the base never reaches.
- **No critic packets left behind:** masterpiece rounds wrote each round's critic packet (renders, references,
  pairs) to the temporary folder and never removed it, so gigabytes built up over many runs. Once a round's answer is recorded the
  packet is removed; its renders were already kept with the round's checkpoint. A packet written with `--out` stays.
- **Twice the lines and triangles:** a construct's page may hold 48,000 lines and 48,000 triangles (was 24,000 each),
  so a large, detailed construct fits; the 3D export's own budgets are unchanged, and terrain, globes and NetLogo runs
  keep drawing as lightly as before.
- **Up to 1,024 parts:** a scene could hold 256 parts, and the best constructs were at the cap (the T1 255,
  Sagrada Família 256), so "make it more detailed, keep every part" had nowhere to go. A scene may now hold as many
  parts as copies (1,024); what costs is copies and lines, and their budgets are unchanged.
- **Glued joints inside joints:** `--pieces glued` named every body after its last joint, so the T1's four sunroof
  panels shared one name, three of its nine joints were lost and in Godot the bus flew apart. Each body now has its own
  name, a part moved by joints inside joints carries the whole chain (one Generic6DOFJoint3D in
  `construct_joints.gd`), a slide's joint sits on the piece it moves rather than at the scene's origin, and a
  construct's pieces no longer collide with one another. Measured in Godot 4.7: the T1 keeps all nine joints and
  nothing moves past its own travel.
- **FreeCAD gets only what it needs:** `construct freecad` ran FreeCAD with a copy of the whole environment, API keys
  included. It now passes only what a program needs to start and keep its files on Windows, macOS and Linux, and
  FreeCAD's own settings (`FREECAD_USER_*`); the job travels in the script. Hermes's skill scan read the copy as a
  possible leak and refused to install the skill from GitHub without `--force`; it now installs as is
  (`hermes skills install rtmandreyev/construct/skills/construct`).
- **The published schema takes 1.2's constructs:** `geometry.schema.json` still allowed 256 parts and 24,000 lines
  and triangles, so an app that re-validated a compiled file against it rejected KESTREL v2 (498 parts) and the R34
  (24,924 triangles). It now allows what the compiler allows; a test ties the two and validates both.
- **A hint for every problem:** fifteen audit codes came back with no fix hint (`tier-*`, `critic-*`, `research`,
  `authoring`, `likeness`, `self-graded`, `identity-unbuilt`, `no-checklist`, `compare-stale`, `data-lock`,
  `glass-name`, `no-surface`, `tube-outline`), though `check` and the MCP tool promise one. Each now has one, and so
  does each `check --fit` finding in `--json` (`pokes`, `crosses-glass`, `open`, `buried`); a test keeps every new
  code from arriving without one.
- **Packaging:** a pip install lacked `construct.nls`, so `netlogo-instrument` failed there; the wheel now carries
  it and film mode's loader, and no longer the tests' fixtures (`testdata/`). The NetLogo extension's zip is made from
  what git holds, not the working tree, and leaves out the tests, their fixtures and the unrendered skill.
- **KESTREL is an original design:** both versions said `subject.accuracy: "generic"`, captioned GENERIC
  RECONSTRUCTION, because the run predated `original`; they now read ORIGINAL DESIGN, a post-run correction their
  pages note. The Eames chair's back cushion no longer comes down through its shell, nor its welts through the
  cushion and the arm pads (`check --fit`); each moved part says so in its `note`. Five older gallery scenes move
  from the `tessera-hologram` format id to `construct-scene`.
- **The film constructs leave:** the three view-only constructs made for a film, never under a licence, are no
  longer in the repository or the gallery, and the gallery's "New things from real ones" group is gone with them
  (`examples/worlds.json`); KESTREL, which anyone may reuse, shows the use case instead.
- **The R34's windows fit their frames:** a second pass judged in the solid and in Blender: its A-pillars, sashes,
  B-pillar and C-pillars hold their glass (every pane meets its frame or panel along at least 95% of its edge,
  within 4 mm; the A-pillars stood up to 9 cm proud), its rear quarter panels end on the tail panel instead of in caps
  standing out of it, its tail lamps sit on the tail panel's face and its bumper flanks end where the bumper's bands
  begin ([its page](examples/nissan-skyline-gt-r-r34/README.md)).
- **The R34, refined for the solid** ([its page](examples/nissan-skyline-gt-r-r34/README.md)): its C-pillar
  closes between the rear glass and the shoulder instead of standing as a fin through the quarter window, its
  bumper flanks are closed, its rear bumper and tail no longer pillow, its sills run straight and flush, its
  diffuser follows the bumper and its tubes are capped. Every part keeps its name; the parts no longer traced say so.

## 1.1.1 — 2026-11-03

- **New things from real ones** ([docs/for/invent-from-what-exists.md](docs/for/invent-from-what-exists.md)): a use
  case for game developers, filmmakers, Blender artists and worldbuilders: how to write a brief that grounds an
  invented ship, vehicle, creature or artefact in real designs, with an invented brief to follow. Three view-only
  examples made for a film joined the gallery as their own group (since withdrawn).
- **The provenance legend on embedded pages:** a page embedded with `ui=0` (every gallery example) coloured
  its parts on **P** but hid the legend that says what each colour means and how many parts are each; it now
  shows wherever **P** does, and stays out of stills (`capture=1`). The viewer's pinned copy moves to
  `testdata/hologram-1.1.1.js`.
- **No copy of Chrome left behind:** on macOS, Chrome copies itself on every launch to check its signature and
  removes the copy when asked to quit, but not when it is terminated. Construct's headless browser (every
  capture, still, kit picture and many tests) was terminated, so each launch left a full copy of Chrome in the
  user's temporary folder (thousands over a week of work). It now asks Chrome to quit first.

## 1.1.0 — 2026-11-02

Models come alive: the NetLogo bridge, made reliable on the whole Models Library and usable from
inside NetLogo; runs as films and 3D models in Blender; and runs for the classroom, compared side by
side, printed as worksheets and cited. The story: [release notes](docs/releases/v1.1.0.md).

- **Construct for NetLogo** ([hosts/netlogo](hosts/netlogo/README.md)): a NetLogo 7 extension,
  built by `scripts/build_netlogo_extension.py`. `extensions [construct]`, a few `construct:` lines
  in setup and go, then `construct:draw "phase"` in the Command Center draws the run and opens it.
  It writes the same recording as `construct.nls` (the same turtles, tick by tick, in the tests);
  recording needs only NetLogo, drawing runs the Construct it carries with Python 3.10 or newer.
  Its errors say what to do ("construct:start first", the options a view takes).
- **Instrumenting, on the whole Models Library:** It finds `reset-ticks` and `tick`
  in the procedures setup and go call, reads models whose code is escaped XML, takes `--setup` and
  `--go` commands (with inputs: `--setup "setup 4"`, which a refusal suggests from the model's own
  buttons), and the recorder's names can no longer clash with a model's (all `construct-`).
- **Pulse, and where the order forms:** a new view, `pulse`, for turtles that switch a state on and off
  again and again (fireflies, firing cells): one ring per tick, its area the share in that state, so
  falling into step shows as a thin, ragged column opening into wide plates; `--view auto` picks it
  when turtles switch a true/false state at least four times each on average, at regular gaps. Moving turtles are measured by their
  alignment and pulses by their synchrony (the order parameter r); when that order forms early in a
  long run, space-time and pulse are drawn over the window where it formed, said in the title, a
  `window` fact and How to read it (`--window whole|auto|TICK`; also in `construct:draw` and MCP).
- **Landmarks:** a construct of a run marks the moments worth marking from its first count (half way and
  most of the way, a peak, or half and all at once for a pulse): dashed frames in the accent, labelled
  with their value and tick, inferred and under the data lock; `--landmarks off` (and in
  `construct:draw` and MCP) leaves them out.
- **Labels wait for their parts:** a construct's labels appear as the build reaches the point each one
  names (the geometry's annotations carry that `phase`), never over an empty frame; the viewer's
  pinned copy moves to `testdata/hologram-1.1.0.js`.
- **A run as a film** (Blender): File > Import > NetLogo Run (.jsonl), `construct netlogo-film run.jsonl
  --out film.mp4` (or `--blend`; it finds Blender), or `(construct:draw … "film" true)` in NetLogo
  (`film.blend` beside the page), draws a recording itself, every turtle at every tick as glowing
  light with a trail in its own NetLogo colour, each link as a line of light while it lasts, the patches
  as a floor of cells in their recorded colours, the world's edge as a line of light, bloom and an
  orbiting camera, at 30 ticks a second, silent, in a steady light. Nothing is sampled, so a long run
  of many agents loses nothing.
- **NetLogo 3D:** the extension records each turtle's height (last in its row, so 2D readers are
  unchanged) and the world's depth, and skips 3D patches; a NetLogo 3D model opens headless in the
  tests' driver. The film flies the turtles at their heights inside the world's box.
- **Two runs side by side:** `construct netlogo-compare a.jsonl b.jsonl` draws two runs the same way on
  one time scale, A on the left and B on the right, each part, fact, label and count marked with its
  run, under one data lock (a run's lock covers every `run…` source in the scene).
- **A worksheet:** printed, a construct with a reading is a one-page worksheet: its picture as on
  screen, how to read it, the counts at that tick, the citation and three questions with room to answer.
- **For a spreadsheet or a report:** a run's *How to read it* panel offers its counts as CSV and a
  citation of the run (model, NetLogo version, seed, ticks, Construct's version, data lock);
  `construct netlogo … --csv` writes the counts at every record.
- **A legend on every NetLogo construct,** each part named where it is and shown from the start;
  no projector or drifting motes on a construct of data. An art layer's `"legend": false` drops it
  where its own annotations replace it (the three examples). A scene may now ask to open with its
  labels showing (`presentation.labels`); other pages are unchanged.
- **The field view's fronts are declared floating** (each hangs at its own tick), so a run whose
  earliest front sits above the floor passes the audit; the Fire example's data lock changes for
  this alone.
- **The Models Library, unattended:** 388 of the 445 two-dimensional stock models now record a run
  with no hand edits (256 at 1.0, counted the same way: at least two records). Setup and go come
  from the model's own buttons when it has them (their whole command), a turtle's forever button is
  asked of every turtle, a model with only step buttons steps, a model that never starts the tick
  counter is recorded by steps (`"clock": "steps"`, and its construct says "step"), and a clock
  that moves in fractions (`tick-advance`: GasLab, Connected Chemistry, system dynamics) records
  each step; the recorder and the extension record each moment once. Most of the 57 left wait for
  a player or a classroom ([NETLOGO.md](docs/NETLOGO.md#how-it-was-checked)).
- **Reading a construct**: a scene may carry a `reading`, how to read it and, for a run,
  its clock and counts. Its page then has a **How to read it** panel (**H**) and a replay bar that
  draws the run up to any tick, with the tick and the counts beside it; labels stay inside the
  window, on a phone too. The bridge writes a reading for every view; an art layer may reword it;
  the clock and counts are under the data lock (the three examples' locks change for this). Pages
  whose scene has no reading are the stock viewer, unchanged (`viewer/reading.js` is added only to
  pages that ask).
- **One command:** `construct:run` in the Command Center runs the model as its buttons do, records
  what is worth recording, lets it run until it stops by itself (or 1000 runs of go;
  `construct:run-for n`), picks the view the data suits and opens the construct; the step-by-step
  commands are unchanged. `--view auto` makes the same choice from the command line: a network that
  grows rises by each turtle's arrival, and static agents are a last resort, said so. A run of a
  model in NetLogo's own Models Library (or unsaved) is written to Documents/NetLogo Constructs,
  not into NetLogo's installation; a setup that fills the world is preferred to one that empties it.
  Checked over the whole Models Library with the new machine checks (`scripts/library_check.py`):
  373 of 445 models draw, every data lock holds, and no label leaves the window or covers another;
  the run fixed a breed born mid-run (now declared floating), fields whose patches all change at
  once (the next view is chosen) and a field over the scene's point budget.
- **Critic rounds for a run** (opt-in): the rounds' critic, given a NetLogo construct, checks
  every label and milestone against the recording's facts and counts and judges how a student
  would read it (`critic-run.md`); with GPT-6.1 Sol it ranked a planted false milestone first. The
  network view's reading line no longer claims the change passed along a link.
- **A run as a 3D model** (opt-in): `construct netlogo … --solid --glb run.glb` adds solids
  (each turtle a sphere where it rose, a cycle as a tube, a spread as a surface) and exports the
  run in its own NetLogo colours, its build replaying the run in Blender; `--materials-out` writes
  the colour map, and `construct:draw … "model" true` does it from NetLogo.
- **NetLogo for every agent**: the MCP server gains `construct_netlogo_instrument` (a model's
  text in, the recording copy, its experiment and the recorder out) and `construct_netlogo_draw` (a
  recording in, the locked construct out, with an art layer, solids and the run's colours on
  request); the skill's NetLogo steps cover the extension, the reading and 3D models.
- **Things you can make**:
  - **3D printing** ([PRINTING.md](docs/PRINTING.md)): `construct print scene.json --out model.3mf`
    (or `.stl`) makes a construct one watertight solid to print, at a size (`--size`, 100 mm on its
    longest side by default) or a scale (`--scale 43` for 1:43). It is made in voxels at the print's
    own scale: closed parts filled, open surfaces and too-thin parts thickened to the wall, gaps
    between parts up to `--join` closed so it is one piece, sealed cavities filled, the surface
    smoothed and moved onto the construct's own surfaces so flat faces come out flat. The report says
    whether it is watertight, how many pieces it is and whether any would start in the air, whether it
    fits the bed, where it needs supports, and which parts were thickened or left out (annotations,
    and parts drawn only in lines unless `--lines`). Also the MCP tool `construct_print` and the
    skill. Checked against PrusaSlicer when it is installed: manifold, one part, and it slices.
  - **FreeCAD** ([FREECAD.md](docs/FREECAD.md)): `construct freecad scene.json --out model.FCStd --step
    model.step` builds a construct in FreeCAD (1.0 or newer, run through its own `freecadcmd`) as named
    solids, each part's closed pieces sewn and refined, its role, certainty, source and stage as
    properties, in a group per stage; each articulation a nested group with its type, axis, pivot,
    amount and an `Open` placement that opens it; then STEP with the same tree and names.
  - **A run you can hold** ([PRINTING.md](docs/PRINTING.md#a-run-you-can-hold)): `construct netlogo-plates
    run.jsonl --out plates/` prints a NetLogo run as plates, one per moment (`--plates N` or `--at
    ticks`): every turtle a dot, tall where its true/false state is on (`--state`, `--tall`), every link
    a ridge; keyed 3 mm and 4 mm pin holes, the plate's number engraved as dots; pins, spacer sleeves
    and a key card with each plate's tick and counts and the recording's SHA-256. Flat faces are merged
    into strips, so a plate is about 2 MB, not 9.
- **Runs in their own colours:** a NetLogo run is drawn in its NetLogo colours, made to read as light (a part
  may now carry `look.color`; the geometry's optional `style_colors[]` carries it to the viewer and the 3D
  model); `--colors house` keeps Construct's tones. Risen turtles of a network end in a bead of light.
- **For game engines** ([GODOT.md](docs/GODOT.md)): `construct export --colliders` (a box collider per part,
  moving with its joint) and `--pieces` (every part a rigid body, for break-apart), checked in Godot with
  its physics; part names Godot would misread (`steering-wheel`) are kept safe. `construct params --seed N`
  draws a seeded variant of an archetype (a new coupe, a new guitar), the same seed the same object.
- **Prints keep their line art:** `construct print --lines engrave` cuts the parts drawn only in lines into
  the surface, like a model kit's panel lines.
- **FreeCAD documents open framed, every part showing.**
- **More than two runs compared:** `construct netlogo-compare` takes 2 to 8 recordings, left to right (in rows of
  four beyond four), on the longest run's time scale, under one data lock over every recording.
- **Kits, Revell-style** ([PRINTING.md](docs/PRINTING.md#a-kit-revell-style)): `construct kit` makes a construct a
  model kit to print, glue and paint: pieces that fit where they meet (overlaps trimmed, clear parts yielding),
  small bits merged into a piece of their own part or paint (never across clear and opaque), panel lines
  engraved, pieces laid flat on numbered plates, a booklet of steps with pictures and a painting guide. A
  critic's brief (`--critic`) and a plan (`--plan`: merges, parts to keep, clear parts, sub-assemblies in
  order) make it the way constructs are made: drafted, reviewed, revised. The FJ62 at 1:24: 68 pieces.
- **Size and shape, known apart** ([CONTRACT.md](CONTRACT.md#two-axis-certainty-an-addition-within-02)): a
  part's certainty may be `{"size": "verified", "shape": "traced"}`, a car body whose length a spec
  sheet gives and whose outline was fitted to a blueprint, and a new certainty, `traced`, for a fit to
  an orthographic drawing a verified size scales. The provenance view keeps fully verified parts white
  and gives size verified (cyan), shape verified (violet) and traced (blue) their own colours; its
  legend counts the parts of each kind and names the sources behind the verified ones. One word still
  means both axes, and geometry readers still get one word (the weaker axis). Fifteen gallery examples
  now say what they knew: the FJ62 has 142 parts traced on its blueprint and 4 of verified size where
  it had 214 inferred; the buildings, modelled mostly from photographs, rightly stay mostly inferred.
  Their light view is unchanged (the compiled geometry is identical but for the certainty fields).
- **Guesses in shades:** in the provenance view an inferred part is deeper amber the more firmly it is
  held to the real thing: designed, described, seen (read from a picture of it), seen and checked (also
  resting on a verified fact, or drawn from a reference a silhouette comparison passed against); a
  traced part deepens to a strong blue once its reference's comparison passes. Computed from what the
  scene already cites (geometry `evidence` per part, `provenance.checked`); the legend shows each shade
  with its count and the comparisons that checked them. On the Duomo the measured facade stands out deep
  against 98 pale spires that cite nothing.
- **Printers, and every detail:** `construct print --printers` says, for five printer classes (small,
  desktop, 256 mm, large and resin), the largest print that stands on each, the smallest feature of the
  real object that survives and how many parts print as themselves; `--printer` takes a class's bed,
  voxel and wall, and `--fit` prints at that largest size, turned a quarter on the bed if it fits only
  that way. `--exact` (3MF) writes the construct's own closed solids as the parts of one object the
  slicer joins, so a print keeps every detail the construct has at the printer's own resolution; only
  open and too-thin surfaces become voxels. The voxel grid now goes to 900 along the longest side (a
  36 cm print at 0.4 mm). PrusaSlicer reads an exact FJ62 as one manifold object of named parts and slices it.
- **True CAD shapes:** `construct freecad` builds parts from their own parameters as real CAD shapes:
  exact boxes, cylinders, cones, spheres and tori, lathes revolved from a spline, extrusions, lofts as
  smooth NURBS surfaces through their sections, tubes swept along a spline. Each is checked against the
  construct's own surfaces and falls back to straight, then to facets, when it does not match. Every part
  of the CFX and the DB5, 89 of the FJ62's 93, are true shapes; STEP files carry cylinders as cylinders.
  `--facets` keeps the old faceted solids.
- **OBJ ready to subdivide, and triangle quality:** an OBJ's positions are shared between faces and its
  strips are quads again, so it subdivides cleanly (it was a soup of separate triangles, which a
  subdivision pulls apart). Every export reports the share of thin triangles (an angle under 10 degrees),
  and `export --quality` colours each triangle by its smallest angle.
- **Pieces that settle:** `export --pieces` now gives every mirrored or repeated copy a body of its own,
  shapes that follow the surface (a hollow body shell is a skin of convex patches, not a solid block),
  interlocked parts as one assembly (a rim in its tyre, an axle through its hubs) and shapes pulled in
  slightly, written with the glTF physics extensions Godot imports. The FJ62 in Godot went from 249
  pairs of pieces pressed into each other at rest, and a burst when released, to 17 pairs and a car that
  falls apart onto the floor.
- **Found by two overnight masterpiece runs (an R34 and a VW T1, on Opus):** `compare` fills a tyre drawn as
  a lathe or cylinder and a wheel well under an arch drawn as a tube (it only knew a torus and a curve); a
  scene's `open` view is shown opened in review even when its still pose is closed; a critique reference
  keyed to the scene's own view reaches the packet; a kit plan's `opaque` overrides a glassy name; a merged
  piece is built at its largest part's stage; the kit's check flags slivers, fragile blades and merges that
  came apart; the kit booklet's pictures keep their dark background when opened on their own (they
  carried a literal `100%%`); `check` says when a file is a trace, not a scene; a critique records the
  run's round.
- **`check --fit`:** the parts that poke through others where it shows (a bit of a part out on the far side
  of another, seen from outside) and the parts buried in others, each with where it is, the most visible first,
  so an agent or a person can refine a solid part by part. A part merely set into another is not reported.
- **Glued buildings stand still:** a glued building's fixed body is static in Godot (a castle on its rock does
  not topple; its doors still hang on it, `construct_joints.gd` joins to static bodies too). All 28 gallery
  constructs of the time export glued with every joint made.
- **Kits of buildings go up from the ground:** in a building what starts lower holds what starts higher.
- **Kits closer to a real model kit:** pieces true to the construct's shapes (each
  surface snapped back onto its parts', untrimmed solids exact); repeated sub-assemblies one step done that many
  times; a 3D guide with the instructions big at the top and lines to the pieces, the controls at the bottom,
  what is built barely dimmed; a booklet with a cover, the paints, plates drawn with each piece's real outline,
  and a card per step with pictures of the parts it needs.
- **Kits in the gallery:** four kits open in the browser, their steps in 3D and their booklets: the Yamaha CFX,
  Tompion's clock, the VW T1 Samba and an owner's Vespa GS 150 (`examples/kits.json`; `scripts/build_site.py`
  makes them with `construct kit`, `--no-kits` leaves them out), and their plates as release zips
  (`scripts/build_kit_zips.py`: `construct-kit-<slug>.zip`, the plates, booklet and 3D guide). The 3D guide no
  longer shows the construct's caption under its controls or its reading panel over the step card.
- **One construct, end to end:** [a longcase clock](docs/END-TO-END.md), built by DeepSeek V4.1 Flash in masterpiece
  mode through Hermes, taken through provenance, the solid, Blender, Godot, a film, FreeCAD, a print and a kit.
  What a first end-to-end run found, fixed: a merged kit piece is named for what its parts are together ("the
  door"); a clear piece stays clear whatever a colour map's catch-all says; the 3D guide frames the whole model
  below its instructions; both construct skills teach kits, kit-ready copies, true CAD shapes and glued pieces.
- **Found by the clock's walkthrough and a sweep of the whole gallery** (every example through check, fit,
  build, every export, FreeCAD, print, PrusaSlicer and kit): glass named only in a label (`"Glazed hood door"`)
  is a `check` warning, since the solid view, exports, prints and kits know glass by its id; an exact print's
  thickened surface that would touch itself (half-ribs meeting at a vault's pointed apex) goes through the
  voxels and stays watertight; a thin part merged into a kit piece no longer moves that piece first in the
  build; a kit merge that came out in pieces counts the bits too small to keep; a kit says how far it has got (a
  building's kit takes many minutes) and says "1 plate", not "1 plates"; FreeCAD stopping early (a crash on a
  busy machine) says how it ended rather than its launcher's copy of the environment; the headless browser that
  draws pictures and films waits to start and to answer on a busy machine, and says which it was; a view is
  centred on the object as it stands, pulled back so that an opened door still fits (it was centred on the
  door's swing). Two gallery parts that were glass only by their label are named so (Neuschwanstein's
  `conservatory-glass`, the Last Light's `lantern-room-glass`); Neuschwanstein's critic record now says, truly,
  that it judged the version before.
- **For everyday use, with no terminal:** Find your path gains an everyday group (a digital copy of something
  you own, a change to your home or garden, your vehicle, a part that is missing, a model kit of your own thing,
  showing someone what you mean), each with a page, an example and a message to copy, and [one
  page](docs/for/in-the-apps.md) on using Construct in the Claude app (Cowork) or the ChatGPT app (Codex), both
  tested. New examples from photos: an Eames Lounge Chair made in the Claude app, a Braun SK 4 with a
  replacement knob to print, a garden shed with a planned change, and a 1960 Vespa GS 150 (GPT-6.1 Sol) with its
  owner's parts told from the factory's.
- **Contact measured on the surfaces** (from a desk fan two models built, reported from use): a part held up
  only because its box reaches its support passed the audit, as did a heavy part carried by a wire-thin strut
  across a gap. `check` now follows support through the solids themselves: a part whose surface meets nothing
  held up is an `unsupported` error, a part carried only by something far thinner than itself a `thin-support`
  warning, each naming the part to rest it on and the gap; both in every mode, needing no vision. It found three
  such gaps in the gallery, now closed: the Aston Martin DB5's side vents and passenger door handle, which stood
  10 to 21 cm off its body, sit on it; the brass orrery's drive bearing reaches the drum (the mechanism above it
  hung in the gear deck's hole); and the James Webb film's sunshield hub reaches the bus (it stopped 22 cm above
  it).
- **Adapters:** [docs/ADAPTERS.md](docs/ADAPTERS.md) says what a construct holds, where an adapter reads it (the
  glTF, the compiled geometry, the scene) and the rules that keep one honest, with a tested template that writes
  a parts sheet and an STL per part ([hosts/adapter-template](hosts/adapter-template/construct_parts.py)).
- **Timeboxed mode:** masterpiece in two hours in all. The same rounds and stop rules, but the
  2-hour ceiling counts the critic's time with the author's (masterpiece counts only the author's,
  as before), so a slow critic means fewer rounds rather than a three-hour wait. `--mode timeboxed`
  or `mode: timeboxed`; the skill uses it only when asked. The published geometry schema knows it, and a test keeps the
  schema's tiers equal to the compiler's.
- **The gallery:** the Nissan Skyline GT-R R34 and the Volkswagen T1 Samba join it; its constructs are in the
  page's own flow (a scroller inside the page caught the wheel), and a construct set in a page takes the wheel
  only once it is clicked, so the page never stops scrolling under it.
- **Kits polished:** booklet drawings as a kit sheet draws them: shaded pieces with
  their outlines and no hidden lines, a lens's elements fanned out along its axis, many of one kind lifted
  together with one callout, small pieces on a big model drawn close; at the bench the 3D guide ghosts the model
  so far around the sub-assembly; copies closer than the kit can print apart are one piece (a whole keyboard, not
  blocks of random widths); every piece also on its own (`pieces/`) and `--only` to print a few again; a check for
  pieces held a hair away from what they are glued to; a big thin piece is no fragile detail; each booklet and
  the docs say that no kit has yet been built by a person. Any page: **T** hides the text printed on surfaces.
- **Kits a careful builder can finish (from a kit critic's review):** at the bench the 3D guide shows only the
  sub-assembly being built, close up, until it is fitted; slivers and long thin pieces that would chip or break
  (hinge leaves, a 1 mm base plate) are moulded with the piece they touch, as a kit does; a lens's ring, cell
  or button is no longer taken for clear plastic. The Leica M3's lens now has its fixed mount sleeve and a cell
  that seats each glass element, so nothing in it floats; the Sainte-Chapelle's turret lanterns are closed at
  the top, so their spires stand on them.
- **Three more kit rules from the car runs' critics:** glass goes into the last opaque part that frames it (a
  windscreen into the roof, not the nose before the roof is on); fragile pieces under 2 mm (chrome, trim, plates)
  go on in a last Details step; a moving part hangs by its largest piece (a lid, not its handle).
- **Kits glued and ordered as a kit designer would:** each piece onto the most firmly joined, more
  foundational piece (never a fixed part onto one that opens; a door's glass into the door); sub-assemblies
  built at the bench before they are fitted (glass into a shell before it meets the chassis, a wheel before
  it goes on), shells after the interior, doors hung last; clear pieces on plates of their own; a merge that
  came out in pieces highlights each piece's own lines. Found by two live runs' kit critics.
- **Kit booklets in colour and in 3D:** step pictures on paper, each new piece in its own colour with its
  number and paint chip, the target darker, bench work drawn alone; plates in each piece's paint; and
  `assembly.html`, the steps on the solid view in the kit's paints, pieces dropping into place, numbered.
- **Glued pieces:** `export --pieces glued` keeps what does not move as one body and gives each articulation
  chain a body of its own with its joint in its extras (pivot, axis, travel, the body it hangs on);
  `hosts/godot/construct_joints.gd` turns them into Godot hinges and sliders. A loose car slumped apart on a
  floor; the glued FJ62 settles within 2 cm and its tailgate falls open on its hinge to its limit.
- **S for solid:** every built page carries the construct's surfaces (packed: quantised positions, normals,
  each part's style and build phase); **S** or `?mode=solid` shows them lit like a modelling program, opening
  and building with the lines, coloured by provenance with **P**. Review writes `solid.png` and the critic
  sees it.
- **Smoother solids:** a solid compile (export, prints, kits, the solid view) passes lofts smoothly
  between their sections (monotone cubics: nothing swells past its neighbours) with rounder corners, and
  gives round tubes twice the sides; the hologram's lines are unchanged.
- **Exact prints without voxels:** `print --exact` gives open surfaces a true shell the wall thick and
  grows too-thin solids to the wall, in their own shape; only a surface that branches or folds still goes
  through the voxels. The R34 at 1:16 prints with no voxel parts (97 thousand triangles, not a million).
- **Plainer answers to files that cannot be read:** a missing or unreadable scene names the file and why
  (`print: cannot read scene.json: No such file or directory`, not `cannot read sheet: FileNotFoundError`),
  a scene nested thousands of brackets deep says so in every command, and `check` counts "1 problem".
- **A provenance note:** `authoring.provenance_note`, shown under the caption in the provenance view
  only. Seven gallery constructs made before 1.1 carry one saying where their shades understate their
  evidence (parts that do not cite what they were read from, traced parts never compared).

## 1.0.0 — 2026-10-27

Construct 1.0 takes a construct beyond the hologram: into Blender, game engines and the web as a
3D model with named parts and working joints, plain or finished, and, for a NetLogo model, a
recorded run drawn in time. The scene and geometry contract keeps its id, `construct/0.2`: 1.0
adds to it and changes nothing in it. [Release notes](docs/releases/v1.0.0.md).

- **Licence: Apache-2.0** from 1.0 (versions up to 0.3.0 stay MIT): as open as before, with the
  NOTICE file kept in every copy, no right to Construct's name, and a patent grant. The Blender
  add-on is GPL-3.0-or-later, as Blender's extensions platform requires.
- **3D export** ([EXPORT.md](docs/EXPORT.md)): `construct export scene.json --out model.glb|.obj`,
  the MCP tool `construct_export`, and a step in the skill.
  - glTF 2.0 (.glb): every part a named node under its stage, with its role, certainty and source;
    surfaces with smoothed normals and a material per role (or from `--materials map.json`); the
    line art as edges, thin tubes (`--wire tubes`) or nothing; the articulations as the `open`
    animation (and `open:<id>` for each), nested so a chain still rides; spin, swing and bob as
    the looping `idle` animation; each vertex's build phase as `_PHASE`.
  - OBJ with its MTL: the same surfaces and edges in one pose (`--pose`, `--frame z-up`).
  - The export reads a solid compile (`compile_scene(scene, solid=True)`), which keeps every
    shape's surfaces; the hologram's own compile is unchanged.
  - Checked against the compiler: every vertex of an opened joint or a spinning part lands where
    the compiler puts it, in a pure-Python glTF evaluator and in Blender 5.2's importer.
- **Construct for Blender** ([hosts/blender](hosts/blender/README.md)): an add-on (a Blender
  extension, 4.2 and later) built by `scripts/build_blender_extension.py`. File → Import →
  Construct reads a scene or a `.glb`; the construct gets three controls, **Build**, **Open** and
  **Light ↔ Metal**, plus the line thickness and an operator that keyframes a reveal. The controls
  are custom properties driving the joints, materials and line art, so a .blend works without the
  add-on. In Blender 5.2 the opened joints land exactly where the compiler puts them. The add-on
  is GPL-3.0-or-later (`hosts/blender/LICENSE`), as Blender's extensions platform requires of
  add-ons; its zip bundles the scene compiler and the export under their Apache-2.0 licence.
- **From light to metal** ([examples/light-to-metal](examples/light-to-metal/README.md)), the full
  pipeline in the gallery: four gallery constructs (the FJ62, the James Webb Space Telescope,
  the Revox A77 and the MiniFreak) as their exported files, lit live with three.js: a scan line
  from the hologram to the solid model, the build, the joints, an exploded view with each part's
  name, role, certainty and size, and a download of each file. The site build exports the files
  (`exports` in `examples/beyond.json`); a beyond card may name its own buttons.
- **Finished models:** a material map's rules take a `finish` (paint, brushed, chrome, wood, rubber,
  plastic, glass, light), exported with standard glTF extensions (clear coat, transmission and IOR,
  emissive strength) and kept in `extras.construct.finish`. The Blender add-on adds a **Plain ↔
  Finished** control, reads `<scene>.materials.json` beside a scene (or a map chosen on import),
  and makes wood, brushed metal and rubber procedural. The example page gains the same control and
  material maps for its four constructs; its hero shows the hologram, the plain model and the
  finished one in one Blender render.
- **Seams, not wireframes:** on the solid and finished model, a part's construction lines (the
  edges of its own surfaces) fade, faint on the plain model and gone on the finished one; parts
  drawn as lines (seams, creases, outlines) stay as seams. In the add-on and on the example page.
- **Fixed in the Blender add-on:** the line art's tubes rendered with Blender's default material
  (geometry made by a modifier carries none); each tone now has a node group that sets it.
- **Game-ready export:** `--merge` merges every part that does not move into one mesh per material
  (the FJ62 goes from about 300 draw calls to 27, its tailgate still opening); `--wire seams` makes
  tubes of the design lines only, in a dark seam material, for a finished model; surfaces carry
  box-projected texture coordinates (also in OBJ); a part named for its glazing gets glass, and
  glass also carries a translucent base colour for engines without transmission. Checked in
  Godot 4.7.2 (`CONSTRUCT_GODOT`).
- **The NetLogo bridge** ([NETLOGO.md](docs/NETLOGO.md)): `construct.nls`, a NetLogo include file that
  records a run (turtles, links, reporters, patch fields, the seed) as JSON Lines, streamed so a
  63,000-patch world records in seconds; `construct netlogo-instrument` adds it to a copy of a model
  with a headless experiment; `construct netlogo run.jsonl --view space-time|network-time|phase|field`
  draws the run as a construct, deterministically, every data part verified against the recording.
  It reproduces the Simple Viral Marketing example's run exactly. Three new examples: Flocking,
  Wolf Sheep Predation and Fire (each CC BY-NC-SA 3.0, like its model).
- **Art direction for a recorded run, with a data lock:** every scene the bridge draws carries a
  `data_lock` fact, the fingerprint of its data, and the audit (so `check` and `build`) refuses a
  scene whose data no longer matches it. `construct netlogo … --art art.json` adds an art-direction
  layer on top (title, views, a data part's label and look, milestones and callouts of its own,
  credited), never the data. The three examples are art-directed by Claude Opus 5.5, every
  milestone computed from the run; the gallery opens them with their labels on.
- **A new shape, `paths`:** up to 4,000 polylines in one part (a contract addition within 0.2).
- **Audit:** `no-surface` warns when a main or structural part is drawn only as lines, so it would
  be missing from a 3D export.
- **Fixed in the export:** a merged file whose stage had all its parts merged kept an empty list
  of children, which glTF forbids. Eleven exports (finished, merged, seam-only, tubes, open,
  plain, animated, a NetLogo run) now pass the Khronos glTF Validator with no errors or warnings.
- **Who it is for:** the README opens on what people make, for game developers, 3D artists, film
  and motion, educators and researchers, and museums, and the skills' descriptions name the 3D
  model and the NetLogo bridge.
- **The gallery in three parts:** the constructs and films in a compact scroller that moves with a
  click, then the full pipeline from hologram to finished model, then the recorded NetLogo models.

## 0.3.0 — 2026-10-24

- **Film mode** ([FILM.md](docs/FILM.md)): a construct can assemble across a whole track of
  music, and you can see the music in it.
  - `construct audio` measures a track per video frame: loudness, brightness, attacks
    (`onset`), the moments it changes section, and a voice stem if you have one. Each track is
    measured against its own range by default (`--scale fixed` keeps one fixed window).
  - `video --assembly S --audio features.json --sound track.wav` renders an assembly of S
    seconds with the track in the MP4. The build nearly pauses in quiet passages and surges in
    loud ones, the light swells and dims (60–140%), strong attacks flare the build front, and
    each new section starts a new stage of the construct. `--reactivity` (0..2, default 1) sets
    how strongly; 0 is an even build.
  - `--camera tour|steady|still` chooses the camera; a scene's own tour keeps its place in a
    longer assembly.
  - Scenes may set an assembly of up to 1200 seconds, with a `long-assembly` warning above 20.
  - The skill knows the film workflow, for requests like "a construct of X that assembles
    across this track".
  - Strictly optional: film mode is its own script (`viewer/film.js`), embedded only with
    `build --film` or a film option to `video`. Without it Construct writes exactly what 0.2.1
    wrote: the viewer is the 0.2.1 viewer, byte for byte, and `check`, `build`, `review` and
    `video` give identical files for stock examples.
  - An optional three.js loader for filmmakers ships in `construct_hologram/film/`.
- **Docs for people new to Construct:** [How a construct is made](docs/HOW-IT-IS-MADE.md) (with a
  construct improving round by round), [The Measured Light style](docs/STYLE.md) (with annotated
  pictures), [Troubleshooting](docs/TROUBLESHOOTING.md), a docs index with a short glossary, and
  release notes. USING is rewritten for users, and the contributor material moved to
  [DEVELOPMENT.md](docs/DEVELOPMENT.md).
- **A README in the house style**: a plain opening, the three most complex examples assembling,
  how it works as a flowchart, then install, quick start, modes, models and requirements.
- **Repository furniture:** a test workflow on every push and pull request, issue and pull
  request templates, and SECURITY.md.
- **The gallery's construct pages** are built without the round history, so no published page
  shows the round timeline, whatever its URL.
- **Tests that need a browser** now skip cleanly as a class when none is available (or with
  `HOLOGRAM_SKIP_CAPTURE=1`); before, the skip marker sat on a helper that compile-only tests
  also use.

## 0.2.1 — 2026-10-23

Construct 0.2.1 makes long runs pay off and makes the result easy to choose and to trust: three
modes, a masterpiece loop judged by an independent critic, drawing rules that keep constructs
detailed, and a gallery of 24 examples made by AI agents.

### Three modes, and the skill picks one

- **fast:** one pass with self-review, about 10 minutes (30 for a richer subject). For generic
  subjects, simple objects and quick requests; cheaper models such as DeepSeek V4.1 Flash do these well.
- **masterpiece:** rounds judged by an independent critic, each new version compared with the
  best so far. It stops after two rounds without a win, at 12 rounds, or after 2 hours of active
  work. For a named car, landmark or building whose likeness matters.
- **unbounded:** the same rounds without the cap or the time limit, only when you ask for it.
  The critic finds an improvement almost every round, so it can run for hours at a high token
  cost; every round is reported, so you can stop it at any time.
- When you name no mode, the skill picks one and tells you before it starts: which mode, why,
  roughly how long and what it costs, and how to switch. It never picks unbounded. A smaller
  model asked for a hard named subject says so and recommends GPT-6.1 Sol or Claude Opus 5.5.
- The old tier names still work: quick, standard and showcase are fast, masterpiece is
  masterpiece. `--mode`, `mode:` in a request, the MCP `construct_limits` tool and the Claude
  Code budget hook all accept them.

### The masterpiece loop (`construct rounds`)

- **One fresh critic a round, in three parts:** it judges the new version on its own, then
  picks the better of the new version and the best so far (unlabelled, in random order, from the
  same views, beside the references), then updates the list of open defects.
- **The pairwise pick decides.** A version that wins is kept and its regressions are repaired
  next; one that loses is reverted. Scores are recorded, but every score below 3 must name the
  defect that holds it back.
- **Small rounds:** at most four defects worked on per round, each edit tagged with the defect
  it addresses, so it is clear what helped.
- **What the renderer cannot draw** (hidden lines showing faintly through solids, tinted glass,
  an opening in a still) is known from the start and never sent back as work.
- **Fair timing:** active time is measured from the run folder's own activity; the critic's
  time is logged separately, and `rounds pause` marks a break.
- **A record you can read and resume:** a short report in chat after every round, `rounds.md`,
  a checkpoint per round, `rounds status` after any interruption, and the round timeline in
  `construct.html`.

### Drawing that reads

- **A drawing-craft guide** (`references/craft.md`): a line-weight hierarchy, dark fills under
  a faint contour wire, a sub-volume per feature, density where the identity lives, and a
  critic round answered by a refine pass, with excerpts from the strongest constructs.
- **Main surfaces keep their contour.** A body, roof or tower drawn as a flat dark shape reads
  as cardboard; `check` now warns `bare-surface`, and the critic is told that faint surface
  contours are form, not clutter.
- **Detail everywhere:** one clear object at full view, and something true to find in every
  region up close. A bare face or an empty corner is unfinished work.

### An independent critic, and likeness you can measure

- `construct critique` writes a packet for a fresh model (instructions, the request, an identity
  checklist, renders beside the reference photos) and records its answer bound to the scene's
  hash. Only the critic can call a construct "good" or "outstanding".
- `authoring.identity`: the features that make the subject itself, each mapped to the parts
  that build it.
- `construct compare` measures the construct's silhouette against a traced reference outline,
  and `construct loft-from-traces` builds a body from side, top and front traces.

### New shapes

- A `loft` shape and a `vehicle` archetype, so cars come out as cars; an architecture kit
  (`tower`, `roof`, `dormer`, `facade`, `battlements`, `buttress`), parabolic towers and ribbed
  `shell` roofs; measured terrain as a building's site; a cleaner globe from dense coastline data.

### Examples

- **24 example constructs** in `examples/`, each with its scene, a hero image, its mode and
  the model that made it, and a live gallery built from them (`scripts/build_site.py`). All of
  them build with this release.
- Six new skill examples drawn with the craft guide: a Leica M3, an open-reel tape recorder, a
  sea cliff at dusk, a Jackson Juggernaut ET7, a Porsche 911 (964) and the Sagrada Família.

### Fixes

- The packaged skills ship the examples and prompts that `critique`, `author` and `prompts`
  read; they crashed from an install before.
- `compare` leaves ornament out of the silhouette, fills a tyre drawn as a wire torus, and finds
  a plan trace drawn in any orientation.
- `check` warns when a car's outline is drawn with thin tubes (`tube-outline`) and when a run
  passes its review rounds (`tier-rounds`); an opt-in Claude Code hook enforces the limits.

## 0.2.0 — Construct (2026-10-19)

The first release as **Construct**, an independent MIT-licensed project.

- **Name and ids.** Skill, MCP server and command `construct`; Python distribution
  `construct-hologram`, import package `construct_hologram`. Contract `construct/0.2` with
  formats `construct-scene` v2, `construct-geometry` v2 and `construct-params` v1. The previous
  ids (`tessera.hologram/0.2`, `tessera-hologram`, `tessera-hologram-params`,
  `tessera-hologram-geometry`) are read for one release with a `legacy-format` warning and are
  never written.
- **Any-model authoring:** `construct author` drafts with any OpenAI-compatible endpoint, checks
  and repairs until clean (the key comes from an environment variable and is never stored).
- **"Construct" is the noun.** What Construct makes is a *construct* ("build a construct of a
  lighthouse"; "holographic" still describes the look). MCP tools are `construct_diagnose`,
  `construct_params_template`, `construct_expand_params` and `construct_compile`; the pre-release
  names `hologram_diagnose`, `hologram_params_template`, `hologram_expand_params` and
  `hologram_compile_scene` still answer for one release (unlisted). `build` writes
  `construct.html` (was `hologram.html`; `review` and `video` still read an old `hologram.html`).
  The tagline is "Holographic constructs any agent can build — from a description, honestly."
- **Research and effort, bounded.** Research is optional and decided by the request: none for
  a generic subject; for a concrete, named one, preferred whenever the model is unsure of its
  identity-defining shape — the maker's pages, specs and reference photos first, viewed and
  measured with vision (any model that can see, DeepSeek V4.1 Flash included), then authoring; the user can
  say "research: on/off". Three effort tiers — quick, standard (default), showcase — with
  wall-clock, check-round, review-round and research limits. The aim is genuinely good
  (an art-direction rubric in `references/review.md` and `prompts/vision-review.md`: silhouette,
  proportions, identity, depth, composition, assembly, motion, density, honesty); the run stops
  at whichever comes first, a "good" verdict or any limit, and delivers the best version so far.
  An optional `authoring` record (tier, research, sources, review rounds, outcome, next
  improvements) is validated, audited and carried into the geometry's provenance.
  Draft early: research takes at most 40% of the time and ends in a complete, valid scene saved
  to disk, improved in place after that; at 80% nothing new is added.
  `construct author` saves every new best valid draft at once and enforces the limits (`--tier`, `--vision` review rounds, `--max-seconds`,
  `--max-images`, `--max-total-tokens`, `--max-cost`); MCP hosts read them from
  `construct_limits`.
- **The review hero is the whole object.** `hero.png` is taken in the hero view's fitted
  framing with the camera held still (`?camera=still`), so a camera tour or drift can no longer
  crop it to a detail.
- **Measured globe.** A `globe` shape (longitude/latitude paths on a sphere, a graticule, glass
  faces) and `construct globe`, which draws GeoJSON coastlines the user supplies (Natural Earth,
  public domain) simplified only as far as the line budget needs, with the axis at the cited
  axial tilt and a slow spin, labelled MEASURED COASTLINES with its scale and data credit.
- **Terrain that looks its part.** Contours about three dozen levels deep with bold index
  contours on round heights (every 100 m at 50 m spacing); the ridgelines that fall from the
  summit traced from the data and lit as identity, with a summit marker; no survey grid on a
  massif or range; closer hero framing. `--dem` takes several tiles or a folder, reads only the
  area thinned to the sampling (twenty 2 m swissALTI3D tiles in about 5 s and 35 MB), reports the
  data's true extremes, and caps the grid at 100 cells per side so the output always fits the
  triangle budget.
- **Measured terrain.** A `terrain` shape (a heightfield of up to 128×128: contours, a survey
  grid, a skirt, glass) and `construct terrain`, which samples an ESRI ASCII grid or XYZ export
  the user supplies (LV95, UTM or degrees), scales it by the ladder (spot, site, valley, massif,
  range), drapes a GPX route, places markers and labels the construct MEASURED TERRAIN with its
  scale and data attribution; a hand-made relief is SKETCHED TERRAIN. Pulled forward from 0.3.
- **Likeness from references.** `construct trace` fits a traced outline (`construct-trace`,
  measured by a model that can see, from the user's photo or a web image viewed and never
  kept) to a documented dimension: an `extrude` profile, features in metres, a `reference_image`
  source, an `inferred` part. `construct trace-image` runs the vision step on any
  OpenAI-compatible vision model; `author --reference` attaches images. `shape-overclaim`
  warns when a free-form shape is verified without a drawing, measurement or dataset.
- **One house palette.** Every construct renders in the house palette whatever the model wrote:
  a scene's `presentation.style_hint` is ignored (warning `style-hint-ignored`). Only a person
  chooses another colour, through a host option (`build --palette`, `--identity`, or the viewer's
  `?palette=`). The examples no longer carry colour hints.
- **Legibility:** thin or small mass and structure parts get a minimum visual weight.
- **Docs:** README with pictures, `docs/ABOUT.md` (what it is, its credits, how
  to talk about it), `docs/USING.md` (every entry point, a worked example, costs and times),
  `docs/ARCHETYPES.md`, `docs/EVALUATION.md`, `CONTRIBUTING.md`; `scripts/docs_media.py` and
  `scripts/release_video.py` render the pictures and the release video.

## 0.2.0-pre — as hologram-studio (2026-10-19)

From the first live runs (Hermes with DeepSeek V4.1 Flash and GPT-6.1 Sol), which passed the audit with
visible defects:

- `detached`: a part whose real surfaces and segments come within 1% of the object's size of
  no other part (and not the ground) is flagged with its nearest part, beyond what bounding
  boxes can see (a shade floating off a diagonal arm). `floating: true` is the exception.
- `thin`: a mass or structure part thinner than 0.6% of the object's largest size (a tube, a
  curve, a long cylinder or box, a torus) gets a minimum radius.
- Both set the report's `needs_repair`, and lead `repair_text`, so the repair loop continues
  until they are fixed.
- `prompts/vision-review.md`: an optional self-review of `hero.png` against the request for
  models that can see images.
- Fixed in the examples by these checks: the jellyfish's oral arms now hang from the bell,
  the can has a lid under its tab, the lighthouse rail is detail, the organism starter's eye
  sits on its body.

First standalone release, extracted from the Tessera project's `hologram-skill` branch with its
history (`git subtree split` of `tools/hologram`: the toolkit's files only, one author).

- Relicensed under MIT by its author (previously Apache-2.0 inside Tessera).
- The product's name lives in `construct_hologram/product.py` and `pyproject.toml`.
- Layout: the package in `construct_hologram/`; the contract, README, licence and notices at the
  root. Removed: the Tessera branch's handoff and working notes and the v0.1
  `create-hologram` skill (superseded by `construct_hologram/skill`).
- Contract `construct/0.2` (accepted by Tessera, with the `open` view): scenes with
  facts and certainty, a closed shape vocabulary, roles, stages, periodic motion, one-shot
  articulations, labels from facts, artwork slots and masks, anchors, views; compiled
  geometry with `geometry.schema.json`.
- Diagnostics with JSON paths, codes, hints and `repair_text`; every problem in one round;
  placeholder values are unknown facts.
- The simple path: parametric archetypes for cases, books, guitars, a synth and vessels, with
  15 synthetic golden documents.
- Any-model prompts and `params.schema.json`; read-only v2 MCP tools; Hermes and Claude Code
  skill packages; a synthetic cross-model evaluation and its scorer.
- WebGL2 viewer: staged construction, idle life, articulations and the `open` view, labels
  set from facts, masks, provenance mode, reduced-motion still; headless review captures and
  video.

## 0.1.0

The construction-sheet prototype (`hologram.py`, `schema.json`, the v0.1 CLI and MCP tools),
kept as a legacy layer.
