# Godot

A construct comes into Godot as a glTF file with its parts named, its joints as an animation, and, if
you ask, a collider per part or every part a body of its own. Tested with Godot 4.7.

```sh
construct export scene.json --out car.glb --merge --wire seams --colliders   # a prop: few draw calls, collisions
construct export scene.json --out car.glb --pieces                           # a prop that breaks apart
```

Drop the `.glb` into the project (`res://`) and Godot imports it; drag it into a scene.

## What arrives

| In the construct | In Godot |
| --- | --- |
| a part | a node named with the part's id; with `--merge`, the parts that do not move become one mesh per material and the parts that move keep their own nodes |
| its joints (doors, lids, a tailgate) | the `open` animation in an AnimationPlayer; each joint is a pivot node, so a script can turn it too |
| periodic motion (a spinning reel) | the `idle` animation |
| `--colliders` | a StaticBody3D with a box CollisionShape3D around each part's surfaces (`<part>-convcolonly`); a moving part's box moves with its joint (static boxes may overlap; they never push each other) |
| `--pieces` | the object as the pieces it would break into, each a RigidBody3D with several convex shapes: give the scene a floor and it falls apart |
| sizes | metres, Y up, as Godot expects |

`--pieces` is for break-apart and assembly mechanics. The pieces are made to settle, not burst:

- **Every copy is a piece:** a mirrored tyre or a repeated window is a body of its own, not one shape
  spanning the gap.
- **Shapes follow the surface:** each connected piece of a part is a convex shape, and a large one (a
  car's body shell) is a skin of convex patches with a little thickness inward, so a hollow body does not
  fill its cabin.
- **Interlocked parts are one piece:** parts whose shapes still meet when the smaller is shrunk to 70%
  (a rim in its tyre, an axle through its hubs, a lamp in its bezel) are one body, an assembly, each part
  keeping its own named mesh inside it. Parts that move (a door) stay apart.
- **Shapes are pulled in** by 0.3% of the object, so parts that only touch start apart.

Measured in Godot 4.7 on the FJ62: 47 pieces with 17 pairs still touching at rest (one convex hull per
part had 249), and released on a floor, none travels more than 1.5 m in two seconds. The bodies and
shapes are written with the glTF physics extensions `OMI_physics_body` and `OMI_physics_shape`, which
Godot imports; an engine that does not read them gets the pieces as named nodes and meshes. Masses are in
proportion to each piece's size, not real. The tests run this in Godot.

## Names Godot would misread

Godot reads some name endings as import instructions: a node ending in `-wheel` becomes a
VehicleWheel3D, `-col` a collision body, `-rigid` a rigid body. A part whose id ends that way (a
`steering-wheel`) is named with `-part` after it (`steering-wheel-part`); its real id stays in the node's
`extras` (`construct.id`), with its role, certainty and sources.

## Levels of detail

Godot makes levels of detail for every imported mesh itself (Import, Meshes, Generate LODs, on by
default), so Construct does not write its own.

## Other engines

The same file opens in Unity (glTFast) and Unreal. They keep the named parts and the `open` animation;
the collider boxes arrive as ordinary meshes named `<part>-convcolonly`, which you can turn into colliders
by hand. Engine packages that do this for you are on the [roadmap](ROADMAP.md).
