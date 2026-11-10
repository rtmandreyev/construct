# Construct for Blender

An add-on (a Blender extension, for Blender 4.2 and later) that imports a construct as a 3D model,
with its named parts, its joints and its assembly, and three controls that move between the
hologram and the solid model.

## Install

```sh
python3 scripts/build_blender_extension.py        # writes dist/construct-blender-<version>.zip
```

In Blender: **Edit → Preferences → Get Extensions → Install from Disk** and choose the zip, or drag
the zip into Blender's window. The zip carries the part of Construct it needs (the scene compiler
and the 3D export, Python standard library only), so nothing else has to be installed.

## Use

**File → Import → Construct (.json, .glb)** reads:

- a construct scene (`scene.json`) or a parameter document: the add-on compiles and exports it
  itself;
- a world (`world.json`): the constructs it places, found beside it (its own `constructs/` folder, or the
  examples in a checkout of Construct), each placement a group; a world whose constructs it cannot find
  asks for its exported `.glb` instead;
- a `.glb` written by `construct export`.

The construct arrives as one root object (its name is the construct's id) with its stages and
named parts below it. Select it and open the **Construct** tab in the sidebar (N):

| Control | What it does |
| --- | --- |
| **Build** (0–1) | the assembly: every vertex appears at its build phase, behind a bright front |
| **Open** (0–1) | every joint (hinges, turns, slides, lifts), in its order groups |
| **Light ↔ Metal** (0–1) | 0 is the hologram: lines of light over dark glass with a violet rim; 1 is the solid model, its lines as dark seams |
| **Plain ↔ Finished** (0–1) | 0 is the plain model in clay; 1 its materials from a material map (paint, chrome, glass, wood, brushed metal, rubber, plastic, light) |
| **Lines** | the line art's thickness, in metres |
| **Keyframe a Reveal** | keys an assembly in light, the turn to metal, the finish and the opening, from the current frame |

The controls are custom properties on the root object, driving the joints, materials and line art
through ordinary drivers, so a saved .blend keeps working without the add-on. Every part keeps its
role, certainty and source as custom properties (`construct`), and periodic motion (a spinning
reel) stays as the `idle` action.

Import options: a material map (by default the construct's own beside its scene: `<scene>.materials.json`,
`scene.materials.json`, `maps/finish.json` or `materials.json`; see
[3D export](../../docs/EXPORT.md#a-material-map-the-finished-model)), the line thickness,
whether the construct starts as metal or light, and whether to keep the file's own `open` actions
beside the Open control.

### A NetLogo run as a film

**File → Import → NetLogo Run (.jsonl)** reads a recording from [Construct for
NetLogo](../netlogo/README.md) (`construct:run`, or `construct.nls`) and plays it as a film: every
turtle at every tick as a small glowing arrowhead in its own NetLogo colour, pointing where it
goes, with a light trail behind it; each link as a thin line of light between its two turtles while
the recording has it; the patches as a floor of cells in their recorded colours; the world's edge as a
line of light (a box, for a NetLogo 3D
run, whose turtles fly at their own heights); bloom; and a camera that orbits slowly. The scene's
frames span the run at 30 ticks a second, in a steady light, without sound.

It draws the recording itself, not a construct of it, so a run of any length and any number of
turtles loses nothing; between two records a turtle moves on a straight line (never across a wrap
of the world), and the trail stops where the turtle wrapped. A frame handler moves the turtles as
the scene plays or renders; the objects keep the recording's path, so a saved .blend replays it
wherever the add-on is installed. Import options: the trail's length in seconds, and the camera.

Headless, to a film, Construct's command line runs Blender for you:

```sh
construct netlogo-film flocking-run.jsonl --out flocking.mp4 --size 1920x1080
```

`--blend` saves the scene instead (or as well); `--from` and `--seconds` render a part of it,
`--samples` sets EEVEE's quality. In NetLogo, `(construct:draw "auto" "film" true)` writes
`film.blend` beside the construct. (Inside Blender, `scripts/run_film.py` does the same.)

## How it works

The add-on uses Blender's own glTF importer for the parts, the stages and the motion, then:

- turns each articulation's pivot into drivers on the **Open** control (axis-angle rotations for
  hinges and turns, locations for slides and lifts), matching the compiler's own joint maths;
- moves each part's line art into its own object, made into thin tubes by a geometry-nodes
  modifier that keeps each vertex's build phase;
- rebuilds the materials: each surface blends from clay to its finished material by **Finish**
  (wood grain, brushed streaks and rubber's tooth are procedural, so no texture coordinates are
  needed), is revealed by **Build** through the `_PHASE` attribute, glows at the build front, and
  turns to dark glass toward **Light**; the line art is light in the hologram and a dark seam on
  the metal. Only design lines (parts drawn as lines: door seams, creases, window outlines) stay as
  seams: a part's construction lines, the edges of its own surfaces, fade as it turns solid, faint
  on the plain model and gone on the finished one.

## Licence

GPL-3.0-or-later ([LICENSE](LICENSE)), as Blender's extensions platform requires of every add-on:
an add-on runs inside Blender, which is GPL. The rest of Construct is Apache-2.0. The zip bundles
the part of Construct the add-on needs (the scene compiler and the 3D export) with its Apache-2.0
licence and NOTICE beside it; Apache-2.0 code may be included in a GPL-3.0 work. What you make with the add-on (your imported
models, your .blend files and your renders) is yours, under either licence.
