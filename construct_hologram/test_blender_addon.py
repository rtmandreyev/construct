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
res["props"] = sorted(k for k in ("build", "open", "metal", "wire") if k in root)
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
                self.assertEqual(res["props"], ["build", "metal", "open", "wire"])
                self.assertTrue(res["drivers_valid"])
                self.assertGreater(res["joint_vertices"], 100)
                self.assertLess(res["joint_worst"], 1e-4)
                self.assertGreater(res["lights"], 0)
                self.assertGreater(res["light_faces"], 0)
                self.assertTrue(res["light_phase"])
                self.assertEqual(res["open_actions"], [])
                self.assertTrue(res["reveal_keyed"])

    def test_the_zip_validates(self):
        with tempfile.TemporaryDirectory() as d:
            path = _builder().build(d)
            r = subprocess.run([BLENDER, "--command", "extension", "validate", str(path)], capture_output=True,
                               text=True, timeout=300, encoding="utf-8", errors="replace")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
