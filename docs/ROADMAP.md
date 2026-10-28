# Roadmap

What comes next, in order. Each phase ends with a review before the next one starts; nothing here
is released until it is done and tested. What is already in Construct is in the
[changelog](../CHANGELOG.md).

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

## v1.1: models come alive

Phases A to E are built for 1.1.0 ([release notes](releases/v1.1.0.md)).

Make agent-based models exciting to learn from: a simulation's whole run as an animated hologram a
student wants to explore (why does it take this shape? how do I read it?), accurate to the run,
and exportable to Blender as a real 3D model. The core stays free, fast and reliable; the heavy
work (art direction, critic rounds, 3D models) is opt-in.

### Phase A: a reliable core (done)

- The recorder's own names never clash with a model's (5 stock models failed on names like `n`).
- The instrumenter follows `reset-ticks` and `tick` into helper procedures, reads every NetLogo 7
  file, takes setup and go from the model's own buttons and records models that never tick or tick
  in fractions: 388 of the 445 two-dimensional stock models record a run unattended (256 at 1.0;
  most of the rest wait for a player or a classroom), and a refusal says what to do.
- A run of the whole Models Library is a regression test: how many record, and why the rest don't.
- Every NetLogo construct gets a legend, shown from the start, and no decoration that could be
  read as data (the projector's rings are off).

### Phase B: an official NetLogo extension (built; listing next)

- `extensions [construct]`: the recording as primitives (`construct:start`, `construct:track-…`,
  `construct:record`) and `construct:draw`, which writes the construct beside the model and opens
  it. In Java, tested in NetLogo 7.0.4 ([hosts/netlogo](../hosts/netlogo/README.md)).
- The same recording format, so the command line, art direction and the data lock keep working.
- Next: listing it in NetLogo's Extensions Manager, through a pull request to NetLogo-Libraries.

### Phase C: learners first (opt-in polish; done)

- A replay control: scrub the run tick by tick and watch the shape form, with the tick and the
  model's own counts on screen. (Done.)
- "How to read it" on the page: the legend plus what each part of the shape means, from the bridge
  or the art layer. (Done.)
- Critic rounds for the art layer: an independent model compares versions, as in masterpiece
  mode; the data lock keeps every round honest. (Done: the run critic.)
- Legends placed to stay inside the frame. (Done.)

### Phase D: real 3D models of a run (opt-in; done, checked in Blender)

- NetLogo constructs export to glTF as proper geometry: tracks and links as tubes, agents as
  solids, one named object per breed or part, the run as the build animation. Tested in Blender.

### Phase E: every agent (MCP tools and skill done)

- NetLogo tools in the MCP server (instrument, draw, art direction), so Hermes and any MCP client
  can drive the bridge, and the skills' steps to match.

### Phase F: runs to music, and runs as films (done)

- `construct:music`: a tick is a moment of a track; `construct:kick`, `energy`, `high` and `hit` let
  a model's own code follow it, and `construct:run` lasts the track. The construct plays back in
  time with the music, its track's fingerprint under the data lock.
- The run as a film in Blender, drawn from the recording itself (nothing sampled): every turtle as
  moving light with a trail, in time with the track; from the add-on, `construct netlogo-film`, or
  `"film" true` in NetLogo.
- NetLogo 3D runs recorded with their heights and flown in the film; hidden turtles recorded and
  kept unlit.
- Demonstrations: Fireflies entraining to the beat (its flashes lock to the kicks), Flocking 3D to
  drum and bass.

### Phase G: museums and classrooms (kiosk done)

- `construct build --kiosk`: a page that runs on its own on a museum screen or a classroom wall
  (full screen, a label, an attract loop, touch to explore, sound after the first touch).
- Next (1.2): two runs side by side for a lesson (parameter A against B), a printable "how to
  read it" sheet, a run's record as CSV and a citable run record.

## Ideas (unordered)

What could come after 1.1, grouped by direction and in no order: each release picks from here
what is most worth building then. 1.5 and 2.0 look beyond research; research and teaching may
come back in 2.1, depending on how 1.1 is received.

### Music

- **Live mode:** constructs that react to live audio (a microphone or a line in) in real time,
  for performances, streams and installations; MIDI controllers mapped to the build, the joints
  and the look.
- **A song as a construct:** a MIDI file or a track drawn with time as height (notes, sections,
  loudness), like a NetLogo run: a sculpture of a song, to orbit, replay or 3D-print. (Begun in 1.1:
  `construct song` draws a track's spectrum as a tower of rings that builds with it; next, MIDI notes,
  and a solid surface to print.)
- **Stems to parts:** each stem (drums, bass, voice) drives its own group of parts, beyond film
  mode's one voice stem.
- **Your gear:** a musician's synth, guitar or rig as a construct, its knobs and switches moving
  with the track's automation.
- **Loops for streaming services and video:** short vertical loops (Spotify Canvas, Reels) and
  full-length visualisers rendered from a construct and a track.

### Film and video

- **Holographic screen graphics:** the hologram itself as a film asset, rendered with a
  transparent background and separate passes, for compositing in After Effects, Nuke or
  Resolve; camera moves imported from a tracked shot.
- **Previs:** a scene's sets, vehicles and props described in words, blocked out at their real
  sizes in Blender, with camera paths and a parts list for the art department.
- **Reconstructions for documentaries:** historical places and objects that say what is known
  and what is reconstructed, on screen.
- **Title sequences and trailers:** constructs assembling to a cut, from an edit's markers.

### Games

- **Blockout kits:** props and buildings at real sizes, with colliders and levels of detail, for
  greyboxing a level.
- **Engine packages:** importers or templates for Godot, Unity and Unreal; short guides for each.
- **The hologram in game:** the Measured Light look as a runtime shader, for scanners,
  blueprints and holographic interfaces, with build and open as game events.
- **Variants without end:** the parametric archetypes as generators: a seed in, a new vehicle or
  building out, in the editor or at runtime.
- **Break-apart:** named parts and joints as the pieces for destruction and assembly mechanics.
- **Texture coordinates for every shape,** for texturing in any engine.

### Makers and 3D

- **3D printing:** STL and 3MF export, with a solid, printable version of a construct or a run.
- **USD and USDZ export:** one tap opens a construct in AR on an iPhone or iPad.
- **From a photo:** a reference image traced into a first draft, then built from facts.
- **An optional surface finish per part** (paint, metal, glass) in the scene itself, as a
  contract addition.
- **Versions and differences:** what changed between two versions of a construct; branches of an
  art layer.

### Immersive

- **WebXR:** walk around a hologram in a headset, in the browser, with no app.
- **Room scale:** a construct at its real size in the room, its parts apart around you.
- **Museum kiosks:** a construct on a touch table, with what is known and what is reconstructed.

### Sharing and community

- **A community gallery:** submitted constructs, each with its audit and provenance shown.
- **Embeds:** a construct in any article, course page or wiki, with its reading.
- **A desktop or web studio:** Construct without a terminal, for people who don't code.

### Research and teaching

- **Richer runs by default:** the critic's general findings as defaults (computed landmarks, the
  run's own colours, readable time axes, milestones with contrast), gated by the machine checks.
- **Strata,** a view for models where things flip or jump rather than travel (Segregation, Life,
  Sandpile); **links in time,** so rewiring and growth show; **numeric globals** recorded and offered
  to the phase view; **meaningful states first** over a model's bookkeeping.
- **Comparing runs:** two seeds or settings side by side, or a BehaviorSpace sweep as small
  multiples.
- **Predict, then replay:** the shape hidden until the student has guessed it.
- **Ask the construct:** a "why this shape?" question answered from the scene's facts (opt-in, a
  model call).
- **For a course:** one file with the page and a short handout, for Canvas or any LMS.
- **More simulation worlds:** Mesa (Python), then GAMA, Repast, AnyLogic exports and plain time
  series; a JavaScript recorder for NetLogo Web.
- **Live runs:** a construct drawn while the model is still running.
- The first survey's findings, for reference (15 models, 2026-10-27): Traffic Basic, Heroes and
  Cowards, Flocking, Virus on a Network, Rumor Mill and Fire read well; Segregation, Life, Small
  Worlds, Wealth Distribution and Termites need the views above.
