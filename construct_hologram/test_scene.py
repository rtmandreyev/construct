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
            for name in ("geometry.json", "geometry.v1.json", "construct.html", "audit.txt"):
                self.assertTrue(Path(d, "out", name).exists(), name)
            Path(d, "bad.json").write_text('{"format": "construct-scene", "format": 2}')
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
    return {"format": "construct-critique", "version": 1, "scene_sha256": tiers.critic_hash(scene_doc),
            "scores": scores, "checklist": [{"feature": "the box", "present": present, "quality": 3}],
            "defects": [{"rank": 1, "severity": severity, "criterion": "proportions", "parts": ["body"],
                         "view": "side", "problem": "the nose is a rectangle from above", "fix": "taper the loft"}]
            if severity else [], "verdict": "outstanding"}


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

    def test_masterpiece_has_no_caps_but_a_user_stop(self):
        lim = tiers.limits("masterpiece")
        self.assertIsNone(lim["wall_clock_s"])
        self.assertIsNone(lim["review_rounds"])
        self.assertEqual(tiers.limits("masterpiece", wall_clock_s=36000)["wall_clock_s"], 36000)
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
        self.assertEqual(hook.TIERS, {k: (v["wall_clock_s"], v["review_rounds"]) for k, v in tiers.TIERS.items()})
        self.assertEqual(hook.WRAP_UP, tiers.WRAP_UP)

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


class Capture(unittest.TestCase):
    def test_review_produces_non_empty_images(self):
        with tempfile.TemporaryDirectory() as d:
            studio.build(str(EXAMPLES / "cd.json"), d)
            paths = render.review(str(Path(d, "construct.html")), str(Path(d, "review")), 640, 400, sheets=("views",))
            for p in paths:
                data = Path(p).read_bytes()
                self.assertTrue(data.startswith(b"\x89PNG"), p)
                self.assertGreater(len(data), 20000, p)  # an empty dark frame compresses far smaller

    def test_a_critique_packet_renders_the_views_of_the_references(self):
        with tempfile.TemporaryDirectory() as d:
            ref = Path(d, "side.png")
            ref.write_bytes((HERE.parent / "docs" / "media" / "provenance.png").read_bytes())  # any image will do
            pk = critic.packet(str(EXAMPLES / "cd.json"), str(Path(d, "critique")), ["side=" + str(ref)], "a CD")
            self.assertTrue(Path(d, "critique", "renders", "still-side.png").exists())
            self.assertEqual(pk["pairs"][0]["render"], "renders/still-side.png")
            text = Path(d, "critique", "packet.md").read_text()
            self.assertIn(pk["scene_sha256"], text)
            self.assertIn("construct-critique", text)

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
