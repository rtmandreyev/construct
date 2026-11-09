# Construct for game developers

Props with named parts, real sizes and joints that work, and since 1.3 whole levels: constructs placed together at
real size, exported as one Godot map whose fixed body stays put while doors swing on their hinges. Every part keeps
its name in the engine, under its placement's, so a script finds `hero-car/left-door-skin` or a hotel's
`left-hotel-middle/r9-lobby-door-leaf` by name. Godot is
tested; Unity and Unreal take the same glTF, or an FBX made from it by Blender.

<p align="center">
  <a href="../../examples/worlds/rain-harbour/"><img src="../../examples/worlds/rain-harbour/hero.jpg" width="95%" alt="Rain Harbour in lines of light: a long wet street between stacked towers, cyan and magenta neon signs in English and Chinese on both sides, the yellow hero car at the front left, the skyline behind"></a>
</p>
<p align="center"><sub>Rain Harbour, a game level made in Hermes from one concept picture: 60 m of street, 21 constructs
placed 50 times. <a href="../../examples/worlds/rain-harbour/">How it was made</a>.</sub></p>

## A level from one picture: Rain Harbour

**The ask.** One message to GPT-6.1 Sol in Hermes Desktop with the Construct plugin, a concept picture attached:
one street block, about 60 m, with its pavements, kerbs and drains, the buildings on both sides and the skyline;
real sizes; separate pieces a level designer can reuse, "a building used twice is one construct placed twice"; neon
signs that say something real in English and Chinese, never the letter-noise of a generated picture; one hero car,
designed as a drivable game vehicle at a real sports car's size. The whole request is on
[its page](../../examples/worlds/rain-harbour/README.md#the-ask).

**What happened.** Sol planned the pieces and went straight on. Each missing construct was built by its own subagent
in masterpiece rounds, a fresh critic judging every round (up to 12; small repeated props fewer). They were placed at
real size with `construct_world`, then the whole world ran 12 rounds of its own against the picture. Final verdict
*good*, 21 of 27, with what the last critic still found written down.

**What you get.**

| | |
| --- | --- |
| Reuse | 21 constructs placed 50 times: the Service Tower and the Offset Balcony Hotel five times each, six bollards, two lamps |
| Signs | eight, in English and Chinese that say the same thing: RAIN HARBOUR / 雨港, NIGHT VOYAGE NOODLES / 夜航面馆, HARBOUR HOTEL / 港湾旅馆… |
| The car | AURIC, an original two-door coupé, 4.4 m long, 185 named parts: gullwing doors on hinges that lift 65°, wheels, tyres, hubs, brakes, tail lights |
| In each construct | its own folder under [constructs/](../../examples/worlds/rain-harbour/constructs/), its own scene, material map and round record, to place in a level of your own |

<p align="center">
  <img src="../../examples/worlds/rain-harbour/car.jpg" width="49%" alt="AURIC, the yellow hero car, close: its long bonnet, the doors' shut lines, the wheels and the tail lights">
  <img src="../../examples/worlds/rain-harbour/car-solid.jpg" width="49%" alt="AURIC in the solid view: yellow body, magenta tail lights, its wheels and rear wing">
</p>
<p align="center"><sub>AURIC in the light and in the solid view (S), where its own colours show.</sub></p>

**Into Godot, one command:**

```sh
construct export examples/worlds/rain-harbour/world.json --out level.glb --pieces glued
# wrote level.glb: a world of 50 constructs, 2081 parts, 329948 triangles, 239531 edges;
#   animations: open, open:hero-car/left-gullwing-open, open:hero-car/right-gullwing-open
```

About 16 seconds on a laptop, a 39 MB file. Each placement is a group named after it; the street and buildings are
the fixed body, the car's doors bodies of their own on hinges once
[`construct_joints.gd`](../../hosts/godot/construct_joints.gd) connects them (below).

**What it is not.** The car is drivable by design and size, not by script: its wheels are named parts of the body
(`left-front-wheel-rim`, `left-front-rubber-tyre`), ready for your own vehicle controller, not Godot wheels. Sizes
other than the 60 m street are designed, not surveyed, and each part says so (**P**). The critic's open notes are
kept: no wet road surface yet (the reflections read as rectangles), regular parallel walls where the picture has
asymmetric masses, and the hotel's three blade signs repeat.

## A prop

Any construct exports as a prop. Four ways, by what you need:

| You want | Command | What arrives |
| --- | --- | --- |
| few draw calls | `--merge --wire seams --materials map.json` | what does not move merged into one mesh per material, the design lines as thin tubes, a finish from a small map. The FJ62: 214 parts in about 37,000 triangles and 22 draw calls, its tailgate still opening |
| collisions | `--colliders` | a box collider per part (`<part>-convcolonly`), moving with its joint |
| a prop that holds together | `--pieces glued` | one rigid body for what stays put, one more for each door, lid or tailgate on its hinge; a building's body is static. The glued FJ62 settles within 2 cm and its tailgate falls open to 86°; the T1 Samba is ten bodies with all nine joints, joints inside joints too |
| a prop that breaks apart | `--pieces` | every piece a rigid body with convex shapes that settle rather than burst: the FJ62 falls apart onto the floor |

Every construct also carries an `open` animation (each joint in order, and `open:<joint>` for one) and an `idle`
one for its periodic motion (a spinning reel, a pendulum). Godot generates levels of detail on import.

<p align="center">
  <img src="../media/tompion-godot.gif" width="30%" alt="Tompion's clock in Godot: the hood door opens on the dial, the trunk door opens, the pendulum swings">
  <img src="../media/kestrel-godot.jpg" width="62%" alt="KESTREL's first build in Godot as a solid model: the cab and cradle, the truss, the tanks, the wings and the four engines">
</p>
<p align="center"><sub>Tompion's clock glued in Godot 4.7, its doors on their hinges and its pendulum swinging
(<a href="../END-TO-END.md#7-in-a-game-engine">how</a>), and KESTREL, an invented ice tug, with the Godot project its
agent wrote around it: <code>set_cradle_open(0…1)</code>, <code>set_radiators_folded(0…1)</code> and a docking
transform (<a href="invent-from-what-exists.md#7-joints-in-godot">how</a>).</sub></p>

## Try it in Godot

```sh
construct export scene.json --out car.glb --pieces glued --colliders
```

Drop `car.glb` and [`hosts/godot/construct_joints.gd`](../../hosts/godot/construct_joints.gd) into the project, then:

```gdscript
const ConstructJoints = preload("res://construct_joints.gd")

func _ready():
    ConstructJoints.connect_joints($Car)   # a HingeJoint3D or SliderJoint3D per joint, with its limits
```

A part whose name Godot would read as an import instruction (a `steering-wheel` would become a VehicleWheel3D) is
renamed `steering-wheel-part`; its real id stays in the node's metadata with its role, certainty and sources.

## In Hermes

A world's card in Hermes Desktop has **Arrange**: drag a construct onto any floor, roof or pavement, turn it, lift
it, duplicate it, then **Save** checks the level (overlaps, collisions, a door that cannot open) and rebuilds it with
no model turn. Its **Export** menu writes the glTF, the Godot game map, FBX, USD or OBJ. To make your own level, ask
for a world from your picture: [worlds, step by step](worlds-walkthrough.md#6-a-world-from-a-picture-in-masterpiece-mode)
says what a good request contains, from the two made this way.

## Unity, Unreal and others

- **Unity:** the glTF through Unity's glTFast package, or `--out level.fbx` (made from the glTF by Blender, when it
  is installed).
- **Unreal:** glTF, or the FBX.
- **USD:** `--out level.usd` for Omniverse or Houdini, `.usdz` for Apple's Reality tools, also through Blender.

They keep the named parts and the `open` animation; the collider boxes arrive as ordinary meshes named
`<part>-convcolonly`, to turn into colliders by hand. Unity and Unreal are not tested here; Godot 4.7 is.

## Good to know

- **A blockout or a prop, not a finished hero asset.** Shapes come from Construct's own vocabulary (boxes, lathes,
  lofts, tubes, extrusions); there are no textures, the texture coordinates are a box projection in metres, and
  joints are mechanical, with no skinned rig.
- **Masses** are in proportion to each piece's size, not real.
- **Budgets:** a construct exports up to 200,000 triangles, a world up to 2,000,000.
- **New things for your game** (a ship, a creature, a vehicle nobody has built): [new things from real ones](invent-from-what-exists.md)
  has the brief to copy. `construct params <archetype> --seed N` draws seeded variants of an archetype (a coupé, a
  guitar), the same seed the same object.

## Go deeper

- [Godot](../GODOT.md): glued and loose pieces, colliders, what was measured
- [3D export](../EXPORT.md): glTF, FBX, USD and OBJ, materials, triangle quality
- [Worlds](../WORLDS.md): placements, the world's audit, limits
- [Archetypes](../ARCHETYPES.md): templates and seeded variants
