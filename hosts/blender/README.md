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
- a `.glb` written by `construct export`.

The construct arrives as one root object (its name is the construct's id) with its stages and
named parts below it. Select it and open the **Construct** tab in the sidebar (N):

| Control | What it does |
| --- | --- |
| **Build** (0–1) | the assembly: every vertex appears at its build phase, behind a bright front |
| **Open** (0–1) | every joint (hinges, turns, slides, lifts), in its order groups |
| **Light ↔ Metal** (0–1) | 0 is the hologram: lines of light over dark glass with a violet rim; 1 is the solid model, its lines as dark seams |
| **Lines** | the line art's thickness, in metres |
| **Keyframe a Reveal** | keys an assembly in light, the turn to metal and the opening, from the current frame |

The controls are custom properties on the root object, driving the joints, materials and line art
through ordinary drivers, so a saved .blend keeps working without the add-on. Every part keeps its
role, certainty and source as custom properties (`construct`), and periodic motion (a spinning
reel) stays as the `idle` action.

Import options: the line thickness, whether the construct starts as metal or light, and whether to
keep the file's own `open` actions beside the Open control.

## How it works

The add-on uses Blender's own glTF importer for the parts, the stages and the motion, then:

- turns each articulation's pivot into drivers on the **Open** control (axis-angle rotations for
  hinges and turns, locations for slides and lifts), matching the compiler's own joint maths;
- moves each part's line art into its own object, made into thin tubes by a geometry-nodes
  modifier that keeps each vertex's build phase;
- rebuilds the materials: each surface keeps its colour, is revealed by **Build** through the
  `_PHASE` attribute, glows at the build front, and turns to dark glass toward **Light**; the line art
  is light in the hologram and a dark seam on the metal.

## Licence

MIT, like the rest of Construct. Blender's extensions platform (extensions.blender.org) lists only
add-ons under GPL-3.0-or-later; listing it there would mean releasing this folder under that
licence as well.
