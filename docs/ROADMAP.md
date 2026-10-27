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

### Phase 4: NetLogo bridge

Bring an agent-based model to life without writing a converter.

- **`construct.nls`**, a NetLogo include file: `construct-start`, `construct-record` each tick,
  `construct-finish` (also as a BehaviorSpace post-run). It records turtles, links, chosen
  variables and patch fields, with the model's name, settings and random seed.
- **`construct netlogo run.json --view network-time | space-time | field`** writes a valid
  construct directly from the recording, without a model; an agent may then add art direction.
  Every data part is `verified` against the recorded run.
- The build order is the tick, so the assembly replays the run; an optional replay control
  (`build --replay`) adds a tick scrubber.
- Examples: three of the best-known models in NetLogo's Models Library (Wolf Sheep Predation,
  Segregation, Flocking), each under its own licence like the Simple Viral Marketing example.
- If the bridge turns out harder than expected, it moves to v1.1 and v1.0 ships without it.

### Phase 5: who it is for

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

## Later

- A NetLogo extension (`extensions [construct]`), listed in NetLogo's extension manager, if the
  include file is adopted.
- Texture coordinates for every shape.
- An optional surface finish per part (paint, metal, glass…), as a contract addition.
- USD and USDZ export.
- Short guides for Godot and Unity.
