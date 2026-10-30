"""3D printing: one watertight body at the asked size, gaps closed, open surfaces thickened, the files
well formed; and, when PrusaSlicer is present, the slicer agrees."""

import io
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from . import printing, studio

HERE = Path(__file__).resolve().parent


def scene_of(*parts):
    sc = studio.starter("object", "A print test")
    sc["parts"] = [dict({"role": "mass", "certainty": "inferred", "stage": 0}, **p) for p in parts]
    return sc


def box(pid, size, at, **kw):
    return dict({"id": pid, "shape": {"type": "box", "size": size}, "at": at}, **kw)


class Print(unittest.TestCase):
    def test_a_box_prints_watertight_at_the_asked_size(self):
        p = printing.make(scene_of(box("block", [0.1, 0.05, 0.04], [0, 0.025, 0])), size=50, detail=0.5)
        r = p["report"]
        self.assertTrue(r["watertight"])
        self.assertEqual((r["pieces"], r["pieces_in_air"]), (1, 0))
        self.assertTrue(all(abs(a - b) <= 0.5 for a, b in zip(r["size_mm"], (50, 20, 25))), r["size_mm"])   # Z up
        self.assertEqual(min(v[2] for v in p["vertices"]), 0.0)   # on the bed
        self.assertEqual(r["scale"], "1:2")
        self.assertFalse(r["needs_supports"])
        self.assertAlmostEqual(printing.make(scene_of(box("block", [0.1, 0.05, 0.04], [0, 0.025, 0])), scale=4,
                                             detail=0.5)["report"]["size_mm"][0], 25.0, delta=0.5)

    def test_gaps_between_parts_close_and_a_wide_one_is_reported(self):
        base = box("base", [0.06, 0.02, 0.06], [0, 0.01, 0])
        near = box("top", [0.03, 0.02, 0.03], [0, 0.0306, 0])    # 0.6 mm above the base at 1:1
        far = box("top", [0.03, 0.02, 0.03], [0, 0.035, 0])      # 5 mm above it
        r = printing.make(scene_of(base, near), scale=1, detail=0.5)["report"]
        self.assertEqual((r["pieces"], r["pieces_in_air"]), (1, 0))
        r = printing.make(scene_of(base, near), scale=1, detail=0.5, join=0)["report"]
        self.assertEqual((r["pieces"], r["pieces_in_air"]), (2, 1))
        r = printing.make(scene_of(base, far), scale=1, detail=0.5)["report"]
        self.assertEqual((r["pieces"], r["pieces_in_air"]), (2, 1))
        self.assertTrue(r["watertight"])
        self.assertIn("would start in the air", " ".join(printing.notes(r)))

    def test_an_open_surface_is_thickened_and_lines_and_annotations_are_left_out(self):
        sc = scene_of(box("base", [0.06, 0.01, 0.06], [0, 0.005, 0]),
                      {"id": "fin", "shape": {"type": "plane", "size": [0.04, 0.03]}, "at": [0, 0.025, 0]},
                      {"id": "seam", "role": "detail", "shape": {"type": "curve", "points": [[-0.03, 0.011, 0.031], [0.03, 0.011, 0.031]]}},
                      box("callout", [0.01, 0.01, 0.01], [0, 0.08, 0], floating=True))
        r = printing.make(sc, scale=1, detail=0.5)["report"]
        self.assertTrue(r["watertight"])
        self.assertEqual(r["pieces"], 1)
        self.assertEqual((r["thickened"], r["lines_left_out"], r["floating_left_out"]), (["fin"], ["seam"], ["callout"]))
        self.assertGreaterEqual(r["size_mm"][2], 39.5)                     # the fin stands on the base
        with_lines = printing.make(sc, scale=1, detail=0.5, lines=True)["report"]
        self.assertEqual(with_lines["lines_left_out"], [])
        self.assertGreater(with_lines["voxels"], r["voxels"])

    def test_a_sealed_cavity_is_filled_and_diagonal_edges_are_joined(self):
        n = (7, 7, 7)
        hollow = {(i, j): (0b11111 if i in (1, 5) or j in (1, 5) else 0b10001) << 1
                  for i in range(1, 6) for j in range(1, 6)}
        self.assertEqual(printing._fill_voids(hollow, n), 27)
        self.assertTrue(all(m == 0b11111 << 1 for m in hollow.values()))
        diagonal = {(1, 1): 0b10, (2, 2): 0b10}
        self.assertEqual(printing._manifold(diagonal), 1)
        verts, faces = printing._surface(diagonal, n)
        self.assertEqual(printing._edges_ok(faces), 0)

    def test_what_cannot_be_printed_says_why(self):
        with self.assertRaisesRegex(printing.PrintError, "nothing to print"):
            printing.make(scene_of({"id": "seam", "shape": {"type": "curve", "points": [[0, 0, 0], [0.1, 0, 0]]}}))
        with self.assertRaisesRegex(printing.PrintError, "coarser --detail"):
            printing.make(scene_of(box("block", [0.1, 0.05, 0.04], [0, 0.025, 0])), size=500, detail=0.1)
        with self.assertRaisesRegex(printing.PrintError, "stl or 3mf"):
            printing.write(scene_of(box("block", [0.1, 0.05, 0.04], [0, 0.025, 0])), "x.obj")

    def test_the_files_are_well_formed(self):
        p = printing.make(scene_of(box("block", [0.1, 0.05, 0.04], [0, 0.025, 0])), size=40, detail=0.5)
        stl = printing.to_stl(p)
        n = struct.unpack("<I", stl[80:84])[0]
        self.assertEqual((n, len(stl)), (len(p["triangles"]), 84 + 50 * n))
        z = zipfile.ZipFile(io.BytesIO(printing.to_3mf(p)))
        self.assertEqual(sorted(z.namelist()), ["3D/3dmodel.model", "[Content_Types].xml", "_rels/.rels"])
        model = z.read("3D/3dmodel.model").decode("utf-8")
        self.assertIn('unit="millimeter"', model)
        self.assertEqual(model.count("<vertex "), len(p["vertices"]))
        self.assertEqual(model.count("<triangle "), n)
        self.assertIn("<metadata name=\"Title\">A print test</metadata>", model)

    def test_a_gallery_construct_prints_as_one_piece(self):
        p = printing.make(studio.load(str(HERE.parent / "examples" / "leica-m3" / "scene.json")), size=80, detail=0.8)
        r = p["report"]
        self.assertTrue(r["watertight"])
        self.assertEqual((r["pieces"], r["pieces_in_air"]), (1, 0))
        self.assertTrue(r["fits_bed"])

    def test_the_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp, "scene.json")
            import json
            src.write_text(json.dumps(scene_of(box("block", [0.1, 0.05, 0.04], [0, 0.025, 0]))), encoding="utf-8")
            run = lambda *a: subprocess.run([sys.executable, "-m", "construct_hologram", "print", str(src), *a],
                                            cwd=HERE.parent, capture_output=True, text=True)
            ok = run("--out", str(Path(tmp, "block.3mf")), "--size", "30", "--detail", "0.5")
            self.assertEqual(ok.returncode, 0, ok.stderr)
            self.assertRegex(ok.stdout, r"block\.3mf: 30(\.\d)? x 12(\.\d)? x 15(\.\d)? mm at 1:3\.3, \d+ triangles")
            self.assertIn("watertight", ok.stdout)
            self.assertTrue(Path(tmp, "block.3mf").is_file())
            self.assertEqual(run("--out", str(Path(tmp, "block.stl")), "--bed", "200x200").returncode, 1)

    def test_mcp(self):
        import base64, json
        doc = scene_of(box("block", [0.1, 0.05, 0.04], [0, 0.025, 0]))
        msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                 "params": {"name": "construct_print", "arguments": {"document": doc, "size": 30, "detail": 0.5}}},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                 "params": {"name": "construct_print", "arguments": {"document": doc, "format": "obj"}}}]
        r = subprocess.run([sys.executable, "-m", __package__ + ".mcp_server"], cwd=HERE.parent, capture_output=True,
                           text=True, input="".join(json.dumps(m) + "\n" for m in msgs))
        lines = [json.loads(x) for x in r.stdout.splitlines() if x.strip()]
        res = lines[1]["result"]["structuredContent"]
        self.assertTrue(res["report"]["watertight"])
        z = zipfile.ZipFile(io.BytesIO(base64.b64decode(res["3mf_base64"])))
        self.assertIn("3D/3dmodel.model", z.namelist())
        self.assertTrue(lines[2]["result"]["isError"])

    @unittest.skipUnless(os.environ.get("CONSTRUCT_PRUSASLICER"), "set CONSTRUCT_PRUSASLICER to the PrusaSlicer binary")
    def test_prusaslicer_agrees(self):
        with tempfile.TemporaryDirectory() as tmp:
            sc = studio.load(str(HERE.parent / "examples" / "toyota-land-cruiser-fj62" / "scene.json"))
            for ext in ("stl", "3mf"):
                path = Path(tmp, "fj62." + ext)
                printing.write(sc, path, size=80, detail=0.5)
                info = subprocess.run([os.environ["CONSTRUCT_PRUSASLICER"], "--info", str(path)],
                                      capture_output=True, text=True, timeout=300).stdout
                self.assertIn("manifold = yes", info)
                self.assertRegex(info, r"number_of_parts =\s+1\b")
            sliced = subprocess.run([os.environ["CONSTRUCT_PRUSASLICER"], "--export-gcode", "--support-material",
                                     "--center", "100,100", "--output", str(Path(tmp, "fj62.gcode")), str(path)],
                                    capture_output=True, text=True, timeout=600)
            self.assertEqual(sliced.returncode, 0, sliced.stderr[-2000:])
            self.assertIn("estimated printing time", Path(tmp, "fj62.gcode").read_text(encoding="utf-8", errors="replace"))


def a_run(ticks=10, n=12):
    """A small spread: n turtles on a ring with links between neighbours, one more infected each tick."""
    import math
    frames = []
    for t in range(ticks + 1):
        turtles = [[k, "turtles", round(6 * math.cos(k), 3), round(6 * math.sin(k), 3), 15, k <= t, False] for k in range(n)]
        f = {"t": t, "turtles": turtles, "patches": []}
        if t == 0:
            f["links"] = [[k, (k + 1) % n, "links"] for k in range(n)]
        frames.append(f)
    return {"header": {"title": "A ring", "netlogo": "7.0.4", "seed": 3, "turtle-vars": ["infected?", "resistant?"],
                       "world": {"min-pxcor": -8, "max-pxcor": 8, "min-pycor": -8, "max-pycor": 8}},
            "frames": frames, "end": ticks}


class Plates(unittest.TestCase):
    def test_a_run_as_plates_that_stack(self):
        from . import plates
        r = plates.make(a_run(), at=[0, 5, 10], size=60)
        self.assertEqual([p["tick"] for p in r["plates"]], [0, 5, 10])
        self.assertEqual([p["on"] for p in r["plates"]], [1, 6, 11])
        self.assertEqual([p["links"] for p in r["plates"]], [12, 12, 12])
        self.assertEqual(r["state"], "infected?")
        meshes = [p["mesh"] for p in r["plates"]] + r["pins"] + [r["sleeves"]]
        self.assertTrue(all(m["report"]["watertight"] for m in meshes))
        top = [max(v[2] for v in p["mesh"]["vertices"]) for p in r["plates"]]
        self.assertTrue(all(abs(z - (plates.THICK_MM + plates.HIGH_MM)) < 0.3 for z in top), top)
        self.assertEqual(r["size_mm"], [76.0, 76.0])                       # 60 mm of world and its rim
        self.assertAlmostEqual(r["stack_mm"], 3 * plates.THICK_MM + 2 * plates.GAP_MM)
        pin = max(v[2] for v in r["pins"][1]["vertices"])
        self.assertGreaterEqual(pin, r["stack_mm"])                        # long enough to go through them all
        none_on = plates.make(a_run(), at=[3], size=60, tall=False)["plates"][0]
        self.assertEqual(none_on["on"], 8)
        self.assertEqual([p["tick"] for p in plates.make(a_run(), count=3, size=60)["plates"]], [0, 5, 10])

    def test_the_key_card_and_what_cannot_be_plated(self):
        from . import plates
        run = a_run()
        with tempfile.TemporaryDirectory() as tmp:
            rec = Path(tmp, "run.jsonl")
            rec.write_text("{}\n", encoding="utf-8")
            r = plates.write(run, Path(tmp, "plates"), "stl", recording=rec, at=[0, 10], size=60)
            names = sorted(p.name for p in Path(tmp, "plates").iterdir())
            self.assertEqual(names, ["KEY.md", "pin-3mm.stl", "pin-4mm.stl", "plate-01-tick-0.stl", "plate-02-tick-10.stl",
                                     "sleeves.stl"])
            key = Path(tmp, "plates", "KEY.md").read_text(encoding="utf-8")
            self.assertIn("| 2 | 10 | 12 | 11 | 12 |", key)
            self.assertIn("sha256 `", key)
            self.assertTrue(r["watertight"])
        for kw, msg in (({"at": [99]}, "outside the run"), ({"state": "nope"}, "no turtle variable"),
                        ({"count": 1}, "at least 2")):
            with self.subTest(msg), self.assertRaisesRegex(plates.PlatesError, msg):
                plates.make(run, size=60, **kw)
        empty = dict(run, frames=[{"t": 0, "turtles": []}])
        with self.assertRaisesRegex(plates.PlatesError, "no turtles"):
            plates.make(empty)

    @unittest.skipUnless(os.environ.get("CONSTRUCT_PRUSASLICER"), "set CONSTRUCT_PRUSASLICER to the PrusaSlicer binary")
    def test_prusaslicer_reads_a_plate_as_one_part(self):
        from . import plates
        with tempfile.TemporaryDirectory() as tmp:
            plates.write(a_run(), tmp, "3mf", at=[0, 10], size=60)
            for f in ("plate-02-tick-10.3mf", "pin-4mm.3mf"):
                info = subprocess.run([os.environ["CONSTRUCT_PRUSASLICER"], "--info", str(Path(tmp, f))],
                                      capture_output=True, text=True, timeout=300).stdout
                self.assertIn("manifold = yes", info)
                self.assertRegex(info, r"number_of_parts =\s+1\b")


if __name__ == "__main__":
    unittest.main()
