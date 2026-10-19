"""Tests for hologram scenes (format version 2): validation, compilation, audit, build and CLI."""

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from . import audit, png, render, scene, studio

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE / "examples" / "v2"


def base(**over):
    s = {"format": "tessera-hologram", "version": 2, "id": "t", "title": "Test", "units": "m", "seed": 1,
         "subject": {"category": "object", "accuracy": "generic", "synthetic": True},
         "sources": [{"id": "req", "kind": "user_request", "title": "test", "rights": "synthetic"}],
         "facts": [{"key": "h", "value": 1.0, "certainty": "inferred", "source": "req"}],
         "parts": [{"id": "body", "role": "mass", "certainty": "inferred", "stage": 0,
                    "shape": {"type": "box", "size": [1, 1, 1], "anchor": "base"}}]}
    s.update(over)
    return s


class Examples(unittest.TestCase):
    def test_every_example_compiles_and_passes_the_audit(self):
        names = sorted(p.stem for p in EXAMPLES.glob("*.json"))
        self.assertGreaterEqual(len(names), 5)
        for name in names:
            sc = studio.load(str(EXAMPLES / (name + ".json")))
            self.assertEqual(scene.validate(sc), [], name)
            geo = scene.compile_scene(sc)
            rep = audit.audit(sc, geo)
            self.assertTrue(rep["ok"], (name, rep["errors"]))

    def test_examples_are_different_objects(self):
        shapes_used, categories = {}, set()
        for path in EXAMPLES.glob("*.json"):
            sc = studio.load(str(path))
            categories.add(sc["subject"]["category"])
            shapes_used[path.stem] = {p["shape"]["type"] for p in sc["parts"]}
        self.assertGreaterEqual(len(categories), 5)
        every = set().union(*shapes_used.values())
        for t in ("lathe", "extrude", "tube", "torus", "cylinder", "box", "plane", "points", "curve", "cone", "sphere"):
            self.assertIn(t, every)

    def test_starters_are_valid(self):
        for cat in studio.STARTER:
            sc = studio.starter(cat)
            self.assertEqual(scene.validate(sc), [], cat)
            self.assertTrue(audit.audit(sc, scene.compile_scene(sc))["ok"], cat)


class Validation(unittest.TestCase):
    def test_minimal_scene_is_valid(self):
        self.assertEqual(scene.validate(base()), [])

    def test_unknown_keys_and_types_are_refused(self):
        s = base()
        s["script"] = "alert(1)"
        s["parts"][0]["shader"] = "void main(){}"
        errs = "\n".join(scene.validate(s))
        self.assertIn("unknown key 'script'", errs)
        self.assertIn("unknown key 'shader'", errs)

    def test_verified_claims_need_sources(self):
        s = base(facts=[{"key": "h", "value": 1.0, "certainty": "verified"}])
        self.assertTrue(any("verified fact" in e for e in scene.validate(s)))
        s = base()
        s["parts"][0]["certainty"] = "verified"
        self.assertTrue(any("verified part" in e for e in scene.validate(s)))

    def test_authentic_artwork_needs_rights_and_source(self):
        s = base(assets=[{"id": "art", "path": "a.png", "sha256": "0" * 64, "media_type": "image/png",
                          "rights": "synthetic", "provenance": "authentic"}])
        self.assertTrue(any("authentic artwork" in e for e in scene.validate(s)))

    def test_asset_paths_stay_inside_the_folder(self):
        for bad in ("/etc/passwd", "../x.png", "https://x/y.png", "a/../../b.png", "C:x.png"):
            s = base(assets=[{"id": "art", "path": bad, "sha256": "0" * 64, "media_type": "image/png",
                              "rights": "synthetic", "provenance": "synthetic"}])
            self.assertTrue(any(".path" in e for e in scene.validate(s)), bad)

    def test_budgets_and_ranges(self):
        s = base()
        s["parts"][0]["repeat"] = {"count": 65, "step": {"at": [1, 0, 0]}}
        self.assertTrue(scene.validate(s))
        s = base()
        s["parts"][0]["shape"] = {"type": "box", "size": [1, 1, 1e9]}
        self.assertTrue(scene.validate(s))
        s = base()
        s["parts"][0]["motion"] = {"type": "spin", "axis": [0, 0, 0], "rpm": 10}
        self.assertTrue(any("must not be zero" in e for e in scene.validate(s)))
        s = base()
        s["animation"] = {"camera": {"tour": [{"view": "nowhere", "at": 1}]}}
        self.assertTrue(any("unknown view" in e for e in scene.validate(s)))

    def test_non_finite_numbers_are_refused(self):
        s = base()
        s["parts"][0]["at"] = [float("nan"), 0, 0]
        self.assertTrue(scene.validate(s))


class Compilation(unittest.TestCase):
    def test_deterministic(self):
        sc = studio.load(str(EXAMPLES / "lantern-jellyfish.json"))
        a = json.dumps(scene.compile_scene(sc), sort_keys=True)
        b = json.dumps(scene.compile_scene(copy.deepcopy(sc)), sort_keys=True)
        self.assertEqual(a, b)

    def test_certainty_is_the_material(self):
        s = base(parts=[
            {"id": "a", "role": "structure", "certainty": "inferred", "stage": 0, "shape": {"type": "box", "size": [1, 1, 1]}},
            {"id": "b", "role": "structure", "certainty": "decorative", "stage": 0, "shape": {"type": "box", "size": [1, 1, 1]}, "at": [0, 1, 0]}])
        g = scene.compile_scene(s)
        line_styles = [st for st in g["styles"] if st[2] > 0]
        by_part = {g["parts"][int(st[6])]["id"]: st for st in line_styles}
        self.assertGreater(by_part["a"][1], by_part["b"][1])      # inferred brighter than decorative
        self.assertEqual(by_part["b"][4], scene.DASH_CODE["dotted"])
        s["presentation"] = {"certainty_style": "explicit"}
        g = scene.compile_scene(s)
        a = [st for st in g["styles"] if st[2] > 0 and g["parts"][int(st[6])]["id"] == "a"][0]
        self.assertEqual(a[4], scene.DASH_CODE["dashed"])

    def test_repeat_and_mirror_carry_motion(self):
        s = base(parts=[{"id": "leg", "role": "structure", "certainty": "inferred", "stage": 0,
                         "shape": {"type": "tube", "path": [[0.3, 1, 0], [0.3, 0, 0]], "radius": 0.02},
                         "repeat": {"count": 4, "radial": {"axis": "y"}}, "mirror": "z",
                         "motion": {"type": "swing", "axis": [0, 0, 1], "pivot": [0.3, 1, 0], "degrees": 5, "period": 3}}])
        g = scene.compile_scene(s)
        self.assertEqual(len(g["motions"]), 8)
        pivots = {tuple(round(x, 4) for x in m["pivot"]) for m in g["motions"]}
        self.assertEqual(len(pivots), 4)  # mirrored copies of the four land on the same four positions
        for m in g["motions"]:
            self.assertAlmostEqual(sum(x * x for x in m["axis"]), 1.0, places=6)

    def test_rotated_part_spins_about_the_stated_world_axis(self):
        s = base(parts=[{"id": "beam", "role": "data", "certainty": "decorative", "stage": 0, "floating": True,
                         "shape": {"type": "cone", "radius_bottom": 0.1, "radius_top": 1, "height": 3}, "at": [0, 2, 0],
                         "rotate": [0, 0, -90], "motion": {"type": "spin", "axis": [0, 1, 0], "rpm": 3}}])
        m = scene.compile_scene(s)["motions"][0]
        self.assertEqual(m["axis"], [0.0, 1.0, 0.0])
        self.assertEqual(m["pivot"], [0.0, 2.0, 0.0])

    def test_build_phases_are_ordered_by_stage(self):
        s = base(parts=[
            {"id": "low", "role": "mass", "certainty": "inferred", "stage": 0, "shape": {"type": "box", "size": [1, 1, 1], "anchor": "base"}},
            {"id": "top", "role": "identity", "certainty": "inferred", "stage": 3, "shape": {"type": "box", "size": [1, 1, 1], "anchor": "base"}, "at": [0, 1, 0]}])
        g = scene.compile_scene(s)
        L, st = g["lines"], g["styles"]
        phases = {}
        for i in range(0, len(L), 9):
            pid = g["parts"][int(st[int(L[i + 6])][6])]["id"]
            phases.setdefault(pid, []).append(max(L[i + 7], L[i + 8]))
        self.assertLess(max(phases["low"]), min(phases["top"]) + 1e-9)

    def test_budget_overflow_is_refused(self):
        s = base(parts=[{"id": "p", "role": "detail", "certainty": "inferred", "stage": 0,
                         "shape": {"type": "sphere", "radius": 1, "lat": 24, "lon": 48, "segments": 96},
                         "repeat": {"count": 64, "step": {"at": [2, 0, 0]}}}])
        with self.assertRaises(scene.SceneError):
            scene.compile_scene(s)

    def test_v1_downgrade_is_readable_by_v1_consumers(self):
        g = scene.compile_scene(studio.load(str(EXAMPLES / "lighthouse.json")))
        v1 = scene.to_v1(g, limit=500)
        self.assertEqual(v1["format"], "tessera-geometry")
        self.assertEqual(len(v1["segments"]), 500)
        for seg in v1["segments"]:
            self.assertIn(seg["tone"], ("accent", "bright", "structure", "dust", "identity", "faint"))
            self.assertTrue(0 <= seg["stage"] <= 5)
            self.assertIn(seg["certainty"], scene.CERTAINTIES)


class Audit(unittest.TestCase):
    def test_floating_part_is_an_error_unless_declared(self):
        s = base()
        s["parts"].append({"id": "hover", "role": "detail", "certainty": "inferred", "stage": 1,
                           "shape": {"type": "box", "size": [0.2, 0.2, 0.2]}, "at": [0, 3, 0]})
        rep = audit.audit(s, scene.compile_scene(s))
        self.assertFalse(rep["ok"])
        self.assertEqual(rep["errors"][0]["code"], "floating")
        s["parts"][1]["floating"] = True
        self.assertTrue(audit.audit(s, scene.compile_scene(s))["ok"])

    def test_parts_hanging_from_a_floating_part_are_held(self):
        s = base(parts=[
            {"id": "bell", "role": "mass", "certainty": "inferred", "stage": 0, "floating": True,
             "shape": {"type": "sphere", "radius": 0.5}, "at": [0, 3, 0]},
            {"id": "arm", "role": "structure", "certainty": "inferred", "stage": 1,
             "shape": {"type": "tube", "path": [[0, 2.6, 0], [0, 1, 0]], "radius": 0.03}}])
        self.assertTrue(audit.audit(s, scene.compile_scene(s))["ok"])

    def test_documented_accuracy_must_be_backed(self):
        s = base()
        s["subject"]["accuracy"] = "documented"
        self.assertFalse(audit.audit(s, scene.compile_scene(s))["ok"])

    def test_stage_order_warning(self):
        s = base(parts=[
            {"id": "base", "role": "mass", "certainty": "inferred", "stage": 3, "shape": {"type": "box", "size": [1, 1, 1], "anchor": "base"}},
            {"id": "roof", "role": "identity", "certainty": "inferred", "stage": 0, "shape": {"type": "box", "size": [1, 0.2, 1], "anchor": "base"}, "at": [0, 1, 0]}])
        codes = [w["code"] for w in audit.audit(s, scene.compile_scene(s))["warnings"]]
        self.assertIn("stage-order", codes)


class Build(unittest.TestCase):
    def test_html_embeds_only_matching_permitted_artwork(self):
        with tempfile.TemporaryDirectory() as d:
            data = png.book_cover(32, 48)
            Path(d, "art.png").write_bytes(data)
            good = hashlib.sha256(data).hexdigest()
            s = base(assets=[{"id": "art", "path": "art.png", "sha256": good, "media_type": "image/png",
                              "rights": "synthetic", "provenance": "generated-decorative"}])
            s["parts"].append({"id": "face", "role": "artwork", "certainty": "decorative", "stage": 1,
                               "shape": {"type": "plane", "size": [0.5, 0.75]}, "at": [0, 0.5, 0.51], "artwork_asset_id": "art"})
            g = scene.compile_scene(s)
            assets, notes = render.embed_assets(g, d)
            self.assertIn("art", assets)
            g["provenance"]["assets"][0]["sha256"] = "f" * 64
            assets, notes = render.embed_assets(g, d)
            self.assertEqual(assets, {})
            self.assertTrue(any("do not match" in n for n in notes))
            html, _ = render.build_html(scene.compile_scene(s), None)
            self.assertNotIn("data:image/png", html)

    def test_html_cannot_be_closed_by_scene_text(self):
        s = base(title="</script><script>alert(1)</script>")
        html, _ = render.build_html(scene.compile_scene(s))
        self.assertEqual(html.count("<script"), 3)  # geometry, assets, viewer

    def test_cli_new_check_build_from_any_directory(self):
        cli = str(HERE / "cli.py")
        with tempfile.TemporaryDirectory() as d:
            subprocess.run([sys.executable, cli, "new", "machine", "--output", "m.json"], cwd=d, check=True, capture_output=True)
            r = subprocess.run([sys.executable, cli, "check", "m.json"], cwd=d, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("audit: PASS", r.stdout)
            r = subprocess.run([sys.executable, cli, "build", "m.json", "--out", "out", "--v1"], cwd=d, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            for name in ("geometry.json", "geometry.v1.json", "hologram.html", "audit.txt"):
                self.assertTrue(Path(d, "out", name).exists(), name)
            Path(d, "bad.json").write_text('{"format": "tessera-hologram", "format": 2}')
            r = subprocess.run([sys.executable, cli, "check", "bad.json"], cwd=d, capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("duplicate", r.stderr)


@unittest.skipUnless(render.find_browser() and os.environ.get("HOLOGRAM_SKIP_CAPTURE") != "1", "no Chromium-family browser")
class Capture(unittest.TestCase):
    def test_review_produces_non_empty_images(self):
        with tempfile.TemporaryDirectory() as d:
            studio.build(str(EXAMPLES / "cd.json"), d)
            paths = render.review(str(Path(d, "hologram.html")), str(Path(d, "review")), 640, 400, sheets=("views",))
            for p in paths:
                data = Path(p).read_bytes()
                self.assertTrue(data.startswith(b"\x89PNG"), p)
                self.assertGreater(len(data), 20000, p)  # an empty dark frame compresses far smaller


if __name__ == "__main__":
    unittest.main()
