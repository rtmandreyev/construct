# Joins a construct's glued pieces (construct export --pieces glued): each hinged or sliding body hangs
# on the body its extras name, at the construct's pivot, about its axis, with the construct's travel.
#
#   const ConstructJoints = preload("res://construct_joints.gd")
#   func _ready():
#       ConstructJoints.connect_joints($Car)    # once the construct is in the scene tree
extends RefCounted


static func connect_joints(root: Node3D) -> int:
	var bodies := {}
	for b in root.find_children("*", "PhysicsBody3D", true, false):   # a building's fixed body is static
		var c = b.get_meta("extras", {}).get("construct", {})
		if c.has("piece"):
			bodies[c["piece"]] = b
	# its pieces do not collide with one another: their shapes are close-fitting hulls that meet at every seam, and
	# touching they would shove each other apart; the joints keep them in place
	var all_bodies := bodies.values()
	for i in all_bodies.size():
		for k in range(i + 1, all_bodies.size()):
			all_bodies[i].add_collision_exception_with(all_bodies[k])
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
		if j.get("chain", []).size() > 1:   # joints inside joints: one joint with all their freedoms
			var made_chain := _chained(j["chain"], xf)
			joint = made_chain[0]
			basis = made_chain[1].basis
			pivot = made_chain[1].origin
		elif j["type"] == "hinge" or j["type"] == "turn":
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


# A piece moved by joints one inside another (a sunroof panel that slides back, then lifts; a cowl that lifts off,
# then turns): one Generic6DOFJoint3D, every freedom locked but the chain's own: each slide along its axis within
# its travel, a turn spinning free about its axis, a hinge swinging up to its angle. Its frame is set along the
# chain's first two directions, at the pivot of a turn or hinge in it, else at the first slide's.
static func _chained(chain: Array, xf: Transform3D) -> Array:
	var dirs := []
	for e in chain:
		var a: Vector3 = (xf.basis * Vector3(e["axis"][0], e["axis"][1], e["axis"][2])).normalized()
		if dirs.size() < 2 and dirs.all(func(d): return absf(a.dot(d)) < 0.999):
			dirs.append(a)
	var x: Vector3 = dirs[0]
	var y: Vector3 = dirs[1] if dirs.size() > 1 else (Vector3.UP if absf(x.y) < 0.9 else Vector3.RIGHT)
	y = (y - x * x.dot(y)).normalized()
	var frame := [x, y, x.cross(y)]
	var g := Generic6DOFJoint3D.new()   # its limits are all 0 to begin with: locked
	var origin = null
	var linear := [Vector2.ZERO, Vector2.ZERO, Vector2.ZERO]
	for e in chain:
		var a: Vector3 = (xf.basis * Vector3(e["axis"][0], e["axis"][1], e["axis"][2])).normalized()
		var k := 0
		for i in 3:
			if absf(frame[i].dot(a)) > absf(frame[k].dot(a)):
				k = i
		var amount := float(e["amount"]) * signf(frame[k].dot(a))
		var p: Vector3 = xf * Vector3(e["pivot"][0], e["pivot"][1], e["pivot"][2])
		var xyz: String = ["x", "y", "z"][k]
		if e["type"] == "slide" or e["type"] == "lift":
			linear[k] += Vector2(minf(0.0, amount), maxf(0.0, amount))
			if origin == null:
				origin = p
		else:
			origin = p
			if e["type"] == "turn":
				g.call("set_flag_" + xyz, Generic6DOFJoint3D.FLAG_ENABLE_ANGULAR_LIMIT, false)
			else:
				var rad := deg_to_rad(absf(amount)) if e.get("unit", "deg") == "deg" else absf(amount)
				g.call("set_param_" + xyz, Generic6DOFJoint3D.PARAM_ANGULAR_LOWER_LIMIT, -rad)
				g.call("set_param_" + xyz, Generic6DOFJoint3D.PARAM_ANGULAR_UPPER_LIMIT, rad)
	for k in 3:
		var xyz: String = ["x", "y", "z"][k]
		g.call("set_param_" + xyz, Generic6DOFJoint3D.PARAM_LINEAR_LOWER_LIMIT, linear[k].x)
		g.call("set_param_" + xyz, Generic6DOFJoint3D.PARAM_LINEAR_UPPER_LIMIT, linear[k].y)
	return [g, Transform3D(Basis(frame[0], frame[1], frame[2]), origin)]
