"""Tests for Construct scenes (format construct-scene, version 2): validation, compilation, audit, build and CLI."""

import copy
import math
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from . import shapes as shapes_mod
from . import compare as compare_mod
from . import trace as trace_mod
from . import audit, critic, diagnose, globe, params, png, render, runner, scene, studio, terrain, tiers

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE / "examples" / "v2"


def base(**over):
    s = {"format": "construct-scene", "version": 2, "id": "t", "title": "Test", "units": "m", "seed": 1,
         "subject": {"category": "object", "accuracy": "generic", "synthetic": True},
         "sources": [{"id": "req", "kind": "user_request", "title": "test", "rights": "synthetic"}],
         "facts": [{"key": "h", "value": 1.0, "certainty": "inferred", "source": "req"}],
         "parts": [{"id": "body", "role": "mass", "certainty": "inferred", "stage": 0,
                    "shape": {"type": "box", "size": [1, 1, 1], "anchor": "base"}}]}
    s.update(over)
    return s


def red_blue_chair(round_06=False):
    """A Red-Blue chair from real use (testdata/red-blue-chair.json, its authoring record left out). With `round_06`,
    the version that passed check --fit: its back board stood on the rear low rail and leaned back with nothing behind
    it, and its reading still gave an older lean."""
    s = json.loads((HERE / "testdata" / "red-blue-chair.json").read_text())
    if round_06:
        s["parts"] = [p for p in s["parts"] if p["id"] != "cross-low-back"]
        back = next(p for p in s["parts"] if p["id"] == "back")
        back.update(at=[0.0, 0.1, -0.3], rotate=[-15.17, 0, 0])
        back["shape"]["size"] = [0.4, 0.7947, 0.012]
        facts = {f["key"]: f for f in s["facts"]}
        facts["back_lean"]["value"], facts["back_board_length"]["value"] = 15.2, 0.795
        s["reading"]["how"][4] = "Fitted: the back board's 11.8 deg lean, from the two published figures."
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



def _json_reads_any_depth():
    try:
        json.loads("[" * 100000 + "]" * 100000)
        return True
    except RecursionError:
        return False


# what brackets nested thousands deep are told: too deep to read, or (where json reads any depth, Python 3.15 on) not
# the one object a scene is
DEEP = "one JSON object" if _json_reads_any_depth() else "nested too deeply"

class Malformed(unittest.TestCase):
    """Found by fuzzing the gallery's scenes: a malformed scene is answered with errors, never a crash."""

    def test_values_of_the_wrong_type_are_errors(self):
        for mutate in (lambda s: s["facts"].__setitem__(0, dict(s["facts"][0], key=["a"])),     # a list where a key goes
                       lambda s: s["facts"].__setitem__(0, dict(s["facts"][0], certainty="verified", source={"a": 1})),
                       lambda s: s["parts"][0].__setitem__("source", [1, 2]),
                       lambda s: s.__setitem__("presentation", 1e308),
                       lambda s: s["parts"][0].__setitem__("id", 5.5),
                       lambda s: s["parts"][0]["shape"].__setitem__("type", ["box"]),
                       lambda s: s.__setitem__("labels", [{"id": "l", "part": "body", "face": "front", "field": {"a": 1}}]),
                       lambda s: s.__setitem__("authoring", {"tier": "standard", "research": "done", "sources": [["req"]]}),
                       lambda s: s["parts"][0].update(certainty="verified", basis=1.5),
                       lambda s: (s["parts"][0]["shape"].__setitem__("type", {"a": 1}),
                                  s.__setitem__("anchors", {"front": {"part": "body", "face": "front"}})),
                       lambda s: s["parts"][0].__setitem__("shape", {"type": "loft", "sections": [[-1, 0.5, 0, 1],
                                                                                                   [1, 1e308, 0, 1]]})):
            sc = base()
            mutate(sc)
            errs = scene.validate(sc)
            self.assertTrue(errs)
            self.assertFalse(any("could not be checked" in e for e in errs), errs)   # answered by the checks themselves
            diagnose.diagnose(sc)

    def test_a_tyre_of_any_round_shape_and_a_tube_arch_count_as_solid(self):
        # found by a live run: a lathe tyre was not filled, and an arch lip drawn as a tube stopped filling its well
        from . import compare as compare_mod
        def tris(shape_type):
            sc = base()
            prof = [[0.2, -0.1], [0.3, -0.1], [0.3, 0.1], [0.2, 0.1]]
            shape = {"type": "lathe", "profile": prof} if shape_type == "lathe" else {"type": "cylinder", "radius": 0.3, "height": 0.2}
            sc["parts"].append({"id": "tyre-front", "role": "detail", "certainty": "inferred", "stage": 1, "shape": shape,
                                "at": [0, 0.5, 0], "rotate": [0, 0, 90]})
            g = scene.compile_scene(sc)
            return len(compare_mod.project(g, 90, 0)[0])
        sc = base()
        g = scene.compile_scene(sc)
        plain = len(compare_mod.project(g, 90, 0)[0])
        self.assertGreater(tris("lathe"), plain)   # its outline filled: more triangles than its surfaces alone

    def test_a_critique_records_the_runs_round(self):
        sc = base()
        out, _ = critic.record(sc, _critique(sc, low=2), round=6)
        self.assertEqual(out["authoring"]["critic"]["round"], 6)

    def test_check_says_what_a_file_is_when_it_is_not_a_scene(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "t.json")
            p.write_text(json.dumps({"format": "construct-trace", "version": 1}), encoding="utf-8")
            r = subprocess.run([sys.executable, "-m", "construct_hologram", "check", str(p)], cwd=HERE.parent,
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("is not a scene, it is a trace", r.stderr)

    def test_a_scene_that_cannot_be_read_says_which_file_and_why(self):
        run = lambda *a: subprocess.run([sys.executable, "-m", "construct_hologram", *a], cwd=HERE.parent,
                                        capture_output=True, text=True)
        with tempfile.TemporaryDirectory() as d:
            missing = str(Path(d, "nowhere.json"))
            r = run("print", missing, "--out", str(Path(d, "x.stl")))
            self.assertEqual(r.returncode, 1)
            self.assertIn("print: cannot read %s: No such file" % missing, r.stderr)
            self.assertNotIn("sheet", r.stderr)                                   # the old word, and no file name
            deep = Path(d, "deep.json")
            deep.write_text("[" * 100000 + "]" * 100000, encoding="utf-8")
            r = run("export", str(deep), "--out", str(Path(d, "x.glb")))
            self.assertIn(DEEP if DEEP != "one JSON object" else "expected an object", r.stderr)
            self.assertNotIn("Traceback", r.stderr)
            one = Path(d, "one.json")
            sc = base()
            sc["parts"][0]["id"] = "Not An Id"
            one.write_text(json.dumps(sc), encoding="utf-8")
            r = run("check", str(one))
            self.assertIn("invalid scene (1 problem)\n", r.stdout)                # one problem, not "1 problems"

    def test_brackets_nested_thousands_deep_are_a_diagnosis(self):
        doc, diags = diagnose.parse_text("[" * 100000 + "]" * 100000)
        self.assertIsNone(doc)
        self.assertIn(DEEP, diags[0]["message"])

    def test_path_points_and_series_values_are_finite_and_in_range(self):
        sc = base()
        sc["parts"].append({"id": "p", "role": "detail", "certainty": "inferred", "stage": 1,
                            "shape": {"type": "paths", "paths": [[[0, 0, 0], [-1e308, 1, 0]]]}})
        self.assertTrue(any("paths" in e for e in scene.validate(sc)))
        sc = base()
        sc["reading"] = {"clock": {"label": "tick", "from": 0, "to": 10, "top": 1},
                         "series": [{"name": "n", "values": [[0, float("nan")]]}]}
        self.assertTrue(any("finite" in e for e in scene.validate(sc)))
        del sc["reading"]["clock"]["label"]   # a missing key is reported, and nothing below reads it
        errs = scene.validate(sc)
        self.assertTrue(any("missing key 'label'" in e for e in errs))
        self.assertFalse(any("could not be checked" in e for e in errs), errs)

    def test_a_title_that_names_a_template_marker_stays_text(self):
        sc = json.loads((EXAMPLES / "cd.json").read_text())
        sc["title"] = "A CD __VIEWER__ __GEOMETRY__ __ASSETS__ </script><b>"
        html, _ = render.build_html(scene.compile_scene(sc))
        start = html.index('type="application/json">') + len('type="application/json">')
        self.assertEqual(json.loads(html[start:html.index("</script>", start)])["title"], sc["title"])
        self.assertEqual(html.count("Hologram.prototype.upload = "), 1)


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

    def test_a_gap_the_boxes_hide_is_found_on_the_surfaces(self):
        # a desk fan as two models built it (reported from use): the stem stops short of a dished base whose box
        # reaches past it, and a motor sits on a pole it does not reach, joined only by a wire-thin strut. Both passed
        # the box check; the surfaces say otherwise
        def fan(*parts):
            s = studio.starter("machine")
            part = lambda **k: dict({"role": "structure", "certainty": "inferred", "stage": 0, "basis": ["height"]}, **k)
            s["parts"] = [part(**p) for p in parts]
            return s
        motor = dict(id="motor", role="mass", shape={"type": "cylinder", "radius": 0.06, "height": 0.14},
                     at=[0, 0.39, -0.07], rotate=[90, 0, 0], stage=2)        # its underside at 0.33 m
        dish = fan(dict(id="dish", role="mass", shape={"type": "lathe", "profile": [[0, 0], [0.13, 0], [0.13, 0.07],
                                                                                    [0.02, 0.02], [0, 0.02]]}),
                   dict(id="stem", shape={"type": "cylinder", "radius": 0.015, "height": 0.25}, at=[0, 0.04, 0],
                        stage=1),                                            # 2 cm above the dish's centre
                   dict(motor, at=[0, 0.35, -0.07]))
        rep = audit.audit(dish, scene.compile_scene(dish))
        self.assertFalse(rep["ok"])
        self.assertEqual([(e["code"], e["part"]) for e in rep["errors"]], [("unsupported", "stem")])
        self.assertIn("'motor', resting on it", rep["errors"][0]["message"])   # one fault, named where to fix it
        self.assertRegex(rep["errors"][0]["message"], r"'dish', 0\.020?\d* m away")
        strut = dict(id="strut", shape={"type": "tube", "path": [[0, 0.28, 0], [0, 0.31, 0.03], [0, 0.34, 0.05]],
                                        "radius": 0.002}, stage=2)
        bridged = fan(dict(id="base", role="mass", shape={"type": "box", "size": [0.3, 0.05, 0.22], "anchor": "base"}),
                      dict(id="pole", shape={"type": "cylinder", "radius": 0.012, "height": 0.25}, at=[0, 0.05, 0],
                           stage=1), motor, strut)                           # the pole's top at 0.30 m: 3 cm short
        rep = audit.audit(bridged, scene.compile_scene(bridged))
        self.assertTrue(rep["ok"])   # it is held, by the strut: a warning, not an error
        thin = [w for w in rep["warnings"] if w["code"] == "thin-support"]
        self.assertEqual([w["part"] for w in thin], ["motor"])
        self.assertIn("'strut'", thin[0]["message"])
        self.assertIn("'pole', 0.03 m away", thin[0]["message"])
        bridged["parts"][2]["at"] = [0, 0.36, -0.07]                          # seated on the pole: nothing to say
        rep = audit.audit(bridged, scene.compile_scene(bridged))
        self.assertEqual([w for w in rep["warnings"] if w["code"] in ("thin-support", "unsupported")], [])
        self.assertTrue(rep["ok"])

    def test_a_part_standing_on_an_edge_with_its_weight_off_it_tips(self):
        # found in real use: a Red-Blue chair's back board stood on the rear low rail along its bottom edge and leaned
        # back with nothing behind it (the upper rail ran on the sitter's side), and check --fit passed it
        fixed = red_blue_chair()
        rep = audit.audit(fixed, scene.compile_scene(fixed))   # its foot on a rail, its back on the upper rail
        self.assertEqual([w for w in rep["warnings"] if w["code"] == "tips"], [])
        flawed = red_blue_chair(round_06=True)
        rep = audit.audit(flawed, scene.compile_scene(flawed))
        tips = [w for w in rep["warnings"] if w["code"] == "tips"]
        self.assertEqual([w["part"] for w in tips], ["back"])
        self.assertIn("'cross-low-rear' only along one edge", tips[0]["message"])
        self.assertRegex(tips[0]["message"], r"weight 0\.\d+ m to the back of it: it would tip over")
        self.assertIn("tips", diagnose.VISIBLE_DEFECTS)
        self.assertIn("tips", diagnose.AUDIT_HINTS)

        def stand(*parts):
            s = studio.starter("object")
            s["parts"] = [dict({"role": "structure", "certainty": "inferred", "stage": 0}, **p) for p in parts]
            rep = audit.audit(s, scene.compile_scene(s))
            return [w["part"] for w in rep["warnings"] if w["code"] == "tips"]
        frame = [dict(id="post", shape={"type": "box", "size": [0.04, 0.5, 0.04], "anchor": "base"}, at=[-0.3, 0, 0],
                      mirror="x"),
                 dict(id="rail", shape={"type": "box", "size": [0.64, 0.04, 0.04], "anchor": "base"}, at=[0, 0.1, 0],
                      stage=1)]
        board = lambda deg: dict(id="board", role="mass", shape={"type": "box", "size": [0.4, 0.8, 0.012],
                                                                  "anchor": "base"}, at=[0, 0.14, 0], rotate=[-deg, 0, 0], stage=2)
        self.assertEqual(stand(*frame, board(15)), ["board"])                       # leans back off its rail
        self.assertEqual(stand(*frame, board(0)), [])                                # upright: its weight over the rail
        self.assertEqual(stand(*frame, board(15),                                    # leans back onto a second rail
                               dict(id="stop", shape={"type": "box", "size": [0.64, 0.04, 0.04], "anchor": "base"},
                                    at=[0, 0.45, -0.115], stage=1),
                               dict(id="post-rear", shape={"type": "box", "size": [0.04, 0.5, 0.04], "anchor": "base"},
                                    at=[-0.3, 0, -0.115], mirror="x")), [])
        wall = dict(id="wall", role="mass", shape={"type": "box", "size": [1, 1, 0.1], "anchor": "base"})
        self.assertEqual(stand(wall, dict(id="shelf", shape={"type": "box", "size": [0.6, 0.012, 0.3], "anchor": "base"},
                                          at=[0, 0.5, 0.2], stage=1)), [])          # fixed into the side of a wall
        self.assertEqual(stand(dict(wall, id="gallows", shape={"type": "box", "size": [0.04, 1, 0.04], "anchor": "base"}),
                               dict(id="arm", shape={"type": "box", "size": [0.5, 0.04, 0.04], "anchor": "base"},
                                    at=[0.27, 0.96, 0], stage=1),
                               dict(id="sign", shape={"type": "box", "size": [0.3, 0.2, 0.012], "anchor": "base"},
                                    at=[0.3, 0.76, 0], stage=2)), [])              # hung from an arm

    def test_a_number_in_the_reading_that_contradicts_its_fact_is_named(self):
        # found in real use: How to read it still gave the back board an 11.8 deg lean after the fact became 15.2
        flawed = red_blue_chair(round_06=True)
        stale = [w for w in audit.audit(flawed, scene.compile_scene(flawed))["warnings"] if w["code"] == "stale-number"]
        self.assertEqual(len(stale), 1)
        self.assertIn("How to read it (line 5) says '11.8 deg', but the fact back_lean is 15.2", stale[0]["message"])
        self.assertIn("stale-number", diagnose.AUDIT_HINTS)
        self.assertEqual(audit.stale_numbers(red_blue_chair()), [])               # 21.8 deg, as the fact says
        s = base(facts=[{"key": "tower.height", "value": 65, "unit": "m", "certainty": "inferred"},
                        {"key": "spire.height", "value": 75.75, "unit": "m", "certainty": "inferred"},
                        {"key": "spire.base", "value": 40, "unit": "m", "certainty": "inferred"},
                        {"key": "width", "value": 0.4, "unit": "m", "certainty": "inferred"}])
        said = lambda *lines: [x[3] for x in audit.stale_numbers(dict(s, reading={"how": list(lines)}))]
        self.assertEqual(said("The tower rises 62 m."), ["62 m"])
        self.assertEqual(said("The tower rises 65 m; the spire 75.75 m."), [])        # as the facts say
        self.assertEqual(said("The tower rises 6500 cm."), [])                         # in another unit
        self.assertEqual(said("The spire stands 70 m high."), [])                      # height or base: not clear
        self.assertEqual(said("The tower is 75.75 m."), [])                           # some fact's value: not stale
        self.assertEqual(said("The tower rises about 62 m."), [])                      # about: near enough
        self.assertEqual(said("A tower of 60-62 m.", "A 3 m wide stair."), [])         # a range; width is too plain
        self.assertEqual(said("Width 0.5 m."), ["0.5 m"])                              # a plain key, right by it

    def test_a_small_gap_is_detached_on_a_large_object(self):
        # found on the R34: touching was 1% of the object's size (4.6 cm on a car), so a fin 2 cm under the floor
        # passed while an arch nearby kept its box in touch
        def car(gap):
            s = studio.starter("machine")
            part = lambda **k: dict({"role": "structure", "certainty": "inferred", "stage": 0}, **k)
            s["parts"] = [part(id="leg", shape={"type": "box", "size": [0.1, 0.5, 0.1], "anchor": "base"},
                               at=[0.8, 0, 2], mirror="x"),
                          part(id="leg-rear", shape={"type": "box", "size": [0.1, 0.5, 0.1], "anchor": "base"},
                               at=[0.8, 0, -2], mirror="x"),
                          part(id="body", role="mass", shape={"type": "box", "size": [1.8, 0.5, 4.6], "anchor": "base"},
                               at=[0, 0.5, 0], stage=1),
                          part(id="arch", shape={"type": "tube", "path": [[0.1, 0.5, -0.5], [0.1, 0.1, 0], [0.1, 0.5, 0.5]],
                                                 "radius": 0.02}, stage=2),
                          part(id="fin", shape={"type": "box", "size": [0.012, 0.04, 0.4], "anchor": "base"},
                               at=[0.1, 0.46 - gap, 0], stage=2)]
            rep = audit.audit(s, scene.compile_scene(s))
            return [w["part"] for w in rep["warnings"] + rep["errors"] if w["code"] in ("detached", "floating")]
        self.assertEqual(car(0.02), ["fin"])
        self.assertEqual(car(0.0), [])

    def test_duplicates_are_a_part_overlapping_itself(self):
        # found on a Braun knob: its skirt and body meet along a ring that both draw, and each lathe, its profile
        # closed by repeating its first point, drew that ring twice: 18% "duplicates" on a clean knob
        def dups(*parts):
            s = studio.starter("object")
            s["parts"] = [dict({"role": "structure", "certainty": "inferred", "stage": 0}, **q) for q in parts]
            return [w for w in audit.audit(s, scene.compile_scene(s))["warnings"] if w["code"] == "duplicates"]
        ring = [[0.003, 0.0], [0.0175, 0.0], [0.0175, 0.0025], [0.003, 0.0025], [0.003, 0.0]]
        skirt = {"id": "skirt", "shape": {"type": "lathe", "profile": ring, "segments": 64}}
        body = {"id": "body", "shape": {"type": "lathe", "profile": [[0.003, 0.0], [0.0167, 0.0], [0.0146, 0.018],
                                                                     [0.003, 0.018], [0.003, 0.0]], "segments": 64},
                "at": [0, 0.0025, 0]}
        self.assertEqual(dups(skirt, body), [])
        self.assertTrue(dups(dict(skirt, mirror="x"), body))   # a copy mirrored onto itself: every line twice

    def test_a_part_set_through_a_face_touches_it(self):
        # found on a grand piano: its pedals pass through the front of the lyre box, and none of their corners,
        # edge midpoints or face centres lies near one of the box's faces
        def detached(z):
            s = studio.starter("object")
            part = lambda **k: dict({"role": "structure", "certainty": "inferred", "stage": 0}, **k)
            s["parts"] = [part(id="post", shape={"type": "box", "size": [0.1, 2.75, 0.1], "anchor": "base"}),
                          part(id="lyre-box", shape={"type": "box", "size": [0.3, 0.09, 0.15]}, at=[0, 1.0, 0.125]),
                          part(id="pedal", role="detail", shape={"type": "box", "size": [0.032, 0.012, 0.12]},
                               at=[0, 0.98, z], stage=1)]
            rep = audit.audit(s, scene.compile_scene(s))
            return [w["part"] for w in rep["warnings"] + rep["errors"] if w["code"] == "detached"]
        self.assertEqual(detached(0.23), [])           # 0.17 to 0.29, through the box's face at 0.2
        self.assertEqual(detached(0.27), ["pedal"])    # 0.21 to 0.33: a centimetre in front of it

    def test_glass_named_only_in_the_label_is_a_warning(self):
        s = base()
        s["parts"].append({"id": "hood-door", "label": "Glazed hood door", "role": "detail", "certainty": "inferred",
                           "stage": 1, "shape": {"type": "box", "size": [0.3, 0.3, 0.005]}, "at": [0, 1, 0.5],
                           "look": {"fill": "glass"}})
        codes = lambda: [w["part"] for w in audit.audit(s, scene.compile_scene(s))["warnings"] if w["code"] == "glass-name"]
        self.assertEqual(codes(), ["hood-door"])
        s["parts"][-1]["id"] = "hood-door-glass"  # the id says glass: the solid view and the exports agree
        self.assertEqual(codes(), [])
        s["parts"][-1].update(id="spoke", label="Spoke")  # glass fill alone is how the light draws it: no warning
        self.assertEqual(codes(), [])

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
    def test_a_built_page_carries_its_solids_packed_and_consistent(self):
        import base64, re, struct
        with tempfile.TemporaryDirectory() as d:
            g, _, _ = studio.build(str(EXAMPLES / "cd.json"), d)
            html = Path(d, "construct.html").read_text(encoding="utf-8")
            m = re.search(r'<script id="hologram-solid" type="application/json">(.*?)</script>', html, re.S)
            sd = json.loads(m.group(1))
            n, count = sd["vertices"], sd["opaque"] + sd["clear"]
            self.assertGreater(n, 0)
            self.assertEqual(count % 3, 0)
            idx = struct.unpack("<%d%s" % (count, "I" if sd["wide"] else "H"), base64.b64decode(sd["idx"]))
            self.assertLess(max(idx), n)
            sty = struct.unpack("<%dH" % n, base64.b64decode(sd["sty"]))
            self.assertLess(max(sty), len(g["styles"]))                       # each vertex wears a style of the page
            self.assertEqual(len(base64.b64decode(sd["pos"])), 6 * n)
            self.assertIn("S solid", html)
        bare = render.build_html(scene.compile_scene(base()))[0]                # no solids given: none, and no S
        self.assertIn('<script id="hologram-solid" type="application/json">null</script>', bare)

    def test_a_smooth_loft_keeps_its_sections_and_never_swells(self):
        secs = [[0, 0.5, 0.0, 0.4], [1, 0.9, 0.1, 1.0], [2, 0.9, 0.1, 1.0], [3, 0.3, 0.3, 0.6, 0.2]]
        fine = shapes_mod.smooth_sections(secs, 4)
        self.assertEqual(len(fine), 13)
        for k, s in enumerate(secs):                                          # the given sections, exactly
            self.assertEqual([round(v, 9) for v in fine[4 * k][:4]], [float(v) for v in s[:4]])
        for i in range(len(secs) - 1):
            for f in fine[4 * i:4 * i + 5]:
                for a in range(1, 4):                                         # between its neighbours, never past
                    lo, hi = sorted((secs[i][a], secs[i + 1][a]))
                    self.assertTrue(lo - 1e-9 <= f[a] <= hi + 1e-9, (i, a, f))
        plain = shapes_mod.loft(secs, 0.4)
        self.assertEqual(len(plain.lines), len(shapes_mod.loft(secs, 0.4, False).lines))
        self.assertGreater(len(shapes_mod.loft(secs, 0.4, True).tris), len(plain.tris))

    def test_html_embeds_only_matching_permitted_artwork(self):
        with tempfile.TemporaryDirectory() as d:
            data = png.book_cover(32, 48)
            Path(d, "art.png").write_bytes(data)
            good = hashlib.sha256(data).hexdigest()
            s = base(assets=[{"id": "art", "path": "art.png", "sha256": good, "media_type": "image/png",
                              "rights": "synthetic", "provenance": "generated-decorative"}])
            s["parts"].append({"id": "face", "role": "artwork", "certainty": "decorative", "stage": 1,
                               "shape": {"type": "plane", "size": [0.5, 0.75]}, "at": [0, 0.5, 0.51],
                               "artwork": {"slot": "cover-front", "asset": "art"}})
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
        self.assertEqual(html.count("<script"), 5)  # geometry, solids, assets, viewer, the rounds' timeline

    def test_cli_new_check_build_from_any_directory(self):
        cli = str(HERE / "cli.py")
        with tempfile.TemporaryDirectory() as d:
            subprocess.run([sys.executable, cli, "new", "machine", "--output", "m.json"], cwd=d, check=True, capture_output=True)
            r = subprocess.run([sys.executable, cli, "check", "m.json"], cwd=d, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("audit: PASS", r.stdout)
            r = subprocess.run([sys.executable, cli, "build", "m.json", "--out", "out", "--v1"], cwd=d, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            for name in ("geometry.json", "geometry.v1.json", "construct.html", "audit.txt"):
                self.assertTrue(Path(d, "out", name).exists(), name)
            Path(d, "bad.json").write_text('{"format": "construct-scene", "format": 2}')
            r = subprocess.run([sys.executable, cli, "check", "bad.json"], cwd=d, capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("appears twice", r.stdout)


def lid_scene():
    """A box with a hinged lid, a sliding card in the lid and a label from a fact."""
    s = base()
    s["facts"].append({"key": "title", "value": "Synthetic Title", "certainty": "user_supplied", "source": "req"})
    s["parts"] += [
        {"id": "lid", "role": "mass", "certainty": "inferred", "stage": 1,
         "shape": {"type": "box", "size": [1, 0.1, 1]}, "at": [0, 1.05, 0]},
        {"id": "card", "role": "artwork", "certainty": "decorative", "stage": 2,
         "shape": {"type": "plane", "size": [0.8, 0.8]}, "at": [0, 1.11, 0], "rotate": [-90, 0, 0],
         "artwork": {"slot": "booklet-page-1"}}]
    s["articulations"] = [
        {"id": "open", "type": "hinge", "parts": ["lid", "card"], "axis": [1, 0, 0], "pivot": [0, 1.0, -0.5], "amount": -90, "order": 0},
        {"id": "out", "type": "slide", "parts": ["card"], "axis": [0, 0, 1], "amount": 0.3, "order": 1}]
    s["labels"] = [{"id": "side", "part": "body", "face": "left", "field": "title", "orientation": "vertical-down"}]
    return s


class Contract02(unittest.TestCase):
    """The construct/0.2 review items: host-owned style, articulations, fact labels,
    anchors, artwork slots and masks, unknown facts."""

    def test_one_house_palette_whatever_the_model_writes(self):
        errs = scene.validate(base(style={"palette": "amber"}))
        self.assertTrue(any("renderer" in e and "style_hint" in e for e in errs), errs)
        plain = scene.compile_scene(base())
        tinted = scene.compile_scene(base(presentation={"style_hint": {"palette": "amber", "identity": "brass"}}))
        self.assertEqual(tinted["presentation"]["style_hint"]["palette"], "violet")
        for g in (plain, tinted):
            g.pop("scene_sha256")
        self.assertEqual(plain, tinted)  # the same construct, byte for byte, whatever style_hint said
        d = diagnose.diagnose(base(presentation={"style_hint": {"palette": "amber"}}))
        self.assertIn(("style-hint-ignored", "$.presentation.style_hint"), {(x["code"], x["path"]) for x in d["diagnostics"]})
        self.assertTrue(d["ok"])

    def test_a_person_can_choose_a_palette_through_the_host(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "s.json").write_text(json.dumps(base()))
            g, _, _ = studio.build(str(Path(d, "s.json")), str(Path(d, "out")), palette="amber")
            self.assertEqual(g["presentation"]["style_hint"]["palette"], "amber")

    def test_unknown_facts_are_absent(self):
        s = base()
        s["facts"].append({"key": "year", "value": None, "certainty": "inferred"})
        self.assertTrue(any("unknown fact is absent" in e for e in scene.validate(s)))

    def test_articulations_compile_to_ordered_joint_chains(self):
        g = scene.compile_scene(lid_scene())
        self.assertEqual([a["id"] for a in g["articulations"]], ["open", "out"])
        self.assertEqual(g["articulations"][0]["instances"], [["lid", 0], ["card", 0]])
        parts = {p["id"]: p for p in g["parts"]}
        self.assertEqual(g["joints"][parts["lid"]["joint"]], [0])
        self.assertEqual(g["joints"][parts["card"]["joint"]], [0, 1])
        self.assertEqual(parts["body"]["joint"], -1)
        for row in g["styles"]:
            self.assertEqual(row[9], g["parts"][row[6]]["joint"])
        # the lid swings up about its back edge: fully open it stands above the box
        self.assertGreater(g["bounds"]["open_max"][1], g["bounds"]["max"][1] + 0.8)

    def test_a_later_articulation_rides_on_the_earlier(self):
        g = scene.compile_scene(lid_scene())
        arts = g["articulations"]
        # the card's centre: slid 0.3 along +Z in the rest frame, then carried up by the hinge
        p = scene._chain_apply([0, 1], arts, (0.0, 1.11, 0.0))
        self.assertAlmostEqual(p[2], -0.5 - 0.11, places=4)
        self.assertAlmostEqual(p[1], 1.0 + 0.5 + 0.3, places=4)

    def test_articulation_checks(self):
        s = lid_scene()
        del s["articulations"][0]["pivot"]
        s["articulations"][1]["parts"] = ["nope"]
        s["articulations"].append({"id": "big", "type": "hinge", "parts": ["lid"], "axis": [0, 1, 0], "pivot": [0, 0, 0], "amount": 400})
        errs = "\n".join(scene.validate(s))
        self.assertIn("pivot", errs)
        self.assertIn("unknown part 'nope'", errs)
        self.assertIn("-180..180", errs)

    def test_labels_take_text_and_certainty_from_facts(self):
        g = scene.compile_scene(lid_scene())
        lb = g["labels"][0]
        self.assertEqual((lb["text"], lb["certainty"], lb["field"]), ("Synthetic Title", "user_supplied", "title"))
        tl, tr, br, bl = lb["corners"]
        # the left face of the box, text running down: first edge goes down, letters face the front
        self.assertLess(tr[1], tl[1])
        self.assertGreater(tl[2], bl[2])
        s = lid_scene()
        s["labels"] = [{"id": "x", "part": "body", "field": "year"}, {"id": "y", "part": "body", "text": "SIDE A"},
                       {"id": "z", "part": "lid", "face": "rim", "text": "oops"}]
        errs = "\n".join(scene.validate(s))
        self.assertIn("no fact 'year'", errs)
        self.assertIn("never guess", errs)
        self.assertIn("a box has the faces", errs)
        del s["labels"][0], s["labels"][1]
        self.assertEqual(scene.compile_scene(s)["labels"][0]["certainty"], "decorative")

    def test_anchors_default_to_the_bounds_and_follow_the_scene(self):
        g = scene.compile_scene(base())
        an = g["anchors"]
        self.assertEqual(an["base"], {"point": [0.0, 0.0, 0.0], "up": [0, 1, 0], "from": "bounds"})
        tl, tr, br, bl = an["front"]["corners"]
        self.assertEqual((tl[2], tr[0] > tl[0], tl[1] > bl[1]), (0.5, True, True))
        self.assertEqual(an["spine"]["corners"][0][0], -0.5)
        self.assertIsNone(an["grip"])
        s = lid_scene()
        s["anchors"] = {"spine": {"part": "body", "face": "left"}, "grip": {"part": "lid"}}
        an = scene.compile_scene(s)["anchors"]
        self.assertEqual((an["spine"]["part"], an["spine"]["from"]), ("body", "scene"))
        self.assertEqual(an["grip"]["point"], [0.0, 1.05, 0.0])

    def test_artwork_slots_and_masks(self):
        s = lid_scene()
        s["parts"].append({"id": "disc", "role": "identity", "certainty": "inferred", "stage": 1,
                           "shape": {"type": "cylinder", "radius": 0.06, "height": 0.0012}, "at": [0, 1.2, 0],
                           "artwork": {"slot": "disc", "mask": "circle", "inner_radius": 0.0075}})
        g = scene.compile_scene(s)
        disc = [a for a in g["artwork"] if a["slot"] == "disc"][0]
        self.assertEqual((disc["mask"], disc["inner_ratio"], disc["asset_id"]), ("circle", 0.125, None))
        s["parts"][-1]["artwork"] = {"slot": "booklet-page-1", "inner_radius": 0.01}
        errs = "\n".join(scene.validate(s))
        self.assertIn("duplicate slot", errs)
        self.assertIn("only a circle mask", errs)
        s["parts"][-1]["artwork"] = {"slot": "poster"}
        self.assertTrue(any("booklet-page-1..64" in e for e in scene.validate(s)))

    def test_z_up_frame_converts_the_new_fields(self):
        g = scene.compile_scene(lid_scene())
        z = scene.reframe(g, "z-up")
        self.assertEqual(z["articulations"][0]["pivot"], [0.0, 0.5, 1.0])
        self.assertEqual(z["anchors"]["base"]["up"], [0, 0, 1])
        self.assertEqual(z["labels"][0]["corners"][0], [g["labels"][0]["corners"][0][0], -g["labels"][0]["corners"][0][2],
                                                        g["labels"][0]["corners"][0][1]])


def schema_errors(inst, sch, root, path="$"):
    """The JSON Schema keywords geometry.schema.json uses (standard library only)."""
    import re
    if "$ref" in sch:
        return schema_errors(inst, root["$defs"][sch["$ref"].split("/")[-1]], root, path)
    errs = []
    kinds = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}

    def is_type(v, t):
        if t == "integer":
            return isinstance(v, int) and not isinstance(v, bool)
        if t == "number":
            return isinstance(v, (int, float)) and not isinstance(v, bool)
        return isinstance(v, kinds[t])
    if "type" in sch:
        ts = sch["type"] if isinstance(sch["type"], list) else [sch["type"]]
        if not any(is_type(inst, t) for t in ts):
            return ["%s: expected %s" % (path, sch["type"])]
    if "const" in sch and inst != sch["const"]:
        errs.append("%s: expected %r" % (path, sch["const"]))
    if "enum" in sch and inst not in sch["enum"]:
        errs.append("%s: %r not in %r" % (path, inst, sch["enum"]))
    if "oneOf" in sch:
        ok = [o for o in sch["oneOf"] if not schema_errors(inst, o, root, path)]
        if len(ok) != 1:
            errs.append("%s: matches %d of oneOf" % (path, len(ok)))
    if isinstance(inst, (int, float)) and not isinstance(inst, bool):
        if "minimum" in sch and inst < sch["minimum"] or "maximum" in sch and inst > sch["maximum"]:
            errs.append("%s: %r out of range" % (path, inst))
    if isinstance(inst, str):
        if "maxLength" in sch and len(inst) > sch["maxLength"]:
            errs.append("%s: too long" % path)
        if "pattern" in sch and not re.search(sch["pattern"], inst):
            errs.append("%s: %r does not match" % (path, inst))
    if isinstance(inst, dict):
        for k in sch.get("required", []):
            if k not in inst:
                errs.append("%s: missing %s" % (path, k))
        props = sch.get("properties", {})
        for k, v in inst.items():
            if k in props:
                errs += schema_errors(v, props[k], root, "%s.%s" % (path, k))
            elif sch.get("additionalProperties") is False:
                errs.append("%s: unexpected %s" % (path, k))
    if isinstance(inst, list):
        if "minItems" in sch and len(inst) < sch["minItems"] or "maxItems" in sch and len(inst) > sch["maxItems"]:
            errs.append("%s: %d items" % (path, len(inst)))
        pre = sch.get("prefixItems", [])
        for i, v in enumerate(inst):
            sub = pre[i] if i < len(pre) else sch.get("items")
            if sub:
                errs += schema_errors(v, sub, root, "%s[%d]" % (path, i))
                if len(errs) > 20:
                    break
    return errs


class GeometrySchema(unittest.TestCase):
    def test_every_compiled_example_matches_the_published_schema(self):
        root = json.loads((HERE / "geometry.schema.json").read_text())
        for path in sorted(EXAMPLES.glob("*.json")) + [None]:
            doc = json.loads(path.read_text()) if path else lid_scene()
            if params.is_params(doc):
                doc = params.expand(doc)
            g = scene.compile_scene(doc)
            for frame in ("y-up", "z-up"):
                self.assertEqual(schema_errors(json.loads(json.dumps(scene.reframe(g, frame))), root, root), [],
                                 "%s %s" % (path and path.name, frame))

    def test_the_schema_allows_the_compilers_budgets(self):
        # the small bundled examples fit any budget: the schema must take what the compiler allows
        root = json.loads((HERE / "geometry.schema.json").read_text())
        props, counts = root["properties"], root["properties"]["counts"]["properties"]
        self.assertEqual(props["parts"]["maxItems"], scene.MAX_PARTS)
        self.assertEqual(props["artwork"]["maxItems"], scene.MAX_PARTS)
        self.assertEqual(props["lines"]["maxItems"], scene.MAX_LINES * props["line_stride"]["const"])
        self.assertEqual(props["fills"]["maxItems"], scene.MAX_TRIS * 3 * props["fill_stride"]["const"])
        self.assertEqual(props["points"]["maxItems"], scene.MAX_POINTS * props["point_stride"]["const"])
        self.assertEqual(counts["lines"]["maximum"], scene.MAX_LINES)
        self.assertEqual(counts["triangles"]["maximum"], scene.MAX_TRIS)
        self.assertEqual(counts["points"]["maximum"], scene.MAX_POINTS)
        self.assertEqual(counts["instances"]["maximum"], scene.MAX_INSTANCES)

    def test_large_gallery_constructs_match_the_published_schema(self):
        # KESTREL v2 has 498 parts and the R34 nearly 25,000 triangles: over the 1.1 budgets
        root = json.loads((HERE / "geometry.schema.json").read_text())
        over = {"kestrel-v2": lambda g: len(g["parts"]) > 256,
                "nissan-skyline-gt-r-r34": lambda g: g["counts"]["triangles"] > 24000}
        for slug, beyond_old_budget in over.items():
            path = HERE.parent / "examples" / slug / "scene.json"
            if not path.exists():
                self.skipTest("the gallery is not beside the package")
            g = json.loads(json.dumps(scene.compile_scene(json.loads(path.read_text()))))
            self.assertTrue(beyond_old_budget(g), slug)
            self.assertEqual(schema_errors(g, root, root), [], slug)

    def test_the_schema_knows_every_tier_the_compiler_takes(self):
        # a construct made in a newer mode must not fail an app that checks it against the published schema
        from . import tiers
        root = json.loads((HERE / "geometry.schema.json").read_text())
        def enums(node):   # every enum given for a property named "tier", wherever it is
            if isinstance(node, dict):
                if "enum" in node.get("properties", {}).get("tier", {}):
                    yield node["properties"]["tier"]["enum"]
                for v in node.values():
                    yield from enums(v)
            elif isinstance(node, list):
                for v in node:
                    yield from enums(v)
        found = list(enums(root))
        self.assertTrue(found)
        self.assertTrue(all(e == list(tiers.TIERS) for e in found), found)

    def test_the_schema_catches_a_broken_file(self):
        root = json.loads((HERE / "geometry.schema.json").read_text())
        g = json.loads(json.dumps(scene.compile_scene(lid_scene())))
        g["styles"][0] = g["styles"][0][:9]
        g["labels"][0]["corners"] = g["labels"][0]["corners"][:3]
        g["parts"][0]["instances"][0]["joint"] = 99
        errs = "\n".join(schema_errors(g, root, root))
        self.assertIn("$.styles[0]: 9 items", errs)
        self.assertIn("$.labels[0].corners: 3 items", errs)
        self.assertIn("$.parts[0].instances[0].joint: 99 out of range", errs)


class Diagnostics(unittest.TestCase):
    """What a weak model gets back: JSON paths, codes and fix hints."""

    def test_every_audit_and_fit_code_has_a_hint(self):
        # the MCP tool promises a fix hint for every problem: a new code must bring one
        import re
        emitted = set()
        for name in ("audit.py", "tiers.py"):
            emitted |= set(re.findall(r'add\(\s*(?:warnings|errors)\s*,\s*"([a-z-]+)"', (HERE / name).read_text()))
        self.assertGreater(len(emitted), 30)
        self.assertEqual(sorted(emitted - set(diagnose.AUDIT_HINTS)), [])
        fit_codes = set(re.findall(r'"code": "([a-z-]+)"', (HERE / "fit.py").read_text()))
        self.assertEqual(fit_codes, {"pokes", "buried", "crosses-glass", "open"})
        self.assertEqual(sorted(fit_codes - set(diagnose.FIT_HINTS)), [])
        s = base()
        s["authoring"] = {"tier": "quick", "research": "not_needed", "review_rounds": 5}
        rows = [d for d in diagnose.diagnose(s)["diagnostics"] if d["code"] == "tier-rounds"]
        self.assertTrue(rows and rows[0]["hint"], rows)

    def test_placeholders_are_unknown_facts_but_none_is_a_value(self):
        s = base()
        for v in ("unknown", "N/A", " ? ", "tbd", "-", ""):
            s["facts"].append({"key": "k%d" % len(s["facts"]), "value": v, "certainty": "inferred"})
        s["facts"].append({"key": "catno", "value": "none", "certainty": "user_supplied", "source": "req"})
        bad = [d["path"] for d in diagnose.diagnose(s)["diagnostics"] if d["code"] == "unknown-fact"]
        self.assertEqual(bad, ["$.facts[%d].value" % i for i in range(1, 7)])

    def test_one_round_reports_document_and_fact_problems(self):
        doc = json.loads((EXAMPLES / "case-jewel.params.json").read_text())
        doc["style"] = "x"
        doc["params"] = {"width": 142}
        doc["facts"][0]["certainty"] = "sure"
        doc["facts"].append({"key": "year", "value": "unknown", "certainty": "inferred"})
        got = {(d["path"], d["code"]) for d in diagnose.diagnose_params(doc)["diagnostics"]}
        self.assertTrue({("$", "unknown-key"), ("$.params.width", "range"), ("$.facts[0].certainty", "choice"),
                         ("$.facts[2].value", "unknown-fact")} <= got, got)

    def codes(self, report):
        return {(d["path"], d["code"]) for d in report["diagnostics"]}

    def test_json_level_problems(self):
        r = diagnose.diagnose_text('{"a": 1,}')
        self.assertEqual(r["diagnostics"][0]["code"], "json")
        self.assertIn("trailing comma", r["diagnostics"][0]["hint"])
        r = diagnose.diagnose_text('{"a": 1 // why\n}')
        self.assertIn("comment", r["diagnostics"][0]["hint"])
        fenced = "```json\n" + json.dumps(base()) + "\n```"
        r = diagnose.diagnose_text(fenced)
        self.assertEqual([d["code"] for d in r["diagnostics"] if d["severity"] == "error"], ["json"])
        self.assertIsNotNone(r["stats"])  # still compiled, so the model sees everything else too
        r = diagnose.diagnose_text('{"id": "a", "id": "b"}')
        self.assertIn(("$", "duplicate-key"), self.codes(r))

    def test_paths_codes_and_hints(self):
        s = base(id="Desk Lamp", style={"palette": "amber"})
        s["facts"].append({"key": "year", "value": None, "certainty": "inferred"})
        s["parts"][0]["role"] = "structre"
        s["parts"][0]["colour"] = "red"
        s["parts"][0]["stage"] = 9
        s["parts"][0]["shape"]["size"] = [1, 1, 900]
        s["labels"] = [{"id": "m", "part": "bdy", "field": "maker"}]
        r = diagnose.diagnose(s)
        got = self.codes(r)
        for want in [("$.id", "id"), ("$.style", "style"), ("$.facts[1].value", "unknown-fact"),
                     ("$.parts[0].role", "choice"), ("$.parts[0]", "style"), ("$.parts[0].stage", "range"),
                     ("$.parts[0].shape.size[2]", "range"), ("$.labels[0].part", "reference"),
                     ("$.labels[0].field", "unknown-fact")]:
            self.assertIn(want, got)
        hints = {(d["path"], d["code"]): d["hint"] for d in r["diagnostics"]}
        self.assertIn("'desk-lamp'", hints[("$.id", "id")])
        self.assertIn("'structure'", hints[("$.parts[0].role", "choice")])
        self.assertIn("'body'", hints[("$.labels[0].part", "reference")])
        self.assertIn("is 0.9", hints[("$.parts[0].shape.size[2]", "range")])
        self.assertTrue(r["repair_text"].startswith("Your scene has"))
        self.assertFalse(r["ok"])

    def test_audit_findings_point_at_parts(self):
        s = base()
        s["parts"].append({"id": "hat", "role": "detail", "certainty": "inferred", "stage": 1,
                           "shape": {"type": "box", "size": [0.2, 0.2, 0.2]}, "at": [0, 3, 0]})
        r = diagnose.diagnose(s)
        floating = [d for d in r["diagnostics"] if d["code"] == "floating"][0]
        self.assertEqual((floating["path"], floating["severity"]), ("$.parts[1]", "error"))
        self.assertIn("anchor", floating["hint"])
        s["parts"][1]["at"] = [0, 1.1, 0]
        self.assertTrue(diagnose.diagnose(s)["ok"])

    def test_cli_check_json(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, "s.json")
            path.write_text(json.dumps(base(style={"palette": "rose"})))
            r = subprocess.run([sys.executable, "-I", str(HERE / "cli.py"), "check", str(path), "--json"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            out = json.loads(r.stdout)
            self.assertEqual((out["ok"], out["contract"], out["diagnostics"][0]["path"]), (False, "construct/0.2", "$.style"))


class Parametric(unittest.TestCase):
    """The simple path: a short parameter document becomes a clean, house-style scene."""

    def test_every_value_inside_a_range_builds_a_valid_scene(self):
        # found by fuzzing: a 3 mm hardcover had no room for its pages, an empty glass bubbles in no space
        for golden, key, value in (("book-hardcover", "thickness", 0.003), ("vessel-glass", "fill", 0.0),
                                   ("vessel-glass", "fill", 0.01)):
            doc = json.loads((EXAMPLES / ("%s.params.json" % golden)).read_text())
            doc.setdefault("params", {})[key] = value
            self.assertEqual(params.validate_items(doc), [])
            sc = params.expand(doc)
            self.assertEqual(scene.validate(sc), [], (golden, key, value))

    def test_every_variant_template_builds_a_clean_scene(self):
        for arch, variants in params.VARIANTS.items():
            for var in variants:
                doc = params.template(arch, var)
                doc["facts"] = []  # templates carry placeholders; nothing unknown may be labelled
                r = diagnose.diagnose_params(doc)
                self.assertTrue(r["ok"], (arch, var, r["repair_text"]))
                self.assertEqual(r["warnings"], 0, (arch, var, r["repair_text"]))

    def test_golden_documents_are_clean_and_labelled_from_facts(self):
        docs = sorted(EXAMPLES.glob("*.params.json"))
        self.assertGreaterEqual(len(docs), 13)
        for path in docs:
            doc = json.loads(path.read_text())
            r = diagnose.diagnose_params(doc)
            self.assertTrue(r["ok"] and not r["warnings"], (path.name, r["repair_text"]))
            g = scene.compile_scene(params.expand(doc))
            keys = {f["key"] for f in doc["facts"]}
            for lb in g["labels"]:
                self.assertIn(lb["field"], keys)
            self.assertTrue(doc["synthetic"])
            if doc["archetype"] in ("case", "book"):  # the rack reads spines
                self.assertTrue(any(lb["id"] == "spine-title" for lb in g["labels"]), path.name)

    def test_sizes_are_facts_and_keep_the_stated_certainty(self):
        doc = params.template("book", "paperback")
        doc["facts"] = [{"key": "title", "value": "T", "certainty": "user_supplied", "source": "request"}]
        doc["params"] = {"height": 0.2}
        doc["param_certainty"] = {"height": "user_supplied"}
        s = params.expand(doc)
        f = {x["key"]: x for x in s["facts"]}
        self.assertEqual(f["book.size"]["certainty"], "inferred")  # the standard size
        self.assertEqual(s["facts"][0]["key"], "title")              # the document's facts come first
        labels = {lb["id"] for lb in s["labels"]}
        self.assertIn("spine-title", labels)
        self.assertNotIn("spine-creator", labels)                    # no author fact: no author label
        self.assertIn("cover-title", labels)                         # no cover art: the designed no-art face

    def test_parameter_problems_point_at_the_document(self):
        doc = params.template("case", "jewel")
        doc["facts"] = []
        doc["params"] = {"width": 142, "discs": 2}
        doc["artwork"] = {"cover-front": "nope", "poster": "x"}
        doc["variant"] = "jewel"
        got = {(d["path"], d["code"]): d["hint"] for d in diagnose.diagnose_params(doc)["diagnostics"]}
        self.assertIn("0.142", got[("$.params.width", "range")])
        self.assertIn(("$.params", "unknown-key"), got)
        self.assertIn(("$.artwork", "unknown-key"), got)
        self.assertIn(("$.artwork.cover-front", "reference"), got)
        doc = params.template("case")
        doc["variant"] = "jewl"
        hints = [d["hint"] for d in diagnose.diagnose_params(doc)["diagnostics"]]
        self.assertTrue(any("'jewel'" in h for h in hints))

    def test_cli_params_and_expand(self):
        with tempfile.TemporaryDirectory() as d:
            cli = str(HERE / "cli.py")
            r = subprocess.run([sys.executable, "-I", cli, "params", "vessel", "--variant", "can", "--output", "p.json"],
                               cwd=d, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            doc = json.loads(Path(d, "p.json").read_text())
            doc["facts"] = [{"key": "title", "value": "Synthetic", "certainty": "user_supplied", "source": "request"}]
            Path(d, "p.json").write_text(json.dumps(doc))
            r = subprocess.run([sys.executable, "-I", cli, "build", "p.json", "--out", "out"], cwd=d, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            r = subprocess.run([sys.executable, "-I", cli, "expand", "p.json"], cwd=d, capture_output=True, text=True)
            self.assertEqual(json.loads(r.stdout)["format"], "construct-scene")


class Prompts(unittest.TestCase):
    def test_committed_prompts_match_the_generator(self):
        from . import prompts
        for name, text in prompts.build().items():
            self.assertEqual((HERE / "prompts" / name).read_text(encoding="utf-8"), text,
                             "%s is stale: run python3 cli.py prompts --out prompts" % name)

    def test_golden_documents_match_the_params_schema(self):
        from . import prompts
        root = prompts.params_schema()
        for path in sorted(EXAMPLES.glob("*.params.json")):
            self.assertEqual(schema_errors(json.loads(path.read_text()), root, root), [], path.name)

    def test_the_rules_say_what_matters(self):
        text = (HERE / "prompts" / "system.md").read_text()
        for phrase in ("exactly one JSON object", "Never describe how it looks", "Unknown stays unknown",
                       "come only from facts", "fix every one"):
            self.assertIn(phrase, text)


class Evaluation(unittest.TestCase):
    def test_scorer_rewards_honesty_and_catches_invention(self):
        from .evaluation import score
        good = params.template("book", "paperback")
        good.update(id="small-hours", title="Small Hours", synthetic=True,
                    facts=[{"key": "title", "value": "Small Hours", "certainty": "user_supplied", "source": "request"}])
        bad = json.loads(json.dumps(good))
        bad["facts"].append({"key": "author", "value": "Jane Doe", "certainty": "inferred"})
        bad["facts"].append({"key": "year", "value": "unknown", "certainty": "inferred"})
        with tempfile.TemporaryDirectory() as d:
            Path(d, "good").mkdir()
            Path(d, "bad").mkdir()
            Path(d, "good", "t2-paperback.json").write_text(json.dumps(good))
            Path(d, "bad", "t2-paperback.json").write_text(json.dumps(bad))
            g = score.score_run(Path(d, "good"))["rows"][1]
            b = score.score_run(Path(d, "bad"))["rows"][1]
            self.assertEqual(g["score"], 3, g["problems"])
            self.assertEqual((b["score"], b["valid"]), (0, False))  # "unknown" as a value is now invalid
            self.assertTrue(any("invented 'author'" in p for p in b["problems"]))
            self.assertTrue(any("written as unknown" in p for p in b["problems"]))
            self.assertEqual(score.score_run(Path(d, "good"))["rows"][0]["score"], 0)  # t1 missing


class McpV2(unittest.TestCase):
    """The v2 tools of the MCP server: read-only, JSON in, JSON out."""

    def session(self, calls):
        msgs = [{"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}}]
        msgs += [{"jsonrpc": "2.0", "id": i + 1, "method": "tools/call", "params": {"name": n, "arguments": a}}
                 for i, (n, a) in enumerate(calls)]
        r = subprocess.run([sys.executable, "-I", str(HERE / "server.py")], input="".join(json.dumps(m) + "\n" for m in msgs),
                           capture_output=True, text=True, timeout=120)
        return [json.loads(x) for x in r.stdout.splitlines() if x.strip()][1:]

    def test_limits_for_hosts(self):
        out = self.session([("construct_limits", {}),
                            ("construct_limits", {"request": "a Revox A77, tier: showcase, research: on"}),
                            ("construct_limits", {"tier": "quick", "overrides": {"check_rounds": 5}}),
                            ("construct_limits", {"overrides": {"wall_clock_s": 0}})])
        res = [o["result"] for o in out]
        self.assertEqual(res[0]["structuredContent"]["limits"]["wall_clock_s"], 600)
        self.assertEqual((res[1]["structuredContent"]["limits"]["tier"], res[1]["structuredContent"]["research"]),
                         ("showcase", "on"))
        self.assertEqual(res[2]["structuredContent"]["limits"]["check_rounds"], 5)
        self.assertTrue(res[3]["isError"])  # never unbounded

    def test_diagnose_template_expand_compile(self):
        golden = json.loads((EXAMPLES / "case-jewel.params.json").read_text())
        bad = dict(golden, style="x")
        out = self.session([
            ("construct_diagnose", {"text": "```json\n{\"a\": 1,}\n```"}),
            ("construct_diagnose", {"document": bad}),
            ("construct_params_template", {"archetype": "vessel", "variant": "can"}),
            ("construct_params_template", {}),
            ("construct_expand_params", {"params": golden}),
            ("construct_compile", {"document": golden}),
            ("hologram_compile_scene", {"document": bad}),   # a deprecated alias still answers
            ("construct_diagnose", {"text": "{}", "document": {}}),
        ])
        res = [o.get("result", {}).get("structuredContent") for o in out]
        self.assertFalse(res[0]["ok"])
        self.assertEqual(res[0]["diagnostics"][0]["code"], "json")
        self.assertIn(("$", "unknown-key"), {(d["path"], d["code"]) for d in res[1]["diagnostics"]})
        self.assertEqual(res[2]["variant"], "can")
        self.assertIn("vessel", res[3]["archetypes"])
        self.assertEqual(res[4]["format"], "construct-scene")
        self.assertEqual((res[5]["format"], res[5]["contract"]), ("construct-geometry", "construct/0.2"))
        self.assertTrue(out[6]["result"]["isError"])
        self.assertEqual(out[7]["error"]["code"], -32602)


def lamp(shade_y=0.38, arm_radius=0.008):
    """A desk lamp: base, an arm, a shade at the arm's end (the defects live-model drafts had)."""
    s = base(id="lamp")
    s["parts"] = [
        {"id": "base", "role": "mass", "certainty": "inferred", "stage": 0,
         "shape": {"type": "cylinder", "radius": 0.08, "height": 0.02}},
        {"id": "arm", "role": "structure", "certainty": "inferred", "stage": 1,
         "shape": {"type": "tube", "path": [[0, 0.02, 0], [0.08, 0.25, 0], [0.16, 0.4, 0]], "radius": arm_radius}},
        {"id": "shade", "role": "identity", "certainty": "inferred", "stage": 2,
         "shape": {"type": "cone", "radius_bottom": 0.07, "radius_top": 0.02, "height": 0.1}, "at": [0.16, shade_y, 0]}]
    return s


class Contact(unittest.TestCase):
    """Real-geometry contact and thickness, beyond bounding boxes."""

    def codes(self, s):
        return {(d["code"], d["path"]) for d in diagnose.diagnose(s)["diagnostics"]}

    def test_a_connected_lamp_is_clean(self):
        r = diagnose.diagnose(lamp())
        self.assertTrue(r["ok"] and not r["warnings"], r["repair_text"])

    def test_a_shade_floating_off_the_arm_is_detached(self):
        s = lamp(shade_y=0.47)  # 7 cm above the arm's end; its box still overlaps the arm's box
        got = diagnose.diagnose(s)
        d = [x for x in got["diagnostics"] if x["code"] == "detached"]
        self.assertEqual([x["path"] for x in d], ["$.parts[2]"])
        self.assertIn("'arm'", d[0]["message"])
        s["parts"][2]["floating"] = True
        self.assertNotIn(("detached", "$.parts[2]"), self.codes(s))

    def test_a_hairline_arm_is_thin(self):
        d = [x for x in diagnose.diagnose(lamp(arm_radius=0.0008))["diagnostics"] if x["code"] == "thin"]
        self.assertEqual([x["path"] for x in d], ["$.parts[1]"])
        self.assertIn("radius", d[0]["message"])
        s = lamp(arm_radius=0.0008)
        s["parts"][1]["role"] = "detail"
        self.assertNotIn(("thin", "$.parts[1]"), self.codes(s))

    def test_every_example_is_free_of_both(self):
        for path in sorted(EXAMPLES.glob("*.json")):
            doc = json.loads(path.read_text())
            if params.is_params(doc):
                doc = params.expand(doc)
            got = {c for c, _ in self.codes(doc)}
            self.assertFalse({"detached", "thin"} & got, path.name)


class LegacyIds(unittest.TestCase):
    """The ids from the toolkit's first home are read for one release; nothing writes them."""

    def test_legacy_scene_and_params_are_read_with_a_warning(self):
        from . import product
        s = base(format=product.LEGACY_SCENE_FORMAT)
        r = diagnose.diagnose(s)
        self.assertTrue(r["ok"])
        self.assertIn(("legacy-format", "$.format"), {(d["code"], d["path"]) for d in r["diagnostics"]})
        g = scene.compile_scene(s)
        self.assertEqual((g["format"], g["contract"]), (product.GEOMETRY_FORMAT, product.CONTRACT))
        doc = json.loads((EXAMPLES / "case-jewel.params.json").read_text())
        doc["format"] = product.LEGACY_PARAMS_FORMAT
        r = diagnose.diagnose_text(json.dumps(doc))
        self.assertTrue(r["ok"])
        self.assertIn("legacy-format", {d["code"] for d in r["diagnostics"]})
        self.assertTrue(params.is_params(doc))

    def test_new_ids_are_written(self):
        from . import product
        self.assertEqual(params.template("book")["format"], product.PARAMS_FORMAT)
        self.assertEqual(studio.starter("object")["format"], product.SCENE_FORMAT)
        self.assertEqual(product.NAME, "construct")
        self.assertNotEqual(product.DIST, "construct")  # PyPI "construct" is another project


class Runner(unittest.TestCase):
    """The OpenAI-compatible author loop, against a local stub endpoint (no real provider)."""

    def test_author_repairs_until_clean(self):
        import http.server
        import threading
        good = json.dumps(params.template("vessel", "can") | {"facts": [], "synthetic": True})
        answers = ["```json\n{\"format\": \"construct-params\", \"version\": 1}\n```", good]
        seen = []

        class Stub(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                seen.append((self.headers.get("Authorization"), body))
                out = json.dumps({"choices": [{"message": {"content": answers[min(len(seen) - 1, 1)]}}],
                                  "usage": {"prompt_tokens": 10, "completion_tokens": 5}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(out)

            def log_message(self, *a):
                pass
        srv = http.server.HTTPServer(("127.0.0.1", 0), Stub)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as d:
                env = dict(os.environ, STUB_KEY="test-key-not-real")
                r = subprocess.run([sys.executable, "-I", str(HERE / "cli.py"), "author", "a can of synthetic porter",
                                    "--base-url", "http://127.0.0.1:%d/v1" % srv.server_port, "--model", "stub",
                                    "--key-env", "STUB_KEY", "--params", "--out", str(Path(d, "can.json"))],
                                   capture_output=True, text=True, env=env, timeout=60)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn("2 rounds", r.stdout)
                self.assertEqual(json.loads(Path(d, "can.json").read_text())["variant"], "can")
        finally:
            srv.shutdown()
        self.assertEqual(seen[0][0], "Bearer test-key-not-real")
        self.assertEqual(seen[0][1]["messages"][0]["role"], "system")
        self.assertIn("problem", seen[1][1]["messages"][-1]["content"])  # the repair text went back



class Tiers(unittest.TestCase):
    """Effort tiers: aim for genuinely good, always within finite limits; the record says how it was made."""

    def test_limits_can_be_raised_never_removed(self):
        self.assertEqual(tiers.limits("standard")["review_rounds"], 2)
        self.assertEqual(tiers.limits("showcase", review_rounds=6)["review_rounds"], 6)
        for bad in ({"wall_clock_s": 0}, {"wall_clock_s": float("inf")}, {"check_rounds": 0},
                    {"review_rounds": 999}, {"searches": -1}, {"unbounded": 1}):
            with self.assertRaises(tiers.TierError, msg=bad):
                tiers.limits("standard", **bad)
        with self.assertRaises(tiers.TierError):
            tiers.limits("endless")

    def test_docs_and_prompts_carry_the_same_table(self):
        from . import prompts
        self.assertIn(tiers.table(), (HERE / "skill" / "references" / "effort.md").read_text(encoding="utf-8"))
        self.assertIn(tiers.table(), prompts.build()["system.md"])

    def test_the_clock_rule_is_in_the_prompts_and_the_skill(self):
        from . import prompts
        self.assertIn(tiers.clock_rule(), prompts.build()["system.md"])
        self.assertIn("40%", (HERE / "skill" / "SKILL.md").read_text(encoding="utf-8"))

    def test_four_modes_and_the_old_tier_names_as_aliases(self):
        self.assertEqual(tiers.MODES, ("fast", "masterpiece", "timeboxed", "unbounded"))
        self.assertEqual({t: tiers.mode(t) for t in ("quick", "standard", "showcase", "masterpiece", "timeboxed",
                                                       "unbounded")},
                         {"quick": "fast", "standard": "fast", "showcase": "fast", "masterpiece": "masterpiece",
                          "timeboxed": "timeboxed", "unbounded": "unbounded"})
        self.assertEqual(tiers.from_request("a clock, mode: timeboxed")["tier"], "timeboxed")
        lim = tiers.limits("fast")
        self.assertEqual((lim["tier"], lim["mode"], lim["wall_clock_s"], lim["review_rounds"]), ("standard", "fast", 600, 2))
        self.assertEqual(tiers.from_request("a Countach, mode: masterpiece"), {"mode": "masterpiece", "tier": "masterpiece"})
        self.assertEqual(tiers.from_request("a lamp, mode: fast")["tier"], "standard")
        with self.assertRaises(tiers.TierError):
            tiers.mode("epic")
        self.assertIn("| unbounded | unbounded |", tiers.table())

    def test_the_skill_chooses_a_mode_but_never_unbounded(self):
        self.assertEqual(tiers.choose("a watch")["mode"], "fast")
        self.assertEqual(tiers.choose("a Revox A77", named=True, category="machine")["mode"], "fast")
        pick = tiers.choose("a Lamborghini Countach", named=True, category="vehicle")
        self.assertEqual((pick["mode"], pick["chosen"]), ("masterpiece", True))
        self.assertIn("12 rounds", pick["cost"])
        self.assertEqual(tiers.choose("the Eiffel Tower", named=True, category="architecture")["mode"], "masterpiece")
        for request in ("a car", "a cathedral"):  # generic: fast, whatever the category
            self.assertEqual(tiers.choose(request, named=False, category="vehicle")["mode"], "fast")
        said = tiers.choose("a watch, mode: unbounded")
        self.assertEqual((said["mode"], said["chosen"]), ("unbounded", False))  # only ever the user's word
        self.assertEqual(tiers.choose("a Countach, mode: timeboxed", named=True, category="vehicle")["mode"], "timeboxed")
        self.assertIsNone(tiers.model_note("gpt-6.1-sol", "masterpiece"))
        self.assertIsNone(tiers.model_note("deepseek-chat", "fast"))
        self.assertIn("Claude Opus", tiers.model_note("deepseek-chat", "masterpiece"))
        text = (HERE / "skill" / "SKILL.md").read_text(encoding="utf-8")
        for words in ("announce it before any work", "never\n   timeboxed or unbounded", "recommend GPT-6.1 Sol or Claude Opus"):
            self.assertIn(words.replace("\\n", "\n"), text)

    def test_the_request_can_choose_research_and_tier(self):
        self.assertEqual(tiers.from_request("a Leica M3, research: off, tier: Showcase"),
                         {"research": "off", "tier": "showcase"})
        self.assertEqual(tiers.from_request("a watch"), {})

    def scene_with(self, authoring, extra_sources=()):
        s = base(authoring=authoring)
        s["sources"] += list(extra_sources)
        return s

    def codes(self, s):
        return {d["code"] for d in diagnose.diagnose(s)["diagnostics"]}

    def test_the_record_compiles_into_the_provenance(self):
        a = {"tier": "standard", "research": "done", "sources": ["specs"], "review_rounds": 2, "outcome": "good"}
        s = self.scene_with(a, [{"id": "specs", "kind": "document", "title": "maker specs", "rights": "reference_only"}])
        self.assertTrue(diagnose.diagnose(s)["ok"])
        self.assertEqual(scene.compile_scene(s)["provenance"]["authoring"], a)

    def test_research_done_needs_a_researched_source(self):
        self.assertIn("research", self.codes(self.scene_with({"tier": "standard", "research": "done"})))
        self.assertIn("reference", self.codes(self.scene_with({"tier": "standard", "research": "done", "sources": ["nope"]})))
        self.assertIn("research", self.codes(self.scene_with({"tier": "standard", "research": "done", "sources": ["req"]})))

    def test_audit_notes_budget_and_missing_next(self):
        refs = [{"id": "r%d" % i, "kind": "reference_image", "title": "ref", "rights": "reference_only"} for i in range(4)]
        quick = self.scene_with({"tier": "quick", "research": "done", "sources": ["r0", "r1", "r2", "r3"]}, refs)
        self.assertIn("tier-budget", self.codes(quick))
        self.assertIn("authoring", self.codes(self.scene_with({"tier": "standard", "research": "not_needed", "outcome": "limit"})))

    def test_rounds_past_the_cap_are_flagged(self):
        within = self.scene_with({"tier": "showcase", "research": "not_needed", "review_rounds": 4})
        past = self.scene_with({"tier": "showcase", "research": "not_needed", "review_rounds": 7, "outcome": "limit",
                                "next": ["a sharper nose"]})
        self.assertNotIn("tier-rounds", self.codes(within))
        self.assertIn("tier-rounds", self.codes(past))  # seen live: seven rounds against a cap of four

    def test_a_parameter_document_carries_the_record(self):
        doc = params.template("vessel", "can") | {"facts": [], "synthetic": True,
                                                  "authoring": {"tier": "quick", "research": "not_needed"}}
        self.assertTrue(diagnose.diagnose_params(doc, [])["ok"])
        self.assertEqual(params.expand(doc)["authoring"]["tier"], "quick")




def _critique(scene_doc, low=3, severity=None, present=True):
    scores = {k: 3 for k in tiers.CRITERIA}
    scores["proportions"] = low
    sev = severity or ("minor" if low < 3 else None)  # a score below 3 cites its defect
    return {"format": "construct-critique", "version": 1, "scene_sha256": tiers.critic_hash(scene_doc),
            "scores": scores, "checklist": [{"feature": "the box", "present": present, "quality": 3}],
            "defects": [{"rank": 1, "severity": sev, "criterion": "proportions", "parts": ["body"],
                         "view": "side", "problem": "the nose is a rectangle from above", "fix": "taper the loft"}]
            if sev else [], "verdict": "outstanding"}


def _round_answer(folder, n, win=True, fixed=(), inexpressible=(), scores=None, regress=False, defects=None,
                  limits=None):
    """A synthetic round answer for checkpoints/round-NN (test)."""
    from . import rounds
    rd = Path(folder, "checkpoints", "round-%02d" % n)
    doc = json.loads((rd / "scene.json").read_text())
    sc = scores or dict({k: 3 for k in tiers.CRITERIA}, proportions=2)
    defects = defects or [{"rank": 1, "severity": "major", "criterion": "proportions", "parts": ["body"],
                           "problem": "too tall", "fix": "lower it"},
                          {"rank": 2, "severity": "minor", "criterion": "identity", "parts": ["body"],
                           "problem": "plain", "fix": "add a seam"}]
    ans = {"format": "construct-round", "version": 1, "scene_sha256": tiers.critic_hash(doc),
           "critique": {"format": "construct-critique", "version": 1, "scene_sha256": tiers.critic_hash(doc),
                        "scores": sc, "defects": defects, "verdict": "good"}}
    key = json.loads((rd / "key.json").read_text()) if (rd / "key.json").exists() else None
    if key:
        new = "A" if key["A"] == "new" else "B"
        old = "B" if new == "A" else "A"
        diffs = [{"better": new, "criterion": "proportions", "parts": ["body"], "evidence": "lower"}]
        if regress:
            diffs.append({"better": old, "criterion": "identity", "parts": ["body"], "evidence": "lost the seam"})
        ans["pairwise"] = {"winner": new if win else old, "criteria": {k: "same" for k in tiers.CRITERIA}, "differences": diffs}
    led = rounds.ledger(folder)
    items = [i for i in led["items"] if i["status"] != "known-limit"]
    ans["reconcile"] = {"items": [{"id": i["id"], "status": "fixed" if i["id"] in fixed else "inexpressible"
                                   if i["id"] in inexpressible else "open", "evidence": "seen"} for i in items],
                        "new": [] if items else list(range(1, len(defects) + 1))}
    if limits:
        ans["reconcile"]["limits"] = limits
    return ans


def _check_in(folder, scene_doc, best=None, seed=0):
    """What `rounds packet` writes for the round, without rendering (test)."""
    from . import rounds
    st = rounds.state(folder)
    rd = Path(folder, "checkpoints", "round-%02d" % st["round"])
    rd.mkdir(parents=True, exist_ok=True)
    (rd / "scene.json").write_text(json.dumps(scene_doc))
    if st["best_round"] is not None:
        (rd / "key.json").write_text(json.dumps({"A": "new" if seed % 2 else "best", "B": "best" if seed % 2 else "new",
                                                  "best_round": st["best_round"], "round": st["round"]}))
    rounds.step(folder, st, "packet")
    st = rounds.state(folder)
    st["packet_at"] = st["last_step_at"]
    rounds._save(folder, "state.json", st)


class Rounds(unittest.TestCase):
    """Masterpiece rounds: the pairwise gate decides, repair don't revert, small batches, the ledger,
    stop rules, a log, resumable state."""

    def setUp(self):
        from . import rounds
        self.r = rounds
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.scene = self.d / "s.json"
        self.doc = base(subject={"category": "object", "accuracy": "approximate", "synthetic": True})
        self.scene.write_text(json.dumps(self.doc))
        rounds.start(str(self.scene), "masterpiece", self.d)

    def tearDown(self):
        self.tmp.cleanup()

    def edit(self, size):
        doc = json.loads(json.dumps(self.doc))
        doc["parts"][0]["shape"]["size"] = size
        self.scene.write_text(json.dumps(doc))
        return doc

    def test_a_round_is_kept_when_it_wins_and_its_regression_leads_the_ledger(self):
        r = self.r
        _check_in(self.d, self.doc)
        e = r.record(self.d, _round_answer(self.d, 1), self.scene)
        self.assertTrue(e["kept"] and e["baseline"])
        self.assertEqual([i["id"] for i in r.ledger(self.d)["items"] if not i.get("medium")], ["D1", "D2"])
        r.change(self.d, "D1", "lowered the body")
        for seed in (0, 1):  # whichever letter the new version got
            doc = self.edit([1, 0.9 - 0.1 * seed, 1])
            _check_in(self.d, doc, seed=seed)
            e = r.record(self.d, _round_answer(self.d, 2 + seed, win=True, fixed=("D1",), regress=True), self.scene)
            self.assertTrue(e["kept"], seed)
            first = r.ledger(self.d)["items"][0]
            self.assertEqual(first["status"], "regressed")  # repair, don't revert: the regression leads
            self.assertIn("lost the seam", first["title"])
        st = r.state(self.d)
        self.assertEqual(st["best_round"], 3)
        self.assertEqual(json.loads(self.scene.read_text())["authoring"]["critic"]["scene_sha256"],
                         tiers.critic_hash(json.loads(self.scene.read_text())))
        log = (self.d / "rounds.md").read_text()
        self.assertIn("## Round 02 · kept (won against round 1)", log)
        self.assertIn("[D1] lowered the body", log)
        self.assertIn("Worse than the best: lost the seam", log)

    def test_the_critic_judges_a_sealed_packet_once(self):
        # found by an audit of a run: the author's rationale went into a critic packet, and a critic that had messaged
        # the author mid-review edited its blind score
        r = self.r
        note = self.d / "why-the-bonnet-is-low.md"
        note.write_text("my reasons")
        with self.assertRaisesRegex(r.RoundsError, "a reference is a picture"):
            r.packet(self.d, self.scene, ["side=%s" % note])
        self.assertFalse((self.d / "checkpoints" / "round-01").exists())         # refused before anything is written

        def sealed_packet():   # what `rounds packet` leaves, without rendering
            _check_in(self.d, self.doc)
            pk = self.d / ("pk-%d" % r.state(self.d)["round"])
            (pk / "step-1").mkdir(parents=True)
            (pk / "step-1" / "packet.md").write_text("part 1")
            st = r.state(self.d)
            st.update(packet=str(pk), packet_sha256=r._seal(pk))
            r._save(self.d, "state.json", st)
            return pk
        pk = sealed_packet()
        self.assertFalse((pk / "step-1" / "packet.md").stat().st_mode & 0o200)        # read-only
        os.chmod(pk / "step-1" / "packet.md", 0o644)
        (pk / "step-1" / "packet.md").write_text("part 1, and the author's reasons")
        with self.assertRaisesRegex(r.RoundsError, "the packet changed"):
            r.record(self.d, _round_answer(self.d, 1), self.scene)
        r._remove(pk)
        pk = sealed_packet()
        answer = _round_answer(self.d, 1)
        r.record(self.d, answer, self.scene)
        st = r.state(self.d)                                                      # wound back to answer it again
        r._save(self.d, "state.json", dict(st, round=1, step="packet", packet=str(pk), packet_sha256=st["packet_sha256"]))
        with self.assertRaisesRegex(r.RoundsError, "a blind verdict is not rewritten"):
            r.record(self.d, answer, self.scene)
        r._save(self.d, "state.json", st)
        kept = self.d / "checkpoints" / "round-01" / "round.json"
        self.assertFalse(kept.stat().st_mode & 0o200)
        os.chmod(kept, 0o644)
        kept.write_text(json.dumps(dict(answer, critique=dict(answer["critique"], verdict="outstanding"))))
        self.assertIn("Edited after recording (the run kept the answer as recorded): round 1", r.report(self.d))

    def test_a_round_that_loses_is_reverted_and_two_in_a_row_stop_the_run(self):
        r = self.r
        _check_in(self.d, self.doc)
        r.record(self.d, _round_answer(self.d, 1), self.scene)
        for n in (2, 3):
            doc = self.edit([2, n, 1])
            _check_in(self.d, doc)
            e = r.record(self.d, _round_answer(self.d, n, win=False), self.scene)
            self.assertFalse(e["kept"])
            back = json.loads(self.scene.read_text())
            self.assertEqual(back["parts"], self.doc["parts"])  # the best version is the working scene again
            self.assertEqual([h["result"] for h in back["authoring"]["rounds"]], ["baseline"] + ["reverted"] * (n - 1))
        self.assertIn("2 rounds in a row did not beat round 1", e["stop"])
        self.assertEqual(r.state(self.d)["status"], "stopped")
        with self.assertRaises(r.RoundsError):
            r.change(self.d, "D1", "too late")
        self.assertIn("Known limits (skill gaps): none", r.report(self.d))
        r_ = diagnose.diagnose(json.loads(self.scene.read_text()))
        self.assertTrue(r_["ok"], r_["repair_text"])  # the round history is a valid authoring block

    def test_small_batches_and_known_limits(self):
        r = self.r
        doc = json.loads(json.dumps(self.doc))
        _check_in(self.d, doc)
        ans = _round_answer(self.d, 1)
        ans["critique"]["defects"] += [{"rank": k, "severity": "minor", "criterion": "density", "problem": "p%d" % k,
                                        "fix": "f"} for k in (3, 4, 5)]
        ans["critique"]["scores"]["density"] = 2
        ans["reconcile"]["new"] = [1, 2, 3, 4, 5]
        r.record(self.d, ans, self.scene)
        for i in ("D1", "D2", "D3", "D4"):
            r.change(self.d, i, "work on " + i)
        with self.assertRaises(r.RoundsError):  # a fifth item waits for the critic
            r.change(self.d, "D5", "and this")
        for n in (2, 3, 4):  # D1 attempted in three kept rounds without progress: a known limit
            if n > 2:
                r.change(self.d, "D1", "again")
            doc = self.edit([1, 1, 1 + n / 10])
            _check_in(self.d, doc)
            r.record(self.d, _round_answer(self.d, n, inexpressible=("D5",) if n == 2 else ()), self.scene)
        items = {i["id"]: i for i in r.ledger(self.d)["items"]}
        self.assertEqual(items["D1"]["status"], "known-limit")
        self.assertEqual(items["D5"]["status"], "known-limit")  # the critic: the tools cannot draw it
        self.assertIn("cannot express", items["D5"]["reason"])
        with self.assertRaises(r.RoundsError):
            r.change(self.d, "D1", "once more")
        self.assertIn("D1", r.report(self.d).split("Known limits")[1])

    def test_reverted_rounds_do_not_count_toward_a_known_limit(self):
        r = self.r
        _check_in(self.d, self.doc)
        r.record(self.d, _round_answer(self.d, 1), self.scene)
        for n in (2, 3, 4):
            r.change(self.d, "D1", "try %d" % n)
            _check_in(self.d, self.edit([1, 1, 1 + n / 10]))
            r.record(self.d, _round_answer(self.d, n, win=(n == 3)), self.scene)
            if r.state(self.d)["status"] != "running":
                break
        self.assertEqual({i["id"]: i for i in r.ledger(self.d)["items"]}["D1"]["status"], "open")

    def test_every_criterion_at_3_stops_and_active_time_skips_interruptions(self):
        r = self.r
        st = r.state(self.d)
        r.tick(st, st["last_step_at"] + 600)       # ten minutes of work
        r.tick(st, st["last_step_at"] + 5 * 3600)  # a usage limit: five hours that do not count
        self.assertAlmostEqual(st["active_seconds"], 600, delta=1)
        _check_in(self.d, self.doc)
        ans = _round_answer(self.d, 1, scores={k: 3 for k in tiers.CRITERIA})
        e = r.record(self.d, ans, self.scene)
        self.assertEqual(e["stop"], "every criterion at 3")
        self.assertEqual(st["limit_seconds"], 7200)  # the 2-hour safety stop on active time

    def test_the_medium_is_seeded_and_only_the_critics_word_files_an_ask_there(self):
        r = self.r
        led = r.ledger(self.d)
        self.assertEqual([(i["id"], i["status"]) for i in led["items"]],
                         [("L1", "known-limit"), ("L2", "known-limit"), ("L3", "known-limit")])
        _check_in(self.d, self.doc)
        e = r.record(self.d, _round_answer(self.d, 1, defects=[
            {"rank": 1, "severity": "major", "criterion": "depth", "parts": ["body"], "problem": "the far wheels show "
             "through the body", "fix": "hide them"},
            {"rank": 2, "severity": "minor", "criterion": "honesty", "parts": ["label"], "problem": "a label seen "
             "through the body anchors on the far side", "fix": "move the anchor"}],
            scores=dict({k: 3 for k in tiers.CRITERIA}, depth=2, honesty=2), limits={"1": "L1"}), self.scene)
        self.assertEqual(len(e["medium"]), 1)
        titles = [i["title"] for i in r.ledger(self.d)["items"] if not i.get("medium")]
        self.assertEqual(titles, ["a label seen through the body anchors on the far side"])  # words alone file nothing
        report = r.report(self.d)
        self.assertIn("Known limits (skill gaps): none", report)
        self.assertIn("The medium (what the renderer cannot do)", report)
        self.assertIn("Asks about the medium (not worked on): L1", (self.d / "rounds.md").read_text())

    def test_the_critics_wait_is_not_the_authors_time(self):
        r = self.r
        st = r.state(self.d)
        t0 = st["last_step_at"]
        (self.d / "work.txt").write_text("x")
        import os
        os.utime(self.d / "work.txt", (t0 + 300, t0 + 300))
        _check_in(self.d, self.doc)  # the author worked until the packet
        st = r.state(self.d)
        st["last_step_at"] = st["packet_at"] = t0 + 360
        r._save(self.d, "state.json", st)
        r.status(self.d, now=t0 + 3000)  # a status call while the critic works adds nothing
        self.assertEqual(r.state(self.d)["active_seconds"], st["active_seconds"])
        e = r.record(self.d, _round_answer(self.d, 1), self.scene, now=t0 + 3600)
        st = r.state(self.d)
        self.assertLess(st["active_seconds"], 1000)  # the hour waiting for the critic is not authoring
        self.assertIn("critic", r.summary(e))
        r.pause(self.d, now=t0 + 3700)
        r.status(self.d, now=t0 + 3700 + 9 * 60)  # time after a pause is an interruption
        self.assertLess(r.state(self.d)["active_seconds"], st["active_seconds"] + 120)

    def test_timeboxed_counts_the_critics_time_and_masterpiece_does_not(self):
        r = self.r
        _check_in(self.d, self.doc)
        st = r.state(self.d)
        st["active_seconds"], st["critic_seconds"] = 3000.0, 4500.0  # 50 minutes of authoring, 75 of the critic
        r._save(self.d, "state.json", st)
        self.assertIsNone(r.record(self.d, _round_answer(self.d, 1), self.scene)["stop"])  # masterpiece: as before
        with tempfile.TemporaryDirectory() as d:
            sc = Path(d, "s.json")
            sc.write_text(json.dumps(self.doc))
            st = r.start(str(sc), "timeboxed", d)
            self.assertEqual((st["max_rounds"], st["limit_seconds"]), (12, 7200))
            _check_in(d, self.doc)
            st = r.state(d)
            st["active_seconds"], st["critic_seconds"] = 3000.0, 4500.0
            r._save(d, "state.json", st)
            e = r.record(d, _round_answer(d, 1), sc)
            self.assertEqual(e["stop"], "the 120-minute ceiling on working time, the critic's included")
            self.assertIn("of 120 minutes in all", r.status(d))

    def test_each_round_logs_whether_a_finish_cap_would_stop_it(self):
        r = self.r
        _check_in(self.d, self.doc)
        r.record(self.d, _round_answer(self.d, 1), self.scene)  # D1: a major proportions item
        log = (self.d / "rounds.md").read_text()
        self.assertIn("Would a 4-round finish cap stop here? finish not started (D1 major proportions open)", log)
        for n in range(2, 7):
            _check_in(self.d, self.edit([1, 1, 1 + n / 10]))
            r.record(self.d, _round_answer(self.d, n, fixed=("D1",)), self.scene)
        log = (self.d / "rounds.md").read_text()
        self.assertIn("finish round 1 (finish from round 2): a 4-round finish cap would not stop yet", log)
        self.assertIn("finish round 4 (finish from round 2): a 4-round finish cap would stop here", log)
        self.assertIn("finish round 5 (finish from round 2): a 4-round finish cap would have stopped at round 5", log)
        self.assertEqual(r.state(self.d)["status"], "running")  # logged only

    def test_masterpiece_stops_at_12_rounds_and_unbounded_only_at_the_stop_rule(self):
        r = self.r
        self.assertEqual(r.state(self.d)["max_rounds"], 12)
        _check_in(self.d, self.doc)
        r.record(self.d, _round_answer(self.d, 1), self.scene)
        for n in range(2, 13):  # every round a win: only the cap ends it
            _check_in(self.d, self.edit([1, 1, 1 + n / 100]))
            e = r.record(self.d, _round_answer(self.d, n), self.scene)
        self.assertIn("the 12-round cap", e["stop"])
        with tempfile.TemporaryDirectory() as d:
            sc = Path(d, "s.json")
            sc.write_text(json.dumps(self.doc))
            st = r.start(str(sc), "unbounded", d)
            self.assertEqual((st["max_rounds"], st["limit_seconds"]), (None, None))
            st["active_seconds"] = 10 * 3600  # ten hours: no ceiling
            r._save(d, "state.json", st)
            _check_in(d, self.doc)
            r.record(d, _round_answer(d, 1), sc)
            for n in range(2, 15):
                _check_in(d, dict(self.doc, parts=[dict(self.doc["parts"][0], at=[0, 0, n / 100])]))
                e = r.record(d, _round_answer(d, n), sc)
            self.assertIsNone(e["stop"])  # 14 winning rounds, ten hours: still running
            self.assertIn("no time ceiling", r.status(d))
            for n in (15, 16):
                _check_in(d, dict(self.doc, parts=[dict(self.doc["parts"][0], at=[0, 0, n / 100])]))
                e = r.record(d, _round_answer(d, n, win=False), sc)
            self.assertIn("2 rounds in a row did not beat", e["stop"])
        for fast in ("fast", "standard", "showcase"):
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(r.RoundsError):
                    r.start(str(self.scene), fast, d)

    def test_answers_are_checked(self):
        r = self.r
        _check_in(self.d, self.doc)
        r.record(self.d, _round_answer(self.d, 1), self.scene)
        _check_in(self.d, self.edit([1, 1, 2]))
        ans = _round_answer(self.d, 2)
        del ans["pairwise"]
        with self.assertRaises(r.RoundsError):
            r.record(self.d, ans, self.scene)  # a later round must judge the pair
        ans = _round_answer(self.d, 2)
        ans["reconcile"]["items"] = ans["reconcile"]["items"][:1]
        with self.assertRaises(r.RoundsError):
            r.record(self.d, ans, self.scene)  # every ledger item is judged
        ans = _round_answer(self.d, 2)
        ans["critique"]["scores"]["depth"] = 2  # no depth defect cited
        with self.assertRaises(r.RoundsError):
            r.record(self.d, ans, self.scene)
        self.assertIn("Next: give the packet", r.status(self.d))


class Critic(unittest.TestCase):
    """The independent critic: its verdict follows its scores, and binds to the scene it judged."""

    def test_the_verdict_follows_the_scores_not_the_claim(self):
        s = base()
        self.assertEqual(critic.verdict(_critique(s)), "outstanding")
        self.assertEqual(critic.verdict(_critique(s, low=2)), "good")
        self.assertEqual(critic.verdict(_critique(s, severity="major")), "good")
        self.assertEqual(critic.verdict(_critique(s, low=2, severity="critical")), "improve")
        self.assertEqual(critic.verdict(_critique(s, present=False)), "improve")
        self.assertEqual(critic.verdict(_critique(s, low=1)), "improve")

    def test_recording_binds_to_the_scene_and_a_later_edit_is_stale(self):
        s = base(authoring={"tier": "showcase", "research": "not_needed",
                            "identity": [{"feature": "the box", "parts": ["body"]}]})
        orig = copy.deepcopy(s)
        new, v = critic.record(s, _critique(s, low=2))
        self.assertEqual((v, new["authoring"]["outcome"], new["authoring"]["critic"]["round"]), ("good", "good", 1))
        codes = {d["code"] for d in diagnose.diagnose(new)["diagnostics"]}
        self.assertFalse(codes & {"critic-stale", "self-graded", "critic-claim"}, codes)
        new["parts"][0]["shape"]["size"] = [2, 1, 1]
        self.assertIn("critic-stale", {d["code"] for d in diagnose.diagnose(new)["diagnostics"]})
        with self.assertRaises(critic.CriticError):
            critic.record(new, _critique(orig))  # judged another version

    def test_the_author_cannot_grade_itself(self):
        s = base(authoring={"tier": "standard", "research": "not_needed", "outcome": "good"})
        self.assertIn("self-graded", {d["code"] for d in diagnose.diagnose(s)["diagnostics"]})

    def test_identity_checklist_must_be_built(self):
        s = base(authoring={"tier": "showcase", "research": "not_needed",
                            "identity": [{"feature": "scissor doors", "parts": ["door-left"]}]})
        self.assertIn("identity-unbuilt", {d["code"] for d in diagnose.diagnose(s)["diagnostics"]})
        self.assertIn("no-checklist", {d["code"] for d in diagnose.diagnose(
            base(authoring={"tier": "masterpiece", "research": "not_needed"}))["diagnostics"]})

    def test_a_critique_is_checked_like_any_draft(self):
        r = diagnose.diagnose_text(json.dumps({"format": "construct-critique", "version": 1, "scene_sha256": "x",
                                               "scores": {}, "defects": [], "verdict": "great"}))
        self.assertFalse(r["ok"])
        self.assertTrue(critic.defects_text(_critique(base(), low=1, severity="critical")).count("taper the loft"))

    def test_masterpiece_runs_until_the_critic_says_outstanding(self):
        good = json.dumps(params.template("vessel", "can") | {"facts": [], "synthetic": True})
        doc = json.loads(good)
        rounds = [_critique(doc, low=1, severity="critical"), _critique(doc, low=2, severity="major"), _critique(doc)]
        calls = []
        saved = runner.chat, critic.packet, critic.run
        runner.chat = lambda *a, **k: (good, {"prompt_tokens": 100, "completion_tokens": 10})
        critic.packet = lambda *a, **k: {"scene_sha256": "x"}

        def fake_run(pk, out, base_url, model, key=None, log=None):
            calls.append(model)
            return rounds[len(calls) - 1], {"prompt_tokens": 50, "completion_tokens": 5}
        critic.run = fake_run
        try:
            with tempfile.TemporaryDirectory() as d:
                rep, text, _, _, meta = runner.author("a can", "http://stub", "author-model", tier="masterpiece",
                                                     workdir=d, checkpoints=str(Path(d, "cp")),
                                                     critic={"base_url": "http://stub", "model": "critic-model"})
                self.assertEqual(len(list(Path(d, "cp").glob("round-*.json"))), 3)
        finally:
            runner.chat, critic.packet, critic.run = saved
        a = json.loads(text)["authoring"]
        self.assertEqual((meta["outcome"], meta["reviews"], calls), ("outstanding", 3, ["critic-model"] * 3))
        self.assertEqual((a["tier"], a["outcome"], a["critic"]["verdict"]), ("masterpiece", "outstanding", "outstanding"))
        self.assertTrue(rep["ok"])
        self.assertNotIn("critic-stale", {d["code"] for d in rep["diagnostics"]})

    def test_masterpiece_has_a_round_cap_a_ceiling_and_a_user_stop_and_unbounded_has_neither(self):
        lim = tiers.limits("masterpiece")
        self.assertEqual((lim["wall_clock_s"], lim["review_rounds"]), (7200, 12))  # 2 hours active, 12 rounds
        self.assertEqual(tiers.limits("masterpiece", wall_clock_s=36000)["wall_clock_s"], 36000)
        lim = tiers.limits("unbounded")
        self.assertEqual((lim["wall_clock_s"], lim["review_rounds"], lim["mode"]), (None, None, "unbounded"))
        good = json.dumps(params.template("vessel", "can") | {"facts": [], "synthetic": True})
        saved = runner.chat, critic.packet, critic.run
        runner.chat = lambda *a, **k: (good, {})
        critic.packet = lambda *a, **k: {}

        def stop(*a, **k):
            raise KeyboardInterrupt
        critic.run = stop
        try:
            rep, text, _, _, meta = runner.author("a can", "http://stub", "m", tier="masterpiece")
        finally:
            runner.chat, critic.packet, critic.run = saved
        self.assertEqual((meta["outcome"], meta["stopped_by"]), ("limit", "the user"))
        self.assertTrue(rep["ok"])


def _budget_hook():
    import importlib.util
    spec = importlib.util.spec_from_file_location("construct_budget", HERE.parent / "hosts" / "claude-code" / "construct_budget.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class BudgetHook(unittest.TestCase):
    """The Claude Code hook that enforces a tier from outside the model."""

    def test_its_table_is_the_tiers(self):
        hook = _budget_hook()
        # the rounds modes count their rounds in `construct rounds`, not review commands
        self.assertEqual(hook.TIERS, {k: (v["wall_clock_s"], None if k in tiers.ROUNDS else v["review_rounds"])
                                      for k, v in tiers.TIERS.items()})
        self.assertEqual(hook.WRAP_UP, tiers.WRAP_UP)
        self.assertEqual(hook.limits({"CONSTRUCT_TIER": "fast"}), ("standard", 600, 2))
        self.assertEqual(hook.limits({"CONSTRUCT_TIER": "unbounded"}), ("unbounded", None, None))

    def test_review_rounds_wrap_up_and_wall_clock(self):
        hook = _budget_hook()
        with tempfile.TemporaryDirectory() as d:
            env = {"CONSTRUCT_TIER": "standard"}
            ev = {"session_id": "s1", "cwd": d}
            review = dict(ev, tool_name="Bash", tool_input={"command": "python3 runtime/cli.py review car.json --out out"})
            check = dict(ev, tool_name="Bash", tool_input={"command": "python3 runtime/cli.py check car.json"})
            edit = dict(ev, tool_name="Edit", tool_input={"file_path": "car.json"})
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
            code, out, _ = hook.handle("session-start", dict(ev, source="startup"), now=1000, env=env)
            self.assertIn("2 review rounds", out)
            for k in range(2):
                self.assertEqual(hook.handle("pre", review, now=1010 + k, env=env)[0], 0)
                hook.handle("post", review, now=1011 + k, env=env)
            code, _, err = hook.handle("pre", review, now=1100, env=env)
            self.assertEqual(code, 2)
            self.assertIn("review rounds", err)
            _, out, _ = hook.handle("post", edit, now=1000 + 490, env=env)
            self.assertIn("wrap-up", json.loads(out)["hookSpecificOutput"]["additionalContext"])
            self.assertEqual(hook.handle("post", edit, now=1000 + 500, env=env)[1], "")  # told once
            self.assertEqual(hook.handle("pre", edit, now=1000 + 601, env=env)[0], 2)
            self.assertEqual(hook.handle("pre", check, now=1000 + 601, env=env)[0], 0)  # deliver: still allowed
            self.assertEqual(hook.handle("pre", dict(ev, tool_name="Read"), now=1000 + 601, env=env)[0], 0)
            self.assertEqual(hook.limits({"CONSTRUCT_TIER": "showcase", "CONSTRUCT_MAX_REVIEWS": "3"})[1:], (1800, 3))

    def test_the_claude_code_package_ships_it_switched_off(self):
        from . import package
        with tempfile.TemporaryDirectory() as d:
            root = package.build(Path(d, "pkg"), hosts=("claude-code",))["claude-code"]
            self.assertTrue((root / "hosts" / "construct_budget.py").exists())
            self.assertFalse((root / "hooks").exists())  # installing the plugin never switches it on


class RunnerLimits(unittest.TestCase):
    """The author loop stops at whichever comes first: a "good" review or any limit (no endpoint, no browser)."""

    GOOD = json.dumps(params.template("vessel", "can") | {"facts": [], "synthetic": True})
    BAD = '{"format": "construct-params", "version": 1}'

    def run_author(self, answers, clock_step=0.0, captures=True, **kw):
        sent, now = [], [0.0]

        def fake_chat(base_url, model, messages, key=None, timeout=300, temperature=0.2):
            sent.append(messages[-1])
            now[0] += clock_step
            return answers[min(len(sent) - 1, len(answers) - 1)], {"prompt_tokens": 1000, "completion_tokens": 100}
        saved = runner.chat, runner._captures, runner.image_part
        runner.chat = fake_chat
        runner._captures = (lambda text, workdir, log: ["hero.png"]) if captures else (lambda *a: [])
        runner.image_part = lambda ref: {"type": "image_url", "image_url": {"url": ref}}
        try:
            out = runner.author("a can", "http://stub", "stub", clock=lambda: now[0], **kw)
        finally:
            runner.chat, runner._captures, runner.image_part = saved
        return out, sent

    def verdict(self, v, low=False, nxt=("trace the rim",)):
        scores = {k: 1 if low else 2 for k in ("silhouette", "proportions", "identity")}
        return json.dumps({"verdict": v, "scores": scores, "weakest": "proportions", "next": list(nxt)})

    def test_check_rounds_bound_a_model_that_never_gets_it_right(self):
        (report, text, _, history, meta), _ = self.run_author([self.BAD], tier="quick")
        self.assertEqual(len(history), 3)
        self.assertEqual((meta["outcome"], meta["stopped_by"]), ("limit", "check rounds (3)"))
        self.assertEqual(json.loads(text)["authoring"]["outcome"], "limit")

    def test_review_rounds_stop_and_record_the_next_improvements(self):
        (report, text, _, _, meta), sent = self.run_author(
            [self.GOOD, self.verdict("improve"), self.GOOD, self.verdict("improve"), self.GOOD], vision=True)
        self.assertEqual((meta["outcome"], meta["reviews"]), ("limit", 2))
        a = json.loads(text)["authoring"]
        self.assertEqual((a["tier"], a["outcome"], a["review_rounds"]), ("standard", "limit", 2))
        self.assertIn("trace the rim", a["next"])
        self.assertTrue(report["ok"])
        self.assertIn("weakest point (proportions)", sent[2]["content"])

    def test_a_good_verdict_ends_the_run_but_not_with_a_low_score(self):
        # the author's own review never records "good": that is an independent critic's verdict
        (_, _, _, _, meta), _ = self.run_author([self.GOOD, self.verdict("good")], vision=True)
        self.assertEqual((meta["outcome"], meta["reviews"]), ("self-reviewed", 1))
        (_, _, _, _, meta), _ = self.run_author([self.GOOD, self.verdict("good", low=True), self.GOOD,
                                                 self.verdict("good")], vision=True)
        self.assertEqual((meta["outcome"], meta["reviews"]), ("self-reviewed", 2))

    def test_the_wall_clock_and_cost_ceilings_deliver_the_best_so_far(self):
        (report, text, _, _, meta), _ = self.run_author([self.GOOD, self.verdict("improve"), self.BAD],
                                                       clock_step=250, vision=True)
        self.assertEqual(meta["outcome"], "limit")
        self.assertTrue(meta["stopped_by"].startswith("wall clock"))
        self.assertTrue(report["ok"])  # the clean draft, not the broken last answer
        (_, _, _, _, meta), _ = self.run_author([self.BAD], max_cost=0.002, prices=(1.0, 1.0))
        self.assertTrue(meta["stopped_by"].startswith("cost ceiling"))

    def test_every_new_best_valid_draft_is_saved_at_once(self):
        saved = []
        (_, _, _, _, meta), _ = self.run_author([self.BAD, self.GOOD, self.verdict("improve"), self.BAD, self.BAD,
                                                 self.BAD, self.BAD], vision=True, save=saved.append)
        self.assertEqual(meta["outcome"], "limit")  # the improvement never came back valid
        self.assertEqual(len(saved), 1)  # only the valid draft, never the broken ones
        doc = json.loads(saved[0])
        self.assertEqual((doc["variant"], doc["authoring"]["outcome"]), ("can", "unreviewed"))

    def test_review_stops_at_the_wrap_up_share(self):
        (_, _, _, _, meta), _ = self.run_author([self.GOOD], clock_step=490, vision=True)
        self.assertTrue(meta["stopped_by"].startswith("wrap-up"))
        self.assertEqual(meta["reviews"], 0)

    def test_without_vision_or_a_browser_it_is_unreviewed(self):
        (_, text, _, _, meta), _ = self.run_author([self.GOOD])
        self.assertEqual(meta["outcome"], "unreviewed")
        self.assertEqual(json.loads(text)["authoring"]["research"], "unavailable")
        (_, _, _, _, meta), _ = self.run_author([self.GOOD], vision=True, captures=False)
        self.assertEqual(meta["outcome"], "unreviewed")

    def test_research_counters_and_overrides(self):
        with self.assertRaises(runner.RunnerError):
            self.run_author([self.GOOD], tier="quick", images=["https://example.org/ref.jpg"])
        with self.assertRaises(runner.RunnerError):
            self.run_author([self.GOOD], research="off", images=["https://example.org/ref.jpg"])
        (_, text, _, _, _), sent = self.run_author([self.GOOD], research="off")
        self.assertEqual(json.loads(text)["authoring"]["research"], "off")


class ShapeEvidence(unittest.TestCase):
    """A spec page verifies dimensions, not an outline (seen in live runs: an invented guitar body marked verified)."""

    def scene_with(self, kind, certainty="verified"):
        s = base()
        s["sources"].append({"id": "src", "kind": kind, "title": "a synthetic source", "rights": "reference_only"})
        s["facts"].append({"key": "body.length", "value": 0.45, "unit": "m", "certainty": "verified", "source": "src"})
        s["parts"].append({"id": "outline", "role": "identity", "certainty": certainty, "stage": 1, "basis": ["body.length"],
                           "shape": {"type": "extrude", "axis": "z", "height": 0.04,
                                     "profile": [[0, 1], [0.2, 1.1], [0.3, 1.3], [0.2, 1.5], [0, 1.4], [-0.2, 1.3], [-0.1, 1.1]]},
                           "at": [0, -0.5, 0.5]})
        return s

    def codes(self, s):
        return {d["code"] for d in diagnose.diagnose(s)["diagnostics"]}

    def test_a_verified_outline_from_a_spec_page_is_flagged(self):
        r = diagnose.diagnose(self.scene_with("document"))
        self.assertIn("shape-overclaim", {d["code"] for d in r["diagnostics"]})
        self.assertTrue(r["needs_repair"])

    def test_drawings_measurements_and_datasets_can_verify_shapes(self):
        for kind in ("drawing", "measurement", "dataset"):
            self.assertNotIn("shape-overclaim", self.codes(self.scene_with(kind)), kind)

    def test_an_inferred_or_traced_outline_is_fine(self):
        self.assertNotIn("shape-overclaim", self.codes(self.scene_with("document", "inferred")))
        self.assertNotIn("shape-overclaim", self.codes(self.scene_with("reference_image", "inferred")))


class TwoAxes(unittest.TestCase):
    """A part's size and shape answered apart: a verified length with a traced or designed outline."""

    codes = ShapeEvidence.codes

    def scene_with(self, kind, certainty):
        s = ShapeEvidence.scene_with(self, kind, certainty)
        s["parts"][-1]["source"] = "src"   # the drawing, image or page it was made from
        return s

    def test_a_verified_size_with_a_traced_shape(self):
        s = self.scene_with("drawing", {"size": "verified", "shape": "traced"})
        self.assertEqual(scene.validate(s), [])
        self.assertNotIn("shape-overclaim", self.codes(s))
        out = next(p for p in scene.compile_scene(s)["parts"] if p["id"] == "outline")
        self.assertEqual(out["certainty"], "traced")   # the weaker axis, for readers of one word
        self.assertEqual(out["certainty_axes"], {"size": "verified", "shape": "traced"})
        self.assertNotIn("certainty_axes", scene.compile_scene(base())["parts"][0])

    def test_a_verified_shape_still_needs_shape_evidence(self):
        self.assertIn("shape-overclaim", self.codes(self.scene_with("document", {"size": "inferred", "shape": "verified"})))
        self.assertNotIn("shape-overclaim", self.codes(self.scene_with("document", {"size": "verified", "shape": "inferred"})))

    def test_traced_cites_the_drawing_or_image_it_was_traced_on(self):
        self.assertEqual(scene.validate(self.scene_with("reference_image", "traced")), [])
        errs = scene.validate(self.scene_with("document", {"size": "verified", "shape": "traced"}))
        self.assertTrue(any("traced part needs" in e for e in errs), errs)

    def test_malformed_axes_are_refused(self):
        for bad in ({"size": "verified"}, {"size": "verified", "shape": "decorative"},
                    {"size": "verified", "shape": "guessed"}, {"size": "verified", "shape": "inferred", "colour": "x"}):
            self.assertTrue(scene.validate(self.scene_with("drawing", bad)), bad)

    def test_the_size_axis_cannot_overclaim_its_basis(self):
        s = self.scene_with("drawing", {"size": "verified", "shape": "inferred"})
        s["facts"][-1]["certainty"] = "inferred"
        del s["parts"][-1]["source"]
        self.assertTrue(scene.validate(s))   # a verified size needs a source or a verified basis fact

    def test_provenance_classes(self):
        cls = lambda c: scene.provenance_class({"certainty": c})
        self.assertEqual(cls("verified"), "verified")
        self.assertEqual(cls({"size": "verified", "shape": "verified"}), "verified")
        self.assertEqual(cls({"size": "verified", "shape": "traced"}), "size_verified")
        self.assertEqual(cls({"size": "inferred", "shape": "verified"}), "shape_verified")
        self.assertEqual(cls({"size": "traced", "shape": "inferred"}), "inferred")



class Shades(unittest.TestCase):
    """How firmly a guess is held to the real thing: what it cites, and a comparison that passed."""

    def scene(self):
        s = base()
        s["sources"] += [{"id": "doc", "kind": "document", "title": "a page", "rights": "reference_only"},
                         {"id": "photo", "kind": "reference_image", "title": "a photo", "rights": "reference_only"},
                         {"id": "plan", "kind": "drawing", "title": "a plan", "rights": "reference_only"}]
        s["facts"].append({"key": "len", "value": 2.0, "unit": "m", "certainty": "verified", "source": "doc"})
        box = {"type": "box", "size": [0.2, 0.2, 0.2], "anchor": "base"}
        for i, extra in enumerate([{}, {"source": "doc"}, {"source": "photo"}, {"source": "photo", "basis": ["len"]},
                                   {"source": "plan", "certainty": "traced"}, {"certainty": "verified", "source": "doc"}]):
            p = {"id": "p%d" % i, "role": "detail", "certainty": "inferred", "stage": 1, "shape": box, "at": [i * 0.3, 1, 0]}
            p.update(extra)
            s["parts"].append(p)
        return s

    def levels(self, s):
        return {p["id"]: p.get("evidence") for p in scene.compile_scene(s)["parts"] if p["id"].startswith("p")}

    def test_levels_from_what_a_part_cites(self):
        self.assertEqual(self.levels(self.scene()), {"p0": 1, "p1": 2, "p2": 3, "p3": 4, "p4": 1, "p5": None})

    def test_a_designed_part_names_the_requirement_it_realises_and_stays_designed(self):
        # a new design's parts are designed, but some are what the user asked for ("two seats") or what a document
        # says it does ("a 64-slot modulation matrix"): they cite it, and stay designed
        s = base(subject={"category": "machine", "accuracy": "original", "synthetic": True})
        s["sources"].append({"id": "manual", "kind": "document", "title": "the synth's manual", "rights": "reference_only"})
        s["facts"] += [{"key": "seats", "value": 2, "certainty": "user_supplied", "source": "req", "requirement": True},
                       {"key": "mod.slots", "value": 64, "certainty": "verified", "source": "manual", "requirement": True},
                       {"key": "width", "value": 0.4, "unit": "m", "certainty": "inferred"}]
        box = {"type": "box", "size": [0.2, 0.2, 0.2], "anchor": "base"}
        for i, basis in enumerate([["seats"], ["mod.slots"], [], ["seats", "width"]]):
            s["parts"].append({"id": "p%d" % i, "role": "detail", "certainty": "inferred", "stage": 1, "shape": box,
                               "at": [i * 0.3 - 0.45, 1, 0], "basis": basis})
        self.assertEqual(scene.validate(s), [])
        g = scene.compile_scene(s)
        self.assertEqual(self.levels(s), {"p0": 1, "p1": 1, "p2": 1, "p3": 2})   # a requirement describes no shape
        self.assertEqual(g["subject"]["accuracy"], "original")
        self.assertTrue(next(f for f in g["provenance"]["facts"] if f["key"] == "seats")["requirement"])
        rep = audit.audit(s, g)
        self.assertEqual(rep["info"]["designed_parts"], {"to_a_requirement": 2, "free": 2})   # body and p2 are free
        self.assertEqual(rep["info"]["requirements_met"], ["mod.slots", "seats"])
        self.assertIn("designed parts: 2 to a requirement (mod.slots, seats), 2 designed freely", audit.format_report(rep))
        self.assertEqual([w for w in rep["warnings"] if w["code"] == "requirement-unmet"], [])
        s["parts"] = s["parts"][:1]                                            # the body alone
        rep = audit.audit(s, scene.compile_scene(s))
        self.assertIn("mod.slots, seats", next(w for w in rep["warnings"] if w["code"] == "requirement-unmet")["message"])
        for bad, says in ((dict(s["facts"][1], requirement="yes"), "true or false"),
                          ({k: v for k, v in s["facts"][1].items() if k != "source"}, "requirement cites where")):
            t = dict(s, facts=[s["facts"][0], bad])
            self.assertTrue(any(says in e for e in scene.validate(t)), (bad, scene.validate(t)))
        js = (HERE / "viewer" / "hologram.js").read_text()
        self.assertIn('original: "ORIGINAL DESIGN"', js)                   # not "APPROXIMATE RECONSTRUCTION"
        self.assertIn('"DESIGNED · TO A REQUIREMENT"', js)

    def test_a_passing_comparison_checks_its_reference_on_this_version_only(self):
        s = self.scene()
        record = {"view": "top", "reference": "plan", "iou": 0.9, "edge": 0.01, "pass": True}
        s["authoring"] = {"tier": "standard", "research": "off", "compare": [dict(record, scene_sha256=tiers.critic_hash(s))]}
        g = scene.compile_scene(s)
        self.assertEqual(next(p for p in g["parts"] if p["id"] == "p4")["evidence"], 2)
        self.assertEqual(g["provenance"]["checked"], [{"reference": "plan", "view": "top", "iou": 0.9}])
        s["authoring"]["compare"][0]["scene_sha256"] = "0" * 64   # made on another version
        g = scene.compile_scene(s)
        self.assertEqual(next(p for p in g["parts"] if p["id"] == "p4")["evidence"], 1)
        self.assertNotIn("checked", g["provenance"])


    def test_a_provenance_note_is_carried_for_the_provenance_view(self):
        s = self.scene()
        s["authoring"] = {"tier": "standard", "research": "off", "provenance_note": "Made before 1.1."}
        self.assertEqual(scene.validate(s), [])
        self.assertEqual(scene.compile_scene(s)["provenance"]["authoring"]["provenance_note"], "Made before 1.1.")
        s["authoring"]["provenance_note"] = "x" * 401
        self.assertTrue(scene.validate(s))


def body_trace():
    """A synthetic traced guitar-like outline in pixels (y down): 600 px tall, nut and bridge marked."""
    import math as m
    pts = []
    for i in range(60):
        a = 2 * m.pi * i / 60
        r = 200 + 40 * m.cos(2 * a)  # a waisted body
        pts.append([round(500 + r * m.sin(a), 1), round(1300 - (300 + 300 * m.cos(a)), 1)])
    return {"format": "construct-trace", "version": 1,
            "reference": {"id": "ref-front", "title": "Synthetic test image", "ref": "user photo",
                          "rights": "user_private", "view": "front"},
            "image": {"width": 1000, "height": 1400},
            "outline": pts, "features": {"bridge": [500, 1150], "nut": [500, 150]}}


class Tracing(unittest.TestCase):
    """Shapes measured from a reference image, fitted to a documented dimension."""

    def test_fit_scales_flips_and_cites(self):
        from . import trace
        r = trace.fit(body_trace(), "nut:bridge=0.648", points=64)
        nut, bridge = r["features"]["nut"], r["features"]["bridge"]
        self.assertAlmostEqual(math.dist(nut, bridge), 0.648, places=4)
        self.assertGreater(nut[1], bridge[1])                      # y is up now: the nut is above the bridge
        self.assertEqual(len(r["profile"]), 60)                   # the measured points are kept
        self.assertAlmostEqual(min(p[1] for p in r["profile"]), 0.0, places=3)   # bottom-centre origin
        self.assertEqual(r["source"]["kind"], "reference_image")
        self.assertEqual(r["part"]["certainty"], "inferred")
        s = base()
        s["sources"].append(r["source"])
        s["parts"].append(dict(r["part"], id="body", role="mass", stage=0,
                               shape={"type": "extrude", "axis": "z", "height": 0.04, "profile": r["profile"]},
                               at=[0, 0, -0.02]))
        s["parts"] = s["parts"][1:]
        self.assertTrue(diagnose.diagnose(s)["ok"], diagnose.diagnose(s)["repair_text"])

    def test_bad_traces_come_back_with_paths(self):
        bad = body_trace()
        bad["outline"] = bad["outline"][:5]
        r = diagnose.diagnose_text(json.dumps(bad))
        self.assertIn("$.outline", {d["path"] for d in r["diagnostics"]})
        loop = body_trace()
        loop["outline"][10], loop["outline"][40] = loop["outline"][40], loop["outline"][10]
        r = diagnose.diagnose_text(json.dumps(loop))
        self.assertTrue(any("crosses itself" in d["message"] for d in r["diagnostics"]))

    def test_cli_trace(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "t.json").write_text(json.dumps(body_trace()))
            r = subprocess.run([sys.executable, "-I", str(HERE / "cli.py"), "trace", "t.json", "--fit", "height=0.45",
                                "--out", "body.json"], cwd=d, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertAlmostEqual(json.loads(Path(d, "body.json").read_text())["size_m"][1], 0.45, places=3)

    def test_trace_image_sends_the_image_and_fits(self):
        import http.server
        import threading
        seen = []

        class Stub(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                seen.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                out = json.dumps({"choices": [{"message": {"content": json.dumps(body_trace())}}]}).encode()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(out)

            def log_message(self, *a):
                pass
        srv = http.server.HTTPServer(("127.0.0.1", 0), Stub)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as d:
                Path(d, "photo.png").write_bytes(png.book_cover(16, 24))
                r = subprocess.run([sys.executable, "-I", str(HERE / "cli.py"), "trace-image", "photo.png",
                                    "--what", "the guitar body outline, front view", "--features", "nut,bridge",
                                    "--fit", "nut:bridge=0.648", "--base-url", "http://127.0.0.1:%d/v1" % srv.server_port,
                                    "--model", "stub", "--out", "body.json"], cwd=d, capture_output=True, text=True, timeout=60)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual(json.loads(Path(d, "body.json").read_text())["part"]["certainty"], "inferred")
        finally:
            srv.shutdown()
        parts = seen[0]["messages"][1]["content"]
        self.assertTrue(parts[1]["image_url"]["url"].startswith("data:image/png;base64,"))
        self.assertIn("construct-trace", parts[0]["text"])


def synthetic_dem(folder, n=81, cell=40.0):
    """A synthetic LV95 elevation grid: one peak at 45.9763 N, 7.6586 E (no real data)."""
    from . import terrain
    cx, cy = terrain.wgs84_to_lv95(45.9763, 7.6586)
    x0, y0 = cx - cell * (n // 2), cy - cell * (n // 2)
    rows = [" ".join("%.1f" % (2500 + 1900 * math.exp(-(((x0 + c * cell - cx) ** 2 + (y0 + (n - 1 - r) * cell - cy) ** 2)
                                                         / (2 * 900.0 ** 2)))) for c in range(n)) for r in range(n)]
    path = Path(folder, "dem.asc")
    path.write_text("ncols %d\nnrows %d\nxllcenter %f\nyllcenter %f\ncellsize %f\nNODATA_value -9999\n" % (n, n, x0, y0, cell)
                    + "\n".join(rows) + "\n")
    gpx = Path(folder, "route.gpx")
    gpx.write_text("<gpx><trk><trkseg>" + "".join('<trkpt lat="%f" lon="%f"></trkpt>' % (45.9763 + 0.008 * (1 - k / 20), 7.6586 + 0.008 * (1 - k / 20))
                                                for k in range(21)) + "</trkseg></trk></gpx>")
    return path, gpx


class Terrain(unittest.TestCase):

    def test_a_metric_grid_near_the_origin_is_not_taken_for_degrees(self):
        # found by feeding it a 10 m grid at (0, 0): it came out 2192 km wide, its metres read as degrees
        self.assertEqual(terrain.guess_crs(8.5, 46.9, 0.00028), "EPSG:4326")      # an arc-second grid in degrees
        with self.assertRaisesRegex(terrain.TerrainError, "--crs"):
            terrain.guess_crs(5.0, 5.0, 10.0)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "g.asc")
            p.write_text("ncols 2\nnrows 2\nxllcorner 0\nyllcorner 0\ncellsize 10\n1 nan\n3 4\n", encoding="utf-8")
            self.assertIsNone(terrain.read_asc(p).z[0][1])                          # not a number: no data
            p.write_text("ncols -3\nnrows 2\ncellsize 0\n1 2 3\n", encoding="utf-8")
            with self.assertRaisesRegex(terrain.TerrainError, "at least 2"):
                terrain.read_asc(p)
    def test_reference_systems(self):
        from . import terrain
        e, n = terrain.wgs84_to_lv95(46 + 2 / 60 + 38.87 / 3600, 8 + 43 / 60 + 49.79 / 3600)  # swisstopo's worked example
        self.assertAlmostEqual(e, 2699999.76, delta=1.0)
        self.assertAlmostEqual(n, 1099999.97, delta=1.0)
        self.assertEqual([round(v, 3) for v in terrain.wgs84_to_utm(0.0, 3.0, 31)], [500000.0, 0.0])

    def test_ridges_of_a_four_sided_pyramid(self):
        # a pyramid whose crests run NE, SE, SW and NW from the top (rows north to south)
        n = 61
        real = [[4000 - 30 * max(abs(r - 30), abs(c - 30)) - 8 * min(abs(r - 30), abs(c - 30)) for c in range(n)]
                for r in range(n)]
        found = terrain.ridges(real)
        bearings = sorted(round(math.degrees(math.atan2(p[-1][1] - p[0][1], -(p[-1][0] - p[0][0]))) % 360) for p in found)
        self.assertEqual(len(found), 4)
        for b, want in zip(bearings, (45, 135, 225, 315)):
            self.assertLess(abs(b - want), 8, bearings)

    def test_the_output_stays_inside_the_budget_at_any_resolution(self):
        # seen in a live run: a 4.4 x 3.8 km area at resolution 128 compiled to 27,940 triangles
        n, cell, x0, y0 = 240, 20.0, 2615000.0, 1090000.0
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, "dem.xyz")
            path.write_text("X Y Z\n" + "".join("%.0f %.0f %.1f\n" % (x0 + c * cell, y0 + r * cell,
                                                                        3000 + 900 * math.sin(r / 17) * math.cos(c / 23))
                                                for r in range(n) for c in range(n)))
            sc = terrain.build(str(path), bbox=(x0 + 100, y0 + 300, x0 + 4500, y0 + 4100), resolution=128,
                               source_title="Synthetic test grid")
        geo = scene.compile_scene(sc)
        self.assertLessEqual(geo["counts"]["triangles"], 24000)
        self.assertTrue(diagnose.diagnose(sc)["ok"])

    def test_measured_terrain_with_a_route_and_a_summit(self):
        from . import terrain
        with tempfile.TemporaryDirectory() as d:
            dem, gpx = synthetic_dem(d)
            sc = terrain.build(str(dem), center=(45.9763, 7.6586), extent=2400, title="Synthetic peak",
                               source_title="Synthetic test grid", gpx=str(gpx), marks=["Summit=45.9763,7.6586"], view_from="NE")
        r = diagnose.diagnose(sc)
        self.assertTrue(r["ok"] and not r["warnings"], r["repair_text"])
        facts = {f["key"]: f["value"] for f in sc["facts"]}
        self.assertEqual(facts["terrain.class"], "valley")
        self.assertAlmostEqual(facts["elevation.max"], 4400, delta=5)
        top = max(max(row) for row in sc["parts"][0]["shape"]["heights"])
        summit = [p for p in sc["parts"] if p["id"] == "mark-1"][0]["at"]
        self.assertAlmostEqual(summit[1], top, delta=0.05)              # the marker sits on the measured top
        self.assertEqual(sc["presentation"]["framing"]["yaw"], 135)
        self.assertEqual(sc["parts"][0]["certainty"], "verified")

    def test_sketched_relief_is_not_verified_by_a_document(self):
        s = base()
        s["sources"].append({"id": "doc", "kind": "document", "title": "a guidebook", "rights": "reference_only"})
        s["parts"] = [{"id": "relief", "role": "mass", "certainty": "verified", "source": "doc", "stage": 0,
                       "shape": {"type": "terrain", "size": [2, 2], "heights": [[0.1, 0.3, 0.2], [0.2, 0.6, 0.3], [0.1, 0.2, 0.1]]}}]
        self.assertIn("shape-overclaim", {d["code"] for d in diagnose.diagnose(s)["diagnostics"]})

    def test_cli_terrain_and_the_area_must_be_inside_the_data(self):
        with tempfile.TemporaryDirectory() as d:
            synthetic_dem(d)
            cli = [sys.executable, "-I", str(HERE / "cli.py"), "terrain", "--dem", "dem.asc", "--center", "45.9763,7.6586",
                   "--source-title", "Synthetic test grid", "--output", "t.json"]
            r = subprocess.run(cli + ["--extent", "2000"], cwd=d, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("measured terrain", r.stdout)
            r = subprocess.run(cli + ["--extent", "90000", "--force"], cwd=d, capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("beyond the elevation data", r.stderr)





class Vehicles(unittest.TestCase):
    """The loft shape and the vehicle archetype (cars came out boxy from every model before)."""

    def test_loft_sections_are_checked(self):
        bad = base(parts=[{"id": "hull", "role": "mass", "certainty": "inferred", "stage": 0,
                           "shape": {"type": "loft", "sections": [[1, 0.5, 0, 1], [0, 0.5, 0, 1]]}}])
        self.assertIn("rule", {d["code"] for d in diagnose.diagnose(bad)["diagnostics"]})
        good = base(parts=[{"id": "hull", "role": "mass", "certainty": "inferred", "stage": 0,
                            "shape": {"type": "loft", "sections": [[-1, 0.3, 0, 0.4], [0, 0.5, 0, 0.6, 0.4], [1, 0.2, 0.1, 0.3]]}}])
        r = diagnose.diagnose(good)
        self.assertTrue(r["ok"], r["repair_text"])

    def test_a_body_of_thin_tubes_is_warned(self):
        car = params.expand(params.template("vehicle", "coupe") | {"facts": [], "synthetic": True})
        self.assertNotIn("tube-outline", {d["code"] for d in diagnose.diagnose(car)["diagnostics"]})
        for k in range(6):
            car["parts"].append({"id": "outline-%d" % k, "role": "structure", "certainty": "inferred", "stage": 2,
                                 "shape": {"type": "tube", "radius": 0.012,
                                           "path": [[0.8 - 0.3 * k, 0.4, -2.0], [0.8 - 0.3 * k, 1.0, 0.0], [0.8 - 0.3 * k, 0.6, 2.0]]}})
        self.assertIn("tube-outline", {d["code"] for d in diagnose.diagnose(car)["diagnostics"]})
        # a body built of surfaces (the T1's 47 panels) keeps its real rails and rods: its drip rail, its bumpers
        for k in range(6):
            car["parts"].append({"id": "panel-%d" % k, "role": "mass", "certainty": "inferred", "stage": 1,
                                 "shape": {"type": "box", "size": [0.4, 0.4, 0.02], "anchor": "base"},
                                 "at": [0.8 - 0.3 * k, 0.6, 2.0]})
        self.assertNotIn("tube-outline", {d["code"] for d in diagnose.diagnose(car)["diagnostics"]})

    def test_a_main_surface_without_lines_is_warned(self):
        def codes(look, role="mass", size=(2, 1, 1)):
            sc = base(parts=[{"id": "body", "role": role, "certainty": "inferred", "stage": 0, "look": look,
                              "shape": {"type": "box", "size": list(size), "anchor": "base"}},
                             {"id": "badge", "role": "identity", "certainty": "inferred", "stage": 1,
                              "shape": {"type": "box", "size": [0.3, 0.3, 0.05], "anchor": "base"}, "at": [0, 1, 0.5]}])
            return {d["code"] for d in diagnose.diagnose(sc)["diagnostics"]}
        self.assertIn("bare-surface", codes({"fill": "dark", "line": "none"}))  # cardboard
        self.assertNotIn("bare-surface", codes({"fill": "dark", "weight": 0.45, "alpha": 0.55}))  # a faint contour
        self.assertNotIn("bare-surface", codes({"fill": "dark", "line": "none"}, role="structure"))  # a backing
        for name in ("porsche-911-964", "leica-m3", "open-reel", "sea-cliff", "juggernaut-et7", "sagrada-familia"):
            sc = json.loads((EXAMPLES / (name + ".json")).read_text())
            self.assertNotIn("bare-surface", {d["code"] for d in diagnose.diagnose(sc)["diagnostics"]}, name)

    def test_a_seed_makes_a_new_plausible_variant_the_same_every_time(self):
        base = params.template("vehicle", "coupe")
        one, again, other = params.vary(base, 7), params.vary(base, 7), params.vary(base, 8)
        self.assertEqual(one, again)
        self.assertNotEqual(one["params"], other["params"])
        self.assertTrue(one["synthetic"])
        self.assertEqual(one["title"], "A coupe (seed 7)")
        std = params.VARIANTS["vehicle"]["coupe"][1]
        for k, v in one["params"].items():
            self.assertLess(abs(v / std[k] - 1), 0.13, k)
        self.assertAlmostEqual(one["params"]["wheelbase"] / one["params"]["length"], std["wheelbase"] / std["length"], delta=0.02)
        self.assertEqual(scene.validate(params.expand(one)), [])
        guitar = params.vary(params.template("object", "electric-guitar"), 3)
        self.assertIn(guitar["params"]["body_style"], params.CHOICES["body_style"])
        self.assertEqual(scene.validate(params.expand(guitar)), [])

    def test_every_variant_is_a_car_not_a_box(self):
        for var in params.VARIANTS["vehicle"]:
            doc = params.template("vehicle", var) | {"facts": [], "synthetic": True}
            r = diagnose.diagnose_params(doc, [])
            self.assertTrue(r["ok"] and not r["warnings"], (var, r["repair_text"]))
            sc = params.expand(doc)
            body = next(p for p in sc["parts"] if p["id"] == "body")["shape"]["sections"]
            widest = max(sec[1] for sec in body)
            self.assertLess(body[-1][1], 0.8 * widest, var)   # the nose is narrower than the cabin
            self.assertLess(body[-1][3], 0.85 * max(sec[3] for sec in body), var)  # and lower
            self.assertTrue(all(sec[4] < sec[1] for sec in body), var)  # the sides lean in
            geo = scene.compile_scene(sc)
            tyres = [p for p in geo["parts"] if p["id"].startswith("tyre-")]
            self.assertAlmostEqual(min(i["min"][1] for p in tyres for i in p["instances"]), 0.0, places=3)  # on the ground



def _trace(view, outline, rid=None):
    return {"format": "construct-trace", "version": 1,
            "reference": {"id": rid or "ref-" + view, "title": "Synthetic %s view (test)" % view, "view": view},
            "image": {"width": 2000, "height": 2000}, "outline": [[round(x, 3), round(y, 3)] for x, y in outline]}


def _rect(w, h, n=8):
    pts = [(w * k / n, 0) for k in range(n)] + [(w, h * k / n) for k in range(n)]
    pts += [(w - w * k / n, h) for k in range(n)] + [(0, h - h * k / n) for k in range(n)]
    return [(100 + x, 100 + y) for x, y in pts]


class Likeness(unittest.TestCase):
    """construct compare and loft-from-traces: likeness measured, not only seen."""

    def box(self, w, h, d=1.0):
        return base(parts=[{"id": "body", "role": "mass", "certainty": "inferred", "stage": 0,
                            "shape": {"type": "box", "size": [d, h, w], "anchor": "base"}}])

    def test_the_same_silhouette_passes_and_a_wrong_one_does_not(self):
        same, _ = compare_mod.compare(self.box(4, 1), _trace("side", _rect(800, 200)), "side")
        self.assertGreater(same["iou"], 0.97)
        self.assertLess(same["edge"], 0.005)
        self.assertTrue(same["pass"])
        tall, _ = compare_mod.compare(self.box(4, 1.5), _trace("side", _rect(800, 200)), "side")
        self.assertLess(tall["iou"], 0.8)
        self.assertFalse(tall["pass"])

    def test_a_reference_facing_the_other_way_is_mirrored(self):
        s = base(parts=[{"id": "wedge", "role": "mass", "certainty": "inferred", "stage": 0, "shape": {
            "type": "extrude", "axis": "x", "height": 1.0, "profile": [[-2, 0], [2, 0], [2, 1.2], [-2, 0.3]]}, "at": [-0.5, 0, 0]}])
        # seen from the side (+X) the scene's +Z is on the left: this trace has the tall end on the right
        pts = [(0, 300), (800, 300), (800, 60), (0, 240)]
        out = []
        for i in range(4):
            a, b = pts[i], pts[(i + 1) % 4]
            out += [(a[0] + (b[0] - a[0]) * k / 4, a[1] + (b[1] - a[1]) * k / 4) for k in range(4)]
        res, png_bytes = compare_mod.compare(s, _trace("side", out), "side")
        self.assertGreater(res["iou"], 0.95)
        self.assertTrue(png_bytes.startswith(b"\x89PNG"))

    def test_recording_cites_the_reference_and_outstanding_needs_a_pass(self):
        car = params.expand(params.template("vehicle", "wedge") | {"facts": [], "synthetic": True})
        res, _ = compare_mod.compare(car, _trace("side", _rect(800, 200)), "side")
        rec = compare_mod.record(car, res, _trace("side", _rect(800, 200)))
        self.assertIn("ref-side", {s["id"] for s in rec["sources"]})
        self.assertEqual(rec["authoring"]["compare"][0]["pass"], False)
        self.assertNotIn("compare-stale", {d["code"] for d in diagnose.diagnose(rec)["diagnostics"]})
        new, v = critic.record(rec, _critique(rec))
        self.assertEqual(v, "good")  # every score 3, but the silhouette does not match yet

    def test_ornament_is_not_silhouette(self):
        # seen live: a shadow ring made a car's plan 2.4 m wide
        car = params.expand(params.template("vehicle", "wedge") | {"facts": [], "synthetic": True})
        ringed = json.loads(json.dumps(car))
        n = 40
        ringed["parts"].append({"id": "ground-shadow", "role": "ornament", "certainty": "decorative", "stage": 0,
                                "shape": {"type": "curve", "closed": True, "points": [
                                    [round(1.2 * math.cos(2 * math.pi * k / n), 4), 0.003,
                                     round(2.0 * math.sin(2 * math.pi * k / n), 4)] for k in range(n)]}})
        trace = _trace("top", _rect(300, 800))
        with_ring, _ = compare_mod.compare(ringed, trace, "top")
        without, _ = compare_mod.compare(car, trace, "top")
        self.assertEqual((with_ring["iou"], with_ring["edge"]), (without["iou"], without["edge"]))

    def test_a_tyre_is_solid_in_a_silhouette(self):
        # seen live: tyres drawn as wire rings left holes, and every car's side IoU fell (0.10 on a cut car)
        tyre = base(parts=[{"id": "tyre-front", "role": "structure", "certainty": "inferred", "stage": 0,
                            "shape": {"type": "torus", "major": 0.26, "minor": 0.07}, "rotate": [0, 0, 90]}])
        disc = [(400 + 300 * math.cos(2 * math.pi * k / 48), 400 + 300 * math.sin(2 * math.pi * k / 48)) for k in range(48)]
        res, _ = compare_mod.compare(tyre, _trace("side", disc), "side")
        self.assertGreater(res["iou"], 0.9, res)

    def test_a_plan_drawn_any_way_round_is_found_and_said(self):
        # seen live: a nose-right plan compared against a nose-up projection scored IoU 0.31, silently
        car = params.expand(params.template("vehicle", "wedge") | {"facts": [], "synthetic": True})
        up, _ = compare_mod.compare(car, _trace("top", _rect(300, 800)), "top")
        across, _ = compare_mod.compare(car, _trace("top", _rect(800, 300)), "top")
        self.assertAlmostEqual(across["iou"], up["iou"], delta=0.01)
        self.assertTrue(across["mirrored"].startswith("t"), across["orientation"])  # turned a quarter (a rectangle ties)
        self.assertTrue(any("drawn across" in w for w in across["warnings"]))
        self.assertFalse(up["warnings"])

    def test_stations_from_three_views(self):
        side = [(0, 230), (250, 200), (380, 130), (520, 80), (640, 85), (760, 120), (930, 140), (1000, 150),
                (1000, 250), (980, 285), (500, 285), (0, 285)]
        side = [(x + 50, y) for x, y in side]
        side = [p for i in range(len(side)) for p in [side[i], ((side[i][0] + side[(i + 1) % len(side)][0]) / 2,
                                                               (side[i][1] + side[(i + 1) % len(side)][1]) / 2)]]
        half = [(300 + 240 * (1 - (1 - k / 30) ** 6) ** 0.5, 50 + 1000 * k / 30) for k in range(31)]
        top = half + [(600 - x, y) for x, y in reversed(half)]
        front = [(40, 300), (560, 300), (570, 220), (520, 170), (430, 120), (170, 120), (80, 170), (30, 220)]
        front = [p for i in range(8) for p in [front[i], ((front[i][0] + front[(i + 1) % 8][0]) / 2,
                                                         (front[i][1] + front[(i + 1) % 8][1]) / 2)]]
        res = trace_mod.stations(_trace("side", side), _trace("top", top), 4.14, _trace("front", front),
                                 nose_side="left", nose_top="up")
        secs = res["loft"]["sections"]
        self.assertGreaterEqual(len(secs), 20)
        self.assertEqual([s_[0] for s_ in secs], sorted(s_[0] for s_ in secs))
        self.assertLess(secs[-1][1], 0.6 * max(s_[1] for s_ in secs))       # the nose narrows in plan
        cabin = max(secs, key=lambda s_: s_[3])
        self.assertLess(cabin[4], 0.9 * cabin[1])                            # the cabin narrows towards its top
        self.assertAlmostEqual(secs[-1][0] - secs[0][0], 4.14, delta=0.05)
        car = params.expand(params.template("vehicle", "wedge") | {"facts": [], "synthetic": True})
        car["parts"] = [p for p in car["parts"] if p["id"] != "glasshouse"]
        body = next(p for p in car["parts"] if p["id"] == "body")
        body["shape"] = res["loft"]
        r = diagnose.diagnose(car)
        self.assertTrue(r["ok"], r["repair_text"])
        traced, _ = compare_mod.compare(car, _trace("top", top), "top")
        plain, _ = compare_mod.compare(params.expand(params.template("vehicle", "wedge") | {"facts": [], "synthetic": True}),
                                       _trace("top", top), "top")
        self.assertGreater(traced["iou"], plain["iou"] + 0.05)



class ArchitectureKit(unittest.TestCase):
    """Towers, roofs, dormers, facades, battlements and buttresses: every variant compiles clean."""

    def one(self, shape):
        return base(subject={"category": "architecture", "accuracy": "generic", "synthetic": True},
                    parts=[{"id": "p", "role": "identity", "certainty": "inferred", "stage": 0, "shape": shape}])

    def test_every_variant_compiles_without_warnings(self):
        shapes = [{"type": "tower", "radius": 2, "height": 10, "roof": r, "eave": e, "sides": sd, "windows": [2, 4]}
                  for r in ("cone", "pyramid", "spire", "onion", "flat", "none") for e in (0, 0.3) for sd in (0, 6)]
        shapes += [{"type": "roof", "size": [8, 5], "height": 3, "style": st, "ridge": rg, "overhang": o, "courses": 4}
                   for st in ("gable", "hip") for rg in ("x", "z") for o in (0, 0.3)]
        shapes += [{"type": "facade", "size": [12, 9], "rows": 3, "cols": 5, "arch": a, "kind": k}
                   for a in ("round", "pointed", "flat", "none") for k in ("windows", "arcade")]
        shapes += [{"type": "battlements", "radius": 4, "height": 1, "merlon": 0.8, "gap": 0.6, "thickness": 0.5},
                   {"type": "battlements", "path": [[0, 0], [10, 0], [10, 6], [0, 6]], "height": 1, "merlon": 0.8,
                    "gap": 0.6, "thickness": 0.5},
                   {"type": "buttress", "width": 1, "depth": 2, "height": 8, "steps": 3},
                   {"type": "dormer", "width": 2, "height": 2, "depth": 1.5},
                   {"type": "shell", "span": 30, "height": 50, "reach": 35, "bulge": 0.3, "ribs": 14},
                   {"type": "tower", "radius": 4, "height": 80, "taper": 0.2, "profile": "parabolic", "roof": "spire",
                    "windows": [10, 5]}]
        for sh in shapes:
            r = diagnose.diagnose(self.one(sh))
            codes = [d["code"] for d in r["diagnostics"] if d["code"] != "no-mass"]
            self.assertTrue(r["ok"] and not codes, (sh, codes))

    def test_shapes_are_checked(self):
        bad = [{"type": "tower", "radius": 2, "height": 10, "sides": 2},
               {"type": "tower", "radius": 2, "height": 10, "roof": "dome"},
               {"type": "battlements", "height": 1, "merlon": 1, "gap": 1, "thickness": 1},
               {"type": "facade", "size": [10, 5], "arch": "ogee"}]
        for sh in bad:
            self.assertFalse(diagnose.diagnose(self.one(sh))["ok"], sh)

    def test_a_parabolic_shaft_narrows_faster_near_the_top(self):
        geo = scene.compile_scene(self.one({"type": "tower", "radius": 4, "height": 90, "taper": 0.25,
                                            "profile": "parabolic", "roof": "none"}))
        lines, st = geo["lines"], geo["line_stride"]
        def width_at(y):
            xs = [abs(lines[i + k]) for i in range(0, len(lines), st) for k in (0, 3)
                  if abs(lines[i + k + 1] - y) < 0.5]
            return max(xs)
        mid, top = width_at(45.0 * (1 - (1 - 4 / 8) ** 1.5) * 2), width_at(90.0)
        self.assertLess(top, 1.1)
        self.assertGreater(width_at(0.0) - mid, 0)

    def test_a_spire_rises_above_its_shaft(self):
        geo = scene.compile_scene(self.one({"type": "tower", "radius": 2, "height": 10, "roof": "spire"}))
        self.assertGreater(geo["bounds"]["max"][1], 10 + 2 * 2.5)

    def test_a_building_on_measured_terrain(self):
        with tempfile.TemporaryDirectory() as d:
            dem, _ = synthetic_dem(d)
            plain = terrain.build(str(dem), center=(45.9763, 7.6586), extent=300, title="Site", source_title="Synthetic grid",
                                  real_scale=True, emphasis=False)
        castle = json.loads((EXAMPLES / "castle.json").read_text())
        castle["parts"] = [p for p in castle["parts"] if p["id"] != "rock"]
        for p in castle["parts"]:
            p["at"][1] -= 6 if p["at"][1] >= 6 else 0
        merged = terrain.plinth(castle, plain)
        site = next(p for p in merged["parts"] if p["id"] == "plinth")
        hs = site["shape"]["heights"]
        self.assertAlmostEqual(site["at"][1] + hs[len(hs) // 2][len(hs[0]) // 2], 0.0, places=3)  # ground at y = 0
        self.assertAlmostEqual(site["shape"]["size"][0], 300, delta=1)  # real metres
        self.assertIn("dem", {s_["id"] for s_ in merged["sources"]})
        self.assertTrue(diagnose.diagnose(merged)["ok"])


class Globe(unittest.TestCase):
    """A measured globe from coastline data (synthetic GeoJSON here; Natural Earth in use)."""

    def write(self, d, features):
        path = Path(d, "coast.geojson")
        path.write_text(json.dumps({"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {}, "geometry": g} for g in features]}))
        return str(path)

    def test_reads_lines_rings_and_polygons(self):
        with tempfile.TemporaryDirectory() as d:
            lines = globe.read_geojson(self.write(d, [
                {"type": "LineString", "coordinates": [[0, 0], [10, 5]]},
                {"type": "MultiLineString", "coordinates": [[[20, 0], [21, 1]], [[30, 0], [31, 1]]]},
                {"type": "Polygon", "coordinates": [[[0, 0], [5, 0], [5, 5], [0, 0]]]},
                {"type": "MultiPolygon", "coordinates": [[[[40, 40], [41, 40], [41, 41], [40, 40]]]]},
                {"type": "Point", "coordinates": [1, 1]}]))
        self.assertEqual(len(lines), 5)
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(globe.GlobeError):
                globe.read_geojson(self.write(d, [{"type": "Point", "coordinates": [1, 1]}]))

    def test_a_dense_coastline_is_simplified_into_the_budget_and_passes(self):
        ring = [[round(170 * math.cos(2 * math.pi * k / 30000), 5), round(60 * math.sin(2 * math.pi * k / 30000)
                 + 3 * math.sin(k / 9), 5)] for k in range(30000)]
        with tempfile.TemporaryDirectory() as d:
            sc = globe.build(self.write(d, [{"type": "LineString", "coordinates": ring}]), title="Synthetic planet",
                             source_title="Synthetic coastline (test)")
        facts = {f["key"]: f for f in sc["facts"]}
        self.assertIn("simplified", facts["coastline.points"]["note"])
        self.assertEqual(facts["earth.axial_tilt"]["value"], 23.44)
        r = diagnose.diagnose(sc)
        self.assertTrue(r["ok"] and not r["warnings"], r["repair_text"])
        geo = scene.compile_scene(sc)
        self.assertLessEqual(geo["counts"]["lines"], 24000)
        coast = next(p for p in geo["parts"] if p["id"] == "coastlines")
        self.assertEqual((coast["certainty"], coast["role"]), ("verified", "identity"))

    def test_shared_edges_are_drawn_once(self):
        lines = globe.dedupe([[[0, 0], [1, 0], [2, 0]], [[2, 0], [1, 0]], [[5, 5], [6, 6]]])
        self.assertEqual(sum(len(q) - 1 for q in lines), 3)

    def test_small_islands_go_only_when_the_budget_needs_it(self):
        def island(lon, lat, size, n):
            ring = [[lon + size * math.cos(2 * math.pi * k / n), lat + size * math.sin(2 * math.pi * k / n)] for k in range(n)]
            return ring + [ring[0]]
        few = [island(10 * k - 170, 0, 0.2, 12) for k in range(30)]
        lines, tol, floor, dropped = globe.fit_budget(few)
        self.assertEqual((tol, dropped, len(lines)), (0.0, 0, 30))
        many = few + [island(0, 40, 30, 15000), island(90, -30, 25, 15000)]
        lines, tol, floor, dropped = globe.fit_budget(many)
        self.assertEqual(dropped, 30)
        self.assertGreaterEqual(tol, globe.MIN_TOLERANCE)  # never sub-pixel segments that bead
        self.assertEqual(len(lines), 2)

    def test_the_antimeridian_is_not_crossed_and_the_tilt_is_the_spin_axis(self):
        m = shapes_mod.globe(1.0, [[[179, 0], [-179, 0]]], graticule=0, faces=False)
        self.assertEqual(len(m.lines), 0)
        with tempfile.TemporaryDirectory() as d:
            sc = globe.build(self.write(d, [{"type": "LineString", "coordinates": [[0, 0], [10, 10], [20, 0]]}]),
                             source_title="Synthetic coastline (test)")
        spin = next(p for p in sc["parts"] if p["id"] == "coastlines")["motion"]
        self.assertAlmostEqual(math.degrees(math.atan2(spin["axis"][0], spin["axis"][1])), 23.44, places=2)


REAL_DEM = os.environ.get("CONSTRUCT_TEST_MATTERHORN_DEM")


@unittest.skipUnless(REAL_DEM, "set CONSTRUCT_TEST_MATTERHORN_DEM to a folder of swissALTI3D XYZ tiles around the Matterhorn")
class RealTerrain(unittest.TestCase):
    """swissALTI3D 2024 (© swisstopo), 20 tiles of 2 m XYZ: never committed, read from where the user keeps them."""

    def test_the_matterhorn_from_twenty_tiles(self):
        sc = terrain.build(REAL_DEM, center=(45.97636, 7.65861), extent=3200, resolution=100, title="Matterhorn",
                           source_title="swissALTI3D 2024, © swisstopo", marks=["Hörnli hut=45.98194,7.67278"],
                           view_from="NE")
        facts = {f["key"]: f["value"] for f in sc["facts"]}
        self.assertEqual(facts["elevation.max"], 4477.2)  # the summit, not the thinned grid's highest sample
        self.assertTrue(diagnose.diagnose(sc)["ok"])
        geo = scene.compile_scene(sc)
        self.assertLessEqual(geo["counts"]["triangles"], 24000)
        hut = next(p for p in sc["parts"] if p.get("label") == "Hörnli hut")
        relief = sc["parts"][0]["shape"]["heights"]
        self.assertLess(hut["at"][1], max(max(r) for r in relief))
        # the Hörnli (NE), Zmutt (NW) and Lion (SW) ridges leave the summit; the Furggen (SE) is short at this grid
        bearings = []
        for p in sc["parts"]:
            if p["id"].startswith("ridge-"):
                a, b = p["shape"]["points"][0], p["shape"]["points"][-1]
                bearings.append(math.degrees(math.atan2(b[0] - a[0], -(b[2] - a[2]))) % 360)
        for want in (55, 300, 240):
            self.assertTrue(any(abs((x - want + 180) % 360 - 180) < 25 for x in bearings), (want, bearings))


@unittest.skipUnless(render.find_browser() and os.environ.get("HOLOGRAM_SKIP_CAPTURE") != "1",
                     "no Chromium-family browser (or HOLOGRAM_SKIP_CAPTURE=1)")
class Capture(unittest.TestCase):
    def test_a_round_packet_is_blind_and_paired_and_the_timeline_renders(self):
        from . import rounds
        with tempfile.TemporaryDirectory() as d:
            scene_path = Path(d, "cd.json")
            doc = json.loads((EXAMPLES / "cd.json").read_text())
            scene_path.write_text(json.dumps(doc))
            ref = Path(d, "refs", "front-photo.png")
            ref.parent.mkdir()
            from . import png as png_mod
            ref.write_bytes(png_mod.encode(8, 8, lambda x, y: (x * 30, y * 30, 90)))
            rounds.start(str(scene_path), "masterpiece", d)
            pk, key = rounds.packet(d, scene_path, ["front=%s" % ref], out=str(Path(d, "pk1")))
            self.assertIsNone(key)
            self.assertFalse(Path(pk, "step-2").exists())
            self.assertTrue(Path(pk, "step-1", "references", "front-photo.png").exists())  # the references travel along
            md = Path(pk, "step-1", "packet.md").read_text()
            self.assertIn("references/front-photo.png", md)
            self.assertNotIn(str(Path(d).resolve()), md)
            self.assertIn("The request: (not given)", md)              # the user's words only, never the author's summary
            self.assertFalse(Path(pk, "packet.md").stat().st_mode & 0o200)   # sealed
            rounds.record(d, _round_answer(d, 1), scene_path)
            doc["parts"][0]["shape"]["size"][1] *= 1.1
            scene_path.write_text(json.dumps(dict(json.loads(scene_path.read_text()), parts=doc["parts"])))
            pk, key = rounds.packet(d, scene_path, ["front=%s" % ref], out=str(Path(d, "pk2")), seed=3)
            pics = sorted(p_.name for p_ in Path(pk, "step-2").glob("*.png"))
            a_views = {n.split("-", 2)[2] for n in pics if n.startswith("A-")}
            self.assertTrue(a_views and a_views == {n.split("-", 2)[2] for n in pics if n.startswith("B-")})  # the same views
            import hashlib
            ones = {hashlib.sha256(p_.read_bytes()).hexdigest() for p_ in Path(pk, "step-1", "renders").glob("*.png")}
            twos = {hashlib.sha256(p_.read_bytes()).hexdigest() for p_ in Path(pk, "step-2").glob("*.png")}
            self.assertFalse(ones & twos)  # no byte match tells which pair image is the new version
            shown = len(json.loads(Path(pk, "step-3", "ledger.json").read_text())["items"])
            self.assertIn("ledger.json (%d items)" % shown, Path(pk, "packet.md").read_text())
            told = " ".join(p_.read_text() for p_ in Path(pk).rglob("*.md")) + " ".join(
                p_.read_text() for p_ in Path(pk).rglob("*.json"))
            self.assertNotIn("best_round", told)  # the key stays with the checkpoint
            self.assertTrue(Path(d, "checkpoints", "round-02", "key.json").exists())
            self.assertTrue(Path(d, "checkpoints", "round-02", "hero.png").exists())
            rounds.record(d, _round_answer(d, 2), scene_path)
            self.assertTrue(Path(pk).exists())   # a packet written where it was asked for stays
            doc["parts"][0]["shape"]["size"][1] *= 1.1
            scene_path.write_text(json.dumps(dict(json.loads(scene_path.read_text()), parts=doc["parts"])))
            pk, key = rounds.packet(d, scene_path, ["front=%s" % ref], seed=4)   # in the temporary folder
            self.assertTrue(Path(pk, "packet.md").exists())
            rounds.record(d, _round_answer(d, 3), scene_path)
            self.assertFalse(Path(pk).exists())   # spent: its renders are kept with the checkpoint
            self.assertTrue(Path(d, "checkpoints", "round-03", "hero.png").exists())
            studio.build(str(scene_path), str(Path(d, "out")))
            paths = render.review(str(Path(d, "out", "construct.html")), str(Path(d, "out", "review")), 640, 400, sheets=())
            self.assertIn("rounds.png", {Path(p_).name for p_ in paths})


    def test_review_produces_non_empty_images(self):
        with tempfile.TemporaryDirectory() as d:
            studio.build(str(EXAMPLES / "cd.json"), d)
            paths = render.review(str(Path(d, "construct.html")), str(Path(d, "review")), 640, 400, sheets=("views",))
            self.assertIn("solid.png", {Path(p).name for p in paths})            # the solid view, for the critic
            for p in paths:
                data = Path(p).read_bytes()
                self.assertTrue(data.startswith(b"\x89PNG"), p)
                self.assertGreater(len(data), 20000, p)  # an empty dark frame compresses far smaller

    def test_a_critique_packet_renders_the_views_of_the_references(self):
        with tempfile.TemporaryDirectory() as d:
            ref = Path(d, "side.png")
            from . import png as png_mod
            ref.write_bytes(png_mod.encode(8, 8, lambda x, y: (x * 30, y * 30, 90)))  # any image will do
            pk = critic.packet(str(EXAMPLES / "cd.json"), str(Path(d, "critique")), ["side=" + str(ref)], "a CD")
            self.assertTrue(Path(d, "critique", "renders", "still-side.png").exists())
            self.assertEqual(pk["pairs"][0]["render"], "renders/still-side.png")
            text = Path(d, "critique", "packet.md").read_text()
            self.assertIn(pk["scene_sha256"], text)
            self.assertIn("construct-critique", text)

    def test_the_open_view_is_taken_opened_whatever_the_still_pose(self):
        # reported by a live run: with the still pose closed, critics were shown an "open" view that was closed
        urls = []

        class Fake:
            def open(self, url):
                urls.append(url)

            def shot(self, path):
                pass

            def close(self):
                pass
        real = render.open_browser
        render.open_browser = lambda *a, **k: Fake()
        try:
            with tempfile.TemporaryDirectory() as d:
                render.stills(str(Path(d, "x.html")), d, ["open", "hero"])
        finally:
            render.open_browser = real
        self.assertIn("open=1", next(u for u in urls if "view=open" in u))
        self.assertNotIn("open=", next(u for u in urls if "view=hero" in u))

    def test_a_reference_keyed_to_the_scenes_own_view_travels_with_the_packet(self):
        # seen in a live run: `ref-front34=photo.jpg` (a view of the scene) was taken whole as a path, so the photo
        # never reached the packet and its absolute path did
        self.assertEqual(critic.parse_references(["ref-front34=a.jpg", "side=b.png", "https://x/y?a=b", "c.png"]),
                         [("ref-front34", "a.jpg"), ("side", "b.png"), (None, "https://x/y?a=b"), (None, "c.png")])
        scene = json.loads((EXAMPLES / "cd.json").read_text())
        own = scene["presentation"]["views"][0]["id"]
        with tempfile.TemporaryDirectory() as d:
            from . import png as png_mod
            ref = Path(d, "photo.png")
            ref.write_bytes(png_mod.encode(8, 8, lambda x, y: (x * 30, y * 30, 90)))
            path = Path(d, "scene.json")
            path.write_text(json.dumps(scene))
            pk = critic.packet(str(path), str(Path(d, "critique")), ["%s=%s" % (own, ref)], "a CD")
            self.assertEqual(pk["pairs"][0], {"view": own, "reference": str(ref), "render": "renders/still-%s.png" % own})
            self.assertTrue(Path(d, "critique", "renders", "still-%s.png" % own).exists())
            with self.assertRaisesRegex(critic.CriticError, "not a view of this scene"):
                critic.packet(str(path), str(Path(d, "critique2")), ["nowhere=%s" % ref], "a CD")

    def test_hero_is_the_fitted_whole_object_even_mid_tour(self):
        # a tour that flies close to a small part right when the hero is taken must not decide it
        scene = json.loads((EXAMPLES / "cd.json").read_text())
        scene["presentation"]["views"].append({"id": "close", "label": "Hinge", "yaw": 40, "pitch": 20,
                                               "distance": 0.4, "target": "hinge"})
        scene["animation"]["camera"]["tour"] = [{"view": "close", "at": 2, "fly": 20}]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, "scene.json")
            path.write_text(json.dumps(scene))
            studio.build(str(path), d)
            render.review(str(Path(d, "construct.html")), str(Path(d, "review")), 640, 400, sheets=())
            tl = json.loads(Path(d, "review", "timeline.json").read_text())
            cam, fitted = tl["hero_camera"], tl["hero_fitted"]
            self.assertAlmostEqual(cam["dist"], fitted["dist"], places=4)
            self.assertAlmostEqual(cam["yaw"], fitted["yaw"], places=4)
            for a, b in zip(cam["target"], fitted["target"]):
                self.assertAlmostEqual(a, b, places=4)


if __name__ == "__main__":
    unittest.main()
