"""3D export: the .glb is valid glTF 2.0, its joints and motions land where the compiler puts them, the
OBJ is well formed, and the hologram's own compile is unchanged."""

import base64
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


def glb_of(sc, **kw):
    out, _ = export.render(sc, "glb", **kw)
    return export.read_glb(out["glb"])


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
