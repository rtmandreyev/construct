"""The Blender add-on: its zip, its bundled runtime, and (with CONSTRUCT_BLENDER set) the add-on itself
in Blender: the import, the controls, joints that open exactly where the compiler puts them, the
line art with its build phase."""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from . import product, scene

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EXAMPLES = HERE / "examples" / "v2"
BLENDER = os.environ.get("CONSTRUCT_BLENDER")


def _builder():
    spec = importlib.util.spec_from_file_location("bbe", ROOT / "scripts" / "build_blender_extension.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Package(unittest.TestCase):
    def test_zip_has_the_addon_its_manifest_and_runtime(self):
        with tempfile.TemporaryDirectory() as d:
            path = _builder().build(d)
            with zipfile.ZipFile(path) as z:
                names = set(z.namelist())
                manifest = z.read("blender_manifest.toml").decode("utf-8")
        self.assertTrue({"__init__.py", "blender_manifest.toml", "LICENSE", "construct_hologram/export.py",
                         "construct_hologram/scene.py"} <= names)
        self.assertIn('version = "%s"' % product.VERSION, manifest)
        self.assertIn('blender_version_min = "4.2.0"', manifest)

    def test_the_bundled_runtime_compiles_and_exports_alone(self):
        # the runtime the zip carries is enough: a scene and a parameter document export from it
        with tempfile.TemporaryDirectory() as d:
            src = _builder().stage(Path(d, "pkg", "construct"))
            (src / "__init__.py").write_text("", encoding="utf-8")   # the add-on itself needs bpy
            code = ("import json, sys\n"
                    "sys.path.insert(0, sys.argv[1])\n"
                    "from construct.construct_hologram import export, params\n"
                    "for p in sys.argv[2:]:\n"
                    "    doc = json.load(open(p, encoding='utf-8'))\n"
                    "    doc = params.expand(doc) if params.is_params(doc) else doc\n"
                    "    out, s = export.render(doc, 'glb')\n"
                    "    print(len(out['glb']) > 1000, s['parts'])\n")
            r = subprocess.run([sys.executable, "-I", "-c", code, str(Path(d, "pkg")), str(EXAMPLES / "cd.json"),
                                str(EXAMPLES / "case-jewel.params.json")], capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([ln.split()[0] for ln in r.stdout.splitlines()], ["True", "True"])


BLENDER_TEST = r'''
import bpy, sys, json, importlib
stage, scene_path = sys.argv[sys.argv.index("--") + 1:]
sys.path.insert(0, stage)
addon = importlib.import_module("construct")
bpy.ops.wm.read_factory_settings(use_empty=True)
addon.register()
res = {"op": list(bpy.ops.import_scene.construct(filepath=scene_path))}
root = bpy.context.view_layer.objects.active
res["props"] = sorted(k for k in ("build", "open", "metal", "finish", "wire") if k in root)
objs = list(bpy.data.objects)
rt = addon.c_export.scene_mod
g = rt.compile_scene(json.load(open(scene_path, encoding="utf-8")), solid=True)

def world(o):
    e = o.evaluated_get(bpy.context.evaluated_depsgraph_get())
    return [tuple(e.matrix_world @ v.co) for v in e.data.vertices]

worst, n = 0.0, 0
for p in g["parts"]:
    if p["joint"] < 0:
        continue
    for o in objs:
        c = o.get("construct")
        if o.type != "MESH" or not c or c.get("part") != p["id"] or o.name.endswith(":light"):
            continue
        root["open"] = 0.0; root.update_tag(); bpy.context.scene.frame_set(1)
        rest = world(o)
        root["open"] = 1.0; root.update_tag(); bpy.context.scene.frame_set(2)
        for a, b in zip(rest, world(o)):
            w = rt._chain_apply(g["joints"][p["joint"]], g["articulations"], (a[0], a[2], -a[1]))
            worst = max(worst, max(abs(x - y) for x, y in zip((w[0], -w[2], w[1]), b))); n += 1
res["joint_vertices"], res["joint_worst"] = n, worst
res["drivers_valid"] = all(fc.driver.is_valid for o in objs if o.animation_data for fc in o.animation_data.drivers)
lights = [o for o in objs if o.name.endswith(":light")]
e = lights[0].evaluated_get(bpy.context.evaluated_depsgraph_get())
res["lights"], res["light_faces"], res["light_phase"] = len(lights), len(e.data.polygons), "_PHASE" in e.data.attributes
res["light_material"] = bool(e.data.materials) and e.data.materials[0] is not None and ":light:" in e.data.materials[0].name
res["edge_materials"] = sorted({m.name.endswith(":edges") for m in bpy.data.materials if ":light:" in m.name and not m.name.startswith("construct:")})
res["open_actions"] = [a.name for a in bpy.data.actions if a.name.startswith("open")]
bpy.ops.construct.animate_reveal()
res["reveal_keyed"] = root.animation_data is not None and root.animation_data.action is not None
print("RESULT " + json.dumps(res))
'''


@unittest.skipUnless(BLENDER, "set CONSTRUCT_BLENDER to a Blender binary to run")
class InBlender(unittest.TestCase):
    def run_in_blender(self, scene_name):
        with tempfile.TemporaryDirectory() as d:
            _builder().stage(Path(d, "construct"))
            Path(d, "t.py").write_text(BLENDER_TEST, encoding="utf-8")
            r = subprocess.run([BLENDER, "-b", "--factory-startup", "--python", str(Path(d, "t.py")), "--", d,
                                str(EXAMPLES / (scene_name + ".json"))], capture_output=True, text=True, timeout=600,
                               encoding="utf-8", errors="replace")
        line = next((ln for ln in r.stdout.splitlines() if ln.startswith("RESULT ")), None)
        self.assertIsNotNone(line, r.stdout[-2000:] + r.stderr[-2000:])
        return json.loads(line[7:])

    def test_controls_and_exact_joints(self):
        for name in ("cd", "juggernaut-et7"):
            with self.subTest(name):
                res = self.run_in_blender(name)
                self.assertEqual(res["op"], ["FINISHED"])
                self.assertEqual(res["props"], ["build", "finish", "metal", "open", "wire"])
                self.assertTrue(res["light_material"])   # the tubes carry the line material, not Blender's default
                self.assertEqual(res["edge_materials"], [False, True])   # design lines and construction lines
                self.assertTrue(res["drivers_valid"])
                self.assertGreater(res["joint_vertices"], 100)
                self.assertLess(res["joint_worst"], 1e-4)
                self.assertGreater(res["lights"], 0)
                self.assertGreater(res["light_faces"], 0)
                self.assertTrue(res["light_phase"])
                self.assertEqual(res["open_actions"], [])
                self.assertTrue(res["reveal_keyed"])

    def test_a_material_map_finishes_the_model(self):
        script = BLENDER_TEST.split("res[\"props\"]")[0] + (
            "import os\n"
            "mats = {m.name: m for m in bpy.data.materials}\n"
            "kinds = lambda m: {n.type for n in m.node_tree.nodes}\n"
            "res['wood'] = 'TEX_WAVE' in kinds(mats['case'])\n"
            "res['brushed'] = 'TEX_NOISE' in kinds(mats['front'])\n"
            "res['finish_mix'] = any(n.type == 'VALUE' and n.label == 'finish' for n in mats['case'].node_tree.nodes)\n"
            "print('RESULT ' + json.dumps(res))\n")
        with tempfile.TemporaryDirectory() as d:
            _builder().stage(Path(d, "construct"))
            sc = json.loads((EXAMPLES / "cd.json").read_text(encoding="utf-8"))
            ids = [p["id"] for p in scene.compile_scene(sc, solid=True)["parts"]]
            Path(d, "cd.json").write_text(json.dumps(sc), encoding="utf-8")
            Path(d, "cd.materials.json").write_text(json.dumps({"materials": [
                {"parts": ids[0], "name": "case", "color": "#8a5a32", "finish": "wood"},
                {"parts": "*", "name": "front", "color": "#c8cbd0", "finish": "brushed"}]}), encoding="utf-8")
            Path(d, "t.py").write_text(script, encoding="utf-8")
            r = subprocess.run([BLENDER, "-b", "--factory-startup", "--python", str(Path(d, "t.py")), "--", d,
                                str(Path(d, "cd.json"))], capture_output=True, text=True, timeout=600,
                               encoding="utf-8", errors="replace")
        line = next((ln for ln in r.stdout.splitlines() if ln.startswith("RESULT ")), None)
        self.assertIsNotNone(line, r.stdout[-2000:] + r.stderr[-2000:])
        res = json.loads(line[7:])
        self.assertEqual(res["op"], ["FINISHED"])   # the map beside the scene was found and used
        self.assertTrue(res["wood"] and res["brushed"] and res["finish_mix"])

    def test_a_netlogo_run_as_a_film(self):
        """Every turtle where the recording puts it, a tick a frame (30 a second); a wrap cuts its trail, a death
        hides it; the frames span the run, with no sound."""
        script = r'''
import bpy, sys, json, importlib
stage, run = sys.argv[sys.argv.index("--") + 1:]
sys.path.insert(0, stage)
addon = importlib.import_module("construct")
bpy.ops.wm.read_factory_settings(use_empty=True)
addon.register()
sc = bpy.context.scene
res = {"op": list(bpy.ops.import_scene.construct_run(filepath=run)), "frames": [sc.frame_start, sc.frame_end]}
agents, trails = bpy.data.objects["agents"], bpy.data.objects["trails"]
def at(frame):
    sc.frame_set(frame)
    return ([tuple(round(c, 4) for c in v.co) for v in agents.data.vertices],
            [a.value for a in agents.data.attributes["alive"].data], [tuple(v.co) for v in trails.data.vertices])
res["f7"], res["alive7"], _ = at(3)          # tick 2: 30 ticks a second, 30 frames a second
_, res["alive16"], trail = at(5)             # tick 4: the wrapped turtle's trail
n = len(trail) // 4
res["trail_step"] = max(sum((a - b) ** 2 for a, b in zip(trail[n + j], trail[n + j + 1])) ** 0.5 for j in range(n - 1))
_, res["alive16"], _ = at(6)                 # tick 5: the third turtle has died
_, _, trail = at(5)                          # tick 4: the fourth, born at tick 3, trails back to its birth only
n = len(trail) // 4
born = trail[3 * n:4 * n]
res["born_spread"] = max(sum((a - b) ** 2 for a, b in zip(born[0], q)) ** 0.5 for q in born)
e = trails.evaluated_get(bpy.context.evaluated_depsgraph_get())
res["tube_faces"] = len(e.data.polygons)
ed = sc.sequence_editor
res["sound"] = len(ed.strips if hasattr(ed, "strips") else ed.sequences) if ed else 0
print("RESULT " + json.dumps(res))
'''
        with tempfile.TemporaryDirectory() as d:
            _builder().stage(Path(d, "construct"))
            rows = [{"construct-netlogo": 1, "title": "Walkers", "netlogo": "7.0.4", "seed": 1, "turtle-vars": [],
                     "reporters": [], "patch-reporter": "", "patch-every": 0,
                     "world": {"min-pxcor": -8, "max-pxcor": 8, "min-pycor": -8, "max-pycor": 8}}]
            for tick in range(7):
                turtles = [[0, "turtles", -6 + tick, 0, 45], [1, "turtles", (6 + tick + 8.5) % 17 - 8.5, 3, 15]]
                if tick < 5:
                    turtles.append([2, "turtles", 0, -4, 105])
                if tick >= 3:
                    turtles.append([3, "turtles", 6, 6, 25])   # born at tick 3, far from the middle
                rows.append({"t": tick, "turtles": turtles})
            rows.append({"end": 6})
            Path(d, "walk.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
            Path(d, "t.py").write_text(script, encoding="utf-8")
            r = subprocess.run([BLENDER, "-b", "--factory-startup", "--python", str(Path(d, "t.py")), "--", d,
                                str(Path(d, "walk.jsonl"))], capture_output=True, text=True, timeout=600,
                               encoding="utf-8", errors="replace")
        line = next((ln for ln in r.stdout.splitlines() if ln.startswith("RESULT ")), None)
        self.assertIsNotNone(line, r.stdout[-2000:] + r.stderr[-2000:])
        res = json.loads(line[7:])
        s = 10 / 17   # the world, 17 patches across, is 10 m
        self.assertEqual(res["op"], ["FINISHED"])
        self.assertEqual(res["frames"], [1, 7])                                   # 6 ticks: 0.2 s at 30 a second
        self.assertAlmostEqual(res["f7"][0][0], -4 * s, places=3)                # the walker at tick 2
        self.assertAlmostEqual(res["f7"][2][1], -4 * s, places=3)
        self.assertEqual(res["alive7"], [1.0, 1.0, 1.0, 0.0])                    # the fourth not yet born
        self.assertEqual(res["alive16"], [1.0, 1.0, 0.0, 1.0])                    # the third has died
        self.assertLess(res["born_spread"], 1e-3)                                 # no streak from where it never was
        self.assertLess(res["trail_step"], 5.0)                                   # the wrap never crosses the world
        self.assertGreater(res["tube_faces"], 0)
        self.assertEqual(res["sound"], 0)

    def test_a_film_draws_links_and_patches(self):
        """A link is a line while the recording has it and both its agents live; the patches are a floor of
        cells in their recorded colours, record by record."""
        script = r'''
import bpy, sys, json, importlib
stage, run = sys.argv[sys.argv.index("--") + 1:]
sys.path.insert(0, stage)
addon = importlib.import_module("construct")
bpy.ops.wm.read_factory_settings(use_empty=True)
addon.register()
sc = bpy.context.scene
res = {"op": list(bpy.ops.import_scene.construct_run(filepath=run))}
links, floor = bpy.data.objects["links"], bpy.data.objects["patches"]
res["faces"] = len(floor.data.polygons)
for frame in (2, 4, 6):   # ticks 1, 3 and 5
    sc.frame_set(frame)
    fade = [a.value for a in links.data.attributes["fade"].data]
    res["links%d" % frame] = [fade[0], fade[2]]
    res["cell%d" % frame] = list(floor.data.attributes["col"].data[0].color)[:3]
print("RESULT " + json.dumps(res))
'''
        with tempfile.TemporaryDirectory() as d:
            _builder().stage(Path(d, "construct"))
            rows = [{"construct-netlogo": 1, "title": "Net", "netlogo": "7.0.4", "seed": 1, "turtle-vars": [],
                     "reporters": [], "patch-reporter": "pcolor", "patch-every": 1,
                     "world": {"min-pxcor": -2, "max-pxcor": 2, "min-pycor": -2, "max-pycor": 2}}]
            for tick in range(6):
                turtles = [[0, "turtles", -1, 0, 45], [1, "turtles", 1, 0, 45]] + ([[2, "turtles", 0, 1, 15]] if tick < 5 else [])
                row = {"t": tick, "turtles": turtles, "patches": [15 if (i < 5 and tick >= 2) else 55 for i in range(25)]}
                if tick == 0:
                    row["links"] = [[0, 1, "links"]]
                if tick == 3:
                    row["links"] = [[0, 1, "links"], [1, 2, "links"]]
                rows.append(row)
            rows.append({"end": 5})
            Path(d, "net.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
            Path(d, "t.py").write_text(script, encoding="utf-8")
            r = subprocess.run([BLENDER, "-b", "--factory-startup", "--python", str(Path(d, "t.py")), "--", d,
                                str(Path(d, "net.jsonl"))], capture_output=True, text=True, timeout=600,
                               encoding="utf-8", errors="replace")
        line = next((ln for ln in r.stdout.splitlines() if ln.startswith("RESULT ")), None)
        self.assertIsNotNone(line, r.stdout[-2000:] + r.stderr[-2000:])
        res = json.loads(line[7:])
        self.assertEqual((res["op"], res["faces"]), (["FINISHED"], 25))
        self.assertEqual(res["links2"], [1.0, 0.0])                    # tick 1: one link
        self.assertEqual(res["links4"], [1.0, 1.0])                    # tick 3: the second linked
        self.assertEqual(res["links6"], [1.0, 0.0])                    # tick 5: its agent died, the link goes dark
        self.assertGreater(res["cell2"][1], res["cell2"][0])           # tick 1: the top row green (55)
        self.assertGreater(res["cell4"][0], res["cell4"][1])           # tick 3: red (15)

    def test_the_zip_validates(self):
        with tempfile.TemporaryDirectory() as d:
            path = _builder().build(d)
            r = subprocess.run([BLENDER, "--command", "extension", "validate", str(path)], capture_output=True,
                               text=True, timeout=300, encoding="utf-8", errors="replace")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
