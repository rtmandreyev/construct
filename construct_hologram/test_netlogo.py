"""The NetLogo bridge: instrumenting a model, reading a recording, every view's construct, the data lock
and the art-direction layer, the `paths` shape, and (with CONSTRUCT_NETLOGO set to NetLogo's folder) a headless run end to end; with CONSTRUCT_JAVAC too, the
NetLogo extension built, run and checked against the recorder it replaces."""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from . import audit, cli, netlogo, scene, studio

HERE = Path(__file__).resolve().parent
NETLOGO = os.environ.get("CONSTRUCT_NETLOGO")
JAVAC = os.environ.get("CONSTRUCT_JAVAC")   # a Java 17 or newer javac, for the extension

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


MODEL3D = """<?xml version="1.0" encoding="utf-8"?>
<model version="NetLogo 3D 7.0.4" snapToGrid="false">
  <code><![CDATA[extensions [construct]
to setup
  clear-all
  create-turtles 8 [ setxyz random-xcor random-ycor random-zcor ]
  reset-ticks
end
to go
  ask turtles [ tilt-up 10 fd 1 ]
  tick
end]]></code>
  <widgets>
    <view3d wrappingAllowedZ="true" x="0" wrappingAllowedX="true" y="0" minPycor="-5" height="200" showTickCounter="true" patchSize="10.0" fontSize="10" wrappingAllowedY="true" width="200" tickCounterLabel="ticks" maxPycor="5" updateMode="1" frameRate="30.0" maxPzcor="4" maxPxcor="5" minPxcor="-5" minPzcor="-4"></view3d>
  </widgets>
</model>
"""


def netlogo_java(folder):
    """NetLogo's own Java (macOS app, Linux tarball, Windows install), else the one on PATH."""
    for rel in ("runtime/Contents/Home/bin/java", "lib/runtime/bin/java", "runtime/bin/java.exe", "runtime/bin/java"):
        if Path(folder, rel).exists():
            return str(Path(folder, rel))
    return "java"


def netlogo_jar(folder):
    return next(Path(folder).glob("**/app/netlogo-*.jar"))


def headless(folder, *args, cwd=None):
    """NetLogo headless, run as its launchers do: its Java, its jar, its bundled extensions."""
    folder = Path(folder)
    ext = next((str(p) for p in (folder / "extensions", folder / "app" / "extensions", folder / "lib" / "app" / "extensions")
                if p.is_dir()), None)
    cmd = [netlogo_java(folder), "-Xmx1536m", "-Dfile.encoding=UTF-8"] + (["-Dnetlogo.extensions.dir=" + ext] if ext else []) \
        + ["-cp", str(netlogo_jar(folder)), "org.nlogo.headless.Main"] + list(args)
    return subprocess.run(cmd, cwd=cwd or folder, capture_output=True, text=True, timeout=600, encoding="utf-8",
                          errors="replace")


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
            netlogo.instrument("<model></model>", "T", "run.jsonl")
        with self.assertRaises(netlogo.NetLogoError):   # no setup procedure and no button that sets up
            netlogo.instrument(MODEL.replace("to setup", "to prepare"), "T", "run.jsonl")

    def test_a_model_that_never_ticks_or_has_only_buttons(self):
        never = MODEL.replace("  reset-ticks\n", "").replace("  tick\n", "")
        model, xml = netlogo.instrument(never, "T", "run.jsonl")
        self.assertIn('  construct-record\nend\n\nto go', model)            # the end of setup
        self.assertIn("  construct-record\nend]]>", model)                     # the end of go
        self.assertIn("<metric>count turtles</metric>", xml)    # not ticks: the counter may never start
        buttons = MODEL.replace("to setup", "to prepare").replace("to go", "to step").replace(
            "</widgets>", '<button kind="Observer" forever="false" display="prepare">prepare</button>'
            '<button kind="Observer" forever="true" display="run">step</button></widgets>')
        model, xml = netlogo.instrument(buttons, "T", "run.jsonl")
        self.assertIn("<setup>prepare</setup>", xml)
        self.assertIn("<go>step</go>", xml)
        inline = MODEL.replace("  tick\n", "").replace(
            "</widgets>", '<button kind="Observer" forever="true" display="go">go\ntick</button></widgets>')
        inline = inline.replace("to go", "to go-step").replace("go\ntick</button>", "go-step\ntick</button>")
        model, xml = netlogo.instrument(inline, "T", "run.jsonl")
        self.assertIn("<go>go-step\ntick\nconstruct-record</go>", xml)
        self.assertIn(">go-step\ntick\nconstruct-record</button>", model)   # pressing the button records too
        own = MODEL.replace("</widgets>", '<button kind="Observer" forever="false">setup\nask turtles [ set color 15 ]'
                            '</button><button kind="Observer" forever="true">go\nask turtles [ rt 5 ]</button></widgets>')
        model, xml = netlogo.instrument(own, "T", "run.jsonl")               # the model's own buttons, whole
        self.assertIn("<setup>setup\nask turtles [ set color 15 ]</setup>", xml)
        self.assertIn("<go>go\nask turtles [ rt 5 ]</go>", xml)
        turtle = MODEL.replace("to go\n  ask turtles [ fd 1 ]", "to step-on\n  ask turtles [ fd 1 ]").replace(
            "to setup", "to walk\n  fd 1\nend\n\nto go\n  walk\nend\n\nto setup").replace(
            "</widgets>", '<button kind="Turtle" forever="true">go</button></widgets>')
        model, xml = netlogo.instrument(turtle, "T", "run.jsonl")            # go, asked of every turtle
        self.assertIn("<go>ask turtles [ go ]\nconstruct-record</go>", xml)
        self.assertIn('<button kind="Turtle" forever="true">go</button>', model)   # a turtle button stays as it was
        step = MODEL.replace("to go", "to step-once").replace(
            "</widgets>", '<button kind="Observer" forever="false">step-once</button></widgets>')
        model, xml = netlogo.instrument(step, "T", "run.jsonl")              # no forever button: a step button
        self.assertIn("<go>step-once</go>", xml)

    def test_escaped_code_helper_procedures_and_commands(self):
        m = MODEL.replace("  reset-ticks\nend", "  setup-world\nend\n\nto setup-world\n  reset-ticks\nend")
        m = m.replace("  tick\nend]]>", "  step\nend\n\nto step\n  if count turtles > 0 [ ]\n  tick\nend]]>")
        code = m.split("<![CDATA[")[1].split("]]>")[0]
        m = m.replace("<![CDATA[" + code + "]]>", code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        self.assertNotIn("CDATA", m)
        model, xml = netlogo.instrument(m, "T", "run.jsonl")
        self.assertIn("  if count turtles &gt; 0 [ ]", model)   # written back escaped, as it came
        self.assertIn("to setup-world\n  reset-ticks\n  construct-start", model)
        self.assertIn("  tick\n  construct-record\nend", model)
        inputs = MODEL.replace("to setup\n", "to setup [ n ]\n").replace(
            "</widgets>", '<button kind="Observer" display="setup">setup 20</button></widgets>')
        model, xml = netlogo.instrument(inputs, "T", "run.jsonl")    # the model's own button gives the input
        self.assertIn("<setup>setup 20</setup>", xml)
        with self.assertRaises(netlogo.NetLogoError) as e:
            netlogo.instrument(inputs, "T", "run.jsonl", setup="setup")
        self.assertIn('--setup "setup 20"', str(e.exception))
        model, xml = netlogo.instrument(inputs, "T", "run.jsonl", setup="setup 7")
        self.assertIn("<setup>setup 7</setup>", xml)

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

    def test_a_legend_shown_from_the_start(self):
        sc = netlogo.scene_from_run(self.run, "network-time", state="infected?")
        legend = {a["part"]: a["text"] for a in sc["annotations"]}
        self.assertEqual(set(legend), {p["id"] for p in sc["parts"] if p["role"] != "mass"})
        self.assertTrue(all(legend[p["id"]] == p["label"][:80] for p in sc["parts"] if p["id"] in legend))
        self.assertIs(sc["presentation"]["labels"], True)
        self.assertFalse(sc["presentation"]["atmosphere"]["projector"])   # nothing that looks like data and isn't
        self.assertIs(scene.compile_scene(sc)["presentation"]["labels"], True)
        plain = json.loads(json.dumps(sc))
        del plain["presentation"]["labels"]
        self.assertNotIn("labels", scene.compile_scene(plain)["presentation"])   # other constructs: unchanged
        plain["presentation"]["labels"] = "yes"
        self.assertTrue(any("labels" in e for e in scene.validate(plain)))

    def test_a_run_by_steps_says_steps(self):
        run = netlogo.read_run(recording(Path(self.tmp.name, "steps.jsonl"), header={"clock": "steps"}))
        sc = netlogo.scene_from_run(run, "space-time")
        self.check(sc)
        text = json.dumps([p["label"] for p in sc["parts"]] + [a["text"] for a in sc["annotations"]]
                          + [sc["subject"]["summary"]] + [f["value"] for f in sc["facts"] if isinstance(f["value"], str)])
        self.assertNotRegex(text, r"\btick")
        self.assertIn("Time, step 0 to 11", text)
        self.assertEqual(next(f for f in sc["facts"] if f["key"] == "clock")["value"], "steps")

    def test_a_reading_and_a_replay(self):
        for view, opts in (("space-time", {}), ("network-time", {"state": "infected?"}), ("phase", {}),
                           ("field", {"levels": 4})):
            with self.subTest(view):
                sc = netlogo.scene_from_run(self.run, view, **opts)
                r = sc["reading"]
                self.assertTrue(3 <= len(r["how"]) <= 8)
                self.assertEqual(r["clock"], {"label": "tick", "from": 0, "to": 11, "top": sc["reading"]["clock"]["top"],
                                              "scale": "linear"})
                g = scene.compile_scene(sc)
                a, b = g["reading"]["clock"]["phase"]
                self.assertAlmostEqual(a * 0 + b, 0.0, delta=0.01)                     # tick 0: the build's start
                self.assertAlmostEqual(a * r["clock"]["top"] + b, 0.82, delta=0.01)    # the last tick: its end
        sc = netlogo.scene_from_run(self.run, "phase")
        self.assertEqual([s["name"] for s in sc["reading"]["series"]], ["count prey", "count predators"])
        self.assertEqual(len(sc["reading"]["series"][0]["values"]), 12)
        bare = netlogo.read_run(recording(Path(self.tmp.name, "bare.jsonl"), header={"reporters": []}))
        sc = netlogo.scene_from_run(bare, "network-time", state="infected?")   # no reporters: the state's count
        self.assertEqual([v[1] for v in sc["reading"]["series"][0]["values"][:4]], [1, 1, 2, 2])
        moved = json.loads(json.dumps(sc))
        moved["reading"]["series"][0]["values"][3][1] = 99                 # a count changed: the lock sees it
        self.assertIsNotNone(netlogo.lock_problem(moved))
        reworded = json.loads(json.dumps(sc))
        reworded["reading"]["how"] = ["Read it from the floor up."]          # the words are not data
        self.assertIsNone(netlogo.lock_problem(reworded))

    def test_a_reading_is_checked_and_its_page_carries_the_replay(self):
        from . import render
        sc = netlogo.scene_from_run(self.run, "space-time")
        for bad in ({"how": "one line"}, {"how": ["x"], "series": [{"name": "n", "values": [[0, 1]]}]},
                    {"clock": {"label": "tick", "from": 5, "to": 5, "top": 6}}, {"colour": "red"}):
            wrong = dict(sc, reading=bad)
            self.assertTrue(any("reading" in e for e in scene.validate(wrong)), bad)
        page, _ = render.build_html(scene.compile_scene(sc))
        self.assertIn("HOW TO READ IT", page)
        self.assertIn("rd-bar", page)
        stock = studio.load(str(HERE / "examples" / "v2" / "cd.json"))
        page, _ = render.build_html(scene.compile_scene(stock))
        self.assertNotIn("HOW TO READ IT", page)   # a construct that asks for nothing: the stock page

    @unittest.skipUnless(__import__("construct_hologram.render", fromlist=["x"]).find_browser()
                         and os.environ.get("HOLOGRAM_SKIP_CAPTURE") != "1", "needs a Chromium-family browser")
    def test_printed_it_is_a_worksheet(self):
        from . import render
        page, _ = render.build_html(scene.compile_scene(netlogo.scene_from_run(self.run, "phase")))
        d = Path(self.tmp.name)
        (d / "w.html").write_text(page, encoding="utf-8")
        b = render.Browser(1000, 700, 1.0, gpu=False)
        try:
            b.open(render._url(str(d / "w.html")))
            b.evaluate("HOLO.ready.then(() => new Promise((r) => setTimeout(r, 300)))")
            b.evaluate("HOLO_WORKSHEET()")
            got = json.loads(b.evaluate("JSON.stringify({title: document.querySelector('.rd-sheet h1').textContent, "
                                        "picture: (document.querySelector('.rd-sheet img') || {}).src.slice(0, 21), "
                                        "how: document.querySelectorAll('.rd-sheet li').length, "
                                        "questions: document.querySelectorAll('.rd-sheet .rd-q').length})"))
            b.call("Emulation.setEmulatedMedia", media="print")
            shown = b.evaluate("[getComputedStyle(document.querySelector('.rd-sheet')).display, "
                               "getComputedStyle(document.getElementById('stage')).display]")
        finally:
            b.close()
        self.assertEqual(got["picture"], "data:image/png;base64")
        self.assertEqual((got["how"] > 2, got["questions"]), (True, 3))
        self.assertEqual(shown, ["block", "none"])   # printed: the worksheet, not the viewer

    def test_the_counts_as_csv_and_a_citation_on_the_page(self):
        from . import render
        csv = netlogo.counts_csv(self.run).splitlines()
        self.assertEqual(csv[0], "tick,count prey,count predators,count walkers")
        self.assertEqual((len(csv), csv[1].split(",")[0], csv[1].split(",")[-1]), (13, "0", "6"))
        page, _ = render.build_html(scene.compile_scene(netlogo.scene_from_run(self.run, "phase")))
        self.assertIn("DATA (CSV)", page)
        self.assertIn("CITE THIS RUN", page)

    def test_two_runs_side_by_side(self):
        d = Path(self.tmp.name)
        short = netlogo.read_run(recording(d / "short.jsonl", frames=6))
        sc = netlogo.compare_runs(self.run, short, "space-time", ("seed 1", "seed 2"))
        self.assertEqual([e for e in scene.validate(sc)], [])
        g = scene.compile_scene(sc)
        self.assertEqual(audit.audit(sc, g)["errors"], [])
        self.assertEqual(sc["reading"]["clock"]["to"], 11)                  # one time scale: the longer run's
        ids = {p["id"] for p in sc["parts"]}
        self.assertTrue({"a-tracks-walkers", "b-tracks-walkers"} <= ids)
        a_at = next(p for p in sc["parts"] if p["id"] == "a-world")["at"][0]
        b_at = next(p for p in sc["parts"] if p["id"] == "b-world")["at"][0]
        self.assertLess(a_at, 0)
        self.assertGreater(b_at, 0)                                          # A on the left, B on the right
        self.assertEqual({f["value"] for f in sc["facts"] if f["key"].endswith("_ticks")}, {11, 5})
        self.assertIsNone(netlogo.lock_problem(sc))
        moved = json.loads(json.dumps(sc))
        next(p for p in moved["parts"] if p["id"] == "b-tracks-walkers")["shape"]["paths"][0][0][0] += 1
        self.assertIsNotNone(netlogo.lock_problem(moved))                    # the lock covers both runs
        self.assertTrue(all(a["text"].startswith(("seed 1:", "seed 2:")) for a in sc["annotations"]))

    def test_hidden_is_a_look_not_a_spread(self):
        run = netlogo.read_run(recording(Path(self.tmp.name, "hid.jsonl"), header={"turtle-vars": ["hidden?"]}))
        view, opts, _ = netlogo.choose_view(run)   # the ring's links and a variable that turns: but it is hidden?
        self.assertNotEqual(opts.get("state"), "hidden?")

    def test_a_run_with_music(self):
        from . import render
        d = Path(self.tmp.name)
        n = 12
        (d / "beat-audio-30.json").write_text(json.dumps({"format": "construct-audio", "version": 2, "fps": 30, "frames": n,
                                                          "energy": [0.5] * n, "high": [0.2] * n, "kick": [0, 1] * (n // 2),
                                                          "onset": [0.0] * n, "voice": [0.0] * n, "sections": []}))
        (d / "beat.wav").write_bytes(b"RIFF")
        music = {"track": "beat.wav", "path": str(d / "beat.wav"), "sha256": "a" * 64, "ticks-per-second": 30, "ticks": n,
                 "features": "beat-audio-30.json"}
        run = netlogo.read_run(recording(d / "music.jsonl", header={"music": music}))
        sc = netlogo.scene_from_run(run, "space-time")
        m = sc["reading"]["music"]
        self.assertEqual((m["track"], m["ticks_per_second"], m["seconds"], m["audio"]["kick"][:2]), ("beat.wav", 30, 0.4, [0, 1]))
        self.assertIn("Press play", sc["reading"]["how"][-1])
        self.assertTrue(any(f["key"] == "music" and f["source"] == "run" for f in sc["facts"]))
        self.assertEqual([e for e in scene.validate(sc) if "music" in e], [])
        self.assertIsNone(netlogo.lock_problem(sc))
        other = json.loads(json.dumps(sc))
        other["reading"]["music"]["sha256"] = "b" * 64            # another track: the lock sees it
        self.assertIsNotNone(netlogo.lock_problem(other))
        self.assertEqual(netlogo.music_track(run), d / "beat.wav")
        with self.assertRaises(netlogo.NetLogoError):              # height is the track's time: never stretched
            netlogo.scene_from_run(run, "network-time", state="infected?", time="sqrt")
        page, _ = render.build_html(scene.compile_scene(sc))
        self.assertIn("runCurve", page)                            # film mode by itself, the features in the page
        for bad in ({"track": "../beat.wav"}, {"ticks_per_second": 0}, {"audio": dict(m["audio"], fps=0)}):
            wrong = json.loads(json.dumps(sc))
            wrong["reading"]["music"].update(bad)
            self.assertTrue(any("music" in e for e in scene.validate(wrong)), bad)
        (d / "beat-audio-30.json").unlink()
        with self.assertRaises(netlogo.NetLogoError):              # the features must travel with the run
            netlogo.scene_from_run(run, "space-time")

    def test_the_view_the_data_suits(self):
        view, opts, _ = netlogo.choose_view(self.run)          # links, and infected? turned for some turtles
        self.assertEqual((view, opts["state"]), ("network-time", "infected?"))
        self.assertIn("network-time", netlogo.scene_from_run(self.run, "auto")["id"])
        run = json.loads(json.dumps(self.run))
        for f in run["frames"]:
            f.pop("links", None)
        self.assertEqual(netlogo.choose_view(run)[0], "field")    # no network: the patches that changed
        for f in run["frames"]:
            f.pop("patches", None)
        view, opts, _ = netlogo.choose_view(run)
        self.assertEqual((view, {opts["x"], opts["z"]}), ("phase", {"count prey", "count predators"}))
        for f in run["frames"]:
            f.pop("reporters", None)
        self.assertEqual(netlogo.choose_view(run)[0], "space-time")
        still = json.loads(json.dumps(run))
        for f in still["frames"]:                                  # agents that never move: said so, not "moving"
            for r in f["turtles"]:
                r[2], r[3] = still["frames"][0]["turtles"][r[0]][2:4]
        self.assertIn("barely move", netlogo.choose_view(still)[2])
        grew = json.loads(json.dumps(self.run))                    # a network that grows: each turtle at its arrival
        for f in grew["frames"]:
            f["turtles"] = [r[:5] + [False] for r in f["turtles"] if r[0] <= f["t"] // 2]
        view, opts, why = netlogo.choose_view(grew)
        self.assertEqual((view, opts["state"]), ("network-time", netlogo.APPEARED))
        sc = netlogo.scene_from_run(grew, "auto")
        self.check(sc)
        self.assertIn("appeared", next(p for p in sc["parts"] if p["id"] == "risen")["label"])

    def test_solids_for_a_3d_model(self):
        plain = netlogo.scene_from_run(self.run, "network-time", state="infected?")
        sc = netlogo.scene_from_run(self.run, "network-time", state="infected?", solid=True)
        self.check(sc)
        nodes = [p for p in sc["parts"] if p["id"].startswith("node-")]
        self.assertEqual((len(nodes), len(sc["parts"]) - len(nodes)), (6, len(plain["parts"])))   # added, nothing else
        self.assertTrue(all(p["shape"]["type"] == "sphere" and p["source"] == "run" for p in nodes))
        risen = next(p for p in nodes if p["id"] == "node-5")             # turtle 5 turns at tick 10
        self.assertAlmostEqual(risen["at"][1], netlogo._World(self.run["header"], 11).height(10), places=2)
        self.assertNotEqual(netlogo.data_lock(sc), netlogo.data_lock(plain))   # the solids are locked data too
        self.assertIn("node-* (6)", next(f for f in sc["facts"] if f["key"] == netlogo.LOCK)["note"])
        sc = netlogo.scene_from_run(self.run, "phase", solid=True)
        self.check(sc)
        tubes = [p for p in sc["parts"] if p["id"].startswith("phase-solid-")]
        self.assertTrue(1 <= len(tubes) <= netlogo.SOLID_TUBES)
        self.assertTrue(all(2 <= len(p["shape"]["path"]) <= netlogo.MAX_TUBE for p in tubes))
        sc = netlogo.scene_from_run(self.run, "field", levels=4, solid=True)
        self.check(sc)
        surf = next(p for p in sc["parts"] if p["id"] == "surface")
        self.assertEqual(surf["shape"]["type"], "terrain")
        hs = [h for row in surf["shape"]["heights"] for h in row]
        self.assertAlmostEqual(max(hs), netlogo._World(self.run["header"], 11).top, places=2)   # never changed: the top

    def test_the_runs_own_colours(self):
        self.assertEqual(netlogo.netlogo_rgb(15), "#d73229")      # red
        self.assertEqual(netlogo.netlogo_rgb(10), "#000000")      # the darkest red is black
        self.assertEqual(netlogo.netlogo_rgb([10, 20, 30]), "#0a141e")
        sc = netlogo.scene_from_run(self.run, "network-time", state="infected?", solid=True)
        mats = netlogo.materials_from_run(self.run, sc)
        where = {pid: m["color"] for m in mats["materials"] for pid in m["parts"]}
        self.assertEqual(where["node-0"], netlogo.netlogo_rgb(15))   # each turtle in its own last colour
        self.assertEqual(where["world"], "#1a1a1e")
        from . import export
        with tempfile.TemporaryDirectory() as d:
            export.export(sc, Path(d, "run.glb"), wire="tubes", materials=mats)
            doc, _ = export.read_glb(Path(d, "run.glb").read_bytes())
            names = {n.get("name") for n in doc["nodes"]}
            self.assertTrue({"node-0", "node-5", "network"} <= names)
            self.assertIn("netlogo #d73229", {m["name"] for m in doc["materials"]})

    def test_the_field_hangs_at_its_ticks(self):
        sc = netlogo.scene_from_run(self.run, "field", levels=4)
        self.assertIs(next(p for p in sc["parts"] if p["id"] == "fronts")["floating"], True)
        self.assertEqual([e["code"] for e in audit.audit(sc, scene.compile_scene(sc))["errors"]], [])

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
        self.assertFalse(out["presentation"]["atmosphere"]["projector"])   # the bridge's atmosphere, kept
        self.assertNotIn("art", [s["id"] for s in self.sc["sources"]])   # the bridge's scene is left as it was

    def test_the_legend_follows_the_art(self):
        art = dict(self.ART, looks={"tracks-walkers": {"label": "Every walker, rising"}})
        out = netlogo.apply_art(self.sc, art)
        self.assertEqual(next(a for a in out["annotations"] if a["id"] == "legend-tracks-walkers")["text"], "Every walker, rising")
        out = netlogo.apply_art(self.sc, dict(art, legend=False))
        self.assertEqual([a["id"] for a in out["annotations"]], ["milestone-note"])
        self.assertIsNone(netlogo.lock_problem(out))

    def test_the_replay_follows_the_data_under_art_of_another_stage(self):
        out = netlogo.apply_art(self.sc, self.ART)            # its milestone is in stage 1, built after the data
        a, b = scene.compile_scene(out)["reading"]["clock"]["phase"]
        top = out["reading"]["clock"]["top"]
        self.assertAlmostEqual(b, 0.0, delta=0.01)
        self.assertAlmostEqual(a * top + b, 0.41, delta=0.01)   # the data's stage: the first half of the build

    def test_art_rewords_the_reading_and_nothing_else_of_it(self):
        out = netlogo.apply_art(self.sc, dict(self.ART, reading={"how": ["Each line is a walker."]}))
        self.assertEqual(out["reading"]["how"], ["Each line is a walker."])
        self.assertEqual(out["reading"]["clock"], self.sc["reading"]["clock"])
        self.assertIsNone(netlogo.lock_problem(out))
        with self.assertRaises(netlogo.NetLogoError):
            netlogo.apply_art(self.sc, dict(self.ART, reading={"how": ["x"], "clock": {"label": "day"}}))

    def test_the_critic_of_a_run(self):
        from . import critic, prompts
        out = netlogo.apply_art(self.sc, self.ART)
        brief = critic._run_brief(out)
        self.assertIn("ticks", [f["key"] for f in brief["facts"]])
        self.assertTrue(brief["reading"] and brief["legend"])
        pk = {"title": out["title"], "scene_sha256": "0" * 64, "request": "readable", "pairs": [], "renders": ["renders/hero.png"],
              "identity": [{"feature": "Half infected", "parts": ["milestone"]}], "run": brief}
        text = critic.packet_text(pk)
        self.assertIn("construct of a NetLogo run", text)              # the run's critic, not the object's
        self.assertIn("The recording's facts", text)
        self.assertNotIn("No reference images", text)
        run_prompt = prompts.build()["critic-run.md"]
        for word in ("accuracy", "critical", "major", "minor", "student"):
            self.assertIn(word, run_prompt)

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


class Mcp(unittest.TestCase):
    """The NetLogo tools over MCP: instrument a model, draw a run with solids and colours, export it."""

    def test_a_run_with_music_takes_its_features(self):
        from . import mcp_server
        with tempfile.TemporaryDirectory() as d:
            n = 12
            music = {"track": "beat.wav", "sha256": "", "ticks-per-second": 30, "ticks": n, "features": "beat-audio-30.json"}
            text = Path(recording(Path(d, "m.jsonl"), header={"music": music})).read_text()
        feats = {"fps": 30, "energy": [0.5] * n, "high": [0.1] * n, "kick": [0.0] * n, "onset": [0.0] * n}
        res = json.loads(mcp_server._call_netlogo("construct_netlogo_draw", {"recording": text, "view": "space-time",
                                                                             "features": feats})["content"][0]["text"])
        self.assertEqual((res["scene"]["reading"]["music"]["seconds"], res["data_lock"]), (0.4, "intact"))
        res = json.loads(mcp_server._call_netlogo("construct_netlogo_draw", {"recording": text, "view": "space-time"})
                         ["content"][0]["text"])
        self.assertIn("MCP: features", res["error"])

    def test_instrument_draw_export(self):
        import base64
        import sys
        from . import export
        with tempfile.TemporaryDirectory() as d:
            run = recording(Path(d, "run.jsonl")).read_text(encoding="utf-8")
        call = lambda i, name, args: {"jsonrpc": "2.0", "id": i, "method": "tools/call",
                                      "params": {"name": name, "arguments": args}}
        msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                call(2, "construct_netlogo_instrument", {"model": MODEL, "title": "Contagion", "turtles": ["infected?"],
                                                         "seed": 3, "ticks": 40}),
                call(3, "construct_netlogo_draw", {"recording": run, "view": "network-time", "state": "infected?",
                                                   "solid": True, "materials": True,
                                                   "art": {"credit": "Claude Opus 5.5", "reading": {"how": ["Read it up."]}}}),
                call(4, "construct_netlogo_draw", {"recording": "{not json", "view": "phase"})]
        r = subprocess.run([sys.executable, "-m", __package__ + ".mcp_server"], cwd=HERE.parent, capture_output=True,
                           text=True, input="".join(json.dumps(m) + "\n" for m in msgs))
        out = {x["id"]: x for x in (json.loads(l) for l in r.stdout.splitlines() if l.strip())}
        inst = out[2]["result"]["structuredContent"]
        self.assertIn('__includes ["construct.nls"]', inst["model"])
        self.assertIn("random-seed 3", inst["experiment"])
        self.assertIn("to construct-record", inst["recorder"])
        drawn = out[3]["result"]["structuredContent"]
        self.assertEqual((drawn["data_lock"], drawn["scene"]["reading"]["how"]), ("intact", ["Read it up."]))
        self.assertTrue(any(p["id"] == "node-0" for p in drawn["scene"]["parts"]))
        self.assertTrue(out[4]["result"]["isError"])
        glb, _ = export.render(drawn["scene"], "glb", "tubes", materials=drawn["materials"])
        doc, _ = export.read_glb(glb["glb"])
        self.assertIn("node-0", {n.get("name") for n in doc["nodes"]})


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
            r = headless(folder, "--model", str(Path(d, "m-construct.nlogox")), "--setup-file",
                         str(Path(d, "construct-experiment.xml")), "--experiment", "construct", "--threads", "1", "--table", "-")
            self.assertEqual(r.returncode, 0, r.stdout[-1500:] + r.stderr[-1500:])
            run = netlogo.read_run(Path(d, "run.jsonl"))
            self.assertEqual((run["header"]["seed"], run["end"]), (4, 30))
            self.assertEqual(len(run["frames"]), 31)
            for view, opts in (("space-time", {}), ("network-time", {"state": "infected?"}), ("phase", {})):
                if view == "network-time":
                    continue   # this model has no links
                self.assertEqual(scene.validate(netlogo.scene_from_run(run, view, **opts)), [])


@unittest.skipUnless(NETLOGO and JAVAC, "set CONSTRUCT_NETLOGO and CONSTRUCT_JAVAC (Java 17 or newer) to run")
class Extension(unittest.TestCase):
    """The NetLogo extension: built, loaded by NetLogo beside a model, its recording the same as construct.nls's."""

    def test_build_record_and_draw(self):
        root, folder = HERE.parent, Path(NETLOGO)
        java = netlogo_java(folder)
        jar = netlogo_jar(folder)
        with tempfile.TemporaryDirectory() as d:
            subprocess.run([sys.executable, str(root / "scripts" / "build_netlogo_extension.py"), "--netlogo", NETLOGO,
                            "--javac", JAVAC, "--out", d], check=True, capture_output=True)
            z = zipfile.ZipFile(next(Path(d).glob("construct-*.zip")))
            self.assertIn("construct.jar", z.namelist())
            self.assertIn("construct_hologram/netlogo.py", z.namelist())
            manifest = zipfile.ZipFile(io.BytesIO(z.read("construct.jar"))).read("META-INF/MANIFEST.MF").decode()
            self.assertIn("Class-Manager: construct.netlogo.ConstructExtension", manifest)
            self.assertIn("NetLogo-Extension-API-Version: 7.0", manifest)
            z.extractall(Path(d, "construct"))
            subprocess.run([JAVAC, "--release", "17", "-cp", str(jar), "-d", d, str(root / "hosts/netlogo/test/Drive.java")],
                           check=True)
            Path(d, "m.nlogox").write_text(MODEL.replace("turtles-own", "extensions [construct]\nturtles-own"),
                                           encoding="utf-8")

            def drive(*commands):   # silent: construct:play keeps time with the clock, never sounding
                return subprocess.run([str(java), "-Djava.awt.headless=true", "-cp", os.pathsep.join([str(jar), d]), "Drive",
                                       str(Path(d, "m.nlogox"))] + list(commands), cwd=d, capture_output=True, text=True,
                                      timeout=600, env=dict(os.environ, CONSTRUCT_SILENT="1"))
            r = drive('random-seed 4 setup construct:start "Contagion" construct:seed 4 '
                      'construct:track-turtles ["infected?"] construct:track-reporter "infected" [-> count turtles with [infected?]] '
                      'construct:record', "repeat 30 [ go construct:record ]", "construct:finish", '(construct:draw "space-time" "max-agents" 10 "time" "sqrt" "model" true)')
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            ext = netlogo.read_run(Path(d, "contagion-run.jsonl"))
            self.assertEqual((ext["header"]["seed"], ext["header"]["reporters"], ext["end"], len(ext["frames"])),
                             (4, ["infected"], 30, 31))
            self.assertTrue(Path(d, "contagion-construct", "construct.html").is_file())
            self.assertTrue(Path(d, "contagion-construct", "run.glb").stat().st_size > 1000)   # "model" true: the 3D model
            self.assertEqual(json.loads(Path(d, "contagion-construct", "audit.json").read_text())["errors"], [])
            r = drive("random-seed 4", "construct:run-for 20")              # one command: setup, run, draw
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("ran m for 20 runs of go", r.stdout)
            self.assertIn("view: space-time", r.stdout)
            self.assertEqual(len(netlogo.read_run(Path(d, "m-run.jsonl"))["frames"]), 21)
            r = drive("setup construct:record")
            self.assertIn("construct:start first", r.stdout)
            r = drive('setup construct:start "C" construct:record', '(construct:draw "phase" "y" "infected")')
            self.assertIn('no option "y"', r.stdout)
            r = drive('setup construct:start "F" construct:record', "repeat 8 [ tick-advance 0.25 construct:record ]",
                      "construct:record", "construct:finish")    # a clock in fractions: every step, each once
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            frac = netlogo.read_run(Path(d, "f-run.jsonl"))
            self.assertEqual(([f["t"] for f in frac["frames"]][-3:], len(frac["frames"]), frac["end"]), ([1.5, 1.75, 2], 9, 2))

            r = drive('setup construct:start "Film" construct:record', "repeat 6 [ go construct:record ]", "construct:finish",
                      '(construct:draw "space-time" "film" true)')   # the run as a film: a .blend, if Blender is here
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            from . import runfilm
            if runfilm.find_blender():
                self.assertTrue(Path(d, "film-construct", "film.blend").is_file(), r.stdout)
                self.assertIn("film.blend", r.stdout)
            else:
                self.assertIn("no film: Blender was not found", r.stdout)
            r = drive("setup show construct:kick")
            self.assertIn('construct:music "track.mp3" first', r.stdout)
            if shutil.which("ffmpeg"):   # music: a tick is a moment of the track, and the run lasts it
                import math
                import struct
                import wave
                with wave.open(str(Path(d, "t.wav")), "wb") as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(16000)
                    w.writeframes(struct.pack("<32000h", *(int(9000 * math.sin(i / 9)) for i in range(32000))))
                r = drive('(construct:music "t.wav" 10)', "random-seed 4", "construct:run")
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn("for the length of t.wav", r.stdout)
                run = netlogo.read_run(Path(d, "m-run.jsonl"))
                self.assertEqual((run["header"]["music"]["ticks-per-second"], run["header"]["music"]["ticks"], run["end"]),
                                 (10, 20, 20))
                self.assertTrue(Path(d, "m-construct", "t.wav").is_file())   # the track beside the page
                r = drive('(construct:music "t.wav" 10)', "setup repeat 5 [ go ] show construct:music-time "
                                                         "show construct:energy >= 0")
                self.assertIn("0.5", r.stdout)
                self.assertIn("true", r.stdout)
                r = drive('(construct:music "t.wav" 10)', "setup construct:play reset-timer repeat 10 [ go construct:sync ] "
                                                         "show timer construct:stop-music")   # live: in time with the track
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                took = float(next(ln for ln in reversed(r.stdout.splitlines()) if ln.startswith("observer:")).split(":")[1])
                self.assertTrue(0.9 <= took <= 1.6, r.stdout)        # 10 ticks at 10 a second: a second
                self.assertIn("keeps time with the clock", r.stdout)

            # NetLogo 3D: each turtle's height last in its row, the world's depth in the header, no 3D patches
            Path(d, "m3.nlogox3d").write_text(MODEL3D, encoding="utf-8")
            r = subprocess.run([str(java), "-Djava.awt.headless=true", "-cp", os.pathsep.join([str(jar), d]), "Drive",
                                str(Path(d, "m3.nlogox3d")), "random-seed 2", "construct:run-for 5"], cwd=d,
                               capture_output=True, text=True, timeout=600)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            run3 = netlogo.read_run(Path(d, "m3-run.jsonl"))
            h3 = run3["header"]
            self.assertEqual((h3.get("zcor"), h3["world"]["min-pzcor"], h3["world"]["max-pzcor"], h3["patch-reporter"]),
                             (True, -4, 4, ""))
            self.assertEqual({len(row) for f in run3["frames"] for row in f["turtles"]}, {6})
            self.assertTrue(all(-4.5 <= row[5] <= 4.5 for f in run3["frames"] for row in f["turtles"]))

            # the same run through construct.nls: the same turtles, tick by tick
            Path(d, "plain.nlogox").write_text(MODEL, encoding="utf-8")
            self.assertEqual(cli.main(["netlogo-instrument", str(Path(d, "plain.nlogox")), "--title", "Contagion", "--out",
                                       str(Path(d, "nls")), "--turtles", "infected?", "--seed", "4", "--ticks", "30"]), 0)
            r = headless(folder, "--model", str(Path(d, "nls", "plain-construct.nlogox")), "--setup-file",
                         str(Path(d, "nls", "construct-experiment.xml")), "--experiment", "construct", "--threads", "1",
                         "--table", "-")
            self.assertEqual(r.returncode, 0, r.stderr[-1500:])
            nls = netlogo.read_run(Path(d, "nls", "run.jsonl"))
            self.assertEqual([f["turtles"] for f in ext["frames"]], [f["turtles"] for f in nls["frames"]])


if __name__ == "__main__":
    unittest.main()
