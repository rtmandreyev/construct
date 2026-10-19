"""Unit tests for tessera-hologram."""

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

from . import hologram

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def _cd():
    return hologram.template("cd")


class TestValidation(unittest.TestCase):
    def test_template_valid(self):
        for kind in hologram.KINDS:
            sheet = hologram.template(kind)
            self.assertEqual(hologram.validate(sheet), [], kind)

    def test_templates_distinct(self):
        ids = set()
        for kind in hologram.KINDS:
            sheet = hologram.template(kind)
            ids.add(sheet["id"])
            self.assertEqual(sheet["kind"], kind)
        self.assertEqual(len(ids), len(hologram.KINDS))

    def test_unknown_key(self):
        sheet = _cd()
        sheet["extra"] = 1
        self.assertTrue(hologram.validate(sheet))

    def test_bool_where_int(self):
        sheet = _cd()
        sheet["seed"] = True
        self.assertTrue(hologram.validate(sheet))

    def test_nonfinite(self):
        sheet = _cd()
        sheet["parts"][0]["position"][0] = float("nan")
        self.assertTrue(hologram.validate(sheet))

    def test_bad_vector(self):
        sheet = _cd()
        sheet["parts"][0]["size"] = [1, 2]
        self.assertTrue(hologram.validate(sheet))

    def test_duplicate_part_ids(self):
        sheet = _cd()
        sheet["parts"][1]["id"] = sheet["parts"][0]["id"]
        self.assertTrue(hologram.validate(sheet))

    def test_resource_bounds(self):
        sheet = _cd()
        sheet["parts"] = [copy.deepcopy(sheet["parts"][0]) for _ in range(129)]
        for i, p in enumerate(sheet["parts"]):
            p["id"] = "p%d" % i
        self.assertTrue(hologram.validate(sheet))

    def test_unsafe_asset_paths(self):
        for bad in ["/abs.png", "C:/x.png", "a\\b.png", "../x.png",
                    "a/../b.png", "http://x/y.png", "a%2e%2e/b.png"]:
            sheet = _cd()
            sheet["assets"] = [{
                "id": "a", "path": bad, "sha256": "0" * 64,
                "media_type": "image/png", "rights": "synthetic",
            }]
            self.assertTrue(hologram.validate(sheet), bad)

    def test_verified_needs_source(self):
        sheet = _cd()
        sheet["parts"][0]["certainty"] = "verified"
        self.assertTrue(hologram.validate(sheet))


class TestCompile(unittest.TestCase):
    def test_determinism_and_immutability(self):
        sheet = _cd()
        snapshot = copy.deepcopy(sheet)
        a = hologram.compile_sheet(sheet)
        b = hologram.compile_sheet(sheet)
        self.assertEqual(a, b)
        self.assertEqual(sheet, snapshot)

    def test_transformed_bounds(self):
        sheet = _cd()
        sheet["parts"] = [{
            "id": "b", "shape": "box", "position": [1.0, 2.0, 3.0],
            "size": [2.0, 2.0, 2.0], "rotation": [0.0, 0.0, 0.0],
            "tone": "accent", "certainty": "decorative", "stage": 0,
        }]
        out = hologram.compile_sheet(sheet)
        self.assertEqual(out["bounds"]["min"], [0.0, 1.0, 2.0])
        self.assertEqual(out["bounds"]["max"], [2.0, 3.0, 4.0])
        self.assertEqual(len(out["segments"]), 12)

    def test_rotation_changes_bounds(self):
        sheet = _cd()
        sheet["parts"] = [{
            "id": "b", "shape": "box", "position": [0.0, 0.0, 0.0],
            "size": [2.0, 1.0, 1.0], "rotation": [0.0, 0.0, 90.0],
            "tone": "accent", "certainty": "decorative", "stage": 0,
        }]
        out = hologram.compile_sheet(sheet)
        self.assertAlmostEqual(out["bounds"]["max"][0], 0.5, places=6)
        self.assertAlmostEqual(out["bounds"]["max"][1], 1.0, places=6)

    def test_compile_rejects_invalid(self):
        sheet = _cd()
        sheet["kind"] = "nope"
        with self.assertRaises(hologram.SheetError):
            hologram.compile_sheet(sheet)


class TestReadSheet(unittest.TestCase):
    def test_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "s.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write('{"a":1,"a":2}')
            with self.assertRaises(hologram.SheetError):
                hologram.read_sheet(path)

    def test_nan_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "s.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write('{"a":NaN}')
            with self.assertRaises(hologram.SheetError):
                hologram.read_sheet(path)


class TestAssets(unittest.TestCase):
    def test_sha_and_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            data = b"hello"
            with open(os.path.join(td, "a.png"), "wb") as fh:
                fh.write(data)
            digest = hashlib.sha256(data).hexdigest()
            sheet = _cd()
            sheet["assets"] = [{
                "id": "a", "path": "a.png", "sha256": digest,
                "media_type": "image/png", "rights": "synthetic",
            }]
            self.assertEqual(hologram.verify_assets(sheet, td), [])
            sheet["assets"][0]["sha256"] = "0" * 64
            self.assertTrue(hologram.verify_assets(sheet, td))

            os.symlink(os.path.join(td, "a.png"), os.path.join(td, "link.png"))
            sheet["assets"][0]["path"] = "link.png"
            self.assertTrue(hologram.verify_assets(sheet, td))

    def test_traversal_escape(self):
        with tempfile.TemporaryDirectory() as td:
            sheet = _cd()
            sheet["assets"] = [{
                "id": "a", "path": "../x.png", "sha256": "0" * 64,
                "media_type": "image/png", "rights": "synthetic",
            }]
            self.assertTrue(hologram.verify_assets(sheet, td))


class TestCLI(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "hologram"] + list(args),
            cwd=ROOT, capture_output=True, text=True,
        )

    def test_template_stdout(self):
        r = self._run("template", "cd")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(json.loads(r.stdout)["kind"], "cd")

    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "o.json")
            r1 = self._run("template", "cd", "--output", out)
            self.assertEqual(r1.returncode, 0)
            r2 = self._run("template", "cd", "--output", out)
            self.assertNotEqual(r2.returncode, 0)
            r3 = self._run("template", "cd", "--output", out, "--force")
            self.assertEqual(r3.returncode, 0)

    def test_validate_invalid(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "s.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"format": "x"}, fh)
            r = self._run("validate", path)
            self.assertNotEqual(r.returncode, 0)


class TestMCP(unittest.TestCase):
    def _session(self, messages):
        payload = "".join(json.dumps(m) + "\n" for m in messages)
        return subprocess.run(
            [sys.executable, "-m", "hologram.mcp_server"],
            cwd=ROOT, input=payload, capture_output=True, text=True,
        )

    def test_initialize_and_list(self):
        r = self._session([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ])
        lines = [json.loads(x) for x in r.stdout.splitlines() if x.strip()]
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]["result"]["protocolVersion"], "2025-11-25")
        names = [t["name"] for t in lines[1]["result"]["tools"]]
        self.assertEqual(names[:3], ["hologram_template", "hologram_validate", "hologram_compile"])
        self.assertEqual(len(names), 7)

    def test_compile_and_validation_error(self):
        sheet = _cd()
        bad = _cd()
        bad["kind"] = "nope"
        r = self._session([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "hologram_compile", "arguments": {"sheet": sheet}}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "hologram_compile", "arguments": {"sheet": bad}}},
        ])
        lines = [json.loads(x) for x in r.stdout.splitlines() if x.strip()]
        self.assertEqual(lines[1]["result"]["structuredContent"]["format"], "tessera-geometry")
        self.assertTrue(lines[2]["result"]["isError"])

    def test_unknown_method_and_notification(self):
        r = self._session([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "bogus"},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
        ])
        lines = [json.loads(x) for x in r.stdout.splitlines() if x.strip()]
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[1]["error"]["code"], -32601)

    def test_call_before_initialize(self):
        r = self._session([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        ])
        lines = [json.loads(x) for x in r.stdout.splitlines() if x.strip()]
        self.assertEqual(len(lines), 1)
        self.assertIn("error", lines[0])


if __name__ == "__main__":
    unittest.main()
