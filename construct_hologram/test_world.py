"""Worlds: constructs placed together, each kept whole (world.py), and what reads a world: the page, the viewer,
the exports and the Blender and Godot sides."""

import json
import math
import os
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

from construct_hologram import export, render, scene, studio, world

HERE = Path(__file__).resolve().parent
V2 = HERE / "examples" / "v2"


def place(*rows, **top):
    doc = {"format": "construct-world", "version": 1, "id": "test-world", "title": "Test world", "placements": []}
    for r in rows:
        doc["placements"].append(dict(r))
    doc.update(top)
    return doc


def lit(name):
    return str(V2 / name)


class Format(unittest.TestCase):
    """The world document is checked as strictly as a scene."""

    def test_a_valid_world(self):
        self.assertEqual(world.validate(place({"id": "a", "construct": lit("cd.json")})), [])

    def test_problems_are_named(self):
        bad = place({"id": "a", "construct": lit("cd.json"), "colour": "red"},
                    {"id": "a", "construct": lit("book.json")},
                    {"id": "B", "construct": ""},
                    {"id": "c", "construct": lit("book.json"), "on": "zz"},
                    {"id": "d", "construct": lit("book.json"), "scale": 0},
                    {"id": "e", "construct": lit("book.json"), "at": [2e6, 0, 0]},
                    {"id": "f", "construct": lit("book.json"), "sky": {"diameter_m": 10, "distance_m": 5}})
        errs = "\n".join(world.validate(bad))
        for want in ("placements[0].colour", "placed twice", "placements[2].id", "placements[2].construct",
                     "placements[3].on", "placements[4].scale", "placements[5].at", "placements[6].sky.distance_m"):
            self.assertIn(want, errs)

    def test_a_placement_cannot_stand_on_a_later_one(self):
        errs = world.validate(place({"id": "a", "construct": lit("cd.json"), "on": "b"},
                                    {"id": "b", "construct": lit("book.json")}))
        self.assertTrue(any("placements[0].on" in e for e in errs))

    def test_a_world_that_places_itself_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "w.json")
            p.write_text(json.dumps(place({"id": "me", "construct": "w.json"})))
            with self.assertRaises(world.WorldError) as cm:
                world.compile_world(world.load(p), d)
            self.assertIn("places itself", str(cm.exception))


class Compile(unittest.TestCase):
    """A world compiles to a construct's geometry, every placed construct whole under its placement's id."""

    @classmethod
    def setUpClass(cls):
        cls.cd = scene.compile_scene(json.loads(Path(lit("cd.json")).read_text()))
        cls.reel = scene.compile_scene(json.loads(Path(lit("open-reel.json")).read_text()))

    def test_parts_sources_facts_and_joints_keep_their_construct(self):
        g = world.compile_world(place({"id": "one", "construct": lit("cd.json")},
                                      {"id": "two", "construct": lit("cd.json"), "at": [1, 0, 0]}))
        ids = [p["id"] for p in g["parts"]]
        self.assertEqual(len(ids), 2 * len(self.cd["parts"]))
        self.assertEqual(len(set(ids)), len(ids))
        self.assertTrue(all(i.startswith(("one/", "two/")) for i in ids))
        self.assertEqual({s["id"].split("/")[0] for s in g["provenance"]["sources"]}, {"one", "two"})
        self.assertEqual({f["key"].split("/")[0] for f in g["provenance"]["facts"]}, {"one", "two"})
        self.assertEqual(len(g["articulations"]), 2 * len(self.cd["articulations"]))
        self.assertEqual(len(g["joints"]), 2 * len(self.cd["joints"]))
        # each placement's basis still names its own facts and sources
        keys = {f["key"] for f in g["provenance"]["facts"]} | {s["id"] for s in g["provenance"]["sources"]}
        for p in g["parts"]:
            for b in p["basis"]:
                self.assertTrue(b.split(".")[0] in keys or b in keys or "/" in b, b)
        self.assertEqual([r["id"] for r in g["world"]["placements"]], ["one", "two"])

    def test_styles_point_at_the_right_part_motion_and_joint(self):
        g = world.compile_world(place({"id": "a", "construct": lit("open-reel.json")},
                                      {"id": "b", "construct": lit("cd.json"), "at": [2, 0, 0]}))
        n = len(self.reel["parts"])
        for st in g["styles"]:
            if st[6] >= n:   # a style of the second placement
                self.assertTrue(g["parts"][int(st[6])]["id"].startswith("b/"))
                if len(st) > 9 and st[9] >= 0:
                    self.assertGreaterEqual(st[9], len(self.reel["joints"]))
        self.assertEqual(len(g["motions"]), len(self.reel["motions"]))

    def test_placement_moves_and_turns_the_geometry(self):
        g = world.compile_world(place({"id": "a", "construct": lit("cd.json"), "at": [10, 2, -3], "yaw": 90}))
        b0, b1 = self.cd["bounds"], g["bounds"]
        # a quarter turn about up: width becomes depth
        w0 = [b0["max"][k] - b0["min"][k] for k in range(3)]
        w1 = [b1["max"][k] - b1["min"][k] for k in range(3)]
        self.assertAlmostEqual(w1[0], w0[2], places=3)
        self.assertAlmostEqual(w1[2], w0[0], places=3)
        self.assertAlmostEqual(w1[1], w0[1], places=3)
        self.assertAlmostEqual(b1["center"][0], 10 + b0["center"][2], places=2)
        # lines and fills moved with it
        xs = g["lines"][0::9]
        self.assertTrue(all(b1["min"][0] - 1e-3 <= x <= b1["max"][0] + 1e-3 for x in xs))

    def test_on_stands_it_on_the_hosts_top(self):
        g = world.compile_world(place({"id": "base", "construct": lit("book.json")},
                                      {"id": "disc", "construct": lit("cd.json"), "on": "base/" + self._top_part()}))
        base = [p for p in g["parts"] if p["placement"] == "base"]
        disc = [p for p in g["parts"] if p["placement"] == "disc"]
        part = next(p for p in base if p["id"] == "base/" + self._top_part())
        top = max(b["max"][1] for b in part["instances"])
        low = min(b["min"][1] for p in disc for b in p["instances"])
        self.assertAlmostEqual(low, top, places=3)

    def _top_part(self):
        g = scene.compile_scene(json.loads(Path(lit("book.json")).read_text()))
        return max(g["parts"], key=lambda p: max(b["max"][1] for b in p["instances"]))["id"]

    def test_more_joints_than_a_construct_may_have(self):
        rows = [{"id": "cd-%d" % i, "construct": lit("cd.json"), "at": [i * 0.3, 0, 0]} for i in range(8)]
        g = world.compile_world(place(*rows))
        self.assertGreater(len(g["joints"]), scene.MAX_JOINTS)
        self.assertGreater(len(g["articulations"]), scene.MAX_ARTICULATIONS)
        self.assertEqual(max(j for p in g["parts"] for j in [p["joint"]]), len(g["joints"]) - 1)

    def test_sky_is_drawn_at_its_real_angular_size_and_never_framed(self):
        g = world.compile_world(place({"id": "here", "construct": lit("book.json")},
                                      {"id": "moon", "construct": lit("cd.json"),
                                       "sky": {"diameter_m": 3.4748e6, "distance_m": 3.844e8, "elevation": 30}}))
        rec = g["world"]["placements"][1]
        self.assertAlmostEqual(rec["angular_deg"], math.degrees(2 * math.atan(3.4748e6 / (2 * 3.844e8))), places=3)
        sky = [p for p in g["parts"] if p.get("sky")]
        self.assertTrue(sky and all(p["placement"] == "moon" for p in sky))
        here = [p for p in g["parts"] if p["placement"] == "here"]
        hi = max(b["max"][1] for p in here for b in p["instances"])
        self.assertLessEqual(g["bounds"]["max"][1], hi + 1e-6)   # the frame is the world, not the sky
        self.assertIn("sky_far", g["bounds"])
        # its angular size, measured from the middle of the world
        c = g["bounds"]["center"]
        lo = [min(b["min"][k] for p in sky for b in p["instances"]) for k in range(3)]
        top = [max(b["max"][k] for p in sky for b in p["instances"]) for k in range(3)]
        mid = [(lo[k] + top[k]) / 2 for k in range(3)]
        dist = math.dist(mid, c)
        self.assertLess(abs(math.degrees(2 * math.atan(max(top[k] - lo[k] for k in range(3)) / 2 / dist))
                            - rec["angular_deg"]) / rec["angular_deg"], 0.6)

    def test_sky_of_sizes_it_by_one_part(self):
        """diameter_m is the disc's (a planet's globe), so the whole is larger by what surrounds it (rings, moons)."""
        sky = {"diameter_m": 3.4748e6, "distance_m": 3.844e8, "elevation": 30}
        whole = world.compile_world(place({"id": "here", "construct": lit("book.json")},
                                          {"id": "moon", "construct": lit("cd.json"), "sky": dict(sky)}))
        by_disc = world.compile_world(place({"id": "here", "construct": lit("book.json")},
                                            {"id": "moon", "construct": lit("cd.json"), "sky": dict(sky, of="disc")}))
        size = lambda g, pid: max(max(b["max"][k] for b in p["instances"]) - min(b["min"][k] for b in p["instances"])
                                  for p in g["parts"] if p["id"] == pid for k in range(3))
        self.assertAlmostEqual(size(by_disc, "moon/disc") / size(whole, "moon/disc"),
                               size(whole, "moon/tray") / size(whole, "moon/disc"), delta=0.35)
        self.assertGreater(size(by_disc, "moon/disc"), size(whole, "moon/disc"))
        with self.assertRaises(world.WorldError):
            world.compile_world(place({"id": "here", "construct": lit("book.json")},
                                      {"id": "moon", "construct": lit("cd.json"), "sky": dict(sky, of="nothing")}))

    def test_views_are_checked_and_shown(self):
        good = place({"id": "a", "construct": lit("book.json")}, {"id": "b", "construct": lit("cd.json"), "at": [1, 0, 0]},
                     presentation={"views": [{"id": "desk", "label": "Desk", "target": "a", "yaw": 20, "distance": 0.8}]})
        self.assertEqual(world.validate(good), [])
        views = world.compile_world(good)["presentation"]["views"]
        self.assertEqual([v["id"] for v in views], ["desk", "a", "b"])   # the world's own, then each placement's
        for bad in ({"id": "x", "target": "nowhere"}, {"id": "Bad Id"}, {"id": "x", "pitch": 120}, {"id": "x", "zoom": 2}):
            doc = place({"id": "a", "construct": lit("book.json")}, presentation={"views": [bad]})
            self.assertTrue(world.validate(doc), bad)

    def test_worlds_inside_worlds(self):
        with tempfile.TemporaryDirectory() as d:
            inner = place({"id": "disc", "construct": lit("cd.json")}, id="inner", title="Inner")
            Path(d, "inner.world.json").write_text(json.dumps(inner))
            outer = place({"id": "a", "construct": "inner.world.json"},
                          {"id": "b", "construct": "inner.world.json", "at": [5, 0, 0]})
            g = world.compile_world(outer, d)
            self.assertTrue(all(p["id"].startswith(("a/disc/", "b/disc/")) for p in g["parts"]))
            self.assertEqual(g["world"]["placements"][0]["kind"], "world")

    def test_budgets_are_a_worlds_own(self):
        self.assertGreater(world.WORLD_MAX_LINES, scene.MAX_LINES)
        self.assertGreater(world.WORLD_EXTENT, scene.MAX_EXTENT)


class Audit(unittest.TestCase):
    def test_overlap_unsupported_and_scale_are_said(self):
        doc = place({"id": "a", "construct": lit("book.json")},
                    {"id": "b", "construct": lit("book.json")},
                    {"id": "c", "construct": lit("cd.json"), "at": [3, 2, 0]},
                    {"id": "d", "construct": lit("cd.json"), "at": [-3, 0, 0], "scale": 2})
        rep = world.audit(doc, world.compile_world(doc))
        codes = {(w["code"], w["part"]) for w in rep["warnings"]}
        self.assertIn(("overlap", "a"), codes)
        self.assertIn(("unsupported", "c"), codes)
        self.assertIn(("scaled", "d"), codes)

    def test_a_thing_must_clear_the_parts_of_what_it_stands_in(self):
        """On a whole placement it shares that placement's space by design, but not its parts' (a car and a column)."""
        top = Compile._top_part(self)
        clear = place({"id": "a", "construct": lit("book.json")}, {"id": "c", "construct": lit("cd.json"), "on": "a/" + top})
        self.assertFalse([w for w in world.audit(clear, world.compile_world(clear))["warnings"] if w["code"] == "collides"])
        inside = place({"id": "a", "construct": lit("book.json")}, {"id": "c", "construct": lit("book.json"), "on": "a"})
        hits = [w for w in world.audit(inside, world.compile_world(inside))["warnings"] if w["code"] == "collides"]
        self.assertEqual([w["part"] for w in hits], ["c"])

    def test_what_opens_needs_room(self):
        """A CD's lid opens up and back: a book standing where it opens is in its way, though nothing touches shut."""
        cd = world.compile_world(place({"id": "cd", "construct": lit("cd.json")}))
        lid = next(b for p in cd["parts"] if p["id"] == "cd/lid" for b in p["instances"])
        shut, opened = (lid["min"], lid["max"]), (lid["open_min"], lid["open_max"])
        # the book just past the shut case, where the open lid reaches
        k = max(range(3), key=lambda i: (opened[1][i] - shut[1][i]) + (shut[0][i] - opened[0][i]) if i != 1 else -1)
        gap = opened[1][k] - shut[1][k] >= shut[0][k] - opened[0][k]
        at = [0, 0, 0]
        at[k] = (shut[1][k] + 0.08) if gap else (shut[0][k] - 0.08)
        doc = place({"id": "cd", "construct": lit("cd.json")}, {"id": "book", "construct": lit("book.json"), "at": at})
        codes = [(w["code"], w["part"]) for w in world.audit(doc, world.compile_world(doc))["warnings"]]
        self.assertIn(("blocks", "book"), codes)
        self.assertNotIn("collides", [c for c, _ in codes])

    def test_check_reads_a_world(self):
        with tempfile.TemporaryDirectory() as d:
            w = Path(d, "w.json")
            w.write_text(json.dumps(place({"id": "a", "construct": lit("book.json")},
                                          {"id": "c", "construct": lit("book.json"), "on": "a"})))
            rep = world.check(str(w))
            self.assertTrue(rep["ok"] and rep["world"])
            self.assertEqual([d["code"] for d in rep["diagnostics"]], ["collides"])
            self.assertEqual(rep["stats"]["placements"], 2)
            w.write_text(json.dumps(place({"id": "a", "construct": "no-such-construct.json"})))
            self.assertFalse(world.check(str(w))["ok"])

    def test_floating_and_on_are_not_unsupported(self):
        doc = place({"id": "a", "construct": lit("book.json")},
                    {"id": "c", "construct": lit("cd.json"), "at": [3, 2, 0], "floating": True})
        rep = world.audit(doc, world.compile_world(doc))
        self.assertFalse([w for w in rep["warnings"] if w["code"] == "unsupported"])


class Arrange(unittest.TestCase):
    """Moved and turned by hand on the page: the world written back so that it compiles to what the page showed."""

    def centre(self, g, pid):
        bs = [b for p in g["parts"] if p.get("placement") == pid for b in p["instances"]]
        return [(min(b["min"][k] for b in bs) + max(b["max"][k] for b in bs)) / 2 for k in range(3)]

    def test_moves_turns_and_carries_what_stands_on_it(self):
        doc = place({"id": "deck", "construct": lit("book.json")},
                    {"id": "cd", "construct": lit("cd.json"), "on": "deck", "at": [0.02, 0, 0.01]},
                    {"id": "far", "construct": lit("cd.json"), "at": [2, 0, 0]})
        g = world.compile_world(doc, ".")
        c = self.centre(g, "deck")
        new, moved = world.arrange(doc, g, [{"id": "deck", "move": [0.5, 0.1, -0.25], "turn": 90, "pivot": [c[0], c[2]]}])
        self.assertEqual(moved, ["deck", "cd"])          # what stands on it goes with it; the rest stays
        g2 = world.compile_world(new, ".")
        a = math.radians(90)
        for pid in ("deck", "cd"):
            o, n = self.centre(g, pid), self.centre(g2, pid)
            x, z = o[0] - c[0], o[2] - c[2]
            want = [math.cos(a) * x + math.sin(a) * z + c[0] + 0.5, o[1] + 0.1, -math.sin(a) * x + math.cos(a) * z + c[2] - 0.25]
            for k in range(3):
                self.assertAlmostEqual(n[k], want[k], places=2)
        self.assertEqual(self.centre(g, "far"), self.centre(g2, "far"))
        self.assertEqual([p.get("yaw") for p in new["placements"]][:2], [90.0, 90.0])
        self.assertNotIn("yaw", doc["placements"][0])   # the document given is never changed

    def test_set_down_by_hand_it_lands_on_what_is_under_it(self):
        doc = place({"id": "deck", "construct": lit("cd.json"), "rotate": [-90, 0, 0]}, {"id": "cd", "construct": lit("book.json"), "on": "deck"})
        g = world.compile_world(doc, ".")
        deck_top = max(b["max"][1] for p in g["parts"] if p.get("placement") == "deck" for b in p["instances"])
        new, landed = world.settle(doc, g, {"cd"})
        self.assertEqual(landed, ["cd"])
        self.assertTrue(new["placements"][1]["on"].startswith("deck/"))
        g2 = world.compile_world(new, ".")
        bottom = min(b["min"][1] for p in g2["parts"] if p.get("placement") == "cd" for b in p["instances"])
        self.assertLess(abs(bottom - deck_top), 0.01)
        self.assertEqual(world.settle(new, g2, {"cd"})[1], [])   # already there: nothing changes
        high = place({"id": "deck", "construct": lit("cd.json"), "rotate": [-90, 0, 0]}, {"id": "cd", "construct": lit("book.json"), "on": "deck"})
        self.assertEqual(world.settle(high, g, {"cd"}, step=0.0)[1], [])   # out of reach: it stays

    def test_what_it_cannot_do_is_refused(self):
        doc = place({"id": "a", "construct": lit("cd.json")},
                    {"id": "moon", "construct": lit("cd.json"), "sky": {"diameter_m": 3.4e6, "distance_m": 3.8e8}})
        g = world.compile_world(doc, ".")
        for bad in ([], [{"id": "nope", "move": [0, 0, 0], "turn": 0, "pivot": [0, 0]}],
                    [{"id": "moon", "move": [1, 0, 0], "turn": 0, "pivot": [0, 0]}],
                    [{"id": "a", "move": [float("nan"), 0, 0], "turn": 0, "pivot": [0, 0]}],
                    [{"id": "a", "move": [1, 0, 0], "turn": 0}], [{"id": "a", "move": [1, 0, 0], "turn": 0, "pivot": [0, 0], "x": 1}]):
            with self.assertRaises(world.WorldError):
                world.arrange(doc, g, bad)


class Build(unittest.TestCase):
    """`construct build` and `construct export` take a world as they take a scene."""

    def test_build_and_export(self):
        with tempfile.TemporaryDirectory() as d:
            w = Path(d, "w.json")
            w.write_text(json.dumps(place({"id": "deck", "construct": lit("cd.json")},
                                          {"id": "reel", "construct": lit("open-reel.json"), "at": [0.6, 0, 0]})))
            g, rep, text = studio.build(str(w), Path(d, "out"))
            html = Path(d, "out", "construct.html").read_text()
            self.assertIn("construct-world", html)
            self.assertIn("world:", text)
            self.assertTrue(rep["ok"])
            geo = json.loads(Path(d, "out", "geometry.json").read_text())
            self.assertEqual(len(geo["world"]["placements"]), 2)
            s = world.export(w, Path(d, "w.glb"), pieces="glued")
            self.assertEqual(s["placements"], 2)
            data = Path(d, "w.glb").read_bytes()
            n = struct.unpack("<I", data[12:16])[0]
            doc = json.loads(data[20:20 + n])
            names = [x.get("name", "") for x in doc["nodes"]]
            self.assertIn("deck", names)
            self.assertIn("reel", names)
            root = next(x for x in doc["nodes"] if x.get("extras", {}).get("construct", {}).get("scene_sha256"))
            self.assertEqual([p["id"] for p in root["extras"]["construct"]["world"]["placements"]], ["deck", "reel"])
            static = [x for x in doc["nodes"] if x.get("extensions", {}).get("OMI_physics_body", {}).get("motion", {})
                      .get("type") == "static"]
            self.assertEqual(len(static), 1)   # a world's fixed body is a map's: it stays put
            self.assertTrue(any(a["name"].startswith("open:deck/") for a in doc.get("animations", [])))

    def test_material_maps_are_merged_under_each_placement(self):
        with tempfile.TemporaryDirectory() as d:
            c = Path(d, "c")
            c.mkdir()
            Path(c, "scene.json").write_text(Path(lit("cd.json")).read_text())
            Path(c, "scene.materials.json").write_text(json.dumps({"materials": [{"parts": "*", "color": "#ff0000"}]}))
            m = world.materials(place({"id": "x", "construct": "c/scene.json"}), d)
            self.assertEqual(m["materials"][0]["parts"], ["x/*"])


class Viewer(unittest.TestCase):
    """The viewer carries any number of joints and motions (a texture, not 16 fixed slots)."""

    def test_no_fixed_joint_or_motion_arrays(self):
        js = (HERE / "viewer" / "hologram.js").read_text()
        self.assertNotIn("uJoint[16]", js)
        self.assertNotIn("uMotion[32]", js)
        self.assertIn("uPose", js)

    @unittest.skipUnless(render.find_browser(), "no browser")
    def test_a_world_with_many_joints_draws_opened(self):
        rows = [{"id": "cd-%d" % i, "construct": lit("cd.json"), "at": [i * 0.3, 0, 0]} for i in range(8)]
        with tempfile.TemporaryDirectory() as d:
            w = Path(d, "w.json")
            w.write_text(json.dumps(place(*rows)))
            studio.build(str(w), Path(d, "out"))
            page = Path(d, "out", "construct.html")
            b = render.open_browser(render._url(page, capture=1, ui=0), 320, 200, 1.0)
            try:
                errs = b.evaluate("(window.__errors || []).length")
                ok = b.evaluate("(() => { HOLO.renderAt(60, { open: 1 }); const g = HOLO.hologram.geo;"
                                " return [g.joints.length, HOLO.hologram.poseJointBase, HOLO.hologram.lastJoints.length / 16]; })()")
            finally:
                b.close()
            self.assertGreater(ok[0], 16)
            self.assertEqual(ok[2], ok[0])

    @unittest.skipUnless(render.find_browser(), "no browser")
    def test_a_worlds_views_are_buttons(self):
        doc = place({"id": "a", "construct": lit("book.json")}, {"id": "b", "construct": lit("cd.json"), "at": [1, 0, 0]},
                    presentation={"views": [{"id": "desk", "label": "Desk", "target": "a"}]})
        with tempfile.TemporaryDirectory() as d:
            w = Path(d, "w.json")
            w.write_text(json.dumps(doc))
            studio.build(str(w), Path(d, "out"))
            b = render.open_browser(render._url(Path(d, "out", "construct.html"), ui=1), 480, 300, 1.0)
            try:
                labels = b.evaluate("[...document.querySelectorAll('.viewsbar button')].map((x) => x.textContent)")
                pressed = b.evaluate("(() => { const x = [...document.querySelectorAll('.viewsbar button')][1]; x.click();"
                                     " return [...document.querySelectorAll('.viewsbar button')]"
                                     ".map((y) => y.getAttribute('aria-pressed')); })()")
                errs = b.evaluate("document.body.getAttribute('data-error')")
            finally:
                b.close()
        self.assertEqual(labels[:2], ["WHOLE", "DESK"])
        self.assertEqual(len(labels), 4)   # the whole, the world's own, one for each placement
        self.assertEqual(pressed[:2], ["false", "true"])
        self.assertIsNone(errs)

    @unittest.skipUnless(render.find_browser(), "no browser")
    def test_many_placements_fold_their_views(self):
        rows = [{"id": "cd-%d" % i, "construct": lit("cd.json"), "at": [i * 0.3, 0, 0]} for i in range(6)]
        with tempfile.TemporaryDirectory() as d:
            w = Path(d, "w.json")
            w.write_text(json.dumps(place(*rows)))
            studio.build(str(w), Path(d, "out"))
            b = render.open_browser(render._url(Path(d, "out", "construct.html"), ui=1), 480, 300, 1.0)
            try:
                got = b.evaluate("(() => { const bs = [...document.querySelectorAll('.viewsbar button')];"
                                 " const shown = () => bs.filter((x) => !x.hidden).length; const before = shown();"
                                 " document.querySelector('.viewsbar .fold').click(); return [bs.length, before, shown()]; })()")
            finally:
                b.close()
        self.assertEqual(got, [8, 2, 8])   # the whole and the fold; then the six placements too

    @unittest.skipUnless(render.find_browser(), "no browser")
    def test_a_world_is_arranged_by_hand(self):
        doc = place({"id": "a", "construct": lit("book.json")}, {"id": "b", "construct": lit("cd.json"), "at": [1, 0, 0]})
        with tempfile.TemporaryDirectory() as d:
            w = Path(d, "w.json")
            w.write_text(json.dumps(doc))
            studio.build(str(w), Path(d, "out"))
            b = render.open_browser(render._url(Path(d, "out", "construct.html"), ui=1, t=30), 480, 300, 1.0)
            try:
                got = b.evaluate("""(() => {
                  const A = HOLO.arrange, h = HOLO.hologram, heard = [];
                  HOLO.onArrange = (s) => heard.push(s.changes.length);
                  const off = A.changes().length;
                  A.set(true);
                  const at = HOLO.project(h.targetOf("b").c), r = document.querySelector("canvas").getBoundingClientRect();
                  const hit = h.pickPlacements(at[0], at[1], r.width, r.height).map((x) => x.id);
                  A.select("b"); A.edit("b", { move: [0.5, 0, 0], turn: 30 });
                  HOLO.renderAt(30);
                  const rows = [h.placeBase, h._poseRows];
                  const box = document.querySelector(".arrange").textContent;
                  const ch = A.changes();
                  A.reset(); A.set(false);
                  return { off, hit, rows, box, ch, heard, after: A.changes().length, base: (HOLO.renderAt(30), h.placeBase) };
                })()""")
                errs = b.evaluate("document.body.getAttribute('data-error')")
            finally:
                b.close()
        self.assertEqual(got["off"], 0)
        self.assertEqual(got["hit"][0], "b")
        self.assertGreaterEqual(got["rows"][0], 0)
        self.assertEqual(got["rows"][1] - got["rows"][0], 2)   # one row for each placement, after the chains
        self.assertIn("MOVED 0.50 M", got["box"])
        self.assertEqual(got["ch"][0]["id"], "b")
        self.assertEqual(got["ch"][0]["move"], [0.5, 0, 0])
        self.assertEqual(got["ch"][0]["turn"], 30)
        self.assertIn(1, got["heard"])
        self.assertEqual((got["after"], got["base"]), (0, -1))
        self.assertIsNone(errs)

    @unittest.skipUnless(render.find_browser(), "no browser")
    def test_arranging_undoes_snaps_chooses_several_and_warns(self):
        doc = place({"id": "a", "construct": lit("book.json")}, {"id": "b", "construct": lit("cd.json"), "at": [1, 0, 0]},
                    {"id": "c", "construct": lit("cd.json"), "at": [2, 0, 0]})
        with tempfile.TemporaryDirectory() as d:
            w = Path(d, "w.json")
            w.write_text(json.dumps(doc))
            studio.build(str(w), Path(d, "out"))
            b = render.open_browser(render._url(Path(d, "out", "construct.html"), ui=1, t=30), 480, 300, 1.0)
            try:
                got = b.evaluate("""(() => {
                  const A = HOLO.arrange, h = HOLO.hologram;
                  A.set(true); A.select("b"); A.turn(90); A.turn(90);
                  const turned = A.changes()[0].turn;
                  A.undo(); const back = A.changes()[0].turn; A.redo(); const again = A.changes()[0].turn;
                  const snap = A.snap();
                  A.edit("b", { move: [1, 0, 0] });   // onto c: it runs into it
                  const hits = h.runsInto("b", new Set());
                  return { turned, back, again, snap, hits, keys: !!document.querySelector(".keys") };
                })()""")
            finally:
                b.close()
        self.assertEqual((got["turned"], got["back"], got["again"]), (180, 90, 180))
        self.assertTrue(got["snap"])
        self.assertEqual(len(got["hits"]), 1)
        self.assertTrue(got["keys"])

    @unittest.skipUnless(render.find_browser(), "no browser")
    def test_a_van_roof_is_somewhere_to_stand(self):
        # the Samba's drawn body lines have a box as big as the van: they must not stop the pointer as a wall
        samba = str(Path(__file__).resolve().parent.parent / "examples" / "volkswagen-t1-samba" / "scene.json")
        doc = place({"id": "van", "construct": samba}, {"id": "cd", "construct": lit("cd.json"), "at": [4, 0, 0]})
        with tempfile.TemporaryDirectory() as d:
            w = Path(d, "w.json")
            w.write_text(json.dumps(doc))
            studio.build(str(w), Path(d, "out"))
            b = render.open_browser(render._url(Path(d, "out", "construct.html"), ui=1, t=60), 480, 300, 1.0)
            try:
                got = b.evaluate("""(() => {
                  const h = HOLO.hologram, r = document.querySelector("canvas").getBoundingClientRect(), t = h.targetOf("van");
                  HOLO.renderAt(60, { view: "van" });
                  let top = -Infinity;
                  for (const p of h.geo.parts) if (p.placement === "van" && p.shape !== "paths" && p.shape !== "points")
                    for (const x of p.instances) top = Math.max(top, x.max[1]);
                  HOLO.arrange.set(true);
                  const at = HOLO.project([t.c[0], top, t.c[2]]);
                  const s = h.surfaceAt(at[0], at[1], r.width, r.height, new Set(["cd"]));
                  return { side: s.side, y: s.point[1], top };
                })()""")
            finally:
                b.close()
        self.assertFalse(got["side"])
        self.assertGreater(got["y"], got["top"] - 0.3)   # on the roof, not the ground beside the van


if __name__ == "__main__":
    unittest.main()
