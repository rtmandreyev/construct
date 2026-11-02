# Adapters: a construct into anything

Construct does one thing: **research → express it deterministically → verify → build.** An agent researches a
thing and writes what it found as a scene: named parts at their real sizes, how each is known and from where,
how they assemble, open and move. Construct checks it and compiles it, the same scene always to the same bytes.
Everything after that is an adapter: the hologram page, glTF and OBJ, FreeCAD and STEP, prints, model kits, the
Godot joints. None of them changes the construct; each reads it and writes something else.

So you can write your own, without changing Construct: a format, an engine, a machine, a craft. This page says
what a construct holds, where to read it, and the few rules that keep an adapter honest. A working template is in
[hosts/adapter-template](../hosts/adapter-template/construct_parts.py).

## What a construct holds

| | in the scene (`scene.json`) | in the compiled geometry |
| --- | --- | --- |
| facts and sources | `facts[]` with their certainty, `sources[]` (kind, title, rights, reference) | `provenance` |
| parts | named, with a label and a role (mass, structure, detail…) | `parts[]`, with each copy's box in metres |
| shapes and sizes | a shape (box, tube, loft, extrude…) and its size in metres | triangles (`fills`), line segments (`lines`) |
| how each part is known | its size and its shape separately: verified, supplied by the user, traced, inferred, decorative | `certainty` and `certainty_axes` |
| assembly order | `stage` | `stages`, and a build phase on every vertex |
| what opens | `articulations`: hinge, turn, slide, lift, with pivot, axis and amount | `articulations`, `joints` |
| what moves on its own | `motion`: spin, swing, bob | `motions` |
| how it looks | `look` (how the light draws it); colour belongs to the renderer | `styles` |

The format is the stable [contract](../CONTRACT.md) (`construct/0.2`): a change bumps its version and is
recorded in the changelog. Lengths are metres; the frame is **Y up, the front facing +Z**.

## Where to read it

Start from whichever is nearest to what you write:

- **The glTF**, from any language. `construct export scene.json --out thing.glb` writes each part as a named
  node under its stage, with its role, certainty and source in `extras.construct`, the facts and sources on the
  root, and the animations `open` and `idle` ([EXPORT.md](EXPORT.md)). For engines and the web: three.js reads
  it with `GLTFLoader` and finds the extras in `userData`.
- **The compiled geometry**, for everything the contract has. In Python,
  `scene.compile_scene(studio.load("scene.json"), solid=True)` gives every part's surfaces, as the exporters use
  them. `construct build scene.json --out dir/` writes the hologram's own geometry as `dir/geometry.json`
  (only the surfaces the hologram shows), for other languages; its structure is published as a
  [JSON Schema](../construct_hologram/geometry.schema.json).
- **The scene**, when you want what is known rather than its shape: a parts list, an evidence sheet, a label.

## The template

```sh
PYTHONPATH=/path/to/construct python3 hosts/adapter-template/construct_parts.py scene.json out/
# wrote out/: 207 parts, 131 with a solid
```

It writes `parts.csv` (each part's name, role, stage, size in millimetres, how its size and its shape are known,
and its source) and one STL per part, in millimetres and Z up. It is about seventy lines and shows the four
things most adapters need:

- finding each triangle's part (a vertex's style, then the style's `part` field, by name, not by position);
- turning the frame (`scene.reframe(g, "z-up")` for the tools that want Z up);
- converting units on purpose (metres in, millimetres out);
- carrying how each part is known (`certainty_axes`) into what it writes.

Copy it and change what it writes. A test runs it on every change to Construct, so it stays current.

## Rules an adapter keeps

- **Carry the certainty along.** A part that was inferred stays inferred in what you write: in a name, a layer,
  a property or a colour. Never present a guess as a measurement. A construct is a reference model, not a
  survey or a set of as-built drawings, unless its parts say they were verified.
- **Keep your choices beside the scene, not in it.** Colours, finishes, a scale, a material, a mapping to your
  format's own names: a small file next to the scene, like the finish maps in [EXPORT.md](EXPORT.md). The scene
  stays what is known.
- **Say what you leave out.** A part drawn only in lines has no surface; a part too small for your format is
  lost. Name them, as `construct print` and `construct freecad` do.
- **Glass is known by its id** (a part whose id says glass, glazing or window), not by how the light draws it.
  In Python, `export.is_glass_name(part_id)`.
- **Check what you read.** Refuse a contract version you don't know, and keep the scene next to its geometry
  (the geometry's `scene_sha256` binds them).
- **Deterministic in, deterministic out.** The same construct should give the same file, so that a change in the
  output always means a change in the construct.

## Adapters someone could write

Each fits what a construct already holds:

- **Robotics (URDF, MJCF):** parts as links, articulations as joints with their axes and limits.
- **Laser cutting and CNC:** a panel's outline as a cut path, its thickness and its material from a map.
- **Wraps, decals and patterns:** true-size panels laid flat, to print at 1:1.
- **CAD and design tools** (Fusion, Onshape, Rhino): named bodies and their joints.
- **Voxel games** (Minecraft schematics): the solid on a grid, a block per material.
- **Documents:** an evidence sheet, a parts list with sources, a museum label.

## Sharing yours

An adapter is a script in your own repository that imports Construct (or reads its glTF or geometry, in any
language). Open an issue or a pull request and it can be listed here.
