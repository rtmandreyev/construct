# Construct for game developers

Props and blockouts with named parts, real dimensions and working joints, as glTF that Godot, Unity and Unreal open as
they are: a door that opens, a tailgate on its hinge, a car that holds together when it falls, or breaks apart when
you want it to. The line-light look is there too, for scanners, holograms and UI.

<p align="center"><a href="https://rtmandreyev.github.io/construct/examples/light-to-metal/"><img src="../media/pipeline-fj62.gif" width="60%" alt="The Toyota Land Cruiser FJ62: from lines of light to a plain model of named parts, then the finished model in paint, chrome and glass"></a></p>
<p align="center"><sub>The FJ62 exported unedited: the hologram, the plain model of named parts, the finished model from a material map.</sub></p>

## What you can do

- **A prop:** `--merge` gives few draw calls (the FJ62: about 21,000 triangles in 27), `--wire seams` the design lines
  as thin tubes, `--materials` a finish from a small colour map, `--colliders` a box per part.
- **A physics prop that holds together:** `--pieces glued` makes what stays put one body and each door, lid or
  tailgate one more on its own hinge. A building's body is static. All 28 gallery constructs export this way, with
  every joint made in Godot.
- **A prop that breaks apart:** `--pieces` makes every piece a rigid body with convex shapes that settle rather than
  burst.
- **Variants:** `params --seed` gives seeded variants of an archetype (a guitar, a bottle, a car).

## Try it in Godot

```sh
construct export scene.json --out car.glb --pieces glued
```

Drop `car.glb` and [`hosts/godot/construct_joints.gd`](../../hosts/godot/construct_joints.gd) into the project, then:

```gdscript
const ConstructJoints = preload("res://construct_joints.gd")

func _ready():
    ConstructJoints.connect_joints($Car)   # each door, lid or tailgate on its own hinge
```

## Go deeper

- [Godot](../GODOT.md): glued and loose pieces, colliders, names Godot would misread
- [3D export](../EXPORT.md): glTF and OBJ, materials, quality, levels of detail
- [Archetypes](../ARCHETYPES.md): templates and seeded variants
