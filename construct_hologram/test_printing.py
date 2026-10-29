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


if __name__ == "__main__":
    unittest.main()
