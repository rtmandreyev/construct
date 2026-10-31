# Construct in Godot

`construct_joints.gd` joins a construct exported with `construct export scene.json --out car.glb --pieces glued`:
each hinged or sliding body hangs on the body named in its metadata, at the construct's pivot, about its axis,
with its travel. Copy it into the project and see [docs/GODOT.md](../../docs/GODOT.md).
