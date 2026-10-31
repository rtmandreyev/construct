# Joins a construct's glued pieces (construct export --pieces glued): each hinged or sliding body hangs
# on the body its extras name, at the construct's pivot, about its axis, with the construct's travel.
#
#   const ConstructJoints = preload("res://construct_joints.gd")
#   func _ready():
#       ConstructJoints.connect_joints($Car)    # once the construct is in the scene tree
extends RefCounted


static func connect_joints(root: Node3D) -> int:
	var bodies := {}
	for b in root.find_children("*", "RigidBody3D", true, false):
		var c = b.get_meta("extras", {}).get("construct", {})
		if c.has("piece"):
			bodies[c["piece"]] = b
	var made := 0
	for b in bodies.values():
		var j = b.get_meta("extras", {}).get("construct", {}).get("joint")
		if j == null or not bodies.has(j["to"]):
			continue
		var xf: Transform3D = root.global_transform   # pivot and axis are in the construct's own frame
		var pivot: Vector3 = xf * Vector3(j["pivot"][0], j["pivot"][1], j["pivot"][2])
		var axis: Vector3 = (xf.basis * Vector3(j["axis"][0], j["axis"][1], j["axis"][2])).normalized()
		var amount := float(j["amount"])
		var joint: Joint3D
		var basis: Basis
		if j["type"] == "hinge" or j["type"] == "turn":
			var h := HingeJoint3D.new()   # turns about its own Z axis
			if j["type"] == "hinge":
				var rad := deg_to_rad(amount) if j.get("unit", "deg") == "deg" else amount
				h.set_flag(HingeJoint3D.FLAG_USE_LIMIT, true)
				h.set_param(HingeJoint3D.PARAM_LIMIT_LOWER, minf(0.0, rad))
				h.set_param(HingeJoint3D.PARAM_LIMIT_UPPER, maxf(0.0, rad))
			var up := Vector3.UP if absf(axis.y) < 0.9 else Vector3.RIGHT
			basis = Basis.looking_at(axis, up)   # its -Z along the axis: the opening is its positive angle (Godot 4.7, measured)
			joint = h
		elif j["type"] == "slide" or j["type"] == "lift":
			var s := SliderJoint3D.new()   # slides along its own X axis
			s.set_param(SliderJoint3D.PARAM_LINEAR_LIMIT_LOWER, minf(0.0, amount))
			s.set_param(SliderJoint3D.PARAM_LINEAR_LIMIT_UPPER, maxf(0.0, amount))
			var other := Vector3.UP if absf(axis.y) < 0.9 else Vector3.RIGHT
			var z := axis.cross(other).normalized()
			basis = Basis(axis, z.cross(axis), z)
			joint = s
		else:
			continue
		root.add_child(joint)
		joint.global_transform = Transform3D(basis, pivot)
		joint.node_a = joint.get_path_to(bodies[j["to"]])
		joint.node_b = joint.get_path_to(b)
		made += 1
	return made
