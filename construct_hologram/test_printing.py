"""3D printing: one watertight body at the asked size, gaps closed, open surfaces thickened, the files
well formed; and, when PrusaSlicer is present, the slicer agrees."""

import io
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from . import kit as kit_mod, printing, studio

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

    def test_lines_engraved_cut_grooves_without_cutting_the_print_apart(self):
        sc = scene_of(box("panel", [0.06, 0.04, 0.02], [0, 0.02, 0]),
                      {"id": "seam", "role": "detail", "shape": {"type": "curve", "points": [[-0.025, 0.02, 0.0101], [0.025, 0.02, 0.0101]]}},
                      {"id": "post", "role": "detail", "shape": {"type": "curve", "points": [[0, 0.04, 0], [0, 0.06, 0]]}})
        plain = printing.make(sc, scale=1, detail=0.5)["report"]
        cut = printing.make(sc, scale=1, detail=0.5, lines="engrave")["report"]
        self.assertTrue(cut["watertight"])
        self.assertEqual(cut["pieces"], 1)
        self.assertLess(cut["voxels"], plain["voxels"])          # the seam is cut into the face
        self.assertEqual(cut["lines_left_out"], [])
        raised = printing.make(sc, scale=1, detail=0.5, lines=True)["report"]   # --lines alone: raised, as before
        self.assertGreater(raised["voxels"], plain["voxels"])
        with self.assertRaisesRegex(printing.PrintError, "lines: one of"):
            printing.make(sc, scale=1, detail=0.5, lines="etch")

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



class Printers(unittest.TestCase):
    """Printer classes: the largest print that stands on each, and the construct's own solids kept exact."""

    def test_fit_takes_the_bed_and_turns_the_print_when_it_must(self):
        sc = scene_of(box("hull", [0.4, 0.1, 1.0], [0, 0.05, 0]))   # 1 m deep, 0.4 m wide, 0.1 m tall
        r = printing.make(sc, fit=True, bed=(250.0, 210.0, 220.0), detail=1.0)["report"]
        self.assertTrue(r["fits_bed"])
        self.assertTrue(r.get("turned"))                             # the long side along the bed's 250 mm
        self.assertAlmostEqual(r["size_mm"][0], 250 * printing.FIT_MARGIN, delta=1.0)
        rows = {x["printer"]: x for x in printing.printers(sc)}
        self.assertEqual(set(rows), set(printing.PRINTERS))
        self.assertGreater(rows["large"]["size_mm"][2], rows["small"]["size_mm"][2])
        self.assertLess(rows["large"]["smallest_real_mm"], rows["small"]["smallest_real_mm"])

    def test_a_voxel_finer_than_the_grid_is_widened_when_asked(self):
        sc = scene_of(box("block", [0.1, 0.05, 0.04], [0, 0.025, 0]))
        with self.assertRaises(printing.PrintError):
            printing.make(sc, size=200, detail=0.05)
        r = printing.make(sc, size=200, detail=0.05, coarsen=True)["report"]
        self.assertGreater(r["detail_mm"], 0.05)
        self.assertEqual(r["detail_asked_mm"], 0.05)

    def test_an_exact_print_keeps_the_solids_as_they_are(self):
        sc = scene_of(box("base", [0.06, 0.02, 0.06], [0, 0.01, 0]),
                      {"id": "dome", "shape": {"type": "sphere", "radius": 0.02}, "at": [0, 0.03, 0]},
                      {"id": "sign", "shape": {"type": "plane", "size": [0.04, 0.02]}, "at": [0, 0.03, 0.031]})
        p = printing.make(sc, size=60, detail=0.5, exact=True)
        r = p["report"]
        self.assertTrue(r["exact"] and r["watertight"])
        self.assertEqual(r["exact_parts"], ["base", "dome"])
        self.assertIn("sign", r["thickened"])                        # an open surface still goes through the voxels
        self.assertEqual((r["pieces"], r["pieces_in_air"]), (1, 0))
        base = next(o for o in p["objects"] if o["name"] == "base")
        self.assertEqual(len(base["triangles"]), 12)                # the box as it is: twelve triangles, not voxels
        data = printing.to_3mf(p)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            self.assertEqual(z.read("3D/3dmodel.model").count(b"<object "), 1)
            self.assertIn(b'value="dome"', z.read("Metadata/Slic3r_PE_model.config"))
        with self.assertRaises(printing.PrintError):
            printing.write(sc, Path(tempfile.gettempdir(), "x.stl"), exact=True)

    @unittest.skipUnless(os.environ.get("CONSTRUCT_PRUSASLICER"), "set CONSTRUCT_PRUSASLICER to the PrusaSlicer binary")
    def test_prusaslicer_reads_an_exact_print_as_one_object_of_parts(self):
        with tempfile.TemporaryDirectory() as tmp:
            sc = studio.load(str(HERE.parent / "examples" / "toyota-land-cruiser-fj62" / "scene.json"))
            path = Path(tmp, "fj62.3mf")
            printing.write(sc, path, size=80, detail=0.5, exact=True)
            info = subprocess.run([os.environ["CONSTRUCT_PRUSASLICER"], "--info", str(path)],
                                  capture_output=True, text=True, timeout=300).stdout
            self.assertIn("manifold = yes", info)
            self.assertEqual(info.count("[fj62.3mf]"), 1)
            sliced = subprocess.run([os.environ["CONSTRUCT_PRUSASLICER"], "--export-gcode", "--center", "100,100",
                                     "--output", str(Path(tmp, "fj62.gcode")), str(path)],
                                    capture_output=True, text=True, timeout=600)
            self.assertEqual(sliced.returncode, 0, sliced.stderr[-2000:])
            self.assertNotIn("conflict", sliced.stdout + sliced.stderr)


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


class Kit(unittest.TestCase):
    def test_a_kit_of_pieces_that_fit_numbered_plated_and_explained(self):
        from . import kit
        sc = studio.load(str(HERE / "examples" / "v2" / "cd.json"))
        k = kit.make(sc, size=120, detail=0.5)
        names = [p["name"] for p in k["pieces"]]
        self.assertEqual(names, ["tray", "hinge (1 of 2)", "hinge (2 of 2)", "lid"])   # the base first; mirrored hinges apart
        self.assertEqual([p["number"] for p in k["pieces"]], [1, 2, 3, 4])
        self.assertEqual(sorted(n for s in k["steps"] for n in s["pieces"]), [1, 2, 3, 4])
        self.assertEqual(sorted(n for pl in k["plates"] for n, _, _ in pl["pieces"]), [1, 2, 3, 4])
        self.assertTrue(all(p["onto"] for p in k["pieces"][1:]))            # each glued to something built
        self.assertEqual(sum(printing._edges_ok(p["mesh"]["triangles"]) for p in k["pieces"]), 0)   # all watertight
        self.assertTrue(all(min(v[2] for v in p["mesh"]["vertices"]) == 0 for p in k["pieces"]))      # on the bed
        cols = [p["cols"] for p in k["pieces"]]
        self.assertTrue(all(not (a.get(c, 0) & m) for i, a in enumerate(cols) for b in cols[i + 1:] for c, m in b.items()))
        self.assertTrue(k["report"]["ok"], k["report"]["problems"])
        one = kit.make(sc, size=120, detail=0.5, plan={"merge": [["tray", "hing*"]], "clear": ["lid"], "title": "A case kit"})
        self.assertEqual([p["name"] for p in one["pieces"]][:1], ["tray"])        # the hinges moulded with the tray
        self.assertIn("booklet", [p["name"] for p in one["pieces"]])             # a clear lid yields: the booklet stays whole
        self.assertEqual(one["pieces"][0]["parts"], ["hinge", "tray"])
        self.assertTrue(next(p for p in one["pieces"] if p["head"] == "lid")["clear"])
        self.assertEqual(one["title"], "A case kit")
        with self.assertRaisesRegex(kit.KitError, "a kit plan is an object"):
            kit.make(sc, plan={"glue": []})

    def test_a_part_two_merges_match_joins_the_first(self):
        sc = scene_of(box("seat-back-1", [0.02, 0.02, 0.02], [0, 0.01, 0]), box("seat-base-1", [0.02, 0.01, 0.02], [0, 0.005, 0.02]),
                      box("seat-back--1", [0.02, 0.02, 0.02], [0.05, 0.01, 0]))
        k = kit_mod.make(sc, size=40, detail=0.5, plan={"merge": [["seat-*--1"], ["seat-*-1"]]})
        self.assertTrue(k["pieces"])

    def test_a_bad_plan_or_size_is_refused_not_a_crash(self):
        sc = scene_of(box("block", [0.1, 0.05, 0.04], [0, 0.025, 0]))
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d, "plan.json")
            bad.write_text('{"merge": 5}', encoding="utf-8")
            for kw in ({"plan": str(Path(d, "missing.json"))}, {"plan": str(bad)}, {"scale": 0}, {"size": -1},
                       {"bed": (0, 0, 0)}):
                with self.assertRaises(kit_mod.KitError):
                    kit_mod.make(sc, detail=0.5, **kw)

    def test_the_command_refuses_a_zero_size_and_a_missing_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, "s.json")
            path.write_text(json.dumps(scene_of(box("block", [0.1, 0.05, 0.04], [0, 0.025, 0]))), encoding="utf-8")
            for args in (["print", str(path), "--out", str(Path(d, "x.stl")), "--size", "0"],
                         ["print", str(path), "--out", str(Path(d, "x.stl")), "--detail", "0"],
                         ["compare", str(path), "--trace", str(Path(d, "missing.json"))]):
                r = subprocess.run([sys.executable, "-m", "construct_hologram"] + args, cwd=HERE.parent,
                                   capture_output=True, text=True)
                self.assertEqual(r.returncode, 1, args)
                self.assertNotIn("Traceback", r.stderr)

    def test_the_kit_files(self):
        from . import kit
        sc = studio.load(str(HERE / "examples" / "v2" / "cd.json"))
        k = kit.make(sc, size=120, detail=0.5)
        with tempfile.TemporaryDirectory() as tmp:
            kit.write(k, tmp)
            z = zipfile.ZipFile(Path(tmp, "plate-1.3mf"))
            model = z.read("3D/3dmodel.model").decode("utf-8")
            self.assertEqual(model.count("<object "), 4)
            self.assertIn('name="1 tray"', model)
            booklet = Path(tmp, "booklet.html").read_text(encoding="utf-8")
            self.assertIn("Step 2", booklet)
            step = Path(tmp, "img", "step-1.svg").read_text(encoding="utf-8")
            self.assertIn("<path d=", step)                                       # drawn in the construct's lines
            self.assertIn(">1</text>", step)                                      # the new piece's callout
            summary = json.loads(Path(tmp, "kit.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["report"]["counts"]["pieces"], 4)
            self.assertIn("kit designer", kit.CRITIC.lower() + " kit designer")


if __name__ == "__main__":
    unittest.main()
