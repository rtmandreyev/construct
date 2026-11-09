"""FreeCAD: the data FreeCAD builds from (millimetres, Z up, joints converted), and, when FreeCAD is
present, the document and STEP it writes: named parts, groups by stage and joint, a joint that opens."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from . import freecad, studio

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE.parent / "examples"


def example(slug):
    return studio.load(str(EXAMPLES / slug / "scene.json"))


class Payload(unittest.TestCase):
    def test_parts_joints_and_frame(self):
        data = freecad.payload(example("leica-m3"))
        ids = [p["id"] for p in data["parts"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("telescoping-inner-barrel", ids)
        self.assertTrue(all(p["solids"] or p["shells"] for p in data["parts"]))
        self.assertTrue(set(data["left_out"]).isdisjoint(ids))
        slide = data["articulations"][0]
        self.assertEqual((slide["type"], slide["unit"], slide["amount"]), ("slide", "mm", 14.0))
        self.assertEqual(slide["axis"], [0.0, -1.0, 0.0])   # construct +Z is FreeCAD -Y
        lens = next(p for p in data["parts"] if p["id"] == "telescoping-inner-barrel")
        self.assertEqual(lens["chain"][0], 0)
        zs = [v[2] for p in data["parts"] for s in p["solids"] + p["shells"] for t in s for v in t]
        self.assertGreater(max(zs), 50.0)   # millimetres, Z up: the camera stands about 77 mm tall
        self.assertLess(max(zs), 120.0)

    def test_each_copy_is_placed_where_the_construct_draws_it(self):
        import math
        data = freecad.payload(example("leica-m3"))
        for pid in ("film-reminder-rim", "focus-ring"):   # turned a quarter, as the camera's dials are
            p = next(x for x in data["parts"] if x["id"] == pid)
            spec = p["exact"]
            self.assertTrue(spec and spec["matrices"])
            if spec["type"] == "cylinder":
                r, h = spec["r0"], spec["height"]
                loc = [(r * math.cos(a), y, r * math.sin(a)) for a in [i * math.pi / 24 for i in range(48)] for y in (0, h)]
            else:
                loc = [(rr * math.cos(a), y, rr * math.sin(a)) for rr, y in spec["profile"]
                       for a in [i * math.pi / 24 for i in range(48)]]
            m = spec["matrices"][0]
            placed = [[sum(m[i][j] * q[j] for j in range(3)) + m[i][3] for i in range(3)] for q in loc]
            mesh = [v for s in p["solids"] + p["shells"] for t in s for v in t]
            for k in range(3):
                self.assertAlmostEqual(min(q[k] for q in placed), min(v[k] for v in mesh), delta=0.5)
                self.assertAlmostEqual(max(q[k] for q in placed), max(v[k] for v in mesh), delta=0.5)
        self.assertIsNone(freecad.payload(example("leica-m3"), exact=False)["parts"][0]["exact"])

    def test_without_freecad_it_says_how_to_get_it(self):
        self.assertIsNone(freecad.find_freecad("/no/such/freecadcmd"))
        real = freecad.find_freecad
        freecad.find_freecad = lambda given=None: None
        try:
            with self.assertRaisesRegex(freecad.FreeCADError, "FreeCAD not found"):
                freecad.make(example("yamaha-cfx"), fcstd="x.FCStd")
        finally:
            freecad.find_freecad = real
        with self.assertRaisesRegex(freecad.FreeCADError, "nothing to write"):
            freecad.make(example("yamaha-cfx"))
        r = subprocess.run([sys.executable, "-m", "construct_hologram", "freecad", str(EXAMPLES / "yamaha-cfx" / "scene.json"),
                            "--out", "x.obj"], cwd=HERE.parent, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("--out FILE.FCStd or FILE.step", r.stderr)

    def test_a_crash_says_how_it_ended_not_the_environment(self):
        # off screen, FreeCAD's launcher prints the environment and Qt its notices whether or not anything is wrong
        noise = "HOME=/Users/someone\nSSH_AUTH_SOCK=/var/run/x\nRunning: /x/freecad\n"
        qt = "This plugin does not support grabbing the keyboard\n" * 8
        crashed = subprocess.CompletedProcess([], -11, noise, qt)
        said = freecad._stopped(crashed)
        self.assertIn("killed (signal 11)", said)
        self.assertIn("try again", said)
        self.assertNotIn("HOME=", said)
        self.assertNotIn("grabbing", said)
        failed = subprocess.CompletedProcess([], 1, noise, qt + "Traceback (most recent call last):\nValueError: bad\n")
        said = freecad._stopped(failed)
        self.assertIn("exit code 1", said)
        self.assertTrue(said.endswith("Traceback (most recent call last):\nValueError: bad"))
        self.assertNotIn("try again", said)

    def test_freecad_is_given_only_what_it_needs(self):
        os.environ["CONSTRUCT_TEST_SECRET"] = "sk-not-for-freecad"
        try:
            env = freecad._freecad_env("/x/FreeCAD")
        finally:
            del os.environ["CONSTRUCT_TEST_SECRET"]
        self.assertNotIn("CONSTRUCT_TEST_SECRET", env)
        self.assertEqual((env["PATH"], env["QT_QPA_PLATFORM"]), (os.environ["PATH"], "offscreen"))
        self.assertNotIn("QT_QPA_PLATFORM", freecad._freecad_env(None))   # its command line has no window to hide
        self.assertNotIn("environ", freecad.SCRIPT)                       # the job is in the script


CHECK = r'''
import FreeCAD, Import, json, os
out = {}
doc = FreeCAD.openDocument(os.environ["FC_FILE"])
feats = [o for o in doc.Objects if o.TypeId == "Part::Feature" and not o.Label.startswith("axis-")]
out["labels"] = sorted(o.Label for o in feats)
out["valid"] = all(o.Shape.isValid() for o in feats)
out["visible"] = all(o.Visibility for o in doc.Objects if hasattr(o, "Visibility"))
out["groups"] = sorted(o.Label for o in doc.Objects if o.TypeId == "App::Part")
lid = [o for o in doc.Objects if o.Label == "joint-lid-open"][0]
part = [o for o in lid.Group if o.Label == "lid"][0]
out["role"] = part.Role
before = part.Shape.BoundBox.ZMax
lid.Placement = lid.Open
out["rise"] = part.Shape.transformGeometry(lid.Placement.toMatrix()).BoundBox.ZMax - before
step = FreeCAD.newDocument("step")
Import.insert(os.environ["FC_STEP"], "step")
out["step_labels"] = sorted(o.Label for o in step.Objects if o.TypeId == "Part::Feature")
json.dump(out, open(os.environ["FC_OUT"], "w"))
'''


@unittest.skipUnless(os.environ.get("CONSTRUCT_FREECAD"), "set CONSTRUCT_FREECAD to FreeCAD's freecadcmd to run")
class InFreeCAD(unittest.TestCase):
    def test_a_piano_with_its_lid(self):
        with tempfile.TemporaryDirectory() as tmp:
            fc, step = Path(tmp, "piano.FCStd"), Path(tmp, "piano.step")
            r = freecad.make(example("yamaha-cfx"), fcstd=fc, step=step)
            self.assertEqual(r["invalid"], [])
            self.assertEqual(r["faceted"], [])                 # every part a true shape
            self.assertEqual(len(r["exact"]), r["parts"])
            self.assertIn("CYLINDRICAL_SURFACE", step.read_text(errors="replace"))   # legs and casters, not polygons
            self.assertEqual(r["joints"], 2)
            self.assertTrue(fc.is_file() and step.is_file())
            if freecad._app(os.environ["CONSTRUCT_FREECAD"]):   # built by the app: it opens with every part showing
                import zipfile
                gui = zipfile.ZipFile(fc).read("GuiDocument.xml").decode("utf-8")
                self.assertIn("orientation 0.7447 0.3085 0.5959", gui)   # opens framed, isometric
            Path(tmp, "check.py").write_text(CHECK, encoding="utf-8")
            env = dict(os.environ, FC_FILE=str(fc), FC_STEP=str(step), FC_OUT=str(Path(tmp, "out.json")))
            subprocess.run([os.environ["CONSTRUCT_FREECAD"], str(Path(tmp, "check.py"))], cwd=tmp, env=env,
                           capture_output=True, timeout=600)
            out = json.loads(Path(tmp, "out.json").read_text(encoding="utf-8"))
            self.assertEqual(len(out["labels"]), r["parts"])
            self.assertIn("lid", out["labels"])
            self.assertTrue(out["valid"])
            self.assertTrue(out["visible"])   # opened in FreeCAD, the model shows
            self.assertIn("joint-lid-open", out["groups"])
            self.assertIn("stage-0", out["groups"])
            self.assertEqual(out["role"], "identity")   # its provenance travels with it
            self.assertGreater(out["rise"], 900)          # a 42 degree hinge on a 1.6 m lid lifts its edge about 1.07 m
            self.assertIn("lid", out["step_labels"])

    def test_a_closed_lathe_off_the_axis_is_a_solid(self):
        with tempfile.TemporaryDirectory() as tmp:   # the knob's body and skirt: closed outlines around a bore
            r = freecad.make(example("braun-sk4-knob"), step=Path(tmp, "knob.step"))
            for pid in ("knob-body", "knob-skirt"):
                self.assertIn(pid, r["exact"])
                self.assertNotIn(pid, r["surfaces"])
            self.assertEqual(r["invalid"], [])


if __name__ == "__main__":
    unittest.main()
