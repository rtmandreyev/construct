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
        self.tools, self.hooks, self.skills, self.unload = {}, {}, {}, []
        self.config = dict(config or {})
        self.cron = None
        self.posted = []

    def register_tool(self, name, toolset, schema, handler, check_fn=None, requires_env=None, is_async=False,
                      description="", emoji="", override=False):
        assert name not in self.tools
        self.tools[name] = {"toolset": toolset, "schema": schema, "handler": handler, "check_fn": check_fn}

    def register_hook(self, hook_name, callback, *, hold_stream=False):
        self.hooks[hook_name] = callback

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
                    "examples/cd.json", "examples/volkswagen-t1-samba.json", "examples/assets/disc-cover.png",
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
        self.assertEqual(len(m["provides_tools"]), 9)
        self.assertEqual(set(m["provides_hooks"]), set(self.ctx.hooks))
        self.assertTrue(all(t["toolset"] == "construct" and t["schema"]["name"] == n for n, t in self.ctx.tools.items()))
        self.assertTrue(all(t["check_fn"]() for t in self.ctx.tools.values()))
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
        mentioned = re.findall(r"`(construct_[a-z]+)`", (self.pkg / "skills" / "construct" / "SKILL.md").read_text())
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
        for area in ("TOOL_MEDIA_RENDERER_AREA", "ROUTES_AREA", "SIDEBAR_NAV_AREA"):
            self.assertIn("typeof sdk.%s === 'string'" % area, js)   # feature-detected, never a named import

    # ------------------------------------------------------------------ the tools, end to end

    def test_start_menu_lists_sources(self):
        menu = self.call("construct_start")
        self.assertIn("cd", menu["examples"])
        self.assertIn("volkswagen-t1-samba", menu["examples"])
        self.assertNotIn("volkswagen-t1-samba.materials", menu["examples"])
        self.assertIn("case / jewel", menu["archetypes"])
        self.assertIn("browser", menu["programs"])

    def test_cd_end_to_end(self):
        r = self.call("construct_start", {"example": "cd", "title": "Test CD"})
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
        self.assertEqual(text, template.replace("__TITLE__", "Test CD"))   # nothing of the construct in it
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
        shutil.copyfile(HERE / "examples" / "v2" / "lighthouse.json", src)
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
        issues = c["fit"]["issues"]
        self.assertTrue(issues)
        self.assertTrue(all(len(i["parts"]) == 2 and i["fix"] and i["code"] in ("pokes", "buried") for i in issues))
        mirror = [i for i in issues if set(i["parts"]) == {"mirror-arm", "mirror-head"}]
        self.assertTrue(mirror, [i["parts"] for i in issues])
        self.assertIn("mirror-head", mirror[0]["fix"])

    @unittest.skipUnless(CAPTURE and FFMPEG, "a film needs a Chromium-family browser and ffmpeg")
    def test_film_runs_as_a_job(self):
        r = self.call("construct_start", {"example": "cd"})
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
        r = self.call("construct_start", {"example": "lighthouse"})
        a = self.call("construct_film", {"project": r["project"], "seconds": 120, "size": "320x200"})
        b = self.call("construct_film", {"project": r["project"], "seconds": 120, "size": "320x200"})
        c = self.call("construct_job", {"job_id": a["job_id"], "cancel": True})
        self.assertTrue(c["cancelled"])
        self.assertEqual(self.until_done(c, 30)["state"], "failed")
        self.mod.jobs.stop_all()   # what ctx.on_unload runs
        self.assertEqual(self.until_done(self.call("construct_job", {"job_id": b["job_id"]}), 30)["state"], "failed")

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
        r = self.call("construct_start", {"example": "cd"})
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
        r = self.call("construct_start", {"example": "book"})
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
