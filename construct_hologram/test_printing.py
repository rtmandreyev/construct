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
        self.assertIn("sign", r["thickened"])
        self.assertEqual((r["shelled"], r["thickened_in_voxels"]), (["sign"], []))   # a true shell, not voxels
        sign = next(o for o in p["objects"] if o["name"] == "sign")
        self.assertEqual(len(sign["triangles"]), 12)                # the plane as a thin slab: two faces, four edges
        span = [max(v[a] for v in sign["vertices"]) - min(v[a] for v in sign["vertices"]) for a in range(3)]
        self.assertAlmostEqual(min(span), 0.8, places=3)            # the wall, measured through the slab
        self.assertEqual((r["pieces"], r["pieces_in_air"]), (1, 0))
        base = next(o for o in p["objects"] if o["name"] == "base")
        self.assertEqual(len(base["triangles"]), 12)                # the box as it is: twelve triangles, not voxels
        data = printing.to_3mf(p)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            self.assertEqual(z.read("3D/3dmodel.model").count(b"<object "), 1)
            self.assertIn(b'value="dome"', z.read("Metadata/Slic3r_PE_model.config"))
        with self.assertRaises(printing.PrintError):
            printing.write(sc, Path(tempfile.gettempdir(), "x.stl"), exact=True)

    def test_a_too_thin_solid_grows_to_the_wall_in_its_own_shape(self):
        sc = scene_of(box("base", [0.06, 0.02, 0.06], [0, 0.01, 0]),
                      box("pane", [0.04, 0.03, 0.0005], [0, 0.035, 0.0]))      # 0.5 mm of glass: 0.5 mm printed at 1:1
        p = printing.make(sc, scale=1, detail=0.4, exact=True)
        r = p["report"]
        self.assertEqual((r["shelled"], r["thickened_in_voxels"]), (["pane"], []))
        pane = next(o for o in p["objects"] if o["name"] == "pane")
        self.assertEqual(len(pane["triangles"]), 12)                           # still a box
        span = sorted(max(v[a] for v in pane["vertices"]) - min(v[a] for v in pane["vertices"]) for a in range(3))
        self.assertTrue(0.8 <= span[0] < 0.85, span)                           # at least the wall, barely more
        self.assertAlmostEqual(span[1] - 30.0, span[0] - 0.5, places=6)        # grown by as much on every side
        self.assertTrue(r["watertight"])

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

    def test_glass_and_its_frame_holding_each_other_are_not_lost(self):
        from . import kit
        # the pane goes into its frame (the last opaque part framing it); the frame's strongest join is the pane, so
        # each was the other's host: a ring the walk from the base never reached, and both vanished
        sc = scene_of(box("body", [0.12, 0.04, 0.12], [0, 0.02, 0]),
                      box("frame", [0.1, 0.1, 0.01], [0, 0.09, 0.0]),               # a plate standing on its edge
                      box("window-glass", [0.1, 0.1, 0.01], [0, 0.09, 0.01]))       # flat against the frame's face
        k = kit.make(sc, size=120, detail=1.0, plan={"order": [{"name": "body", "parts": ["body"]},
                                                              {"name": "glass", "parts": ["window-glass"]},
                                                              {"name": "frame", "parts": ["frame"]}]})
        self.assertEqual(sorted(p["head"] for p in k["pieces"]), ["body", "frame", "window-glass"])
        self.assertEqual(sorted(n for s in k["steps"] for n in s["new"]), [1, 2, 3])            # each glued once
        self.assertTrue(all(p["onto"] for p in k["pieces"][1:]))

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

    def test_a_plan_can_make_glass_opaque_and_a_merge_keeps_its_heads_stage(self):
        # found by a live run's kit critic: a chrome mirror glass printed clear; a shell built before its interior
        sc = scene_of(box("shell", [0.2, 0.05, 0.1], [0, 0.025, 0]),
                      dict(box("strut-tower", [0.02, 0.03, 0.02], [0.05, 0.04, 0]), stage=0),
                      dict(box("mirror-glass", [0.02, 0.02, 0.004], [0.11, 0.04, 0]), stage=2))
        sc["parts"][0]["stage"] = 1
        k = kit_mod.make(sc, size=100, detail=0.5, plan={"merge": [["shell", "strut-tower"]], "opaque": ["mirror-*"]})
        mirror = next(p for p in k["pieces"] if "mirror-glass" in p["parts"])
        self.assertFalse(mirror["clear"])
        shell = next(p for p in k["pieces"] if "shell" in p["parts"])
        self.assertEqual(shell["stage"], 1)   # the shell's, not the small tower's earlier stage

    def test_the_fit_names_what_pokes_through_and_what_is_buried_not_what_is_set_in(self):
        from . import fit
        sc = scene_of(box("body", [0.2, 0.1, 0.1], [0, 0.05, 0]),
                      box("aerial", [0.01, 0.16, 0.01], [0.05, 0.07, 0.0]),            # in the body, its tip out the top
                      box("badge", [0.04, 0.02, 0.01], [0, 0.05, 0.052]),             # set into the front face
                      box("block", [0.02, 0.02, 0.02], [-0.05, 0.05, 0]))             # wholly inside
        sc["parts"][1]["shape"]["size"] = [0.01, 0.16, 0.01]
        sc["parts"][1]["at"] = [0.05, 0.09, 0.0]                                      # from y 0.01 to 0.17: out of the top
        r = fit.check(sc, cells=80)
        codes = {(i["code"], i["parts"][0]) for i in r["issues"]}
        self.assertIn(("buried", "block"), codes)
        self.assertNotIn("badge", {i["parts"][0] for i in r["issues"]})               # set in, not poking through
        self.assertIn("fit:", fit.report(r))

    def test_a_part_already_in_pieces_by_itself_is_not_said_to_poke(self):
        from . import fit
        from unittest import mock
        # a skin whose surface voxels fall apart by themselves: a big piece and a crumb (x 4..13 and x 15), one layer
        # thick, lying on a block (x 0..6). What is left of the skin off the block is the same two pieces, not a poke
        grid = printing._Grid([0, 0, 0], [16, 4, 8], 1.0, 0)
        skin = {(x, y): 1 << 4 for x in list(range(4, 14)) + [15] for y in range(4)}
        block = {(x, y): (1 << 5) - 1 for x in range(0, 7) for y in range(4)}
        with mock.patch.object(fit, "_volumes", return_value=(grid, {"skin": skin, "block": block}, {})), \
                mock.patch.object(fit.scene_mod, "compile_scene", return_value=None):
            self.assertEqual(fit.check(scene_of(box("x", [1, 1, 1], [0, 0, 0])))["issues"], [])

    def test_the_same_sub_assembly_built_twice_is_one_step_done_twice(self):
        self.assertEqual({kit_mod._kind_of(n) for n in ("tyre-front (1 of 2)", "tyre-rear--1", "tyre-left", "tyre-r")}, {"tyre"})
        piece = lambda n, name, size: {"number": n, "name": name, "size_mm": size}
        pieces = [piece(1, "chassis", [100, 50, 10]), piece(2, "wheel-front-left", [20, 20, 8]), piece(3, "hub-front-left", [6, 6, 4]),
                  piece(4, "wheel-rear-right", [21, 20, 8]), piece(5, "hub-rear-right", [6, 6, 4]),
                  piece(6, "lamp-left", [9, 5, 3]), piece(7, "lamp-right", [30, 5, 3])]
        steps = [{"kind": "base", "new": [1], "pieces": [1], "glue": [(1, None)]},
                 {"kind": "bench", "assembly": 2, "new": [2, 3], "pieces": [2, 3], "glue": [(2, None), (3, 2)]},
                 {"kind": "fit", "assembly": 2, "new": [], "pieces": [2], "glue": [(2, 1)]},
                 {"kind": "bench", "assembly": 4, "new": [4, 5], "pieces": [4, 5], "glue": [(4, None), (5, 4)]},
                 {"kind": "fit", "assembly": 4, "new": [], "pieces": [4], "glue": [(4, 1)]},
                 {"kind": "bench", "assembly": 6, "new": [6], "pieces": [6], "glue": [(6, None)]},
                 {"kind": "fit", "assembly": 6, "new": [], "pieces": [6], "glue": [(6, 1)]},
                 {"kind": "bench", "assembly": 7, "new": [7], "pieces": [7], "glue": [(7, None)]},
                 {"kind": "fit", "assembly": 7, "new": [], "pieces": [7], "glue": [(7, 1)]}]
        out = kit_mod._combine(steps, pieces)
        self.assertEqual(len(out), 7)                                        # the two wheels are one step, done twice
        self.assertEqual(out[1]["times"], 2)
        self.assertEqual(sorted(out[1]["new"]), [2, 3, 4, 5])
        self.assertIn("2 ×", out[1]["name"])
        self.assertFalse(any(s.get("times", 1) > 1 for s in out[3:]))      # two lamps of different sizes stay apart
        self.assertEqual(out[2]["name"], "Fit the 2 wheel assemblies onto the chassis")
        # copies of one part (key sections of different widths, with different numbers of black keys) are built alike
        keys = [dict(piece(1, "keybed", [100, 20, 10]), parts=["keybed"]),
                dict(piece(2, "white-keys (1 of 2)", [10, 12, 2]), parts=["white-keys"]), piece(3, "black-keys-1", [2, 9, 2]),
                piece(4, "black-keys-2", [2, 9, 2]), dict(piece(5, "white-keys (2 of 2)", [4, 12, 2]), parts=["white-keys"]),
                piece(6, "black-keys-3", [2, 9, 2])]
        steps = [{"kind": "base", "new": [1], "pieces": [1], "glue": [(1, None)]},
                 {"kind": "bench", "assembly": 2, "new": [2, 3, 4], "pieces": [2, 3, 4], "glue": [(2, None), (3, 2), (4, 2)]},
                 {"kind": "fit", "assembly": 2, "new": [], "pieces": [2], "glue": [(2, 1)]},
                 {"kind": "bench", "assembly": 5, "new": [5, 6], "pieces": [5, 6], "glue": [(5, None), (6, 5)]},
                 {"kind": "fit", "assembly": 5, "new": [], "pieces": [5], "glue": [(5, 1)]}]
        out = kit_mod._combine(steps, keys)
        self.assertEqual([s.get("times", 1) for s in out], [1, 2, 2])
        self.assertEqual(out[1]["name"], "At the bench: build the 2 white keys assemblies")   # alike, not the same

    def test_a_small_sub_assembly_inside_another_is_glued_in_place(self):
        piece = lambda n, name: {"number": n, "name": name, "size_mm": [10, 10, 10]}
        pieces = [piece(1, "body"), piece(2, "focus-ring"), piece(3, "lock-arm"), piece(4, "lock-button")]
        st = lambda kind, new, glue, **k: dict({"kind": kind, "stage": 0, "new": new, "pieces": new or [k.get("assembly")],
                                               "glue": glue}, **k)
        steps = [st("base", [1], [(1, None)]), st("bench", [2], [(2, None)], assembly=2),
                 st("bench", [3, 4], [(3, None), (4, 3)], assembly=3), st("fit", [], [(3, 2)], assembly=3, onto=2),
                 st("fit", [], [(2, 1)], assembly=2, onto=1)]
        out = kit_mod._flatten(steps, pieces)
        self.assertEqual([s["kind"] for s in out], ["base", "bench", "fit"])   # the arm and button go on at the bench
        self.assertEqual(out[1]["glue"], [(2, None), (3, 2), (4, 3)])
        self.assertEqual(out[1]["name"], "At the bench: build the focus ring, with the lock arm and the lock button")

    def test_a_kit_glues_like_a_kit_designer(self):
        # found by two live runs' kit critics: glass went into a closed body, a pillar was glued to a door, a seat to
        # the dash, steps ran in piece-number order, clear and opaque pieces shared a plate
        sc = scene_of(dict(box("chassis", [0.30, 0.02, 0.14], [0, 0.01, 0]), stage=0),
                      dict(box("seat", [0.05, 0.05, 0.05], [0.05, 0.045, 0]), stage=1),
                      dict(box("dash", [0.02, 0.04, 0.12], [-0.06, 0.04, 0]), stage=1),
                      dict(box("shell-roof", [0.30, 0.01, 0.14], [0, 0.125, 0]), stage=1),   # a hollow body: roof
                      dict(box("shell-right", [0.30, 0.10, 0.004], [0, 0.07, 0.068]), stage=1),   # and two sides
                      dict(box("shell-left", [0.30, 0.10, 0.004], [0, 0.07, -0.068]), stage=1),
                      dict(box("side-window", [0.10, 0.04, 0.004], [0.0, 0.10, 0.072]), stage=2),
                      dict(box("door", [0.10, 0.06, 0.006], [0.0, 0.05, -0.073]), stage=2),
                      dict(box("door-glass", [0.08, 0.03, 0.003], [0.0, 0.095, -0.0775]), stage=2),
                      dict(box("pillar", [0.01, 0.06, 0.006], [0.06, 0.05, -0.079]), stage=2))
        sc["articulations"] = [{"id": "door-open", "type": "hinge", "parts": ["door", "door-glass"], "axis": [0, 1, 0],
                                "pivot": [-0.05, 0.05, -0.073], "amount": 60, "order": 0}]
        k = kit_mod.make(sc, size=150, detail=0.5, plan={"merge": [["shell-*"]]})
        by = {p["head"]: p for p in k["pieces"]}
        by["shell"] = next(p for p in k["pieces"] if "shell-roof" in p["parts"])
        steps = k["steps"]
        self.assertIn(k["pieces"][0]["head"], ("chassis", "shell-roof"))              # a chassis or a body is the base
        self.assertEqual(by["door-glass"]["onto"]["head"], "door")                     # glass into its door
        self.assertNotEqual((by["pillar"]["onto"] or {}).get("head"), "door")          # never onto what opens
        step_of = {n: s["number"] for s in steps for n in s.get("new", s["pieces"])}
        join = min(s["number"] for s in steps if s["kind"] == "fit"
                   and {s["assembly"], s["glue"][0][1]} == {by["shell"]["number"], by["chassis"]["number"]})
        self.assertLess(step_of[by["seat"]["number"]], join)                           # the interior before the body closes
        self.assertLess(step_of[by["side-window"]["number"]], join)                    # glazed before, not after
        self.assertGreater(step_of[by["door"]["number"]], join)                        # the door is hung last
        plates = {n: pl.get("clear", False) for pl in k["plates"] for n, _, _ in pl["pieces"]}
        self.assertTrue(all(plates[p["number"]] == p["clear"] for p in k["pieces"]))   # clear plastic on its own plates
        with tempfile.TemporaryDirectory() as tmp:
            kit_mod.write(k, tmp)
            page = Path(tmp, "assembly.html").read_text(encoding="utf-8")
            self.assertIn("K.steps.length", page)                                   # the step-by-step script
            self.assertIn('"kind": "bench"', page)                                  # with its bench steps
            self.assertIn("hologram-solid", page)
            self.assertIn("assembly.html#step-", Path(tmp, "booklet.html").read_text(encoding="utf-8"))

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
            for name in os.listdir(Path(tmp, "img")):                             # a valid size, not "100%%"
                if name.endswith(".svg"):
                    self.assertNotIn("%%", Path(tmp, "img", name).read_text(encoding="utf-8"), name)
            self.assertTrue(Path(tmp, "img", "part-1.png").read_bytes().startswith(b"\x89PNG"))   # the part pictures
            self.assertNotIn("%%", booklet)
            summary = json.loads(Path(tmp, "kit.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["report"]["counts"]["pieces"], 4)
            self.assertIn("kit designer", kit.CRITIC.lower() + " kit designer")


if __name__ == "__main__":
    unittest.main()
