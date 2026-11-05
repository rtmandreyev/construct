---
title: Use it in a game engine
summary: A prop with named parts, real sizes and working joints, as glTF for Godot, Unity or Unreal: doors that open, a car that holds together.
group: Makers and creators
example: toyota-land-cruiser-fj62
time: about 15 minutes
status: ready
---

## Prompt

Teach me to take a construct into a game engine, step by step, one step at a time and waiting for me between steps. Follow the Construct tutorial: skill_view("construct:construct", file_path="tutorials/04-game-engine.md"). Start by showing me the Toyota Land Cruiser FJ62 example.

## Steps

1. **Show the example.** `construct_start(example="toyota-land-cruiser-fj62")` and `construct_build`; MEDIA line in
   the reply. Ask the user to replay the opening: the doors and tailgate are articulations, and they leave as joints.
   `construct_inspect` lists the articulations and their travel.
2. **A prop.** `construct_export(project=<id>, format="glb", merge=true, wire="seams", colliders=true)`: few draw
   calls, the design lines as thin seams, a box collider per part. Report the triangle count from the summary.
   Colours only if the user names them, as `materials` (part ids or patterns to colour and finish).
3. **A physics prop that holds together.** `construct_export(format="glb", pieces="glued")`: what stays put is one
   body, and each door, lid or tailgate one more on its own hinge, its joint in the file. In Godot, drop the `.glb`
   and Construct's `construct_joints.gd` (in the Construct repository, `hosts/godot/`) into the project, then:
   ```gdscript
   const ConstructJoints = preload("res://construct_joints.gd")
   func _ready():
       ConstructJoints.connect_joints($Car)
   ```
4. **A prop that breaks apart.** `construct_export(format="glb", pieces="loose")`: every piece a rigid body with
   convex shapes, made to settle rather than burst. `pose="open"` rests it with its doors open.
5. **Variants.** Seeded variants of an archetype: `construct_start(archetype="vehicle", variant="sedan", seed=3)`
   (also guitars, bottles, cans), check, build, export. Each seed gives sizes drawn near the standard.
6. **The user's own prop.** Ask what they need (the object, its size, what opens), then author it as SKILL.md says,
   with joints as articulations; `construct_check` until clean; export as in step 3 or 4.

**What next:** `09-invent-from-real-designs.md` (ships, vehicles and creatures that do not exist), `05-blender.md`.

## Notes

- Correctly sized named parts with working joints, without textures: a blockout or a prop, not a hero asset.
- A `no-surface` audit warning names a part drawn only as lines, which would be missing in the engine: give it a
  solid shape.
- Unity and Unreal open the same glTF; the joint helper script is for Godot.
