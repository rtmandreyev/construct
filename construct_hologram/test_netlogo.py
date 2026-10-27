"""The NetLogo bridge: instrumenting a model, reading a recording, every view's construct, the data lock
and the art-direction layer, the `paths` shape, and (with CONSTRUCT_NETLOGO set to NetLogo's folder) a headless run end to end."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from . import audit, cli, netlogo, scene, studio

HERE = Path(__file__).resolve().parent
NETLOGO = os.environ.get("CONSTRUCT_NETLOGO")

MODEL = """<?xml version="1.0" encoding="utf-8"?>
<model version="NetLogo 7.0.4" snapToGrid="false">
  <code><![CDATA[turtles-own [ infected? ]

to setup
  clear-all
  create-turtles 20 [ setxy random-xcor random-ycor set infected? false ]
  ask one-of turtles [ set infected? true ]
  reset-ticks
end

to go
  ask turtles [ fd 1 ]
  ask turtles with [ infected? ] [ ask other turtles in-radius 2 [ set infected? true ] ]
  tick
end]]></code>
  <widgets>
    <view x="190" wrappingAllowedX="true" y="13" frameRate="30.0" minPycor="-8" height="350" showTickCounter="true" patchSize="20.0" fontSize="10" wrappingAllowedY="true" width="350" tickCounterLabel="ticks" maxPycor="8" updateMode="1" maxPxcor="8" minPxcor="-8"></view>
  </widgets>
</model>
"""


def recording(path, frames=12, header=None, **extra):
    """A small synthetic recording: 6 turtles on a ring, one spreading a state, two reporters, a patch field."""
    import math
    h = {"construct-netlogo": 1, "title": "Test model", "netlogo": "7.0.4", "seed": 5,
         "world": {"min-pxcor": -8, "max-pxcor": 8, "min-pycor": -8, "max-pycor": 8},
         "turtle-vars": ["infected?"], "reporters": ["count prey", "count predators"],
         "patch-reporter": "pcolor", "patch-every": 1}
    h.update(header or {})
    lines = [json.dumps(h)]
    for t in range(frames):
        row = {"t": t, "turtles": [[w, "walkers", round(6 * math.cos(w + t / 4), 3), round(6 * math.sin(w + t / 4), 3), 15,
                                    w <= t // 2] for w in range(6)],
               "reporters": [50 + 30 * math.sin(t / 2), 20 + 10 * math.cos(t / 2)],
               "patches": [55 if (i % 17) > t else 15 for i in range(17 * 17)]}
        if t == 0:
            row["links"] = [[w, (w + 1) % 6, "links"] for w in range(6)]
        lines.append(json.dumps(row))
    lines.append(json.dumps({"end": frames - 1}))
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


class Instrument(unittest.TestCase):
    def test_adds_the_include_the_recording_and_an_experiment(self):
        model, xml = netlogo.instrument(MODEL, "Contagion", "run.jsonl", ["infected?"], ["count turtles"],
                                        ("pcolor", 5), seed=9, ticks=50)
        code = model.split("<![CDATA[")[1]
        self.assertTrue(code.startswith('__includes ["construct.nls"]'))
        setup = code[code.index("to setup"):code.index("to go")]
        self.assertLess(setup.index("reset-ticks"), setup.index('construct-start "Contagion" "run.jsonl"'))
        for line in ("construct-seed 9", 'construct-track-turtles ["infected?"]',
                     'construct-track-reporters ["count turtles"]', 'construct-track-patches "pcolor" 5'):
            self.assertIn(line, setup)
        go = code[code.index("to go"):]
        self.assertLess(go.index("tick"), go.index("construct-record"))
        self.assertIn("<postRun>construct-finish</postRun>", xml)
        self.assertIn("random-seed 9\nsetup", xml)
        self.assertIn('timeLimit="50"', xml)
        with self.assertRaises(netlogo.NetLogoError):
            netlogo.instrument(model, "Again", "run.jsonl")          # already recording itself

    def test_merges_an_existing_include_and_refuses_what_it_cannot_place(self):
        m = MODEL.replace("turtles-own", '__includes ["other.nls"]\nturtles-own')
        model, _ = netlogo.instrument(m, "T", "run.jsonl")
        self.assertIn('__includes ["construct.nls" "other.nls"]', model)
        with self.assertRaises(netlogo.NetLogoError):
            netlogo.instrument(MODEL.replace("  reset-ticks\n", ""), "T", "run.jsonl")
        with self.assertRaises(netlogo.NetLogoError):
            netlogo.instrument("<model></model>", "T", "run.jsonl")

    def test_the_recorder_ships_with_the_package(self):
        text = netlogo.NLS.read_text(encoding="utf-8")
        for proc in ("to construct-start", "to construct-record", "to construct-finish", "to construct-skip-turtles",
                     "to-report construct-json"):
            self.assertIn(proc, text)


class Views(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run = netlogo.read_run(recording(Path(self.tmp.name, "run.jsonl")))

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, sc):
        self.assertEqual(scene.validate(sc), [])
        g = scene.compile_scene(sc)
        self.assertGreater(g["counts"]["lines"], 0)
        facts = {f["key"]: f for f in sc["facts"]}
        self.assertEqual((facts["model"]["value"], facts["seed"]["value"], facts["ticks"]["value"]), ("Test model", 5, 11))
        self.assertEqual(next(s for s in sc["sources"] if s["id"] == "run")["kind"], "dataset")
        self.assertTrue(all(p["certainty"] == "verified" for p in sc["parts"]))
        return g

    def test_every_view_compiles(self):
        for view, opts in (("space-time", {}), ("network-time", {"state": "infected?"}), ("phase", {"smooth": 3}),
                           ("field", {"levels": 4})):
            with self.subTest(view):
                self.check(netlogo.scene_from_run(self.run, view, **opts))

    def test_time_is_height(self):
        sc = netlogo.scene_from_run(self.run, "space-time")
        tracks = next(p for p in sc["parts"] if p["id"].startswith("tracks"))["shape"]["paths"]
        ys = [q[1] for path in tracks for q in path]
        self.assertAlmostEqual(max(ys), netlogo.FLOOR, places=2)   # the cube: as tall as it is wide, at the last tick
        self.assertEqual(min(ys), 0.0)
        root = netlogo.scene_from_run(self.run, "network-time", state="infected?", time="sqrt")
        self.assertIn("square root", next(f for f in root["facts"] if f["key"] == "coordinates")["value"])

    def test_network_time_lifts_each_node_to_its_change(self):
        sc = netlogo.scene_from_run(self.run, "network-time", state="infected?")
        stems = next(p for p in sc["parts"] if p["id"] == "risen")["shape"]["paths"]
        tops = sorted(round(s[1][1], 3) for s in stems)
        want = sorted(round(netlogo.HEIGHT * min(t for t in range(12) if w <= t // 2) / 11, 3) for w in range(6))
        self.assertEqual(tops, want)

    def test_a_wrap_breaks_a_track(self):
        w = netlogo._World(self.run["header"], 10)
        self.assertTrue(w.jump((-8.2, 0), (8.1, 0)))
        self.assertFalse(w.jump((1, 1), (1.5, 1.2)))

    def test_errors_name_what_is_missing(self):
        with self.assertRaises(netlogo.NetLogoError):
            netlogo.scene_from_run(self.run, "network-time", state="nope")
        with self.assertRaises(netlogo.NetLogoError):
            netlogo.scene_from_run(self.run, "phase", x="count wolves")
        with self.assertRaises(netlogo.NetLogoError):
            netlogo.scene_from_run(self.run, "spiral")
        bare = netlogo.read_run(recording(Path(self.tmp.name, "bare.jsonl"), header={"patch-reporter": ""}))
        with self.assertRaises(netlogo.NetLogoError):
            netlogo.scene_from_run(bare, "field")
        Path(self.tmp.name, "bad.jsonl").write_text("{not json\n", encoding="utf-8")
        with self.assertRaises(netlogo.NetLogoError):
            netlogo.read_run(Path(self.tmp.name, "bad.jsonl"))

    def test_the_examples_are_valid_and_credited(self):
        for slug in ("netlogo-flocking", "netlogo-wolf-sheep", "netlogo-fire"):
            with self.subTest(slug):
                d = HERE.parent / "examples" / slug
                sc = studio.load(str(d / "scene.json"))
                self.assertEqual(scene.validate(sc), [])
                self.assertIn("CC BY-NC-SA 3.0", (d / "LICENSE").read_text(encoding="utf-8"))
                self.assertIn("Uri Wilensky", (d / "README.md").read_text(encoding="utf-8"))
                self.assertIn("examples/%s/" % slug, (HERE.parent / "NOTICE").read_text(encoding="utf-8"))
                model = next(d.glob("*-construct.nlogox")).read_text(encoding="utf-8")
                self.assertIn('__includes ["construct.nls"]', model)
                self.assertIn(netlogo.LOCK, {f["key"] for f in sc["facts"]})
                self.assertIsNone(netlogo.lock_problem(sc))


class ArtDirection(unittest.TestCase):
    ART = {"credit": "Claude Opus 5.5", "title": "A run, directed",
           "looks": {"world": {"label": "The world", "look": {"alpha": 0.3}}},
           "parts": [{"id": "milestone", "label": "Half infected", "role": "data", "certainty": "inferred",
                      "source": "art", "stage": 1, "floating": True,
                      "shape": {"type": "curve", "points": [[-4, 3, -4], [4, 3, -4], [4, 3, 4]]}}],
           "annotations": [{"id": "milestone-note", "part": "milestone", "text": "half infected"}],
           "presentation": {"framing": {"yaw": 20, "pitch": 30}}}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run = netlogo.read_run(recording(Path(self.tmp.name, "run.jsonl")))
        self.sc = netlogo.scene_from_run(self.run, "space-time")

    def tearDown(self):
        self.tmp.cleanup()

    def errors(self, sc):
        return [e["code"] for e in audit.audit(sc, scene.compile_scene(sc))["errors"]]

    def test_the_lock_holds_the_data_not_its_look(self):
        self.assertEqual(self.errors(self.sc), [])
        same = json.loads(json.dumps(self.sc).replace(".0,", ","))   # 1.0 written as 1
        self.assertIsNone(netlogo.lock_problem(same))
        restyled = json.loads(json.dumps(self.sc))
        tracks = next(p for p in restyled["parts"] if p["id"].startswith("tracks"))
        tracks.update(label="Each track", look={"tone": "accent", "alpha": 0.9}, note="emphasised")
        self.assertEqual(self.errors(restyled), [])
        tracks["shape"]["paths"][0][1][1] += 0.5   # a point moved
        self.assertEqual(self.errors(restyled), ["data-lock"])
        for change in (lambda s: s["parts"].pop(),                                     # a data part removed
                       lambda s: s["parts"].append(dict(s["parts"][0], id="extra")),   # one more claims the run
                       lambda s: next(f for f in s["facts"] if f["key"] == "ticks").update(value=99),
                       lambda s: next(f for f in s["facts"] if f["key"] == "coordinates").update(value="Y is down.")):
            moved = json.loads(json.dumps(self.sc))
            change(moved)
            self.assertIsNotNone(netlogo.lock_problem(moved))

    def test_art_adds_its_own_and_keeps_the_data(self):
        out = netlogo.apply_art(self.sc, self.ART)
        self.assertEqual(scene.validate(out), [])
        self.assertEqual(self.errors(out), [])
        self.assertIn("Art direction by Claude Opus 5.5", [s["title"] for s in out["sources"]])
        world = next(p for p in out["parts"] if p["id"] == "world")
        self.assertEqual((world["label"], world["look"]["alpha"], world["look"]["weight"]), ("The world", 0.3, 0.5))
        self.assertEqual((out["title"], out["presentation"]["framing"]["yaw"]), ("A run, directed", 20))
        self.assertTrue(out["presentation"]["atmosphere"]["projector"])
        self.assertNotIn("art", [s["id"] for s in self.sc["sources"]])   # the bridge's scene is left as it was

    def test_art_never_touches_the_data(self):
        part = dict(self.ART["parts"][0], source="run")
        for bad in ({"title": "no credit"}, dict(self.ART, colour="red"),
                    dict(self.ART, looks={"world": {"shape": {"type": "box", "size": [1, 1, 1]}}}),
                    dict(self.ART, looks={"nope": {"label": "x"}}), dict(self.ART, parts=[part]),
                    dict(self.ART, facts=[{"key": "ticks", "value": 3, "certainty": "verified", "source": "run"}]),
                    dict(self.ART, facts=[{"key": "view", "value": "phase", "certainty": "inferred"}])):
            with self.assertRaises(netlogo.NetLogoError, msg=str(bad)[:80]):
                netlogo.apply_art(self.sc, bad)
        moved = json.loads(json.dumps(self.sc))
        moved["parts"].pop()
        with self.assertRaises(netlogo.NetLogoError):
            netlogo.apply_art(moved, self.ART)


class Paths(unittest.TestCase):
    def test_the_paths_shape(self):
        sc = studio.starter("object")
        sc["parts"].append({"id": "tracks", "role": "identity", "certainty": "inferred", "stage": 0,
                            "shape": {"type": "paths", "paths": [[[0, 0, 0], [0.1, 0.2, 0]], [[0, 0, 0.1], [0.2, 0.3, 0.1]]]}})
        self.assertEqual(scene.validate(sc), [])
        self.assertEqual(len(scene._local_mesh(sc["parts"][-1]["shape"], 0).lines), 2)
        for bad in ([], [[[0, 0, 0]]], [[[0, 0], [1, 1]]], [[[0, 0, 0], [1, 1, "x"]]]):
            sc["parts"][-1]["shape"]["paths"] = bad
            self.assertTrue(scene.validate(sc), bad)


class Command(unittest.TestCase):
    def test_cli(self):
        with tempfile.TemporaryDirectory() as d:
            run = recording(Path(d, "run.jsonl"))
            out = Path(d, "scene.json")
            self.assertEqual(cli.main(["netlogo", str(run), "--view", "phase", "--smooth", "3", "--out", str(out)]), 0)
            self.assertEqual(scene.validate(json.loads(out.read_text(encoding="utf-8"))), [])
            self.assertEqual(cli.main(["netlogo", str(run), "--view", "network-time", "--out", str(out), "--force"]), 1)
            Path(d, "art.json").write_text(json.dumps(ArtDirection.ART), encoding="utf-8")
            self.assertEqual(cli.main(["netlogo", str(run), "--view", "space-time", "--art", str(Path(d, "art.json")),
                                       "--out", str(out), "--force"]), 0)
            self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["title"], "A run, directed")
            Path(d, "art.json").write_text("{not json", encoding="utf-8")
            self.assertEqual(cli.main(["netlogo", str(run), "--view", "space-time", "--art", str(Path(d, "art.json")),
                                       "--out", str(out), "--force"]), 1)
            Path(d, "m.nlogox").write_text(MODEL, encoding="utf-8")
            self.assertEqual(cli.main(["netlogo-instrument", str(Path(d, "m.nlogox")), "--title", "M", "--out",
                                       str(Path(d, "inst")), "--turtles", "infected?", "--patches", "pcolor:3"]), 0)
            for name in ("m-construct.nlogox", "construct.nls", "construct-experiment.xml"):
                self.assertTrue(Path(d, "inst", name).is_file(), name)


@unittest.skipUnless(NETLOGO, "set CONSTRUCT_NETLOGO to NetLogo's folder to run")
class Headless(unittest.TestCase):
    """NetLogo itself: an instrumented model runs headless and its recording draws."""

    def test_record_and_draw(self):
        folder = Path(NETLOGO)
        with tempfile.TemporaryDirectory() as d:
            Path(d, "m.nlogox").write_text(MODEL, encoding="utf-8")
            self.assertEqual(cli.main(["netlogo-instrument", str(Path(d, "m.nlogox")), "--title", "Contagion", "--out", d,
                                       "--turtles", "infected?", "--reporters", "count turtles with [infected?];ticks",
                                       "--seed", "4", "--ticks", "30"]), 0)
            env = dict(os.environ, JAVA_HOME=str(folder / "runtime" / "Contents" / "Home"))
            r = subprocess.run([str(folder / "netlogo-headless.sh"), "--model", str(Path(d, "m-construct.nlogox")),
                                "--setup-file", str(Path(d, "construct-experiment.xml")), "--experiment", "construct",
                                "--threads", "1", "--table", "-"], cwd=folder, capture_output=True, text=True,
                               timeout=600, env=env, encoding="utf-8", errors="replace")
            self.assertEqual(r.returncode, 0, r.stdout[-1500:] + r.stderr[-1500:])
            run = netlogo.read_run(Path(d, "run.jsonl"))
            self.assertEqual((run["header"]["seed"], run["end"]), (4, 30))
            self.assertEqual(len(run["frames"]), 31)
            for view, opts in (("space-time", {}), ("network-time", {"state": "infected?"}), ("phase", {})):
                if view == "network-time":
                    continue   # this model has no links
                self.assertEqual(scene.validate(netlogo.scene_from_run(run, view, **opts)), [])


if __name__ == "__main__":
    unittest.main()
