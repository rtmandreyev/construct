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

from . import audit, diagnose, params, png, render, scene, studio

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
            self.assertIn("appears twice", r.stdout)


@unittest.skipUnless(render.find_browser() and os.environ.get("HOLOGRAM_SKIP_CAPTURE") != "1", "no Chromium-family browser")
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
    """The tessera.hologram/0.2 review items: host-owned style, articulations, fact labels,
    anchors, artwork slots and masks, unknown facts."""

    def test_colour_is_a_hint_in_presentation(self):
        errs = scene.validate(base(style={"palette": "amber"}))
        self.assertTrue(any("renderer" in e and "style_hint" in e for e in errs), errs)
        g = scene.compile_scene(base(presentation={"style_hint": {"palette": "amber"}}))
        self.assertEqual(g["presentation"]["style_hint"]["palette"], "amber")
        self.assertNotIn("style", g)

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
            if doc["format"] == params.FORMAT:
                doc = params.expand(doc)
            g = scene.compile_scene(doc)
            for frame in ("y-up", "z-up"):
                self.assertEqual(schema_errors(json.loads(json.dumps(scene.reframe(g, frame))), root, root), [],
                                 "%s %s" % (path and path.name, frame))

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
            self.assertEqual((out["ok"], out["contract"], out["diagnostics"][0]["path"]), (False, "tessera.hologram/0.2", "$.style"))


class Parametric(unittest.TestCase):
    """The simple path: a short parameter document becomes a clean, house-style scene."""

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
            self.assertEqual(json.loads(r.stdout)["format"], "tessera-hologram")


class Prompts(unittest.TestCase):
    def test_committed_prompts_match_the_generator(self):
        from . import prompts
        for name, text in prompts.build().items():
            self.assertEqual((HERE / "prompts" / name).read_text(encoding="utf-8"), text,
                             "%s is stale: run python3 -m hologram.prompts" % name)

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
            self.assertEqual(b["score"], 2)
            self.assertTrue(any("invented 'author'" in p for p in b["problems"]))
            self.assertTrue(any("written as unknown" in p for p in b["problems"]))
            self.assertEqual(score.score_run(Path(d, "good"))["rows"][0]["score"], 0)  # t1 missing


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
