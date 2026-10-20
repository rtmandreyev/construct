"""Tests for the construct optional skill (stdlib + pytest only; no network, no browser)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[2] / "optional-skills" / "creative" / "construct"
CLI = SKILL / "scripts" / "cli.py"
EXAMPLES = sorted((SKILL / "assets" / "examples").glob("*.json"))


def run(*args, cwd=None):
    return subprocess.run([sys.executable, "-I", str(CLI), *args], cwd=cwd, capture_output=True, text=True, timeout=120)


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda p: p.name)
def test_every_bundled_example_passes_the_audit(example):
    r = run("check", str(example))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "audit: PASS (0 errors, 0 warnings)" in r.stdout


def test_params_check_build_from_a_temp_folder(tmp_path):
    assert run("params", "vessel", "--variant", "can", "--output", "can.json", cwd=tmp_path).returncode == 0
    doc = json.loads((tmp_path / "can.json").read_text())
    doc["facts"] = [{"key": "title", "value": "Synthetic Stout", "certainty": "user_supplied", "source": "request"}]
    (tmp_path / "can.json").write_text(json.dumps(doc))
    r = run("check", "can.json", "--json", cwd=tmp_path)
    assert json.loads(r.stdout)["ok"] is True
    assert run("build", "can.json", "--out", "out", cwd=tmp_path).returncode == 0
    assert (tmp_path / "out" / "hologram.html").stat().st_size > 10_000


def test_unknown_facts_and_colours_are_refused(tmp_path):
    bad = json.loads((SKILL / "assets" / "examples" / "case-jewel.params.json").read_text())
    bad["facts"].append({"key": "year", "value": "unknown", "certainty": "inferred"})
    bad["colour"] = "red"
    (tmp_path / "bad.json").write_text(json.dumps(bad))
    report = json.loads(run("check", "bad.json", "--json", cwd=tmp_path).stdout)
    codes = {d["code"] for d in report["diagnostics"]}
    assert not report["ok"] and {"unknown-fact", "style"} <= codes
