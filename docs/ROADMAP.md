# Roadmap

What comes next, in order. Work is divided into areas, one release each, and lands in small steps
that are tested as they arrive; each phase ends with a review before the next one starts, and
nothing here is released until it is done and tested. What is already in Construct is in the
[changelog](../CHANGELOG.md). Work built ahead of its release waits on a branch (see
[Parked work](#parked-work)).

## v1.0.0: a hologram, a 3D model and its parts

A construct already describes a thing as named parts in metres, with an assembly order, joints and
motions. Version 1.0 makes that description usable outside the hologram: in Blender, in game
engines and in classrooms.

### Phase 1: 3D export

`construct export scene.json --format glb|obj`, also as an MCP tool and a step in the skill.

- **Solid surfaces for every part.** The compiler already makes surfaces for every shape and keeps
  them only where the hologram shows a fill; export keeps them all (`--solid`).
- **Parts are named nodes** (glTF 2.0), each with its role, certainty and source in `extras`.
- **Articulations become an `open` animation** (hinge, turn, slide, lift), as nested pivot nodes,
  so a part that rides on another still does. Periodic motions (spin, swing, bob) become looping
  clips.
- **The assembly order travels with the model:** a per-vertex build phase (`_PHASE`) and one node
  group per stage, so an engine can replay the build or scan the model in.
- **Lines** come along as edges, or as thin tubes (`--wire tubes`) for engines that drop line
  primitives.
- **Materials** are named by role; `--materials map.json` maps part ids to colour, metalness and
  roughness.
- **Options:** `--pose open|closed`, `--frame z-up`.
- **Standard for every construct:** the audit warns when a structural part has no surface (it would
  be missing from the solid), and every gallery example offers its `.glb`.
- Python standard library only. Tested by structure, by loading in three.js and by importing in
  Blender headless.

### Phase 2: Blender

A Construct add-on (a Blender extension, 4.2 and later) that imports a construct natively:

- parts as named objects, the line art as curves with a hologram material;
- three controls on the object: **Build** (replays the assembly), **Open** (drives every joint) and
  **Light ↔ Metal** (from the hologram to the solid).

### Phase 3: from light to metal (gallery example)

One page, three constructs from the gallery: the Toyota Land Cruiser FJ62, the James Webb Space
Telescope and the Revox A77. Each assembles as a hologram, turns solid behind a scan front, opens
its joints, separates into its named parts and shows its certainty, all from the exported `.glb`,
with the file to download and a render made in Blender from it, unedited.

Also tested on a well-documented object built from its manual (a synthesizer), to check the
exported parts and dimensions against the documentation.

### Phase 3a: finished models

The full pipeline, from a hologram to a plain model to a finished one:

- **Finishes in the material map:** besides a colour, a finish per part (paint, brushed metal,
  chrome, wood, rubber, plastic, glass, light), exported as standard glTF materials, glass with
  real transmission.
- **In Blender,** the add-on turns each finish into a procedural shader that needs no texture
  coordinates (wood grain, brushed streaks, chrome, glass), and adds a **Finish** control (0–1)
  from the plain model to the finished one.
- **On the page,** the same **Finish** control; and for each of the FJ62, the James Webb Space
  Telescope, the Revox A77 and the MiniFreak a material map chosen from reference photographs.
  The colours are the exporter's choice, kept beside the construct, never facts in it.
- **The showpiece:** one Blender render of the FJ62 in three panels (hologram, plain, finished).

### Phase 3b: game-ready

So that an exported construct drops into a game engine as it is:

- `--merge`: parts merged per material, keeping the ones that move (joints, motion) separate, so a
  prop is a handful of draw calls instead of one per part;
- a glass material for glazing parts (transmission), instead of opaque grey;
- simple texture coordinates for every shape, so a model can be textured and lightmapped;
- checked by importing into Godot (done: Godot 4.7.2), and with the Khronos glTF validator
  (pending the owner's OK to download it).

### Phase 4: NetLogo bridge (done)

Bring an agent-based model to life without writing a converter ([NETLOGO.md](NETLOGO.md)).

- **`construct.nls`**, a NetLogo include file, and `construct netlogo-instrument`, which adds it to a
  copy of a model with a headless experiment. It records turtles, links, reporters and patch
  fields, with the model's name, NetLogo's version and the seed.
- **`construct netlogo run.jsonl --view space-time | network-time | phase | field`** writes a valid
  construct directly from the recording, without a model; every data part is `verified` against
  it, and the assembly replays the run. A new shape, `paths`, holds many polylines in one part.
- Checked: the Simple Viral Marketing example's run is reproduced exactly (all 500 adoption ticks).
- Examples: Flocking (space-time), Wolf Sheep Predation (phase) and Fire (field). Fire replaced
  Segregation, whose story is its colours, which a construct does not draw.
- Optional art direction (done): an `art.json` layer of views, labels and milestones on top of the
  data, which a `data_lock` fact keeps exactly as the bridge drew it. The three examples were
  art-directed by Claude Opus 5.5.
- Later: a replay control with a tick scrubber (`build --replay`); a NetLogo extension.

### Phase 5: who it is for (done)

The README and the gallery, reorganised around what people make with Construct: game developers
(props, blockouts, scanner effects), 3D artists (Blender), educators and researchers (NetLogo),
museums (honest provenance), and film and motion (film mode).

The gallery, in three parts, in this order:

1. **Constructs:** the individual constructs and the films (the long, music-driven assemblies)
   first, in compact rows that scroll with a click, so the page opens on a few and holds them all
   without growing long.
2. **The full pipeline:** a detailed showcase of the finished models, from hologram to plain model
   to finished model, with the files to download and the Blender add-on.
3. **Models come alive:** the agent-based models (the NetLogo examples) last, once the bridge is
   done.

### Phase 6: release

A release candidate, the full test suite and CI, then v1.0.0. The release videos (the X and
LinkedIn cuts) are redone around the 3D export: constructs turning from light to metal, rendered in
Blender from their exported files, with new posts to match. The package version becomes 1.0.0;
the scene and geometry contract keeps its id (`construct/0.2`), because nothing in it changes.

- Released 2026-10-27 ([release notes](releases/v1.0.0.md)): the full suite passes, and every
  export option passes the Khronos glTF Validator. Construct is Apache-2.0 from 1.0; the Blender
  add-on is GPL-3.0-or-later, for Blender's extensions platform.
- Left: the release videos and posts, and the add-on's listing on extensions.blender.org.

## v1.1: models come alive (NetLogo), and things you can make

1.1 is NetLogo first: a simulation's whole run as a hologram a student wants to explore (why does it
take this shape? how do I read it?), accurate to the run, and exportable to Blender as a real 3D
model or a film. The makers' work planned for 1.2 (printing, FreeCAD, a run you can hold) and the
easy half of the games work planned for 1.5 (colliders, break-apart pieces, seeded variants, a Godot
guide) were brought into 1.1 on 29 October 2026 (owner's decision). The core stays free, fast and reliable; the heavy work (art direction, critic
rounds, 3D models) is opt-in. Runs to music were built and removed (28 October 2026): a run is its
model alone.

### Phase A: a reliable core (done)

- The recorder's own names never clash with a model's (5 stock models failed on names like `n`).
- The instrumenter follows `reset-ticks` and `tick` into helper procedures, reads every NetLogo 7
  file, takes setup and go from the model's own buttons and records models that never tick or tick
  in fractions: 388 of the 445 two-dimensional stock models record a run unattended (256 at 1.0;
  most of the rest wait for a player or a classroom), and a refusal says what to do.
- A run of the whole Models Library is a regression test: how many record, and why the rest don't.
- Every NetLogo construct gets a legend, each label shown as its part is drawn, and no decoration
  that could be read as data.

### Phase B: an official NetLogo extension (built; listing after the release)

- `extensions [construct]`: the recording as primitives and `construct:run`, one command from a
  stock model to its construct; `construct:draw` for full control. In Java, tested in NetLogo 7.0.4
  ([hosts/netlogo](../hosts/netlogo/README.md)).
- Next: listing it in NetLogo's Extensions Manager, through a pull request to NetLogo-Libraries.

### Phase C: learners first (done)

- A replay control, How to read it, the counts as CSV, Cite this run, a printable worksheet, two
  runs side by side (`construct netlogo-compare`), and critic rounds for the art layer.

### Phase D: real 3D models of a run (done, checked in Blender)

- NetLogo constructs export to glTF as proper geometry: tracks and links as tubes, agents as
  solids, one named object per breed or part, the run as the build animation.

### Phase E: every agent (done)

- NetLogo tools in the MCP server (instrument, draw, art direction), and the skills' steps to match.

### Phase F: runs as films (done; links and patches next)

- The run as a film in Blender, drawn from the recording itself (nothing sampled): every turtle as
  moving light with a trail, at 30 ticks a second, silent; NetLogo 3D runs in their box; hidden
  turtles unlit.
- To do: **links and patches in the film** (the same film for every model: a network's links as
  light between its agents, the patches as a floor that changes tick by tick).

### Phase G: where the order forms (done)

- The `pulse` view for turtles that switch a state on and off at regular gaps (Fireflies), and the
  automatic window where order forms (alignment for movers, synchrony for pulses), on by default
  and off with `--window whole` or `--view space-time`.

### Phase H: finishing 1.1

- Take the exhibits and music work off main (they wait on their branches, see Parked work), and
  the release notes, changelog and README to match: 1.1 says only what it ships.
- **Richer runs by default:** the critic's general findings as defaults (computed landmarks, the
  run's own colours, readable time axes, milestones with contrast), gated by the machine checks.
- **NetLogo examples showing every 1.1 feature, Blender included:** a run in one command, reading
  and replay, two runs compared, the worksheet, a 3D model, a film, a pulse and a window.
- **Done 29 October:** landmarks, the run's own colours made to read as light (a part's own colour in
  the scene and geometry), the NetLogo examples, two Models Library bugs (374 of 445 draw); printing
  (with engraved line art), FreeCAD and STEP, the plates; for game engines, colliders, pieces, seeded
  variants and the Godot guide.
- **Also 29 October:** size and shape certainty answered apart (`traced`, size verified, shape
  verified), the provenance view's colours and its sources legend, and the gallery examples moved to it;
  guesses in shades (designed, described, seen, seen and checked). Later: a per-part likeness from the
  critic, to tell a well-observed window from a rough one in the same photograph.
- Next: the Revell-style kits (v1.2), then freeze; the Models Library check, Linux and Windows CI, the
  README's pictures, the release videos and the repository's organisation; then the release and the
  Extensions Manager listing.

## v1.2: makers

Constructs into things you make. Printing, FreeCAD, the plates and a first version of the kits shipped early,
in 1.1 (`construct kit`); what is left:

- **Kits, Revell-style** (owner's idea, 29 October 2026): a construct as a model kit to print, glue
  and paint: its parts (small ones merged) as pieces that fit where they meet, laid out on print
  plates and numbered, an instruction booklet from the construct's own build stages, a painting
  guide from its colours, and clear parts for glass. Made with a critic, as constructs are: a draft
  kit reviewed for buildability (pieces too small, steps out of order, joints that cannot be glued)
  and revised. Tested on the Land Cruiser FJ62 and compared with a real Revell kit's published
  parts count, sprues and steps. Then locating pins and glue tabs where parts meet, an interior floor and
  the underside detail (springs, engine) a construct leaves out, so a kit reaches a real kit's count.
- **Openings for glass** in a print, and finer prints for resin printers.

- **3D printing:** a construct (or a run) to a printable, watertight model: STL and 3MF export, the
  checks a slicer would make (closed, manifold, wall thickness), and a hand-off to a slicer. Tested
  without a printer by validating the mesh and slicing it with a slicer's command line; a real print
  before a claim of fit (pins, tolerances). Started: `construct print` ([PRINTING.md](PRINTING.md)).
- **FreeCAD:** constructs in FreeCAD as parts with their names, sizes and joints, for engineering
  work and CAD formats (STEP). Started: `construct freecad` ([FREECAD.md](FREECAD.md)).
- **A simulation you can hold** (owner's idea, 28 October 2026): a printed miniature of a run that
  shows its process in the physical world and assembles like a building set, for any model a
  construct can draw. A construct of a run already has time as its height, so the general form is
  **a stack of plates, one per moment**, numbered and keyed with pins to stack in order: assembling
  it replays the run, and taking it apart steps back through time. Each view has a physical form:
  - a spread on a network: a base plate with the network, and a pin for each node cut to the tick it
    turned (set in order, the pins rise as the spread did);
  - a field's fronts: stacked contour plates, like a topographic model;
  - a cycle (phase): the rising loop as one printed tube on a stand;
  - moving agents and pulses: one plate per slice.
  To work out: every line thickened to printable ribs (about 1 mm and up), plates that fit a common
  bed, pin tolerances, the run's own colours by filament changes, and a printed key (what each plate
  is, the model and its data lock), so a classroom set is honest about what it shows.
  Started: `construct netlogo-plates` (one plate per moment, dots and links, keyed pins, a key card;
  [PRINTING.md](PRINTING.md#a-run-you-can-hold)).

## v1.3: artworks, exhibits and provenance

For educators, museums and visual artists: what is known, shown as clearly as what is beautiful.
Its truth-first stance is inspired by [Anatomy](https://github.com/wheresryan22/anatomy); its methods
are its own.

- **High-provenance mode:** a construct that maximises accuracy: every part with a source or
  visibly marked as a guess, a critic that judges accuracy only, a sources panel (touch a part to
  see where it comes from), a certainty view and a printable evidence sheet for a class or a label.
  (1.1 brought size and shape certainty answered apart and the provenance view's sources legend.)
- **Artworks as constructs:** a painting as a relief of its composition (figures, perspective, the
  vanishing point), each element with its source (catalogue, conservation reports, X-ray and
  infrared studies), and what lies under the paint (underdrawings, pentimenti) as marked layers.
- **A painting as a 3D scene:** the room and the figures of a painting such as David's *The Death of
  Socrates* built in 3D to explore, with moments before and after the painted one, reconstructed
  from the sources (for Socrates, Plato's *Phaedo*) and marked as reconstruction.
- **Sculpture and architecture at real size,** improved and with every guess marked.
- **Exhibits:** kiosk pages and shows (fixed: the kiosk's title over the viewer's caption, and
  exploring by touch in full screen), opening in the provenance view if asked; live mode with two
  demos, one for a classroom and one for a museum.

## v1.4: music

- **A song you can hold:** a track as a sculpture to print, made unique to its track (its key,
  tempo, stereo width and sections shaping the form; forms to choose, such as a tower, a spiral or a
  vessel; its title and length on the base).
- **Scores and a MIDI player:** a score as a sculpture, and a 3D construct of an instrument (a piano
  first) that plays a MIDI file, recorded and exported to Blender and game engines; generalised to
  other instruments if it proves itself.
- **Instruments that don't exist yet:** from a plugin's manual (a synth, an amp simulator, a channel
  strip), the hardware it could be: its controls from the manual (verified), its panel and body
  designed and marked as design, to render and to model after.

## v1.5: games

- **Blockout kits:** props and buildings at real sizes. Colliders shipped in 1.1; levels of detail are
  left to the engines, which make them on import.
- **Engine packages:** importers or templates for Godot, Unity and Unreal that turn the collider boxes
  and joints into each engine's own. The Godot guide shipped in 1.1.
- **The hologram in game:** the Measured Light look as a runtime shader, for scanners, blueprints
  and holographic interfaces, with build and open as game events.
- **Variants without end:** seeded variants shipped in 1.1 (`params --seed`); next, generators in the
  editor or at runtime, and buildings.
- **Break-apart:** shipped in 1.1 (`export --pieces`); next, pieces that start apart (so they settle
  rather than burst) and joints as physics joints.
- **Texture coordinates for every shape,** for texturing in any engine (box-projected today).

## v1.6: film, documentary and AR

- **Reconstructions for documentaries:** historical places and objects that say on screen what is
  known and what is reconstructed (with the high-provenance mode of 1.3).
- **Holographic screen graphics:** the hologram as a film asset, rendered with a transparent
  background and separate passes (lines, glow, depth), for compositing over live action; camera
  moves imported from a tracked shot.
- **USD and USDZ export:** Pixar's scene format for film pipelines, and its single-file package for
  AR: on an iPhone or iPad, one tap opens a construct in the room at its real size, with no app.

## Parked work

Built ahead of its release, kept on local branches until its area comes; main holds only what is
being released.

| Branch | Holds | Comes back in |
| --- | --- | --- |
| `parked/exhibits` | kiosk pages and shows (`construct build --kiosk`, `construct kiosk`, viewer/kiosk.js), live mode (`?live=1` in viewer/film.js) | 1.3 |
| `parked/music` | songs as towers (`construct song`, song.py, the `rings` shape, `--solid`), MIDI scores (score.py), Keyframe to Its Track in Blender, construct audio's `kick` | 1.4 |

Both branches were cut from main at `9fd80bd` (28 October 2026), before the exhibits and music work
is taken off main for 1.1. Scrapped, not parked: runs to music (removed in `3e246d6`), the beat
tracker, and Keyframe to Its Track as a "3D visualiser" (the MIDI player of 1.4 replaces it).

## Ideas (unordered)

What could come later, grouped by direction and in no order: each release picks from here what is
most worth building then.

### Music

- **Stems to parts:** each stem (drums, bass, voice) drives its own group of parts.
- **Your gear:** a musician's synth, guitar or rig as a construct, its knobs and switches moving
  with the track's automation.
- **Loops for streaming services and video:** short vertical loops (Spotify Canvas, Reels).
- **Strudel:** a construct of a live-coded pattern, its exact timing drawing polyrhythms and
  polymeters as they are, each layer its own cycle; a page that follows Strudel's clock in a
  performance.

### Film and video (to decide)

- **Previs:** a scene's sets, vehicles and props described in words, blocked out at their real
  sizes in Blender, with camera paths and a parts list for the art department.
- **Title sequences and trailers:** constructs assembling to a cut, from an edit's markers.

### People (later)

- **People:** human figures as constructs: bodies from anthropometric proportions (the source
  marked), posed by their joints, clothing as shells over them, heads with their features and
  expressions as parameters; sculptural, not photographic; a real person's likeness needs their
  consent. Started on the branch `v1.3-people` (standing, walking and seated figures from cited
  proportions); moved to a later release on 29 October 2026.

### Makers and 3D

- **Detail from AI mesh generators** (from a Reddit comment, 29 October 2026): a part's fine detail
  (a car seat's creases, a sculpture's surface) generated by a mesh model such as Tripo or Rodin and
  fitted inside the part's envelope in the scene, which stays the source of truth for its place, size
  and joints; the checker confirms it stays inside, and the mesh is marked generated, never evidence.

- **From a photo:** a reference image traced into a first draft, then built from facts.
- **An optional surface finish per part** (paint, metal, glass) in the scene itself.
- **Versions and differences:** what changed between two versions of a construct.

### Immersive

- **WebXR:** walk around a hologram in a headset, in the browser, with no app.
- **Room scale:** a construct at its real size in the room, its parts apart around you.

### Sharing and community

- **A community gallery:** submitted constructs, each with its audit and provenance shown.
- **Embeds:** a construct in any article, course page or wiki, with its reading.
- **A desktop or web studio:** Construct without a terminal, for people who don't code.

### Research and teaching

- **Strata,** a view for models where things flip or jump rather than travel (Segregation, Life,
  Sandpile); **links in time,** so rewiring and growth show; **numeric globals** recorded and offered
  to the phase view; **meaningful states first** over a model's bookkeeping.
- **Sweeps:** a BehaviorSpace sweep as small multiples.
- **Predict, then replay:** the shape hidden until the student has guessed it.
- **Ask the construct:** a "why this shape?" question answered from the scene's facts (opt-in).
- **For a course:** one file with the page and a short handout, for Canvas or any LMS.
- **More simulation worlds:** Mesa (Python), then GAMA, Repast, AnyLogic exports and plain time
  series; a JavaScript recorder for NetLogo Web.
- **Live runs:** a construct drawn while the model is still running.
- The first survey's findings, for reference (15 models, 2026-10-27): Traffic Basic, Heroes and
  Cowards, Flocking, Virus on a Network, Rumor Mill and Fire read well; Segregation, Life, Small
  Worlds, Wealth Distribution and Termites need the views above.
