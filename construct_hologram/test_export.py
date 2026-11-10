"""3D export: the .glb is valid glTF 2.0, its joints and motions land where the compiler puts them, the
OBJ is well formed, and the hologram's own compile is unchanged."""

import base64
import csv
import json
import math
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from . import audit, cli, export, scene, studio

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE / "examples" / "v2"
ROOT = HERE.parent
TOL = 2e-4   # metres: float32 vertices and transforms


def load(name):
    return studio.load(str(EXAMPLES / (name + ".json")))


def load_example(name):
    return studio.load(str(ROOT / "examples" / name / "scene.json"))


def glb_of(sc, **kw):
    out, _ = export.render(sc, "glb", **kw)
    return export.read_glb(out["glb"])


GODOT_GLUE = """extends SceneTree
const ConstructJoints = preload("res://construct_joints.gd")
var bodies = []
var start = {}
var gate
var gate_basis
var frame = 0
var made = 0
func _initialize():
	var root3d = Node3D.new()
	get_root().add_child(root3d)
	var floor = StaticBody3D.new()
	var fs = CollisionShape3D.new()
	fs.shape = WorldBoundaryShape3D.new()
	floor.add_child(fs)
	root3d.add_child(floor)
	var inst = load(OS.get_cmdline_user_args()[0]).instantiate()
	root3d.add_child(inst)
	for b in inst.find_children("*", "RigidBody3D", true, false):
		bodies.append(b)
func _physics_process(_d):
	frame += 1
	if frame == 1:
		made = ConstructJoints.connect_joints(get_root().get_child(0).get_child(1))
		for b in bodies:
			start[b] = b.global_transform
			if b.get_meta("extras", {}).get("construct", {}).has("joint"):
				gate = b
	if frame == 240:
		var far = 0.0
		for b in bodies:
			if b != gate:
				far = max(far, b.global_position.distance_to(start[b].origin))
		var rel_now = gate.global_transform.basis
		var rel0 = start[gate].basis
		var turn = rad_to_deg((rel0.inverse() * rel_now).get_rotation_quaternion().get_angle())
		print("RESULT ", JSON.stringify({"bodies": bodies.size(), "joints": made, "far": far, "gate_turn": turn}))
		quit()
	return false
"""

GODOT_CHECK = """extends SceneTree

func _initialize() -> void:
	var floor := StaticBody3D.new()
	var shape := CollisionShape3D.new()
	shape.shape = WorldBoundaryShape3D.new()
	floor.add_child(shape)
	root.add_child(floor)
	var c := (load("res://c.glb") as PackedScene).instantiate()
	var p := (load("res://p.glb") as PackedScene).instantiate()
	root.add_child(p)
	await physics_frame
	var bodies := p.find_children("*", "RigidBody3D", true, false)
	var start := {}
	for b in bodies:
		start[b] = b.global_position
	for i in 60:
		await physics_frame
	var moved := 0
	var far := 0.0
	var span := 0.0
	for b in bodies:
		var d: float = (b.global_position - start[b]).length()
		far = max(far, d)
		if d > 0.001:
			moved += 1
		for o in bodies:
			span = max(span, (start[o] - start[b]).length())
	var anims := []
	for ap in c.find_children("*", "AnimationPlayer", true, false):
		anims = ap.get_animation_list()
	print("RESULT " + JSON.stringify({"static": c.find_children("*", "StaticBody3D", true, false).size(),
		"rigid": bodies.size(), "moved": moved, "far": far, "span": span, "animations": anims,
		"shapes": p.find_children("*", "CollisionShape3D", true, false).size()}))
	quit()
"""


# ---------------------------------------------------------------------------- a small glTF reader

COMPONENTS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
CTYPES = {5126: "f", 5125: "I", 5123: "H"}


def accessor(doc, binary, i):
    a = doc["accessors"][i]
    v = doc["bufferViews"][a["bufferView"]]
    n = COMPONENTS[a["type"]]
    vals = struct.unpack_from("<%d%s" % (a["count"] * n, CTYPES[a["componentType"]]), binary, v["byteOffset"])
    return [vals[k:k + n] if n > 1 else vals[k] for k in range(0, len(vals), n)]


def qmat(q):
    x, y, z, w = q
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]


def slerp(a, b, f):
    d = sum(a[k] * b[k] for k in range(4))
    if d < 0:
        b, d = [-x for x in b], -d
    if d > 0.9995:
        r = [a[k] + f * (b[k] - a[k]) for k in range(4)]
    else:
        th = math.acos(d)
        s0, s1 = math.sin((1 - f) * th) / math.sin(th), math.sin(f * th) / math.sin(th)
        r = [s0 * a[k] + s1 * b[k] for k in range(4)]
    n = math.sqrt(sum(x * x for x in r))
    return [x / n for x in r]


def sample(doc, binary, anim, t):
    """{node: {"rotation"|"translation": value}} of one animation at time t (LINEAR, clamped)."""
    out = {}
    for ch in anim["channels"]:
        s = anim["samplers"][ch["sampler"]]
        times, vals = accessor(doc, binary, s["input"]), accessor(doc, binary, s["output"])
        if t <= times[0]:
            v = vals[0]
        elif t >= times[-1]:
            v = vals[-1]
        else:
            k = next(i for i in range(len(times) - 1) if times[i] <= t <= times[i + 1])
            f = (t - times[k]) / (times[k + 1] - times[k])
            v = slerp(vals[k], vals[k + 1], f) if ch["target"]["path"] == "rotation" else \
                [vals[k][j] + f * (vals[k + 1][j] - vals[k][j]) for j in range(3)]
        out.setdefault(ch["target"]["node"], {})[ch["target"]["path"]] = list(v)
    return out


def world_points(doc, binary, node_i, pose):
    """Every vertex of every mesh under node_i, in world space, with the pose's overrides."""
    parent = {c: i for i, n in enumerate(doc["nodes"]) for c in n.get("children", [])}

    def apply(i, p):
        n = doc["nodes"][i]
        o = pose.get(i, {})
        r = o.get("rotation", n.get("rotation", [0, 0, 0, 1]))
        t = o.get("translation", n.get("translation", [0, 0, 0]))
        m = qmat(r)
        return tuple(sum(m[a][b] * p[b] for b in range(3)) + t[a] for a in range(3))

    pts = []

    def walk(i):
        n = doc["nodes"][i]
        if "mesh" in n:
            for prim in doc["meshes"][n["mesh"]]["primitives"]:
                for p in accessor(doc, binary, prim["attributes"]["POSITION"]):
                    q, j = p, i
                    while j is not None:
                        q = apply(j, q)
                        j = parent.get(j)
                    pts.append(q)
        for c in n.get("children", []):
            walk(c)

    walk(node_i)
    return pts


def node_named(doc, name):
    return next(i for i, n in enumerate(doc["nodes"]) if n.get("name") == name)


# ---------------------------------------------------------------------------- tests

class Structure(unittest.TestCase):
    """What a glTF validator checks first: the container, the references, the ranges."""

    def check(self, doc, binary):
        self.assertEqual(doc["asset"]["version"], "2.0")
        self.assertEqual(len(binary) % 4, 0)
        for v in doc["bufferViews"]:
            self.assertEqual(v["byteOffset"] % 4, 0)
            self.assertLessEqual(v["byteOffset"] + v["byteLength"], doc["buffers"][0]["byteLength"])
        for i, a in enumerate(doc["accessors"]):
            v = doc["bufferViews"][a["bufferView"]]
            size = {5126: 4, 5125: 4, 5123: 2}[a["componentType"]] * COMPONENTS[a["type"]] * a["count"]
            self.assertLessEqual(size, v["byteLength"])
        parents = {}
        for i, n in enumerate(doc["nodes"]):
            self.assertNotEqual(n.get("children"), [], "node %d: an empty array is invalid glTF" % i)
            for c in n.get("children", []):
                self.assertNotIn(c, parents, "a node has one parent")
                parents[c] = i
            if "mesh" in n:
                self.assertLess(n["mesh"], len(doc["meshes"]))
            if "rotation" in n:
                self.assertAlmostEqual(sum(x * x for x in n["rotation"]), 1.0, places=5)
        roots = doc["scenes"][0]["nodes"]
        self.assertEqual([i for i in range(len(doc["nodes"])) if i not in parents], roots)
        for m in doc["meshes"]:
            for p in m["primitives"]:
                pos = doc["accessors"][p["attributes"]["POSITION"]]
                self.assertIn("min", pos)
                self.assertIn("max", pos)
                pts = accessor(doc, binary, p["attributes"]["POSITION"])
                for k in range(3):
                    self.assertAlmostEqual(min(q[k] for q in pts), pos["min"][k], places=4)
                    self.assertAlmostEqual(max(q[k] for q in pts), pos["max"][k], places=4)
                idx = accessor(doc, binary, p["indices"])
                self.assertLess(max(idx), pos["count"])
                self.assertEqual(len(idx) % {4: 3, 1: 2, 0: 1}[p["mode"]], 0)
                ph = accessor(doc, binary, p["attributes"]["_PHASE"])
                self.assertTrue(all(0.0 <= x <= 1.0 for x in ph))
                if "NORMAL" in p["attributes"]:
                    for nrm in accessor(doc, binary, p["attributes"]["NORMAL"]):
                        self.assertAlmostEqual(sum(x * x for x in nrm), 1.0, places=3)
                self.assertLess(p["material"], len(doc["materials"]))
        for a in doc.get("animations", []):
            for s in a["samplers"]:
                times = accessor(doc, binary, s["input"])
                self.assertTrue(all(times[k] < times[k + 1] for k in range(len(times) - 1)), a["name"])
                self.assertEqual(len(accessor(doc, binary, s["output"])), len(times))
            for ch in a["channels"]:
                self.assertLess(ch["target"]["node"], len(doc["nodes"]))

    def test_examples_are_valid(self):
        for name in ("cd", "open-reel", "leica-m3", "lighthouse", "castle"):
            with self.subTest(name):
                self.check(*glb_of(load(name)))

    def test_wire_modes(self):
        sc = load("lighthouse")
        g = scene.compile_scene(sc, solid=True)
        modes = lambda doc: [p["mode"] for m in doc["meshes"] for p in m["primitives"]]
        doc, binary = glb_of(sc)
        edges = sum(len(accessor(doc, binary, p["indices"])) // 2 for m in doc["meshes"] for p in m["primitives"]
                    if p["mode"] == 1)
        self.assertEqual(edges, g["counts"]["lines"])
        doc, binary = glb_of(sc, wire="tubes")
        self.check(doc, binary)
        self.assertNotIn(1, modes(doc))
        doc, _ = glb_of(sc, wire="none")
        self.assertNotIn(1, modes(doc))

    def test_deterministic(self):
        a, _ = export.render(load("cd"), "glb")
        b, _ = export.render(load("cd"), "glb")
        self.assertEqual(a["glb"], b["glb"])


class Parts(unittest.TestCase):
    def test_every_part_is_a_named_node_with_its_provenance(self):
        sc = load("cd")
        g = scene.compile_scene(sc, solid=True)
        doc, _ = glb_of(sc)
        names = {n.get("name"): n for n in doc["nodes"]}
        for p in g["parts"]:
            self.assertIn(p["id"], names)
            ex = names[p["id"]]["extras"]["construct"]
            self.assertEqual((ex["role"], ex["certainty"], ex["stage"]), (p["role"], p["certainty"], p["stage"]))
        root = doc["nodes"][doc["scenes"][0]["nodes"][0]]["extras"]["construct"]
        self.assertEqual(root["scene_sha256"], g["scene_sha256"])
        self.assertEqual(root["contract"], "construct/0.2")
        self.assertEqual(len(root["facts"]), len(sc["facts"]))

    def test_solid_keeps_every_surface_and_the_hologram_is_unchanged(self):
        sc = load("castle")
        holo, solid = scene.compile_scene(sc), scene.compile_scene(sc, solid=True)
        self.assertEqual(holo, scene.compile_scene(sc, solid=False))
        self.assertGreater(solid["counts"]["triangles"], holo["counts"]["triangles"])
        strip = lambda ln: [ln[i:i + 6] + ln[i + 7:i + 9] for i in range(0, len(ln), 9)]   # styles renumber
        self.assertEqual(strip(solid["lines"]), strip(holo["lines"]))

    def test_build_phase_travels_with_the_vertices(self):
        sc = load("lighthouse")
        g = scene.compile_scene(sc, solid=True)
        doc, binary = glb_of(sc)
        have = {x for m in doc["meshes"] for p in m["primitives"]
                for x in accessor(doc, binary, p["attributes"]["_PHASE"])}
        f32 = lambda v: struct.unpack("<f", struct.pack("<f", v))[0]
        want = {f32(g["fills"][i + 4]) for i in range(0, len(g["fills"]), 5)}
        self.assertTrue(want <= have)

    def test_material_map(self):
        sc = load("cd")
        first = scene.compile_scene(sc, solid=True)["parts"][0]["id"]
        doc, _ = glb_of(sc, materials={"materials": [{"parts": [first], "name": "black glass", "color": "#101012",
                                                      "metallic": 0.1, "roughness": 0.05}]})
        n = doc["nodes"][node_named(doc, first)]
        mesh = doc["meshes"][n["mesh"] if "mesh" in n else doc["nodes"][n["children"][-1]]["mesh"]]
        self.assertIn("black glass", [doc["materials"][p["material"]]["name"] for p in mesh["primitives"]])
        for bad in ({"materials": [{"color": "#fff"}]}, {"materials": [{"parts": "x", "color": "red"}]},
                    {"materials": [{"parts": "x", "roughness": 2}]}, {"nope": []}):
            with self.assertRaises(export.ExportError):
                glb_of(sc, materials=bad)


class Finishes(unittest.TestCase):
    def test_finishes_become_standard_gltf_materials(self):
        sc = load("cd")
        ids = [p["id"] for p in sc["parts"] if scene._local_mesh(p["shape"], 0).tris]   # parts with a surface
        rules = [{"parts": ids[0], "name": "glass", "color": "#d8e2e8", "finish": "glass"},
                 {"parts": ids[1], "name": "paint", "color": "#99191d", "finish": "paint"},
                 {"parts": ids[2], "name": "lamp", "color": "#fff3dc", "finish": "light"},
                 {"parts": ids[3], "name": "chrome", "color": "#dddddd", "finish": "chrome", "roughness": 0.1}]
        doc, _ = glb_of(sc, materials={"materials": rules})
        mats = {m["name"]: m for m in doc["materials"]}
        self.assertEqual(mats["glass"]["extensions"]["KHR_materials_transmission"]["transmissionFactor"], 0.92)
        self.assertIn("KHR_materials_ior", mats["glass"]["extensions"])
        self.assertEqual(mats["paint"]["extensions"]["KHR_materials_clearcoat"]["clearcoatFactor"], 1.0)
        self.assertEqual(mats["lamp"]["extensions"]["KHR_materials_emissive_strength"]["emissiveStrength"], 4.0)
        self.assertEqual(mats["chrome"]["pbrMetallicRoughness"]["metallicFactor"], 1.0)
        self.assertEqual(mats["chrome"]["pbrMetallicRoughness"]["roughnessFactor"], 0.1)   # the rule's own wins
        self.assertEqual(mats["glass"]["extras"]["construct"]["finish"], "glass")
        for e in ("KHR_materials_transmission", "KHR_materials_clearcoat", "KHR_materials_emissive_strength"):
            self.assertIn(e, doc["extensionsUsed"])
        with self.assertRaises(export.ExportError):
            glb_of(sc, materials={"materials": [{"parts": "x", "finish": "velvet"}]})

    def test_a_construct_finishes_with_its_own_map_by_default(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "maps").mkdir()
            (d / "scene.json").write_text("{}", encoding="utf-8")
            self.assertIsNone(export.map_beside(d / "scene.json"))
            (d / "maps" / "finish.json").write_text("{}", encoding="utf-8")
            self.assertEqual(export.map_beside(d / "scene.json"), d / "maps" / "finish.json")
            (d / "scene.materials.json").write_text("{}", encoding="utf-8")   # the plugin's name comes first
            self.assertEqual(export.map_beside(d / "scene.json"), d / "scene.materials.json")
        # `construct export` with no --materials uses the gallery's own map (the Vespa's), not the role greys
        with tempfile.TemporaryDirectory() as d:
            out = Path(d, "v.glb")
            from construct_hologram import cli
            self.assertEqual(cli.main(["export", str(ROOT / "examples" / "vespa-gs150" / "scene.json"), "--out", str(out)]), 0)
            names = {m.get("name", "") for m in export.read_glb(out.read_bytes())[0]["materials"]}
            self.assertFalse(any(n.startswith("construct:mass") for n in names), names)

    def test_tyres_are_rubber_and_chrome_is_chrome_without_a_map(self):
        self.assertEqual(export.name_finish("front-left-tyre"), "rubber")
        self.assertEqual(export.name_finish("chrome-bumper"), "chrome")
        self.assertIsNone(export.name_finish("body-left"))
        sc = load("open-reel")
        sc["parts"][0] = dict(sc["parts"][0], id="reel-tyre")
        doc, _ = glb_of(sc)
        mat = next(m for m in doc["materials"] if m["name"].startswith("construct:rubber"))
        self.assertGreater(mat["pbrMetallicRoughness"]["roughnessFactor"], 0.9)

    def test_a_map_that_misses_surfaces_lists_them(self):
        sc = load("open-reel")
        _, summary = export.render(sc, "glb", materials={"materials": [{"parts": [sc["parts"][0]["id"]], "color": "#ff0000"}]})
        self.assertIn("unmapped", summary)
        self.assertNotIn(sc["parts"][0]["id"], summary["unmapped"])

    def test_a_material_map_names_the_key_it_does_not_know(self):
        with self.assertRaises(export.ExportError) as cm:
            export._load_materials({"materials": [{"parts": ["x"], "metalness": 1.0}]})
        self.assertIn('unknown key "metalness"', str(cm.exception))
        with self.assertRaises(export.ExportError) as cm:
            export._load_materials({"materials": [{"color": "#ffffff"}]})
        self.assertIn('"parts" is missing', str(cm.exception))

    def test_the_example_maps_cover_every_surface(self):
        import fnmatch
        maps = ROOT / "examples" / "light-to-metal" / "maps"
        for name, slug in (("fj62", "toyota-land-cruiser-fj62"), ("revox", "revox-a77"),
                           ("jwst", "films/james-webb-space-telescope"), ("minifreak", "arturia-minifreak")):
            with self.subTest(name):
                sc = studio.load(str(ROOT / "examples" / slug / "scene.json"))
                rules = export._load_materials(maps / (name + ".json"))
                solid = [p["id"] for p in sc["parts"] if scene._local_mesh(p["shape"], 0).tris]
                self.assertEqual([i for i in solid if not any(fnmatch.fnmatchcase(i, q) for r in rules
                                                               for q in r["patterns"])], [])
                self.assertIn("not facts of the construct", json.loads((maps / (name + ".json")).read_text())["about"])

    def test_every_finish_map_beside_a_scene_covers_every_surface(self):
        import fnmatch
        said = {"aston-martin-db5", "eames-lounge-chair-chatgpt", "leica-m3", "jackson-juggernaut-et7", "braun-sk4",
                "braun-sk4-knob", "rietveld-red-blue-chair", "state-bench", "garden-shed", "garden-shed-planned",
                "saturn", "sagrada-familia", "sainte-chapelle", "duomo-di-milano", "neuschwanstein"}
        found = set()
        for path in sorted((ROOT / "examples").glob("*/maps/finish.json")):
            slug = path.parent.parent.name
            found.add(slug)
            with self.subTest(slug):
                sc = studio.load(str(path.parent.parent / "scene.json"))
                rules = export._load_materials(path)
                solid = [p["id"] for p in sc["parts"] if scene._local_mesh(p["shape"], 0).tris]
                self.assertEqual([i for i in solid if not any(fnmatch.fnmatchcase(i, q) for r in rules
                                                               for q in r["patterns"])], [])
                if slug in said:   # these say which colours are documented and which chosen
                    self.assertIn("not facts of the construct", json.loads(path.read_text())["about"])
        self.assertTrue(said <= found)


class GameReady(unittest.TestCase):
    def test_merge_keeps_moving_parts_and_their_exact_joints(self):
        sc = load("open-reel")
        g = scene.compile_scene(sc, solid=True)
        doc, binary = glb_of(sc, merge=True)
        Structure().check(doc, binary)
        merged = doc["nodes"][node_named(doc, "merged")]
        self.assertGreater(len(merged["extras"]["construct"]["merged_parts"]), 0)
        moving = {p["id"] for p in g["parts"] if p["joint"] >= 0 or any(i["motion_slot"] >= 0 for i in p["instances"])}
        names = {n.get("name") for n in doc["nodes"]}
        self.assertTrue(moving <= names)                                  # moving parts keep their nodes
        self.assertFalse(set(merged["extras"]["construct"]["merged_parts"]) & moving)
        materials = [p["material"] for p in doc["meshes"][merged["mesh"]]["primitives"]]
        self.assertEqual(len(materials), len(set(materials)))            # one primitive per material
        anim = next(a for a in doc["animations"] if a["name"] == "open")
        end = max(max(accessor(doc, binary, s["input"])) for s in anim["samplers"])
        for p in g["parts"]:
            if p["joint"] >= 0:
                ni = node_named(doc, p["id"])
                for a, b in zip(world_points(doc, binary, ni, sample(doc, binary, anim, 0.0)),
                                world_points(doc, binary, ni, sample(doc, binary, anim, end))):
                    want = scene._chain_apply(g["joints"][p["joint"]], g["articulations"], a)
                    self.assertLess(max(abs(want[k] - b[k]) for k in range(3)), TOL)

    def test_surfaces_have_texture_coordinates(self):
        doc, binary = glb_of(load("castle"))
        for m in doc["meshes"]:
            for p in m["primitives"]:
                if p["mode"] == 4:
                    self.assertIn("TEXCOORD_0", p["attributes"])
                    self.assertEqual(len(accessor(doc, binary, p["attributes"]["TEXCOORD_0"])),
                                     doc["accessors"][p["attributes"]["POSITION"]]["count"])

    def test_seams_are_dark_tubes_for_the_parts_drawn_as_lines_only(self):
        sc = load("lighthouse")
        g = scene.compile_scene(sc, solid=True)
        doc, _ = glb_of(sc, wire="seams")
        self.assertNotIn(1, [p["mode"] for m in doc["meshes"] for p in m["primitives"]])
        surfaced = {g["parts"][int(g["styles"][int(g["fills"][i + 3])][6])]["id"] for i in range(0, len(g["fills"]), 5)}
        for m in doc["meshes"]:
            for p in m["primitives"]:
                if doc["materials"][p["material"]]["name"] == "construct:seam":
                    self.assertNotIn(m["name"], surfaced)
        seam = next(x for x in doc["materials"] if x["name"] == "construct:seam")
        self.assertNotIn("extensions", seam)                            # lit like a surface, not unlit light

    def test_glazing_is_glass_and_glass_falls_back_to_alpha(self):
        sc = studio.starter("machine")
        sc["parts"][2]["id"] = "rear-window"   # the mast, renamed: nothing else refers to it
        doc, _ = glb_of(sc)
        glass = next(m for m in doc["materials"] if m["name"] == "construct:glass")
        self.assertIn("KHR_materials_transmission", glass["extensions"])
        self.assertEqual((glass["alphaMode"], glass["pbrMetallicRoughness"]["baseColorFactor"][3]), ("BLEND", 0.35))

    def test_obj_has_texture_coordinates(self):
        out, _ = export.render(load("cd"), "obj", wire="none")
        self.assertIn("\nvt ", out["obj"])
        f = next(ln for ln in out["obj"].splitlines() if ln.startswith("f "))
        self.assertRegex(f, r"^f \d+/\d+/\d+ ")


@unittest.skipUnless(os.environ.get("CONSTRUCT_GODOT"), "set CONSTRUCT_GODOT to a Godot 4 binary to run")
class Godot(unittest.TestCase):
    """Godot's own glTF loader: the game-ready file arrives with its parts, glass and joints."""

    def test_godot_loads_a_game_ready_model(self):
        script = ("extends SceneTree\n"
                  "func _init() -> void:\n"
                  "\tvar doc = GLTFDocument.new()\n"
                  "\tvar state = GLTFState.new()\n"
                  "\tvar err = doc.append_from_file(\"res://cd.glb\", state)\n"
                  "\tvar scene = doc.generate_scene(state)\n"
                  "\tvar anims = []\n"
                  "\tfor p in scene.find_children(\"*\", \"AnimationPlayer\", true, false):\n"
                  "\t\tanims += Array(p.get_animation_list())\n"
                  "\tprint(\"RESULT \" + JSON.stringify({\"err\": err, \"meshes\": scene.find_children(\"*\", "
                  "\"MeshInstance3D\", true, false).size(), \"anims\": anims}))\n"
                  "\tscene.free()\n"
                  "\tquit()\n")
        with tempfile.TemporaryDirectory() as d:
            Path(d, "project.godot").write_text("config_version=5\n", encoding="utf-8")
            Path(d, "check.gd").write_text(script, encoding="utf-8")
            export.export(load("cd"), Path(d, "cd.glb"), merge=True, wire="seams")
            r = subprocess.run([os.environ["CONSTRUCT_GODOT"], "--headless", "--path", d, "--script", "res://check.gd"],
                               capture_output=True, text=True, timeout=300, encoding="utf-8", errors="replace")
        res = json.loads(next(ln for ln in r.stdout.splitlines() if ln.startswith("RESULT "))[7:])
        self.assertEqual(res["err"], 0)
        self.assertGreater(res["meshes"], 0)
        self.assertIn("open", res["anims"])


class Motion(unittest.TestCase):
    """The animations land every vertex exactly where the compiler's own maths puts it."""

    def test_open_matches_the_compiler_including_chains(self):
        for name in ("cd", "leica-m3", "juggernaut-et7", "open-reel"):
            with self.subTest(name):
                sc = load(name)
                g = scene.compile_scene(sc, solid=True)
                doc, binary = glb_of(sc)
                anim = next(a for a in doc["animations"] if a["name"] == "open")
                end = max(max(accessor(doc, binary, s["input"])) for s in anim["samplers"])
                closed, opened = sample(doc, binary, anim, 0.0), sample(doc, binary, anim, end)
                checked = 0
                for p in g["parts"]:
                    if p["joint"] < 0:
                        continue
                    ni = node_named(doc, p["id"])
                    rest, done = world_points(doc, binary, ni, closed), world_points(doc, binary, ni, opened)
                    for a, b in zip(rest, done):
                        want = scene._chain_apply(g["joints"][p["joint"]], g["articulations"], a)
                        self.assertLess(max(abs(want[k] - b[k]) for k in range(3)), TOL, p["id"])
                        checked += 1
                self.assertGreater(checked, 0)

    def test_a_chain_is_nested(self):
        doc, _ = glb_of(load("cd"))
        lift, out = node_named(doc, "booklet:booklet-lift"), node_named(doc, "booklet:booklet-out")
        self.assertIn(out, doc["nodes"][lift]["children"])
        self.assertIn("open:booklet-out", [a["name"] for a in doc["animations"]])

    def test_open_pose_rests_open(self):
        sc = load("cd")
        g = scene.compile_scene(sc, solid=True)
        doc, binary = glb_of(sc, pose="open")
        lid = next(p for p in g["parts"] if p["id"] == "lid")
        rest = world_points(*glb_of(sc), node_named(doc, "lid"), {})
        now = world_points(doc, binary, node_named(doc, "lid"), {})
        for a, b in zip(rest, now):
            want = scene._chain_apply(g["joints"][lid["joint"]], g["articulations"], a)
            self.assertLess(max(abs(want[k] - b[k]) for k in range(3)), TOL)

    def test_idle_spins_about_the_pivot(self):
        sc = load("open-reel")
        g = scene.compile_scene(sc, solid=True)
        doc, binary = glb_of(sc)
        anim = next(a for a in doc["animations"] if a["name"] == "idle")
        slot = next(i for i, m in enumerate(g["motions"]) if m["type"] == "spin")
        m = g["motions"][slot]
        part = m["part"]
        styles = [s for s in g["styles"] if int(s[7]) == slot]
        self.assertTrue(styles)
        node = node_named(doc, "%s:motion-%d" % (part, slot))
        base = {node: {"rotation": [0, 0, 0, 1]}}
        for t in (0.0, 0.37, 1.1):
            rest = world_points(doc, binary, node, base)
            moved = world_points(doc, binary, node, sample(doc, binary, anim, t))
            ang = math.degrees(m["rpm"] * 2 * math.pi / 60 * t + 2 * math.pi * m["phase"])
            r = scene._axis_rot(m["axis"], ang)
            for a, b in list(zip(rest, moved))[:200]:
                q = scene._mul(r, tuple(a[k] - m["pivot"][k] for k in range(3)))
                want = tuple(q[k] + m["pivot"][k] for k in range(3))
                self.assertLess(max(abs(want[k] - b[k]) for k in range(3)), 1e-3)


class Obj(unittest.TestCase):
    def test_obj_is_well_formed(self):
        sc = load("cd")
        out, s = export.render(sc, "obj", name="cd")
        v = sum(1 for ln in out["obj"].splitlines() if ln.startswith("v "))
        vn = sum(1 for ln in out["obj"].splitlines() if ln.startswith("vn "))
        for ln in out["obj"].splitlines():
            if ln.startswith("f "):
                for c in ln.split()[1:]:
                    a, _, n = c.split("/")
                    self.assertTrue(1 <= int(a) <= v and 1 <= int(n) <= vn)
            if ln.startswith("usemtl "):
                self.assertIn("newmtl " + ln.split()[1], out["mtl"])
        self.assertIn("mtllib cd.mtl", out["obj"])
        self.assertEqual(sum(1 for ln in out["obj"].splitlines() if ln.startswith("l ")), s["edges"])

    def test_z_up_and_open(self):
        sc = load("cd")
        g = scene.compile_scene(sc, solid=True)
        out, _ = export.render(sc, "obj", frame="z-up", pose="open", wire="none")
        vs = [tuple(map(float, ln.split()[1:])) for ln in out["obj"].splitlines() if ln.startswith("v ")]
        lid = next(p for p in g["parts"] if p["id"] == "lid")
        f = g["fills"]
        st = g["styles"]
        lid_i = g["parts"].index(lid)
        first = next(i for i in range(0, len(f), 5) if int(st[int(f[i + 3])][6]) == lid_i)
        want = scene._chain_apply(g["joints"][lid["joint"]], g["articulations"], tuple(f[first:first + 3]))
        want = (want[0], -want[2], want[1])
        self.assertLess(min(max(abs(a[k] - want[k]) for k in range(3)) for a in vs), 1e-5)

    def test_glb_refuses_z_up_and_bad_formats(self):
        with self.assertRaises(export.ExportError):
            export.render(load("cd"), "glb", frame="z-up")
        with self.assertRaises(export.ExportError):
            export.render(load("cd"), "stl")


class Audit(unittest.TestCase):
    def test_a_load_bearing_curve_has_no_surface(self):
        sc = studio.starter("machine")
        sc["parts"][2]["shape"] = {"type": "curve", "points": [[0, 0.6, 0], [0, 0.85, 0]]}
        codes = [(w["code"], w["part"]) for w in audit.audit(sc, scene.compile_scene(sc))["warnings"]]
        self.assertIn(("no-surface", "mast"), codes)
        self.assertNotIn("no-surface", [c for c, _ in audit.audit(studio.starter("machine"), scene.compile_scene(
            studio.starter("machine")))["warnings"]])


class Hosts(unittest.TestCase):
    def test_cli(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d, "cd.glb")
            self.assertEqual(cli.main(["export", str(EXAMPLES / "cd.json"), "--out", str(out)]), 0)
            export.read_glb(out.read_bytes())
            self.assertEqual(cli.main(["export", str(EXAMPLES / "cd.json"), "--out", str(Path(d, "cd.obj")),
                                       "--wire", "tubes"]), 0)
            self.assertTrue(Path(d, "cd.mtl").exists())
            self.assertEqual(cli.main(["export", str(EXAMPLES / "cd.json"), "--out", str(Path(d, "cd.stl"))]), 1)

    def test_the_adapter_template_runs_as_docs_adapters_says(self):
        # the template a third-party adapter starts from: a parts sheet and one STL per part, Z up, millimetres
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, str(ROOT / "hosts" / "adapter-template" / "construct_parts.py"),
                                str(EXAMPLES / "cd.json"), d], cwd=ROOT, capture_output=True, text=True,
                               env=dict(os.environ, PYTHONPATH=str(ROOT)))
            self.assertEqual(r.returncode, 0, r.stderr)
            rows = list(csv.DictReader(open(Path(d, "parts.csv"), encoding="utf-8")))
            self.assertEqual([row["id"] for row in rows], [p["id"] for p in load("cd")["parts"]])
            tray = next(row for row in rows if row["id"] == "tray")
            self.assertTrue(tray["stl"] and Path(d, tray["stl"]).read_text().startswith("solid tray"))
            box = next(p for p in scene.compile_scene(load("cd"), solid=True)["parts"] if p["id"] == "tray")["instances"][0]
            self.assertAlmostEqual(float(tray["height_mm"]), (box["max"][1] - box["min"][1]) * 1000, delta=0.1)   # Y up is Z up
            self.assertAlmostEqual(float(tray["depth_mm"]), (box["max"][2] - box["min"][2]) * 1000, delta=0.1)

    def test_for_game_engines_colliders_pieces_and_names_godot_reads_right(self):
        sc = load("cd")
        doc = glb_of(sc, colliders=True)[0]
        names = [n.get("name", "") for n in doc["nodes"]]
        cols = [n for n in names if n.endswith("-convcolonly")]
        self.assertTrue(cols)
        self.assertTrue(all(n[:-len("-convcolonly")] in names for n in cols))   # one per part with surfaces
        lid = next(n for n in doc["nodes"] if n.get("name") == "lid-convcolonly")
        hinge = next(n for n in doc["nodes"] if lid in [doc["nodes"][c] for c in n.get("children", [])])
        self.assertIn("lid:", hinge["name"])                                      # it moves with the lid's joint
        merged = glb_of(sc, colliders=True, merge=True)[0]
        self.assertEqual(len([n for n in merged["nodes"] if n.get("name", "").endswith("-convcolonly")]), len(cols))
        pieces = glb_of(sc, pieces=True)[0]
        bodies = [n for n in pieces["nodes"] if "motion" in n.get("extensions", {}).get("OMI_physics_body", {})]
        self.assertTrue(bodies)
        shapes = pieces["extensions"]["OMI_physics_shape"]["shapes"]
        colliders = [n for n in pieces["nodes"] if "collider" in n.get("extensions", {}).get("OMI_physics_body", {})]
        self.assertEqual(len(colliders), len(shapes))
        self.assertTrue(all(sh["type"] == "convex" for sh in shapes))
        self.assertTrue({"OMI_physics_body", "OMI_physics_shape"} <= set(pieces["extensionsUsed"]))
        self.assertFalse(any(n.get("name", "").endswith(("-rigid", "-convcolonly")) for n in pieces["nodes"]))
        with self.assertRaisesRegex(export.ExportError, "does not go with --merge"):
            glb_of(sc, pieces=True, merge=True)
        wheel = studio.starter("machine")
        wheel["parts"][2]["id"] = "spare-wheel"   # the mast, renamed: nothing else refers to it
        names = [n.get("name", "") for n in glb_of(wheel)[0]["nodes"]]
        self.assertIn("spare-wheel-part", names)   # not a VehicleWheel3D in Godot

    def test_obj_shares_positions_and_keeps_quads_and_quality_is_reported(self):
        out, summary = export.render(load("cd"), "obj")
        lines = out["obj"].splitlines()
        v = sum(1 for x in lines if x.startswith("v "))
        faces = [x.split()[1:] for x in lines if x.startswith("f ")]
        self.assertTrue(any(len(f) == 4 for f in faces))                       # strips are quads again
        refs = [int(c.split("/")[0]) for f in faces for c in f]
        self.assertTrue(all(1 <= r <= v for r in refs))
        self.assertLess(v, sum(len(f) for f in faces))                          # positions are shared
        q = summary["quality"]
        self.assertEqual(q["triangles"], summary["triangles"])
        self.assertTrue(0.0 <= q["thin_share"] <= 1.0)
        self.assertAlmostEqual(export.smallest_angle([(0, 0, 0), (1, 0, 0), (0, 1, 0)]), 45.0, places=6)
        self.assertEqual(export.smallest_angle([(0, 0, 0), (0, 0, 0), (0, 1, 0)]), 0.0)
        doc = glb_of(load("cd"), quality=True)[0]
        self.assertTrue(any(m["name"].startswith("construct:quality:") for m in doc["materials"]))
        with self.assertRaisesRegex(export.ExportError, "quality"):
            export.render(load("cd"), "obj", quality=True)
        with self.assertRaisesRegex(export.ExportError, "quality"):
            glb_of(load("cd"), quality=True, merge=True)

    def test_what_holds_the_glass_is_not_glass(self):
        # seen in a live run: a part named windscreen-frame was taken for glass, and its kit piece for clear plastic
        self.assertTrue(export.is_glass_name("windscreen"))
        self.assertTrue(export.is_glass_name("side-window-left"))
        for pid in ("windscreen-frame", "window-crank", "window-seal-left", "visor-hinge"):
            self.assertFalse(export.is_glass_name(pid), pid)

    def test_pieces_copies_apart_interlocked_parts_together(self):
        def part(pid, size, at, **kw):
            return dict({"id": pid, "role": "mass", "certainty": "inferred", "stage": 0,
                         "shape": {"type": "box", "size": size}, "at": at}, **kw)
        sc = studio.starter("object", "Pieces")
        sc["parts"] = [part("base", [0.4, 0.1, 0.2], [0, 0.05, 0]),
                       part("tyre", [0.04, 0.1, 0.1], [0.25, 0.05, 0], mirror="x"),    # a pair: two bodies
                       part("rim", [0.03, 0.05, 0.05], [0.25, 0.05, 0], mirror="x"),   # inside each tyre: with it
                       part("lid", [0.4, 0.02, 0.2], [0, 0.11, 0])]                     # resting on the base: apart
        doc = glb_of(sc, pieces=True)[0]
        pieces = [n["extras"]["construct"]["parts"] for n in doc["nodes"]
                  if "motion" in n.get("extensions", {}).get("OMI_physics_body", {})]
        self.assertIn(["base"], pieces)
        self.assertIn(["lid"], pieces)
        self.assertEqual(sorted(sorted(p) for p in pieces if "tyre-1" in p or "tyre-2" in p),
                         [["rim-1", "tyre-1"], ["rim-2", "tyre-2"]])
        a = [(x, y, z) for x in (0, 1) for y in (0, 1) for z in (0, 1)]
        self.assertTrue(export._intersect(a, [(p[0] + 0.5, p[1], p[2]) for p in a]))
        self.assertFalse(export._intersect(a, [(p[0] + 1.5, p[1] + 0.2, p[2]) for p in a]))

    def test_pieces_write_each_mesh_once_and_count_it_once(self):
        sc = load_example("toyota-land-cruiser-fj62")
        plain, plain_summary = export.render(sc, "glb")
        for mode in (True, "glued"):
            with self.subTest(mode):
                out, summary = export.render(sc, "glb", pieces=mode)
                doc = export.read_glb(out["glb"])[0]
                used = {n["mesh"] for n in doc["nodes"] if "mesh" in n}
                used |= {s["convex"]["mesh"] for s in doc["extensions"]["OMI_physics_shape"]["shapes"]}
                self.assertEqual(sorted(set(range(len(doc["meshes"]))) - used), [])   # no mesh left unreferenced
                self.assertEqual(summary["triangles"], plain_summary["triangles"])
                self.assertLess(len(out["glb"]), 2 * len(plain["glb"]))   # the shapes beside the meshes, not a second copy

    def test_glued_pieces_are_one_body_and_one_per_joint_with_the_joint_in_its_extras(self):
        doc = glb_of(load_example("toyota-land-cruiser-fj62"), pieces="glued")[0]
        bodies = {n["extras"]["construct"]["piece"]: n["extras"]["construct"] for n in doc["nodes"]
                  if "motion" in n.get("extensions", {}).get("OMI_physics_body", {})}
        self.assertEqual(sorted(bodies), ["toyota-land-cruiser-fj62-body", "toyota-land-cruiser-fj62-tailgate-down"])
        j = bodies["toyota-land-cruiser-fj62-tailgate-down"]["joint"]
        self.assertEqual((j["type"], j["to"], j["amount"], j["axis"]), ("hinge", "toyota-land-cruiser-fj62-body", 85, [-1.0, 0.0, 0.0]))
        self.assertNotIn("joint", bodies["toyota-land-cruiser-fj62-body"])

    def test_joints_inside_joints_glue_as_one_body_with_the_whole_chain(self):
        doc = glb_of(load_example("volkswagen-t1-samba"), pieces="glued")[0]
        bodies = [n["extras"]["construct"] for n in doc["nodes"]
                  if "motion" in n.get("extensions", {}).get("OMI_physics_body", {})]
        names = [b["piece"] for b in bodies]
        self.assertEqual(len(names), len(set(names)))                   # each body its own name: none hangs on nothing
        self.assertEqual(sorted({a["articulation"] for b in bodies if "joint" in b
                                 for a in b["joint"].get("chain", [b["joint"]])}),
                         sorted(a["id"] for a in json.loads((ROOT / "examples" / "volkswagen-t1-samba" / "scene.json").read_text())
                                ["articulations"]))   # all nine
        panel = next(b for b in bodies if b["piece"].endswith("sunroof-fold-0-sunroof-stack-lift"))
        j = panel["joint"]
        self.assertEqual(([e["articulation"] for e in j["chain"]], j["to"]),
                         (["sunroof-fold-0", "sunroof-stack-lift"], "vw-type-2-t1-samba-1963-body"))
        self.assertGreater(j["chain"][0]["pivot"][1], 1.5)              # a slide's joint on its panel, not at the origin

    def test_a_glued_building_stands_still_and_its_doors_still_hang(self):
        doc = glb_of(load_example("tea-house"), pieces="glued")[0]
        motions = {n["extras"]["construct"]["piece"]: n["extensions"]["OMI_physics_body"]["motion"]["type"]
                   for n in doc["nodes"] if "motion" in n.get("extensions", {}).get("OMI_physics_body", {})}
        fixed = [k for k, v in motions.items() if v == "static"]
        self.assertEqual(len(fixed), 1)                                  # the house itself: it does not topple
        self.assertTrue(all(v == "dynamic" for k, v in motions.items() if k not in fixed))   # the shoji slides

    def test_glued_articulations_that_move_alike_are_one_body(self):
        """SERUM's service deck opens as four articulations on one hinge (for its parts' count): one body, so an
        engine cannot let its light fader strip flap free of the heavy deck it rides on."""
        with tempfile.TemporaryDirectory() as d:
            out = Path(d, "serum.glb")
            export.export(load_example("serum-2-61"), out, pieces="glued")
            doc, _ = export.read_glb(out.read_bytes())
            pieces = [n["extras"]["construct"]["piece"] for n in doc["nodes"]
                      if "piece" in n.get("extras", {}).get("construct", {})]
            self.assertEqual(len([x for x in pieces if "service-deck-open" in x]), 1, pieces)

    @unittest.skipUnless(os.environ.get("CONSTRUCT_GODOT"), "set CONSTRUCT_GODOT to the Godot binary to run")
    def test_godot_holds_glued_pieces_together_and_opens_the_tailgate_on_its_hinge(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            export.export(load_example("toyota-land-cruiser-fj62"), d / "car.glb", pieces="glued")
            (d / "project.godot").write_text('config_version=5\n[application]\nconfig/name="glue"\n', encoding="utf-8")
            (d / "construct_joints.gd").write_text((ROOT / "hosts" / "godot" / "construct_joints.gd").read_text(), encoding="utf-8")
            (d / "glue.gd").write_text(GODOT_GLUE, encoding="utf-8")
            g = os.environ["CONSTRUCT_GODOT"]
            subprocess.run([g, "--headless", "--path", str(d), "--import"], capture_output=True, timeout=300)
            r = subprocess.run([g, "--headless", "--path", str(d), "-s", "glue.gd", "--", "res://car.glb"],
                               capture_output=True, text=True, timeout=300)
            out = json.loads(next(x for x in r.stdout.splitlines() if x.startswith("RESULT "))[7:])
            self.assertEqual((out["bodies"], out["joints"]), (2, 1))
            self.assertLess(out["far"], 0.05)                       # the car stays a car: it settles, it does not slump
            self.assertTrue(80 <= out["gate_turn"] <= 90, out)     # the tailgate falls open on its hinge to its 85 degrees
            export.export(load_example("volkswagen-t1-samba"), d / "bus.glb", pieces="glued")   # joints inside joints
            subprocess.run([g, "--headless", "--path", str(d), "--import"], capture_output=True, timeout=300)
            r = subprocess.run([g, "--headless", "--path", str(d), "-s", "glue.gd", "--", "res://bus.glb"],
                               capture_output=True, text=True, timeout=300)
            out = json.loads(next(x for x in r.stdout.splitlines() if x.startswith("RESULT "))[7:])
            self.assertEqual((out["bodies"], out["joints"]), (10, 9))
            self.assertLess(out["far"], 1.2)                        # nothing flies off: each moves within its own travel

    @unittest.skipUnless(os.environ.get("CONSTRUCT_GODOT"), "set CONSTRUCT_GODOT to the Godot binary to run")
    def test_godot_imports_colliders_and_pieces_that_fall(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            export.export(load("cd"), d / "c.glb", colliders=True, merge=True)
            export.export(load("cd"), d / "p.glb", pieces=True)
            (d / "project.godot").write_text('config_version=5\n[application]\nconfig/name="check"\n', encoding="utf-8")
            (d / "check.gd").write_text(GODOT_CHECK, encoding="utf-8")
            g = os.environ["CONSTRUCT_GODOT"]
            subprocess.run([g, "--headless", "--path", str(d), "--import"], capture_output=True, timeout=300)
            r = subprocess.run([g, "--headless", "--path", str(d), "-s", "check.gd"], capture_output=True, text=True, timeout=300)
            line = next(x for x in r.stdout.splitlines() if x.startswith("RESULT "))
            out = json.loads(line[7:])
            self.assertGreater(out["static"], 0)
            self.assertGreater(out["rigid"], 0)
            self.assertGreaterEqual(out["shapes"], out["rigid"])
            self.assertLess(out["far"], 1.5 * out["span"] + 0.05)   # the pieces settle; they do not burst
            self.assertIn("open", out["animations"])

    def test_mcp(self):
        msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                 "params": {"name": "construct_export", "arguments": {"document": load("cd")}}},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                 "params": {"name": "construct_export", "arguments": {"document": load("cd"), "format": "obj"}}}]
        r = subprocess.run([sys.executable, "-m", __package__ + ".mcp_server"], cwd=ROOT, capture_output=True,
                           text=True, input="".join(json.dumps(m) + "\n" for m in msgs))
        lines = [json.loads(x) for x in r.stdout.splitlines() if x.strip()]
        res = lines[1]["result"]["structuredContent"]
        doc, _ = export.read_glb(base64.b64decode(res["glb_base64"]))
        self.assertEqual(res["summary"]["format"], "glb")
        self.assertIn("lid", [n.get("name") for n in doc["nodes"]])
        self.assertIn("mtllib", lines[2]["result"]["structuredContent"]["obj"])


@unittest.skipUnless(os.environ.get("CONSTRUCT_BLENDER"), "set CONSTRUCT_BLENDER to a Blender binary to run")
class Blender(unittest.TestCase):
    """Blender's own glTF importer: parts, the open animation and the build phase arrive."""

    def test_import(self):
        script = ("import bpy, sys, json\n"
                  "bpy.ops.wm.read_factory_settings(use_empty=True)\n"
                  "bpy.ops.import_scene.gltf(filepath=sys.argv[-1])\n"
                  "ms = [o for o in bpy.data.objects if o.type == 'MESH']\n"
                  "print('RESULT ' + json.dumps({'names': [o.name for o in bpy.data.objects], "
                  "'actions': [a.name for a in bpy.data.actions], "
                  "'phase': all('_PHASE' in o.data.attributes for o in ms)}))\n")
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, "cd.glb")
            export.export(load("cd"), path)
            Path(d, "s.py").write_text(script, encoding="utf-8")
            r = subprocess.run([os.environ["CONSTRUCT_BLENDER"], "-b", "--factory-startup", "--python",
                                str(Path(d, "s.py")), "--", str(path)], capture_output=True, text=True,
                               timeout=300, encoding="utf-8", errors="replace")
        res = json.loads(next(ln for ln in r.stdout.splitlines() if ln.startswith("RESULT "))[7:])
        self.assertIn("lid", res["names"])
        self.assertIn("open", res["actions"])
        self.assertTrue(res["phase"])


if __name__ == "__main__":
    unittest.main()


class ThroughBlender(unittest.TestCase):
    """FBX and USD: the glTF carried over by Blender, when it is installed."""

    def test_an_unknown_format_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(export.ExportError):
                export.via_blender(Path(d, "x.glb"), Path(d, "x.dwg"), "dwg")

    @unittest.skipUnless(__import__("construct_hologram.runfilm", fromlist=["find_blender"]).find_blender(), "no Blender")
    def test_a_construct_becomes_an_fbx(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d, "cd.fbx")
            r = subprocess.run([sys.executable, "-m", "construct_hologram", "export", str(EXAMPLES / "cd.json"), "--out", str(out)],
                               cwd=str(ROOT), capture_output=True, text=True, timeout=600)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(out.is_file())
            self.assertEqual(out.read_bytes()[:18], b"Kaydara FBX Binary")
            self.assertIn("through Blender", r.stdout)


def art_scene(folder, glow=None, sha=None, joint=False):
    """A box with a picture on its front face: a 4 x 2 PNG whose top-left pixel is red, the rest blue."""
    import hashlib
    from . import png
    data = png.encode(4, 2, lambda x, y: (255, 0, 0) if (x, y) == (0, 0) else (0, 0, 255))
    Path(folder, "art.png").write_bytes(data)
    s = {"format": "construct-scene", "version": 2, "id": "t", "title": "Test", "units": "m", "seed": 1,
         "subject": {"category": "object", "accuracy": "generic", "synthetic": True},
         "sources": [{"id": "req", "kind": "user_request", "title": "test", "rights": "synthetic"}],
         "facts": [{"key": "h", "value": 1.0, "certainty": "inferred", "source": "req"}],
         "assets": [{"id": "art", "path": "art.png", "sha256": sha or hashlib.sha256(data).hexdigest(),
                     "media_type": "image/png", "rights": "synthetic", "provenance": "generated-decorative"}],
         "parts": [{"id": "body", "role": "mass", "certainty": "inferred", "stage": 0,
                    "shape": {"type": "box", "size": [1, 1, 1], "anchor": "base"}},
                   {"id": "face", "role": "artwork", "certainty": "inferred", "stage": 1,
                    "shape": {"type": "box", "size": [0.5, 0.75, 0.02]}, "at": [0, 0.5, 0.52],
                    "artwork": {"slot": "cover-front", "asset": "art"}}]}
    if glow is not None:
        s["parts"][1]["look"] = {"glow": glow}
    if joint:
        s["articulations"] = [{"id": "lid", "type": "hinge", "parts": ["face"], "axis": [1, 0, 0],
                               "pivot": [0, 0.875, 0.53], "amount": -60}]
    return s


def png_pixel(data, x, y):
    """One pixel of an 8-bit RGB PNG with unfiltered rows (png.encode's)."""
    import zlib
    w = struct.unpack(">I", data[16:20])[0]
    i, idat = 8, b""
    while i < len(data):
        n, kind = struct.unpack_from(">I4s", data, i)
        if kind == b"IDAT":
            idat += data[i + 8:i + 8 + n]
        i += 12 + n
    raw = zlib.decompress(idat)
    row = raw[y * (1 + 3 * w):(y + 1) * (1 + 3 * w)]
    return tuple(row[1 + 3 * x:4 + 3 * x])


class Artwork(unittest.TestCase):
    """A scene's artwork (a sign's lettering, a cover) in the file: a textured face under its part."""

    def test_a_picture_becomes_a_textured_face_under_its_part(self):
        with tempfile.TemporaryDirectory() as d:
            doc, binary = glb_of(art_scene(d, glow=0.4), asset_root=d)
            Structure.check(self, doc, binary)
            self.assertEqual((len(doc["images"]), len(doc["textures"])), (1, 1))
            self.assertEqual(doc["images"][0]["mimeType"], "image/png")
            q = node_named(doc, "face.artwork")
            self.assertIn(q, doc["nodes"][node_named(doc, "face")]["children"])
            prim = doc["meshes"][doc["nodes"][q]["mesh"]]["primitives"][0]
            mat = doc["materials"][prim["material"]]
            self.assertEqual(mat["pbrMetallicRoughness"]["baseColorTexture"]["index"], 0)
            self.assertTrue(mat["doubleSided"])
            # it glows: the image is its own light
            self.assertEqual(mat["emissiveTexture"]["index"], 0)
            self.assertEqual(mat["emissiveFactor"], [1.0, 1.0, 1.0])
            # the image's top-left pixel (red) lands on the face's top-left corner, seen from the front (+Z)
            pos = accessor(doc, binary, prim["attributes"]["POSITION"])
            uv = accessor(doc, binary, prim["attributes"]["TEXCOORD_0"])
            v = doc["bufferViews"][doc["images"][0]["bufferView"]]
            img = bytes(binary[v["byteOffset"]:v["byteOffset"] + v["byteLength"]])
            self.assertEqual(png_pixel(img, 0, 0), (255, 0, 0))
            tl = pos[uv.index((0.0, 0.0))]
            self.assertAlmostEqual(tl[0], -0.25, places=4)
            self.assertAlmostEqual(tl[1], 0.875, places=4)
            br = pos[uv.index((1.0, 1.0))]
            self.assertAlmostEqual(br[0], 0.25, places=4)
            self.assertAlmostEqual(br[1], 0.125, places=4)
            self.assertGreater(min(p[2] for p in pos), 0.53)   # in front of its face
            nrm = accessor(doc, binary, prim["attributes"]["NORMAL"])
            self.assertAlmostEqual(nrm[0][2], 1.0, places=4)
            a, b_, c = [pos[i] for i in accessor(doc, binary, prim["indices"])[:3]]
            self.assertGreater(export._cross(export._sub(b_, a), export._sub(c, a))[2], 0)   # wound to face out

    def test_a_face_that_does_not_glow_is_not_emissive(self):
        with tempfile.TemporaryDirectory() as d:
            doc, _ = glb_of(art_scene(d), asset_root=d)   # an artwork part: no glow of its own
            m = next(m for m in doc["materials"] if m["name"].startswith("construct:artwork:"))
            self.assertNotIn("emissiveTexture", m)
            doc, _ = glb_of(art_scene(d), asset_root=d,
                            materials={"materials": [{"parts": "face", "color": "#ffffff", "finish": "light"}]})
            m = next(m for m in doc["materials"] if m["name"].startswith("construct:artwork:"))
            self.assertIn("emissiveTexture", m)   # the material map makes it a light

    def test_only_matching_bytes_are_embedded(self):
        with tempfile.TemporaryDirectory() as d:
            out, summary = export.render(art_scene(d, sha="f" * 64), "glb", asset_root=d)
            doc, _ = export.read_glb(out["glb"])
            self.assertNotIn("images", doc)
            self.assertFalse(any(n.get("name") == "face.artwork" for n in doc["nodes"]))
            self.assertTrue(any("do not match" in n for n in summary["notes"]))
            # without an asset folder (the MCP tool's document) the face is left out, as the page leaves its slot empty
            doc, _ = glb_of(art_scene(d))
            self.assertNotIn("images", doc)

    def test_a_moving_part_carries_its_artwork(self):
        with tempfile.TemporaryDirectory() as d:
            sc = art_scene(d, joint=True)
            doc, binary = glb_of(sc, asset_root=d)
        q = node_named(doc, "face.artwork")
        pivot = node_named(doc, "face:lid")
        self.assertIn(q, doc["nodes"][pivot]["children"])
        self.assertIn(pivot, doc["nodes"][node_named(doc, "face")]["children"])
        g = scene.compile_scene(sc, solid=True)
        corners = g["artwork"][0]["corners"]
        anim = next(a for a in doc["animations"] if a["name"] == "open")
        end = sample(doc, binary, anim, 1e9)
        got = world_points(doc, binary, q, end)
        want = [scene._chain_apply(g["joints"][0], g["articulations"], tuple(c)) for c in corners]
        for w in want:   # each opened corner is a vertex of the opened face
            self.assertLess(min(math.dist(w, p) for p in got), TOL)

    def test_merged_and_pieces_keep_the_face_with_its_part(self):
        with tempfile.TemporaryDirectory() as d:
            sc = art_scene(d)
            doc, _ = glb_of(sc, asset_root=d, merge=True)
            self.assertIn(node_named(doc, "face.artwork"), doc["nodes"][node_named(doc, "merged")]["children"])
            for pieces in (True, "glued"):
                doc, binary = glb_of(sc, asset_root=d, pieces=pieces)
                q = node_named(doc, "face.artwork")
                body = next(n for n in doc["nodes"] if q in n.get("children", []))
                self.assertIn("OMI_physics_body", body.get("extensions", {}), pieces)
                pts = world_points(doc, binary, q, {})
                self.assertAlmostEqual(min(p[1] for p in pts), 0.125, places=4)   # where the page draws it
                self.assertAlmostEqual(max(p[1] for p in pts), 0.875, places=4)

    def test_obj_maps_the_image(self):
        with tempfile.TemporaryDirectory() as d:
            summary = export.export(art_scene(d, glow=0.5), Path(d, "out", "m.obj"), asset_root=d)
            mtl = Path(d, "out", "m.mtl").read_text()
            obj = Path(d, "out", "m.obj").read_text()
            self.assertTrue(Path(d, "out", "m.art.png").is_file())
        self.assertIn(str(Path(d, "out", "m.art.png")), summary["files"])
        self.assertIn("map_Kd m.art.png", mtl)
        self.assertIn("map_Ke m.art.png", mtl)
        self.assertIn("o face.artwork", obj)
        block = obj.split("o face.artwork")[1].splitlines()
        vs = [tuple(map(float, ln.split()[1:])) for ln in block if ln.startswith("v ")]
        vts = [tuple(map(float, ln.split()[1:])) for ln in block if ln.startswith("vt ")]
        tl = vs[vts.index((0.0, 1.0))]   # OBJ counts v from the image's bottom: the top-left pixel is (0, 1)
        self.assertAlmostEqual(tl[0], -0.25, places=4)
        self.assertAlmostEqual(tl[1], 0.875, places=4)

    def test_cli_reads_the_artwork_beside_the_scene(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "scene.json").write_text(json.dumps(art_scene(d, glow=0.3)), encoding="utf-8")
            r = subprocess.run([sys.executable, str(HERE / "cli.py"), "export", str(Path(d, "scene.json")), "--out",
                                str(Path(d, "m.glb"))], cwd=str(ROOT), capture_output=True, text=True, timeout=120)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("artwork: 1 face, 1 image", r.stdout)
            doc, _ = export.read_glb(Path(d, "m.glb").read_bytes())
        self.assertEqual(len(doc["images"]), 1)
