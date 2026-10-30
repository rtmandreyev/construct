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
| `--colliders` | a StaticBody3D with a box CollisionShape3D around each part's surfaces (`<part>-convcolonly`); a moving part's box moves with its joint |
| `--pieces` | each part with surfaces a RigidBody3D (`<part>-rigid`) with a convex shape from its mesh: give the scene a floor and the object falls apart |
| sizes | metres, Y up, as Godot expects |

`--pieces` is for break-apart and assembly mechanics. A construct's parts touch and overlap a little,
so their shapes start out pressed together and push apart hard the moment physics runs: the object
bursts rather than sags. Freeze the bodies (`freeze = true`) until the moment it should come apart, or
lower their mass. The tests run this in Godot: every piece of the CD case moves.

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
