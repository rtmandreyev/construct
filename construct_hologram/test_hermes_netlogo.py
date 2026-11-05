"""Tests for the Hermes plugin's NetLogo tools (hosts/hermes/construct/netlogo_*.py): their schemas and registration,
their refusals, drawing recorded runs without NetLogo, and (when NetLogo and a Java are found: CONSTRUCT_NETLOGO,
the usual install places, or a NetLogo folder one level under the home folder) a headless run of an installed
Models Library model ending in a published construct that the other tools work on, three seeded runs compared
and summarised, and a run shown growing while it runs. No Models Library file is copied into the repository: the
library model is the one installed here, read at test time, and the other models are written by the tests."""

import importlib.util
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

from . import netlogo
from .test_hermes_plugin import FakeContext, generator, media_paths
from .test_netlogo import MODEL, recording

LIBRARY_PICKS = ("Fireflies", "Simple Viral Marketing", "Flocking")


def _netlogo_folder():
    """NetLogo's folder for the tests: CONSTRUCT_NETLOGO, else the plugin's own search, else a NetLogo folder one
    level under the home folder (a developer's unpacked copy)."""
    given = os.environ.get("CONSTRUCT_NETLOGO")
    if given and Path(given).is_dir():
        return str(Path(given))
    for p in sorted(Path.home().glob("*/NetLogo 7*"), reverse=True):
        if (p / "app").is_dir():
            return str(p)
    return None


# a small contagion model of the tests' own (no library code), with a setting that slows each tick down on request
SLOW = MODEL.replace("to go\n", "to go\n  repeat slowness [ set busy sin random 360 ]\n").replace(
    "turtles-own [ infected? ]", "turtles-own [ infected? ]\nglobals [ busy ]").replace(
    "</widgets>",
    '  <button x="10" y="10" height="40" disableUntilTicks="false" forever="false" kind="Observer" width="80">setup</button>\n'
    '    <button x="10" y="60" height="40" disableUntilTicks="true" forever="true" kind="Observer" width="80">go</button>\n'
    '    <slider x="10" step="100" y="110" max="1000000" width="150" display="slowness" height="50" min="0" '
    'direction="Horizontal" default="0.0" variable="slowness"></slider>\n  </widgets>')
LICENSED = MODEL.replace("</widgets>", "</widgets>\n  <info><![CDATA[## HOW TO CITE\n\nFor the model itself:\n\n"
                                       "* Someone, A. (2001).  NetLogo Test model.  http://ccl.northwestern.edu/netlogo/"
                                       "models/Test.\n\n## COPYRIGHT AND LICENSE\n\nCopyright 2001 A. Someone.\n\nThis "
                                       "model is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike "
                                       "3.0 License.]]></info>")


class Base(unittest.TestCase):
    """The generated package, loaded as Hermes loads it, its data folder and NetLogo setting in a temporary place."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.pkg = generator.build(Path(cls.tmp.name) / "dist")
        name = "construct_netlogo_plugin_under_test_%s" % cls.__name__
        spec = importlib.util.spec_from_file_location(name, cls.pkg / "__init__.py", submodule_search_locations=[str(cls.pkg)])
        cls.mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.mod
        spec.loader.exec_module(cls.mod)
        cls.folder = _netlogo_folder()
        cls.ctx = FakeContext({"netlogo_folder": cls.folder} if cls.folder else {})
        cls.mod.register(cls.ctx)
        cls.events = []
        cls.mod.jobs.set_reporters(post=cls.ctx.post_message, event=lambda n, p: cls.events.append((n, p)))
        cls.data = Path(cls.tmp.name) / "data"
        cls.mod.runtime.configure(data=cls.data)
        cls.nt = cls.mod.netlogo_tools
        cls.nt._found["at"] = 0.0
        cls.found = cls.nt.find_netlogo(fresh=True)
        cls.module_name = name

    @classmethod
    def tearDownClass(cls):
        for fn in cls.ctx.unload:
            fn()
        sys.modules.pop(cls.module_name, None)
        cls.tmp.cleanup()

    def call(self, name, args=None):
        out = self.ctx.tools[name]["handler"](args if args is not None else {}, task_id="t", session_id="s")
        self.assertIsInstance(out, str)
        return json.loads(out)

    def until_done(self, result, seconds=300):
        deadline = time.time() + seconds
        while result.get("state") == "running" and time.time() < deadline:
            time.sleep(1.0)
            result = self.call("construct_job", {"job_id": result["job_id"]})
        return result

    def model(self, text, name="contagion"):
        path = Path(self.tmp.name) / "models" / ("%s.nlogox" % name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def published(self, r):
        """A result that ends in a construct shown like any other: its loader, its page and card, its scene."""
        self.assertTrue(r.get("success"), r)
        (loader,) = media_paths(r)
        self.assertEqual(loader.name, "loader.html")
        self.assertEqual(r["media_tag"], "MEDIA:%s" % loader)
        self.assertEqual(r["file_path"], str(loader))
        self.assertTrue(loader.with_name("construct.html").is_file())
        card = json.loads(loader.with_name("card.json").read_text(encoding="utf-8"))
        self.assertEqual((card["project"], card["build"], card["source"]), (r["project"], r["build"], "netlogo"))
        self.assertTrue(loader.resolve().is_relative_to(self.data.resolve()))
        scene = json.loads(Path(r["files"]["scene"]).read_text(encoding="utf-8"))
        self.assertIsNone(netlogo.lock_problem(scene))
        return loader, scene

    def items(self, project):
        return json.loads((self.data / "shown" / project / "items.json").read_text(encoding="utf-8"))


class Tools(Base):
    """Registration, schemas and refusals: no NetLogo needed."""

    def test_registered_with_schemas_that_teach(self):
        for name in ("construct_netlogo_run", "construct_netlogo_draw"):
            t = self.ctx.tools[name]
            self.assertEqual(t["toolset"], "construct")
            schema = t["schema"]
            self.assertEqual(schema["name"], name)
            self.assertGreater(len(schema["description"]), 80)

            def typed(props, where):
                for k, v in props.items():
                    self.assertIn("type", v, "%s.%s" % (where, k))
                    self.assertTrue(v.get("description"), "%s.%s" % (where, k))
                    if v["type"] == "object" and "properties" in v:
                        typed(v["properties"], "%s.%s" % (where, k))
            typed(schema["parameters"]["properties"], name)
        self.assertIs(self.ctx.tools["construct_netlogo_run"]["check_fn"], self.nt.ready)
        self.assertTrue(self.ctx.tools["construct_netlogo_draw"]["check_fn"]())   # the runtime alone
        self.assertEqual(set(self.mod.netlogo_tools.HANDLERS), {"construct_netlogo_run", "construct_netlogo_draw"})

    def test_check_fn_hides_the_run_without_netlogo(self):
        saved = self.nt._candidates
        try:
            self.nt._candidates = lambda: []
            self.nt._found["at"] = 0.0
            self.assertFalse(self.nt.ready())
            r = self.call("construct_netlogo_run", {"model": "Flocking"})
            self.assertIn("NetLogo was not found", r["error"])
            self.assertIsNone(self.call("construct_netlogo_run", {"search": "flock"})["netlogo"])
        finally:
            self.nt._candidates = saved
            self.nt._found["at"] = 0.0
            self.nt.find_netlogo(fresh=True)

    def test_refusals_never_raise(self):
        bad = [("construct_netlogo_run", {}), ("construct_netlogo_run", {"nonsense": 1}),
               ("construct_netlogo_run", {"search": 5}),
               ("construct_netlogo_run", {"model": "/no/such/model.nlogox"}),
               ("construct_netlogo_draw", {}),
               ("construct_netlogo_draw", {"recordings": ["relative.jsonl"]}),
               ("construct_netlogo_draw", {"recordings": ["/no/such/run.jsonl"]}),
               ("construct_netlogo_draw", {"recordings": "x"}),
               ("construct_netlogo_draw", {"project": "no-such-project"}),
               ("construct_netlogo_draw", {"project": "Bad Slug"}),
               ("construct_netlogo_draw", {"recordings": ["/tmp/a.jsonl"], "project": "x"})]
        for name, args in bad:
            with self.subTest(name=name, args=args):
                self.assertIn("error", self.call(name, args))
        for garbage in (None, [], "x", 3):
            for name in ("construct_netlogo_run", "construct_netlogo_draw"):
                out = self.ctx.tools[name]["handler"](garbage)
                self.assertIsInstance(json.loads(out), dict)
        rec = recording(Path(self.tmp.name) / "refuse.jsonl")
        for args, words in (({"view": "sideways"}, "view must be"), ({"options": {"wobble": 1}}, "unknown option"),
                            ({"options": {"levels": 1}}, "levels must be"), ({"options": {"window": "soon"}}, "window"),
                            ({"labels": ["a", "b"]}, "2 labels for 1"), ({"art": "/no/art.json"}, "no art layer"),
                            ({"options": "x"}, "options must be")):
            with self.subTest(args=args):
                self.assertIn(words, self.call("construct_netlogo_draw", dict(args, recordings=[str(rec)]))["error"])
        r = self.call("construct_netlogo_draw", {"recordings": [str(rec), str(rec)], "model_3d": True})
        self.assertIn("one recording", r["error"])
        if self.found:
            v6 = Path(self.tmp.name) / "old.nlogo"
            v6.write_text("old", encoding="utf-8")
            self.assertIn("NetLogo 6", self.call("construct_netlogo_run", {"model": str(v6)})["error"])
            m = self.model(SLOW, "refusals")
            for args, words in (({"constants": {"no-such-slider": 1}}, "no setting"), ({"runs": 0}, "runs must be"),
                                ({"model_3d": True, "runs": 2}, "model_3d is for one run"),
                                ({"turtles": "infected?"}, "turtles must be a list"),
                                ({"setup": "x ]]> y"}, "setup must be")):
                with self.subTest(args=args):
                    self.assertIn(words, self.call("construct_netlogo_run", dict(args, model=str(m)))["error"])
            self.assertIn("no model named", self.call("construct_netlogo_run", {"model": "No Such Model Anywhere"})["error"])

    def test_a_recording_that_is_not_one_fails_as_a_job(self):
        junk = Path(self.tmp.name) / "junk.jsonl"
        junk.write_text("not json\n", encoding="utf-8")
        r = self.until_done(self.call("construct_netlogo_draw", {"recordings": [str(junk)]}))
        self.assertEqual(r["state"], "failed")
        self.assertIn("not JSON", r["error"] + r.get("log", ""))

    def test_what_is_recorded_without_being_told_and_the_models_credit(self):
        child = self.mod.netlogo_child
        rec = child.auto_record(MODEL)
        self.assertEqual(rec["turtles"], ["infected?"])
        self.assertEqual(rec["reporters"], [])
        self.assertEqual(rec["patches"], ("pcolor", 1))
        breeds = MODEL.replace("turtles-own [ infected? ]",
                               "breed [ wolves wolf ]\nbreed [ sheep a-sheep ]\nsheep-own [ fed? ]\nturtles-own [ energy ]")
        rec = child.auto_record(breeds)
        self.assertEqual((rec["turtles"], rec["reporters"]), ([], ["count wolves", "count sheep"]))
        self.assertIsNone(child.credit_of(MODEL, "/x/m.nlogox"))
        c = child.credit_of(LICENSED, "/x/Test.nlogox")
        self.assertEqual(c["licence"], "CC BY-NC-SA 3.0")
        self.assertIn("Someone, A. (2001)", c["citation"])
        self.assertEqual(c["copyright"], "© 2001 A. Someone")
        self.assertEqual(c["url"], "http://ccl.northwestern.edu/netlogo/models/Test")
        lib = child.credit_of(MODEL, "/lib/models/Sample/m.nlogox", "/lib/models")
        self.assertTrue(lib["library"])
        self.assertIsNone(lib["licence"])
        settings = child.model_settings(SLOW)
        self.assertEqual(settings["slowness"]["kind"], "slider")

    def test_the_package_bundles_no_netlogo_model_or_run(self):
        for p in self.pkg.rglob("*"):
            self.assertFalse(p.suffix.lower().startswith((".nlogo", ".jsonl")), p)


class Draw(Base):
    """Recorded runs drawn into projects (no NetLogo)."""

    def test_one_recording_drawn_and_the_project_works_with_the_other_tools(self):
        rec = recording(Path(self.tmp.name) / "drawn.jsonl", frames=20)
        r = self.until_done(self.call("construct_netlogo_draw", {"recordings": [str(rec)], "title": "Drawn run",
                                                                 "model_3d": True}))
        loader, scene = self.published(r)
        project = r["project"]
        folder = self.data / "projects" / project
        self.assertEqual(Path(r["files"]["recordings"][0]).resolve(), (folder / "run.jsonl").resolve())
        self.assertEqual(scene["title"], "Drawn run")
        self.assertTrue(Path(r["files"]["glb"]).read_bytes().startswith(b"glTF"))
        self.assertTrue((folder / "scene.materials.json").is_file())
        kinds = {i["kind"] for i in self.items(project)}
        self.assertTrue({"run", "export", "file"} <= kinds, kinds)
        self.assertIn("netlogo-plates", r["next"])

        info = self.call("construct_inspect", {"project": project})
        self.assertNotIn("error", info)
        self.assertIn("verified", info["parts"]["by_certainty"])
        check = self.until_done(self.call("construct_check", {"project": project}))
        self.assertEqual((check["ok"], check["needs_repair"]), (True, False), check)
        e = self.until_done(self.call("construct_export", {"project": project, "format": "glb"}))
        self.assertTrue(e.get("success"), e)
        (glb,) = media_paths(e)
        self.assertEqual(glb.read_bytes()[:4], b"glTF")

        # drawn again, another view, into the same project: the project's scene follows
        again = self.until_done(self.call("construct_netlogo_draw", {"project": project, "view": "phase",
                                                                     "options": {"smooth": 3}}))
        _, sc = self.published(again)
        self.assertEqual(again["view"], "phase")
        self.assertEqual(json.loads((folder / "project.json").read_text())["scene"], Path(again["files"]["scene"]).name)
        self.assertEqual(self.call("construct_inspect", {"project": project})["title"], sc["title"])

    def test_runs_compared_and_a_model_beside_the_recording_credited(self):
        d = Path(self.tmp.name) / "credited"
        d.mkdir()
        (d / "Test.nlogox").write_text(LICENSED, encoding="utf-8")
        a = recording(d / "a.jsonl", frames=10)
        b = recording(d / "b.jsonl", frames=16, header={"seed": 9})
        r = self.until_done(self.call("construct_netlogo_draw", {"recordings": [str(a), str(b)],
                                                                 "labels": ["short", "long"]}))
        _, scene = self.published(r)
        self.assertEqual(len(r["runs"]), 2)
        self.assertIn("short", scene["title"])
        self.assertIn("model", {s["id"] for s in scene["sources"]})
        self.assertEqual(r["credit"]["licence"], "CC BY-NC-SA 3.0")
        readme = Path(r["credit"]["readme"]).read_text(encoding="utf-8")
        self.assertIn("CC BY-NC-SA 3.0", readme)
        self.assertIn("Someone, A. (2001)", readme)
        self.assertIn("model_licence", {f["key"] for f in scene["facts"]})


@unittest.skipUnless(_netlogo_folder() or os.environ.get("CONSTRUCT_NETLOGO"),
                     "NetLogo was not found (set CONSTRUCT_NETLOGO to NetLogo's folder to run)")
class Headless(Base):
    """NetLogo itself, run headless by the plugin."""

    def setUp(self):
        if not (self.found and self.found.get("java")):
            self.skipTest("NetLogo or a Java to run it was not found")

    def library_model(self):
        models = self.nt.library_models(self.found)
        for name in LIBRARY_PICKS:
            if any(m.stem == name for m in models):
                return name
        self.skipTest("none of %s is in the installed library" % ", ".join(LIBRARY_PICKS))

    def test_a_library_model_run_and_the_project_with_the_other_tools(self):
        name = self.library_model()
        found = self.call("construct_netlogo_run", {"search": name.split()[0].lower()})
        self.assertIn(name, [m["name"] for m in found["models"]])
        constants = {"Fireflies": {"number": 150}, "Flocking": {"population": 60}}.get(name, {})
        r = self.until_done(self.call("construct_netlogo_run", {"model": name, "ticks": 40, "seed": 11,
                                                                "constants": constants}))
        loader, scene = self.published(r)
        project = r["project"]
        folder = self.data / "projects" / project
        self.assertEqual(r["run"]["seed"], 11)
        self.assertLessEqual(r["run"]["ticks"], 40)
        self.assertEqual(Path(r["files"]["recording"]).resolve(), (folder / "run.jsonl").resolve())
        self.assertEqual(netlogo.read_run(folder / "run.jsonl")["header"]["seed"], 11)
        # the library's licence travels with everything made from the model, and nothing of it leaves the project
        self.assertEqual(r["credit"]["licence"], "CC BY-NC-SA 3.0")
        self.assertIn("Wilensky", r["credit"]["line"])
        self.assertIn("CC BY-NC-SA 3.0", (folder / "README.md").read_text(encoding="utf-8"))
        self.assertIn("model", {s["id"] for s in scene["sources"]})
        self.assertIn("Wilensky", scene["subject"]["summary"])
        self.assertTrue(list((folder / "netlogo").glob("*-construct.nlogox")))
        self.assertIn("run", {i["kind"] for i in self.items(project)})
        self.assertEqual(self.events[-1][0], "run.preview")
        self.assertTrue(self.events[-1][1]["final"])
        # an ordinary project for every other tool
        self.assertEqual(self.call("construct_inspect", {"project": project})["title"], scene["title"])
        check = self.until_done(self.call("construct_check", {"project": project}))
        self.assertEqual((check["ok"], check["needs_repair"]), (True, False), check)
        e = self.until_done(self.call("construct_export", {"project": project, "format": "glb"}))
        self.assertTrue(e.get("success"), e)
        self.assertEqual(media_paths(e)[0].read_bytes()[:4], b"glTF")

    def test_three_seeded_runs_compared_and_summarised(self):
        m = self.model(SLOW, "three")
        r = self.until_done(self.call("construct_netlogo_run", {
            "model": str(m), "runs": 3, "seed": 20, "ticks": 25, "reporters": ["count turtles with [infected?]"],
            "turtles": ["infected?"], "view": "space-time"}))
        _, scene = self.published(r)
        folder = self.data / "projects" / r["project"]
        self.assertEqual(r["summary"]["runs"], 3)
        self.assertEqual(r["summary"]["seeds"], [20, 21, 22])
        final = r["summary"]["final"]["count turtles with [infected?]"]
        self.assertTrue(final["min"] <= final["median"] <= final["max"] <= 20)
        self.assertEqual(r["compared"], 3)
        self.assertEqual(sorted(p.name for p in (folder / "runs").glob("*.jsonl")),
                         ["run-20.jsonl", "run-21.jsonl", "run-22.jsonl"])
        seeds = [netlogo.read_run(p)["header"]["seed"] for p in sorted((folder / "runs").glob("*.jsonl"))]
        self.assertEqual(seeds, [20, 21, 22])
        self.assertEqual(json.loads((folder / "summary.json").read_text())["runs"], 3)
        self.assertEqual(sum(1 for s in scene["sources"] if s["id"].startswith("run-")), 3)
        kinds = [i["kind"] for i in self.items(r["project"])]
        self.assertEqual((kinds.count("run"), kinds.count("compare")), (3, 1))
        self.assertNotIn("credit", r)   # the tests' own model names no licence

    def test_a_model_whose_go_fails_says_so(self):
        m = self.model(SLOW.replace("repeat slowness [ set busy sin random 360 ]", "set busy 1 / (ticks - 4)"), "failing")
        r = self.until_done(self.call("construct_netlogo_run", {"model": str(m), "ticks": 20, "seed": 1}))
        self.published(r)
        self.assertEqual(r["run"]["ticks"], 4)
        self.assertFalse(r["run"]["stopped_by_itself"])
        self.assertIn("go ran 20 times but the clock stopped at tick 4", r["warning"])

    def test_a_run_shown_growing_while_it_runs(self):
        m = self.model(SLOW, "growing")
        saved = self.nt.QUICK
        self.nt.QUICK = 1
        start = len(self.events)
        try:
            # slow ticks: the run takes some seconds, so the first answer is a preview and the job
            first = self.call("construct_netlogo_run", {"model": str(m), "ticks": 400, "seed": 5,
                                                        "constants": {"slowness": 200000}})
        finally:
            self.nt.QUICK = saved
        if first.get("state") != "running":
            self.skipTest("the run ended before a preview (a very fast machine)")
        self.assertIn("job_id", first)
        self.assertIn("preview", first, first)
        (loader,) = media_paths(first)
        self.assertTrue(loader.is_file())
        self.assertIn("running: tick", loader.with_name("construct.html").read_text(encoding="utf-8")[:4000] +
                      json.dumps(first["preview"]))
        self.assertGreater(first["progress"].get("total", 0), 0)
        final = self.until_done(first)
        self.published(final)
        self.assertNotEqual(final["build"], first["preview"]["build"])
        seen = [p for n, p in self.events[start:] if n == "run.preview"]
        self.assertFalse(seen[0]["final"])
        self.assertTrue(seen[-1]["final"])
        self.assertEqual(seen[-1]["build"], final["build"])
        self.assertTrue(all(p["project"] == first["project"] and p["job_id"] == first["job_id"] for p in seen))
        self.assertEqual(sum(1 for p in seen if p["final"]), 1)


if __name__ == "__main__":
    unittest.main()
