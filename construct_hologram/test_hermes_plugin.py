"""Tests for the Hermes plugin (hosts/hermes/construct, packaged by scripts/hermes_plugin.py): the package's contents,
its manifest against what it registers, every tool end to end on real scenes, the loader, the backend's refusals
and the Desktop half's forbidden patterns. Captures and films run when a browser (and ffmpeg) are installed."""

import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

from . import params, render, scene as scene_mod, studio

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
V2 = HERE / "examples" / "v2"
CAPTURE = bool(render.find_browser()) and os.environ.get("HOLOGRAM_SKIP_CAPTURE") != "1"
FFMPEG = shutil.which("ffmpeg") is not None
BINARY_MAGIC = (b"\x7fELF", b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"MZ", b"\0asm")


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


generator = _load(ROOT / "scripts" / "hermes_plugin.py", "hermes_plugin_generator")


def manifest(path):
    """plugin.yaml's top-level scalars and flow lists (the subset this manifest uses), without a YAML library."""
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([a-z_]+):\s*(.*)$", line)
        if not m:
            continue
        key, value = m.groups()
        if value.startswith("["):
            out[key] = [v.strip() for v in value.strip("[]").split(",") if v.strip()]
        else:
            out[key] = value.strip().strip('"')
    return out


class FakeContext:
    """The parts of Hermes's PluginContext the plugin uses, recording what it registers."""

    def __init__(self, config=None):
        self.tools, self.hooks, self.skills, self.unload, self.commands = {}, {}, {}, [], {}
        self.config = dict(config or {})
        self.cron = None
        self.posted = []

    def register_tool(self, name, toolset, schema, handler, check_fn=None, requires_env=None, is_async=False,
                      description="", emoji="", override=False):
        assert name not in self.tools
        self.tools[name] = {"toolset": toolset, "schema": schema, "handler": handler, "check_fn": check_fn}

    def register_hook(self, hook_name, callback, *, hold_stream=False):
        self.hooks[hook_name] = callback

    def register_command(self, name, handler, description="", args_hint="", argument_mode=None):
        assert name not in self.commands
        self.commands[name] = {"handler": handler, "description": description, "args_hint": args_hint}

    def register_skill(self, name, path, description="", frontmatter=None):
        assert Path(path).is_file(), path
        self.skills[name] = {"path": Path(path), "description": description, "frontmatter": frontmatter}

    def on_unload(self, callback):
        self.unload.append(callback)

    def get_config(self, key, default=None):
        return self.config.get(key, default)

    def current_cron_execution(self):
        return self.cron

    def session_surface(self):
        return "desktop"

    def post_message(self, text):
        self.posted.append(text)

        class Handle:
            def edit(_, t):
                self.posted.append(t)
        return Handle()


def media_paths(result):
    paths = []
    for line in result.get("media", []):
        assert line.startswith("MEDIA:/"), line
        paths.append(Path(line[len("MEDIA:"):]))
    return paths


class Plugin(unittest.TestCase):
    """The generated package, loaded as Hermes loads it, with its data folder in a temporary directory."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.pkg = generator.build(Path(cls.tmp.name) / "dist")
        spec = importlib.util.spec_from_file_location("construct_plugin_under_test", cls.pkg / "__init__.py",
                                                      submodule_search_locations=[str(cls.pkg)])
        cls.mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.mod
        spec.loader.exec_module(cls.mod)
        cls.ctx = FakeContext()
        cls.mod.register(cls.ctx)
        cls.data = Path(cls.tmp.name) / "data"
        cls.mod.runtime.configure(data=cls.data)
        cls.api = _load(cls.pkg / "dashboard" / "plugin_api.py", "construct_plugin_api_under_test")

    @classmethod
    def tearDownClass(cls):
        for fn in cls.ctx.unload:
            fn()
        sys.modules.pop("construct_plugin_under_test", None)
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

    # ------------------------------------------------------------------ the package

    def test_package_is_complete(self):
        for rel in ("plugin.yaml", "__init__.py", "schemas.py", "tools.py", "jobs.py", "runtime.py", "child.py",
                    "templates/loader.html", "desktop/plugin.js", "dashboard/manifest.json", "dashboard/plugin_api.py",
                    "skills/construct/SKILL.md", "skills/construct/references/craft.md",
                    "skills/construct/references/trace-prompt.md", "README.md", "LICENSE", "NOTICE",
                    "examples/catalog.json", "examples/braun-sk4-knob/scene.json", "examples/kestrel-v2/scene.json",
                    "examples/volkswagen-t1-samba/scene.materials.json", "examples/vespa-gs150/kit-plan.json",
                    "examples/sainte-chapelle/thumb.jpg", "skills/construct/tutorials/01-copy-your-thing.md",
                    "scene_edit.py", "readback.py", "stock.py", "commands.py",
                    "_vendor/construct_hologram/viewer/hologram.js", "_vendor/construct_hologram/construct.nls"):
            self.assertTrue((self.pkg / rel).is_file(), rel)
        sub = _load(ROOT / "scripts" / "hermes_submission.py", "hermes_submission_for_test")
        for module in sub.RUNTIME:
            self.assertEqual((self.pkg / "_vendor" / "construct_hologram" / module).read_bytes(), (HERE / module).read_bytes(),
                             module)
        self.assertFalse(list(self.pkg.glob("plugin.js")), "a root plugin.js would win over desktop/plugin.js")
        self.assertNotIn("python3 TOOLS", (self.pkg / "skills" / "construct" / "references" / "rounds.md").read_text())

    def test_package_has_no_bytecode_binaries_or_environ_misuse(self):
        for p in self.pkg.rglob("*"):
            rel = p.relative_to(self.pkg)
            self.assertNotIn("__pycache__", rel.parts, rel)
            self.assertFalse(p.is_symlink(), rel)
            if not p.is_file():
                continue
            self.assertNotIn(p.suffix, (".pyc", ".pyo", ".so", ".pyd", ".whl", ".wasm", ".dylib", ".dll", ".exe"), rel)
            head = p.read_bytes()[:4]
            self.assertFalse(any(head.startswith(m) for m in BINARY_MAGIC), rel)
            if p.suffix == ".py":
                for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                    # Hermes's scanner: os.environ other than .get(...) outside comments is a HIGH finding
                    self.assertIsNone(re.search(r"^[^#\n]*os\.environ\b(?!\s*\.get\s*\()", line), "%s:%d" % (rel, n))
                    self.assertNotIn("os.system(", line, "%s:%d" % (rel, n))
                    self.assertNotIn("shell=True", line, "%s:%d" % (rel, n))
            self.assertLess(p.stat().st_size, 1024 * 1024, rel)
        self.assertNotRegex((self.pkg / "README.md").read_text(encoding="utf-8"), r"/Users/[A-Za-z]|/home/[a-z]")

    def test_package_is_deterministic(self):
        def digest(root):
            h = hashlib.sha256()
            for p in sorted(x for x in root.rglob("*") if x.is_file()):
                h.update(str(p.relative_to(root)).encode() + b"\0" + p.read_bytes())
            return h.hexdigest()
        with tempfile.TemporaryDirectory() as other:
            self.assertEqual(digest(self.pkg), digest(generator.build(Path(other))))

    def test_manifest_matches_what_register_registers(self):
        m = manifest(self.pkg / "plugin.yaml")
        self.assertEqual(m["name"], "construct")
        self.assertEqual(m["version"], "0.1.0")
        self.assertEqual(m["license"], "Apache-2.0")
        self.assertEqual(m["requires_hermes"], ">=0.22")
        self.assertEqual(m["homepage"], "https://github.com/rtmandreyev/construct")
        self.assertEqual(set(m["provides_tools"]), set(self.ctx.tools))
        self.assertEqual(len(m["provides_tools"]), 12)
        self.assertEqual(set(m["provides_hooks"]), set(self.ctx.hooks))
        self.assertTrue(all(t["toolset"] == "construct" and t["schema"]["name"] == n for n, t in self.ctx.tools.items()))
        # every tool shows while the runtime is there; the NetLogo run only where NetLogo and Java are found
        self.assertTrue(all(t["check_fn"]() for n, t in self.ctx.tools.items() if n != "construct_netlogo_run"))
        self.assertIsInstance(self.ctx.tools["construct_netlogo_run"]["check_fn"](), bool)
        skill = self.ctx.skills["construct"]
        self.assertTrue(skill["description"])
        self.assertEqual(skill["frontmatter"]["metadata"]["hermes"]["requires_tools"], ["construct_start", "construct_build"])
        self.assertTrue(self.ctx.unload)
        api = json.loads((self.pkg / "dashboard" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual((api["name"], api["api"]), ("construct", "plugin_api.py"))

    def test_schemas_follow_construct(self):
        s = self.mod.schemas
        self.assertEqual(s.ARCHETYPES, sorted(params.VARIANTS))
        self.assertEqual(s.CATEGORIES, sorted(studio.STARTER))
        self.assertEqual(tuple(s.PALETTES), scene_mod.PALETTES)
        self.assertEqual(tuple(s.IDENTITIES), scene_mod.IDENTITIES)
        self.assertEqual(tuple(s.SHEETS), render.SHEETS)
        for t in s.TOOLS:
            self.assertTrue(t["name"].startswith("construct_"))
            self.assertGreater(len(t["description"]), 80, t["name"])
            self.assertEqual(t["parameters"]["type"], "object")
            for name, prop in t["parameters"]["properties"].items():
                self.assertIn("type", prop, "%s.%s" % (t["name"], name))
        mentioned = re.findall(r"`(construct_[a-z_]+)`", (self.pkg / "skills" / "construct" / "SKILL.md").read_text())
        self.assertTrue(set(mentioned) <= set(s.NAMES))
        self.assertEqual(set(mentioned), set(s.NAMES))

    # ------------------------------------------------------------------ the Desktop half

    def test_plugin_js_stays_inside_the_sdk(self):
        js = (self.pkg / "desktop" / "plugin.js").read_text(encoding="utf-8")
        self.assertNotRegex(js, r"(?i)<script")
        self.assertNotRegex(js, r"\beval\s*\(|new\s+Function\s*\(|\bimport\s*\(")
        self.assertNotRegex(js, r"createElement\s*\(\s*['\"]script|webview|data-slot|data-testid|\.observe\(\s*document\.body")
        self.assertNotIn("window.hermesDesktop", js)
        specs = re.findall(r"^\s*import\s[^'\"]*['\"]([^'\"]+)['\"]", js, re.M)
        self.assertEqual(set(specs), {"@hermes/plugin-sdk", "react", "react/jsx-runtime"})
        self.assertIn("id: ID", js)
        self.assertIn("const ID = 'construct'", js)
        for area in ("TOOL_MEDIA_RENDERER_AREA", "ROUTES_AREA", "SIDEBAR_NAV_AREA", "PALETTE_AREA"):
            self.assertIn("typeof sdk.%s === 'string'" % area, js)   # feature-detected, never a named import

    # ------------------------------------------------------------------ the tools, end to end

    def test_a_card_shown_before_an_update_gets_the_current_loader(self):
        old = '<!doctype html>\n<html lang="en" data-page="assembly.html">\n<head><title>Villa Savoye kit</title></head>OLD'
        new = self.api._current_loader(old)
        self.assertNotIn("OLD", new)
        self.assertIn("<title>Villa Savoye kit</title>", new)
        self.assertIn('data-page="assembly.html"', new)
        self.assertIn(".kc{display:none", new)
        self.assertEqual(self.api._current_loader("not a loader"), "not a loader")

    def test_a_command_that_wrote_its_output_with_problems_has_not_failed(self):
        # `construct kit` exits 1 when it lists problems to fix, after writing the kit: that is not a failure
        jobs = sys.modules["construct_plugin_under_test.jobs"]
        self.assertEqual(jobs.outcome({"code": 0}, ""), "done")
        self.assertEqual(jobs.outcome({"code": 1}, "kit: drawing step 3 of 3\nwrote kit: 20 pieces on 1 plate\n  37 (wall) is 1.3 mm thick"), "warned")
        self.assertEqual(jobs.outcome({"code": 1}, "error: no scene"), "failed")
        self.assertEqual(jobs.outcome({"code": 2}, "wrote x\ncapture not possible"), "failed")

    def test_start_menu_lists_sources(self):
        menu = self.call("construct_start")
        names = [e["name"] for e in menu["examples"]]
        self.assertEqual(set(names), set(self.mod.stock.STOCK))
        self.assertEqual(len(names), 16)
        for e in menu["examples"]:
            self.assertTrue(e["title"] and e["line"] and e["parts"] > 0, e)
        self.assertEqual(next(e for e in menu["examples"] if e["name"] == "kestrel-v2")["parts"], 498)
        self.assertIn("case / jewel", menu["archetypes"])
        self.assertIn("browser", menu["programs"])

    def test_cd_end_to_end(self):
        r = self.call("construct_start", {"from_path": str(V2 / "cd.json"), "title": "Test CD"})
        self.assertNotIn("error", r)
        project, scene = r["project"], Path(r["scene"])
        self.assertTrue(scene.is_file())
        self.assertTrue(scene.resolve().is_relative_to(self.data.resolve()))
        self.assertTrue((scene.parent / "assets" / "disc-cover.png").is_file())   # the artwork it names came along

        check = self.call("construct_check", {"project": project})
        self.assertEqual((check["ok"], check["needs_repair"], check["errors"]), (True, False, 0))

        info = self.call("construct_inspect", {"project": project})
        self.assertEqual(info["title"], "Test CD")
        self.assertEqual(info["parts"]["count"], 6)
        self.assertIn("decorative", info["parts"]["by_certainty"])
        self.assertTrue(info["articulations"]["items"])

        b = self.call("construct_build", {"project": project})
        self.assertTrue(b.get("success"), b)
        self.assertEqual(b["parts"], 6)
        self.assertTrue(b["audit"]["ok"])
        (loader,) = media_paths(b)
        self.assertEqual(loader.name, "loader.html")
        self.assertEqual(b["media_tag"], "MEDIA:%s" % loader)
        page = loader.with_name("construct.html")
        self.assertTrue(page.is_file() and Path(b["page"]).is_file())
        text = loader.read_text(encoding="utf-8")
        self.assertLess(len(text.encode("utf-8")), 200 * 1024)
        template = (self.pkg / "templates" / "loader.html").read_text(encoding="utf-8")
        self.assertEqual(text, template.replace("__TITLE__", "Test CD").replace("__PAGE__", "construct.html"))   # nothing of the construct in it
        geometry = (Path(b["page"]).parent / "geometry.json").read_text(encoding="utf-8")
        self.assertNotIn(geometry[200:400], text)

        # the backend serves it, by ids only
        listed = self.api.projects(self.data)
        self.assertIn(project, [p["project"] for p in listed])
        view = self.api.view(self.data, project, b["build"])
        self.assertEqual(view["html"], page.read_text(encoding="utf-8"))
        self.assertEqual(view["loader"], text)
        self.assertEqual(view["card"]["parts"], 6)
        if CAPTURE:
            self.assertTrue(self.api.thumb(self.data, project)["data_url"].startswith("data:image/png;base64,"))

        e = self.call("construct_export", {"project": project, "format": "glb", "pieces": "glued"})
        self.assertTrue(e.get("success"), e)
        (glb,) = media_paths(e)
        self.assertEqual(glb.read_bytes()[:4], b"glTF")
        self.assertTrue(glb.resolve().is_relative_to(self.data.resolve()))

        p = self.call("construct_export", {"project": project, "format": "3mf", "size_mm": 80})
        self.assertTrue(p.get("success"), p)
        self.assertIn("printable", p)

        if CAPTURE:
            rv = self.call("construct_review", {"project": project, "sheets": ["views"], "size": "640x400"})
            rv = self.until_done(rv)
            self.assertTrue(rv.get("success"), rv)
            shown = media_paths(rv)
            self.assertTrue(shown and all(x.is_file() and x.suffix == ".png" for x in shown))
            self.assertIn("hero", rv["images"])

    def test_params_document_end_to_end(self):
        r = self.call("construct_start", {"archetype": "object", "variant": "synth", "title": "A Synth"})
        self.assertEqual(r["kind"], "parameter document")
        self.assertTrue(r["scene"].endswith("scene.params.json"))
        self.assertTrue(self.call("construct_check", {"project": r["project"]})["ok"])
        b = self.call("construct_build", {"project": r["project"], "thumbnail": False})
        self.assertTrue(b.get("success"), b)
        self.assertEqual(b["title"], "A Synth")

    def test_scene_by_path_writes_into_a_project(self):
        src = Path(self.tmp.name) / "elsewhere" / "lamp.json"
        src.parent.mkdir()
        shutil.copyfile(V2 / "lighthouse.json", src)
        r = self.call("construct_check", {"scene": str(src)})
        self.assertTrue(r.get("ok"), r)
        b = self.call("construct_build", {"scene": str(src), "thumbnail": False})
        self.assertTrue(b.get("success"), b)
        self.assertTrue(Path(b["page"]).resolve().is_relative_to(self.data.resolve()))
        self.assertEqual(sorted(p.name for p in src.parent.iterdir()), ["lamp.json"])   # nothing written beside it

    def test_inspect_t1_reads_its_record(self):
        r = self.call("construct_start", {"example": "volkswagen-t1-samba"})
        self.assertTrue(Path(r["project_dir"], "scene.materials.json").is_file())
        info = self.call("construct_inspect", {"project": r["project"]})
        groups = info["parts"]["by_certainty"]
        self.assertEqual(sum(g["count"] for g in groups.values()), info["parts"]["count"])
        self.assertIn("designed", groups)
        self.assertIn("wheelbase 2.4 m", info["dimensions"]["verified"])
        self.assertEqual(len(info["articulations"]["items"]), 9)
        self.assertTrue(all(re.match(r"^-?[0-9.]+ (deg|m)$", a["travel"]) for a in info["articulations"]["items"]))
        self.assertEqual(info["authoring"]["tier"], "masterpiece")
        self.assertGreater(info["authoring"]["rounds"]["count"], 0)
        self.assertTrue(any(s.get("ref", "").startswith("https://") for s in info["sources"]["items"]))
        self.assertLess(len(json.dumps(info)), 24000)

    def test_check_fit_t1_names_parts_and_fixes(self):
        r = self.call("construct_start", {"example": "volkswagen-t1-samba"})
        c = self.until_done(self.call("construct_check", {"project": r["project"], "fit": True}))
        self.assertIn("fit", c, json.dumps(c)[:1500])
        issues = c["fit"]["issues"]
        self.assertTrue(issues)
        self.assertTrue(all(i["fix"] and (len(i["parts"]) == 2 and i["code"] in ("pokes", "buried", "crosses-glass") or
                                          len(i["parts"]) == 1 and i["code"] == "open") for i in issues), issues)
        mirror = [i for i in issues if set(i["parts"]) == {"mirror-arm", "mirror-head"}]
        self.assertTrue(mirror, [i["parts"] for i in issues])
        self.assertIn("mirror-head", mirror[0]["fix"])

    @unittest.skipUnless(CAPTURE and FFMPEG, "a film needs a Chromium-family browser and ffmpeg")
    def test_film_runs_as_a_job(self):
        r = self.call("construct_start", {"from_path": str(V2 / "cd.json")})
        f = self.call("construct_film", {"project": r["project"], "seconds": 1, "fps": 12, "size": "320x200"})
        self.assertIn(f.get("state"), ("running", "done"), f)   # a one-second film may end while the call waits
        done = self.until_done(self.call("construct_job", {"job_id": f["job_id"]}), 240)
        self.assertTrue(done.get("success"), done)
        (mp4,) = media_paths(done)
        self.assertTrue(mp4.is_file() and mp4.suffix == ".mp4")
        self.assertEqual(self.call("construct_job", {"job_id": f["job_id"]})["file_path"], done["file_path"])  # kept
        self.assertIn(f["job_id"], [j["job_id"] for j in self.call("construct_job")["jobs"]])

    @unittest.skipUnless(CAPTURE and FFMPEG, "a film needs a Chromium-family browser and ffmpeg")
    def test_jobs_stop_on_cancel_and_unload(self):
        r = self.call("construct_start", {"from_path": str(V2 / "lighthouse.json")})
        a = self.call("construct_film", {"project": r["project"], "seconds": 120, "size": "320x200"})
        b = self.call("construct_film", {"project": r["project"], "seconds": 120, "size": "320x200"})
        c = self.call("construct_job", {"job_id": a["job_id"], "cancel": True})
        self.assertTrue(c["cancelled"])
        self.assertEqual(self.until_done(c, 30)["state"], "failed")
        self.mod.jobs.stop_all()   # what ctx.on_unload runs
        self.assertEqual(self.until_done(self.call("construct_job", {"job_id": b["job_id"]}), 30)["state"], "failed")

    # ------------------------------------------------------------------ edit, inspect sizes, verified exports, jobs

    def test_edit_by_part_id(self):
        r = self.call("construct_start", {"example": "braun-sk4-knob"})
        project, scene = r["project"], Path(r["scene"])
        before = json.loads(scene.read_text(encoding="utf-8"))
        body = next(p for p in before["parts"] if p["id"] == "knob-body")
        ops = [{"op": "move", "part": "knob-body", "by": [0, 0.001, 0]},
               {"op": "set", "part": "knob-*", "field": "look.weight", "value": 1.3},
               {"op": "add_fact", "fact": {"key": "test-depth", "value": 0.02, "unit": "m", "certainty": "user_supplied",
                                           "source": before["sources"][0]["id"]}},
               {"op": "certainty", "part": "knob-body", "certainty": "inferred", "basis": ["test-depth"]}]
        dry = self.call("construct_edit", {"project": project, "operations": ops, "dry_run": True})
        self.assertFalse(dry["written"], dry)
        self.assertEqual(json.loads(scene.read_text(encoding="utf-8")), before)
        e = self.call("construct_edit", {"project": project, "operations": ops})
        self.assertTrue(e["written"], e)
        self.assertTrue(e["check"]["ok"], e["check"])
        self.assertEqual(e["applied"][0]["changes"][0]["before"], body["at"])
        self.assertAlmostEqual(e["applied"][0]["changes"][0]["after"][1], body["at"][1] + 0.001)
        self.assertGreater(len(e["applied"][1]["changes"]), 1)   # the pattern matched every knob part
        after = json.loads(scene.read_text(encoding="utf-8"))
        self.assertEqual(next(p for p in after["parts"] if p["id"] == "knob-body")["basis"], ["test-depth"])
        self.assertEqual(json.loads(Path(e["undo"]).read_text(encoding="utf-8")), before)
        # an edit that breaks the scene is not written, and names its step
        bad = self.call("construct_edit", {"project": project, "operations": [
            {"op": "move", "part": "knob-body", "by": [0, 0.001, 0]}, {"op": "set", "part": "knob-body", "field": "role", "value": "nope"}]})
        self.assertFalse(bad["written"])
        self.assertTrue(bad["introduced"])
        self.assertIn("new_problems", bad["applied"][1])
        self.assertEqual(json.loads(scene.read_text(encoding="utf-8")), after)
        for refused in ([{"op": "set", "path": "assets.0.path", "value": "/etc/passwd"}],
                        [{"op": "set", "path": "notes", "value": {"path": "../../outside.png"}}],
                        [{"op": "move", "part": "no-such-part", "by": [0, 0, 0]}],
                        [{"op": "set", "part": "knob-body", "field": "id", "value": "x"}], [{"op": "launch"}], []):
            out = self.call("construct_edit", {"project": project, "operations": refused})
            self.assertFalse(out.get("written"), refused)
            self.assertIn("error", out, refused)
        self.assertEqual(json.loads(scene.read_text(encoding="utf-8")), after)
        outside = Path(self.tmp.name) / "outside-edit" / "knob.json"
        outside.parent.mkdir()
        shutil.copyfile(scene, outside)
        self.assertIn("outside the projects", self.call("construct_edit", {"scene": str(outside), "operations": ops[:1]})["error"])

    def test_inspect_gives_the_body_apart_from_what_stands_out(self):
        r = self.call("construct_start", {"example": "volkswagen-t1-samba"})
        size = self.call("construct_inspect", {"project": r["project"]})["size"]
        self.assertEqual(size["unit"], "m")
        self.assertLess(size["body"]["width"], size["overall"]["width"])
        self.assertAlmostEqual(size["body"]["width"], 1.77, delta=0.03)   # the bus is 1.72-1.75 m wide, not its mirrors
        self.assertIn("mirror-head", [x["part"] for x in size["stands_out"]["width"]])
        self.assertIn("wide", size["say"])
        knob = self.call("construct_start", {"example": "braun-sk4-knob"})
        self.assertEqual(self.call("construct_inspect", {"project": knob["project"]})["size"]["unit"], "mm")

    def test_export_is_read_back(self):
        r = self.call("construct_start", {"example": "volkswagen-t1-samba"})
        glb = self.until_done(self.call("construct_export", {"project": r["project"], "format": "glb"}))
        v = glb["verified"]
        self.assertGreater(v["named_parts"], 200)
        self.assertIn("open", [a["name"] for a in v["animations"]])
        self.assertAlmostEqual(v["bounds"]["m"][2], 4.24, delta=0.05)
        self.assertIn("MB GLB", glb["summary"])
        self.assertIn("4240", glb["summary"])
        self.assertTrue(glb["item"])
        self.assertIn("no need to open the file", glb["next"])
        stl = self.until_done(self.call("construct_export", {"project": r["project"], "format": "stl", "size_mm": 80}))
        self.assertAlmostEqual(max(stl["verified"]["bounds"]["mm"]), 80, delta=2)
        self.assertGreater(stl["verified"]["triangles"], 1000)
        tmf = self.until_done(self.call("construct_export", {"project": r["project"], "format": "3mf", "size_mm": 80}))
        self.assertEqual(tmf["verified"]["triangles"], stl["verified"]["triangles"])
        obj = self.until_done(self.call("construct_export", {"project": r["project"], "format": "obj"}))
        self.assertGreater(obj["verified"]["objects"], 200)
        # the Constructs page lists them, and serves the model by id
        row = self.api.project(self.data, r["project"])
        exports = [i for i in row["items"] if i["kind"] == "export"]
        self.assertEqual(len(exports), 4)
        got = self.api.item(self.data, r["project"], glb["item"])
        self.assertTrue(got["data_url"].startswith("data:model/gltf-binary;base64,"))
        self.assertEqual(got["summary"]["named_parts"], v["named_parts"])

    def test_readback_step_and_fcstd(self):
        rb = self.mod.readback
        step = Path(self.tmp.name) / "box.step"
        step.write_text("ISO-10303-21;\nHEADER;FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));ENDSEC;DATA;\n"
                        "#1=PRODUCT('lid','lid','',(#9));\n#2=PRODUCT('base','base','',(#9));\n"
                        "#3=MANIFOLD_SOLID_BREP('',#4);\n#5=ADVANCED_FACE('',(#6),#7,.T.);\n#7=PLANE('',#8);\n"
                        "#10=CARTESIAN_POINT('',(0.,0.,0.));\n#11=CARTESIAN_POINT('',(120.,40.,25.5));\n"
                        "#12=VERTEX_POINT('',#10);\n#13=VERTEX_POINT('',#11);\n"
                        "#14=(LENGTH_UNIT()NAMED_UNIT(*)SI_UNIT(.MILLI.,.METRE.));\nENDSEC;END-ISO-10303-21;\n")
        got = rb.read(step)
        self.assertEqual((got["products"], got["solids"], got["faces"]), (2, 1, 1))
        self.assertEqual(got["part_names"], ["lid", "base"])
        self.assertEqual(got["bounds"]["mm"], [120.0, 40.0, 25.5])
        self.assertEqual(got["bounds"]["m"], [0.12, 0.04, 0.0255])
        made = rb.construct_report("wrote x.step: 12 named parts, 2 joints\n  true shapes (exact solids, splines, NURBS): 9 of 12 parts\n")
        self.assertEqual((made["parts"], made["joints"], made["exact"], made["faceted"]), (12, 2, 9, 3))
        bad = Path(self.tmp.name) / "bad.glb"
        bad.write_bytes(b"not a model")
        self.assertIn("error", rb.read(bad))

    def test_step_export_counts_exact_shapes(self):
        if not self.mod.runtime.programs().get("freecad"):
            self.skipTest("STEP export needs FreeCAD")
        r = self.call("construct_start", {"example": "braun-sk4-knob"})
        st = self.until_done(self.call("construct_export", {"project": r["project"], "format": "step"}), 400)
        self.assertTrue(st.get("success"), st)
        v = st["verified"]
        self.assertGreater(v["solids"], 0)
        self.assertIn("exact", v["construct"])
        self.assertIn("exact CAD shapes", st["summary"])

    def test_job_waits_instead_of_sleeping(self):
        r = self.call("construct_start", {"example": "braun-sk4-knob"})
        b = self.call("construct_command", {"argv": ["check", "scene.json", "--json"], "project": r["project"],
                                            "wait_seconds": 1})
        if b.get("state") == "running":
            done = self.call("construct_job", {"job_id": b["job_id"], "wait_seconds": 120})
            self.assertEqual(done["state"], "done")
            self.assertLess(done["waited_s"], 120)
        self.assertIn("error", self.call("construct_job", {"job_id": "0" * 12, "wait_seconds": 5}))
        self.assertIn("error", self.call("construct_job", {"job_id": "abc", "wait_seconds": 999}))

    def test_every_shipped_construct_compiles(self):
        for name, files in self.mod.runtime.examples().items():
            code, out, err = self.mod.runtime.run_child("cli", "check", str(files["scene"]), "--json", timeout=300)
            report = json.loads(out)
            self.assertEqual(report["errors"], 0, (name, report.get("repair_text")))
            self.assertIsNotNone(report["stats"], name)
        catalog = json.loads((self.pkg / "examples" / "catalog.json").read_text(encoding="utf-8"))
        self.assertEqual([c["name"] for c in catalog], list(self.mod.stock.STOCK))
        self.assertTrue(all(c["has_thumb"] for c in catalog))
        self.assertTrue(self.api.example_thumb("garden-shed", self.pkg)["data_url"].startswith("data:image/jpeg;base64,"))
        with self.assertRaises(self.api.NotFound):
            self.api.example_thumb("../secret", self.pkg)

    # ------------------------------------------------------------------ kits, the Constructs page, /construct, tutorials

    def test_kit_opens_with_its_steps_and_booklet(self):
        r = self.call("construct_start", {"example": "braun-sk4-knob"})
        k = self.until_done(self.call("construct_command", {"argv": ["kit", "scene.json", "--size", "60", "--out", "kit"],
                                                            "project": r["project"]}), 400)
        self.assertIn(k.get("exit"), (0, 1), k)
        kit = k["kit"]
        (loader,) = [p for p in media_paths(k) if p.name == "loader.html"]
        self.assertEqual(loader.parent.parent.name, "kits")
        self.assertIn('data-page="assembly.html"', loader.read_text(encoding="utf-8"))
        page = self.api.kit(self.data, r["project"], kit["kit"], "assembly")
        self.assertIn('id="hologram-geometry"', page["html"])
        booklet = self.api.kit(self.data, r["project"], kit["kit"], "booklet")["html"]
        self.assertNotRegex(booklet, r"src=['\"]img/")   # its pictures are inside it now
        self.assertIn("data:image/", booklet)
        self.assertNotRegex(booklet, r"(?i)<script")
        self.assertGreater(kit["pieces"], 0)
        row = self.api.project(self.data, r["project"])
        self.assertEqual(row["kits"][0]["kit"], kit["kit"])
        for bad in (("x", "assembly"), (kit["kit"], "../../x"), ("../" + kit["kit"], "booklet")):
            with self.assertRaises(self.api.NotFound):
                self.api.kit(self.data, r["project"], *bad)

    def test_constructs_page_groups_projects(self):
        a = self.call("construct_start", {"example": "garden-shed"})
        b = self.call("construct_start", {"example": "garden-shed"})
        self.assertNotEqual(a["project"], b["project"])
        for r in (a, b):
            self.assertTrue(self.call("construct_build", {"project": r["project"], "thumbnail": False}).get("success"))
        rows = {x["project"]: x for x in self.api.projects(self.data)}
        self.assertEqual(rows[a["project"]]["title"], rows[b["project"]]["title"])
        self.assertFalse(rows[a["project"]]["changed_since"])
        self.call("construct_edit", {"project": a["project"], "operations": [{"op": "set", "path": "subject.accuracy",
                                                                               "value": "approximate"}]})
        time.sleep(0.01)
        self.assertTrue(self.api.project(self.data, a["project"])["changed_since"])
        self.assertFalse(self.api.project(self.data, b["project"])["changed_since"])
        # a file is served only through the index, from inside its own project
        index = self.data / "shown" / a["project"] / "items.json"
        secret = Path(self.tmp.name) / "secret.glb"
        secret.write_bytes(b"glTF")
        self.mod.runtime.write_json(index, [{"id": "20260101-000000-abcd", "kind": "export", "path": str(secret),
                                             "name": "secret.glb"}])
        with self.assertRaises(self.api.NotFound):
            self.api.item(self.data, a["project"], "20260101-000000-abcd")
        with self.assertRaises(self.api.NotFound):
            self.api.item(self.data, a["project"], "../x")

    def test_slash_command(self):
        handle = self.mod.commands.handle
        r = self.call("construct_start", {"example": "braun-sk4-knob"})
        self.call("construct_build", {"project": r["project"], "thumbnail": False})
        self.assertIn(r["project"], handle(""))
        events = []
        opened = handle("open " + r["project"], event=lambda n, p: events.append((n, p)))
        self.assertIn("newest build", opened)
        self.assertEqual(events, [("open", {"project": r["project"]})])
        self.assertIn("No project", handle("open nothing-like-it"))
        self.assertIn("kestrel-v2", handle("examples"))
        self.assertIn("skill_view", handle("learn 1"))
        self.assertIn("Simulations", handle("learn"))
        self.assertTrue(handle("jobs"))
        self.assertIn("/construct", handle("what"))
        self.assertIn("construct", self.ctx.commands)

    def test_tutorials_are_data_the_skill_and_page_share(self):
        rows = self.api.tutorials(self.pkg)
        files = sorted((self.pkg / "skills" / "construct" / "tutorials").glob("*.md"))
        self.assertEqual(len(rows), len(files))
        self.assertGreaterEqual(len(rows), 16)
        self.assertEqual([t["order"] for t in rows], sorted(t["order"] for t in rows))
        examples = set(self.mod.stock.STOCK)
        for t in rows:
            self.assertIn(t["file"], t["prompt"], t["id"])   # the message names the file the skill reads
            self.assertLessEqual(len(t["prompt"]), 500, t["id"])
            self.assertIn(t["group"], ("Everyday", "Makers and creators", "Simulations"), t["id"])
            self.assertIn(t["status"], ("ready", "placeholder"))
            if t["example"]:
                self.assertIn(t["example"], examples, t["id"])
            self.assertIn("## Steps", (self.pkg / "skills" / "construct" / t["file"]).read_text(encoding="utf-8"))
        self.assertIn("tutorials/", (self.pkg / "skills" / "construct" / "SKILL.md").read_text(encoding="utf-8"))

    def test_three_is_bundled_with_its_licence(self):
        js = (self.pkg / "desktop" / "plugin.js").read_text(encoding="utf-8")
        self.assertNotIn(generator.THREE_MARK, js)
        self.assertIn("var THREE_BUNDLE=", js)
        self.assertIn("three.js r180 (npm three@0.180.0)", js)
        self.assertIn("Permission is hereby granted, free of charge", js)
        self.assertLess(len(js.encode("utf-8")), 1024 * 1024)
        if shutil.which("node"):
            import subprocess
            with tempfile.TemporaryDirectory() as t:
                copy = Path(t) / "plugin.mjs"
                copy.write_text(js, encoding="utf-8")
                r = subprocess.run(["node", "--check", str(copy)], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)

    # ------------------------------------------------------------------ refusals

    def test_handlers_never_raise(self):
        for name in self.ctx.tools:
            for bad in (None, {"nonsense": 1}, {"project": "../../etc"}, {"project": 5}, {"scene": "/no/such.json"},
                        {"job_id": "zz"}, {"argv": "ls"}):
                out = self.call(name, bad)
                self.assertIsInstance(out, dict)
                if bad is not None or name not in ("construct_start", "construct_job"):
                    self.assertIn("error", out, (name, bad))

    def test_command_is_guarded(self):
        r = self.call("construct_start", {"from_path": str(V2 / "cd.json")})
        project = r["project"]
        refused = [["author", "a lamp", "--base-url", "http://x", "--model", "m", "--out", "o"],
                   ["trace-image", "a.png"], ["critique", "scene.json", "--base-url", "http://x"],
                   ["rounds", "run"], ["build", "scene.json", "--out", "/tmp/elsewhere"],
                   ["export", "scene.json", "--out=../../../outside.glb"], ["ls", "-la"], ["template", "cd"]]
        for argv in refused:
            self.assertIn("error", self.call("construct_command", {"argv": argv, "project": project}), argv)
        ok = self.call("construct_command", {"argv": ["params", "--list"], "project": project})
        self.assertEqual(ok["exit"], 0, ok)
        self.assertIn("case / jewel", ok["output"])
        wrote = self.call("construct_command", {"argv": ["expand", "scene.json", "--output", "expanded.json"],
                                                "project": project})
        self.assertEqual(wrote["exit"], 0, wrote)
        self.assertTrue(any(f.endswith("expanded.json") for f in wrote["files"]), wrote)
        self.assertIn("error", self.call("construct_command", {"argv": ["expand", "scene.json"], "project": "nope"}))

    def test_backend_refuses_traversal(self):
        r = self.call("construct_start", {"from_path": str(V2 / "book.json")})
        self.call("construct_build", {"project": r["project"], "thumbnail": False})
        outside = Path(self.tmp.name) / "secret"
        (outside / "20260101-000000-abcd").mkdir(parents=True)
        (outside / "20260101-000000-abcd" / "construct.html").write_text("<!doctype html>secret")
        (outside / "20260101-000000-abcd" / "loader.html").write_text("x")
        os.symlink(outside, self.data / "shown" / "linked")
        for project, build in (("../secret", None), ("..", None), ("linked", None), ("linked", "20260101-000000-abcd"),
                               (r["project"], "../../secret/20260101-000000-abcd"), (r["project"], "x"), ("", None),
                               ("UPPER", None), (r["project"] + "/..", None)):
            with self.assertRaises(self.api.NotFound, msg=(project, build)):
                self.api.view(self.data, project, build)
        self.assertNotIn("linked", [p["project"] for p in self.api.projects(self.data)])
        if getattr(self.api, "router", None) is not None:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            app = FastAPI()
            app.include_router(self.api.router)
            self.api.data_dir = lambda: self.data
            client = TestClient(app)
            self.assertEqual(client.get("/view", params={"project": "../secret"}).status_code, 404)
            self.assertEqual(client.get("/view", params={"project": r["project"]}).status_code, 200)
            self.assertEqual(client.get("/projects").status_code, 200)

    def test_approval_gate(self):
        gate = self.ctx.hooks["pre_tool_call"]
        self.assertIsNone(gate(tool_name="construct_review", args={}))   # off by default
        self.ctx.config["confirm_runs"] = True
        try:
            self.mod.runtime.configure(config=self.ctx.get_config)
            self.assertIsNone(gate(tool_name="construct_check", args={}))
            self.assertIsNone(gate(tool_name="terminal", args={}))
            ask = gate(tool_name="construct_film", args={})
            self.assertEqual(ask["action"], "approve")
            self.assertIn("ffmpeg", ask["message"])
            self.assertEqual(gate(tool_name="construct_export", args={"format": "step"})["action"], "approve")
            self.assertIsNone(gate(tool_name="construct_export", args={"format": "glb"}))
            self.assertEqual(gate(tool_name="construct_command", args={"argv": ["netlogo-film", "r.jsonl"]})["action"],
                             "approve")
            self.ctx.cron = object()
            self.assertEqual(gate(tool_name="construct_review", args={})["action"], "block")
        finally:
            self.ctx.cron = None
            self.ctx.config.pop("confirm_runs")


if __name__ == "__main__":
    unittest.main()
