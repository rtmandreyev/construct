"""Tests for the host packages: structure, frontmatter, manifests and an isolated run."""

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from . import package

HERE = Path(__file__).resolve().parent


def frontmatter(path):
    fields, body = package.split_frontmatter(path.read_text(encoding="utf-8"))
    return fields, body


class Packages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.roots = package.build(Path(cls.tmp.name) / "dist")
        cls.hermes = cls.roots["hermes"]
        cls.claude = cls.roots["claude-code"]
        cls.claude_skill = cls.claude / "skills" / package.NAME

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_hermes_frontmatter_follows_its_conventions(self):
        fields, body = frontmatter(self.hermes / "SKILL.md")
        self.assertEqual(fields["name"], "hologram-studio")
        self.assertEqual(fields["version"], package.VERSION)
        self.assertEqual(fields["license"], "Apache-2.0")
        self.assertTrue(json.loads(fields["description"]))
        self.assertIn("metadata", fields)
        self.assertIn("${HERMES_SKILL_DIR}/runtime/cli.py", body)
        self.assertNotIn("{{", body)

    def test_claude_code_plugin_and_skill(self):
        plugin = json.loads((self.claude / ".claude-plugin" / "plugin.json").read_text())
        self.assertEqual(plugin["name"], package.NAME)
        self.assertEqual(plugin["version"], package.VERSION)
        fields, body = frontmatter(self.claude_skill / "SKILL.md")
        self.assertEqual(set(fields), {"name", "description"})
        self.assertIn(package.SKILL_DIR_TOKEN["claude-code"] + "/runtime/cli.py", body)
        self.assertNotIn("{{", body)

    def test_references_linked_from_the_skill_exist(self):
        for root in (self.hermes, self.claude_skill):
            _, body = frontmatter(root / "SKILL.md")
            links = re.findall(r"\]\((references/[^)]+)\)", body)
            self.assertGreaterEqual(len(links), 5)
            for link in links:
                self.assertTrue((root / link).is_file(), link)

    def test_manifest_matches_the_files(self):
        for root in (self.hermes, self.claude):
            manifest = json.loads((root / "MANIFEST.json").read_text())
            self.assertEqual(manifest["contract"], "tessera.hologram/0.2")
            on_disk = {p.relative_to(root).as_posix() for p in root.rglob("*")
                       if p.is_file() and p.name != "MANIFEST.json"}
            self.assertEqual(set(manifest["files"]), on_disk)
            for rel, digest in manifest["files"].items():
                self.assertEqual(hashlib.sha256((root / rel).read_bytes()).hexdigest(), digest)

    def test_no_private_or_foreign_material(self):
        for path in Path(self.tmp.name).rglob("*"):
            if not path.is_file():
                continue
            self.assertNotIn(path.suffix, {".sqlite3", ".db", ".env", ".key", ".pem"}, path)
            if path.suffix in {".md", ".json", ".py", ".js", ".html"}:
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("/Users/", text, path)
                self.assertNotRegex(text, r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"][A-Za-z0-9]", path)

    def test_refuses_a_non_empty_output_folder(self):
        with self.assertRaises(package.PackageError):
            package.build(Path(self.tmp.name) / "dist")

    def test_runs_from_an_isolated_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp) / "elsewhere" / package.NAME
            shutil.copytree(self.claude_skill, skill)
            work = Path(tmp) / "work"
            work.mkdir()
            cli = str(skill / "runtime" / "cli.py")

            def run(*args):
                return subprocess.run([sys.executable, "-I", cli] + list(args), cwd=work,
                                      capture_output=True, text=True, timeout=120)

            for example in sorted((skill / "examples").glob("*.json")):
                r = run("check", str(example))
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn("audit: PASS", r.stdout)
            r = run("new", "machine", "--output", "m.json")
            self.assertEqual(r.returncode, 0, r.stderr)
            r = run("build", "m.json", "--out", "out")
            self.assertEqual(r.returncode, 0, r.stderr)
            html = (work / "out" / "hologram.html").read_text(encoding="utf-8")
            self.assertIn("tessera-hologram-geometry", html)
            r = run("build", str(skill / "examples" / "cd.json"), "--out", "cd")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("data:image/png;base64,", (work / "cd" / "hologram.html").read_text())

    def test_starters_open_without_warnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            cli = str(self.hermes / "runtime" / "cli.py")
            for category in ("object", "architecture", "machine", "organism", "cd", "book"):
                out = str(Path(tmp) / (category + ".json"))
                subprocess.run([sys.executable, "-I", cli, "new", category, "--output", out],
                               check=True, capture_output=True)
                r = subprocess.run([sys.executable, "-I", cli, "check", out], capture_output=True, text=True)
                self.assertIn("audit: PASS (0 errors, 0 warnings)", r.stdout, category)


if __name__ == "__main__":
    unittest.main()
