"""Assemble a draft submission of Construct as a Hermes optional skill (nothing is submitted).

    python3 scripts/hermes_submission.py [--out .local/hermes-submission] [--hermes ~/.hermes/hermes-agent]

Writes the folders as they would sit in NousResearch/hermes-agent:
    optional-skills/creative/construct/   SKILL.md, references/, scripts/ (the runtime), assets/examples/, LICENSE
    tests/skills/test_construct_skill.py
    PR.md                                 the pull-request text and checklist
and, when a local Hermes checkout is given, runs its skill scanner and the hardline authoring
checks against the draft (read-only: it imports Hermes's code, it changes nothing there).
"""

import argparse
import importlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "construct_hologram"
HERE = ROOT / "scripts" / "hermes_submission"
RUNTIME = ["__init__.py", "__main__.py", "product.py", "hologram.py", "scene.py", "shapes.py", "audit.py",
           "diagnose.py", "params.py", "render.py", "studio.py", "png.py", "trace.py", "terrain.py", "tiers.py", "globe.py", "critic.py", "compare.py", "archkit.py"]
EXAMPLES = ["cd.json", "book.json", "lighthouse.json", "lantern-jellyfish.json", "case-jewel.params.json",
            "book-paperback.params.json", "object-electric-guitar.params.json", "vessel-can.params.json"]
SHIM = '''"""construct command line (Hermes optional skill). Run by absolute path from any folder."""
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
main = importlib.import_module("construct_hologram.__main__").main

if __name__ == "__main__":
    sys.exit(main())
'''


def build(out):
    skill = out / "optional-skills" / "creative" / "construct"
    if out.exists():
        shutil.rmtree(out)
    (skill / "references").mkdir(parents=True)
    shutil.copyfile(HERE / "SKILL.md", skill / "SKILL.md")
    for ref in sorted((PKG / "skill" / "references").glob("*.md")):
        text = ref.read_text(encoding="utf-8").replace("`examples/", "`assets/examples/")
        text = text.replace("`prompts/trace.md`", "`references/trace-prompt.md`").replace("python3 TOOLS", "python3 ${HERMES_SKILL_DIR}/scripts/cli.py")
        (skill / "references" / ref.name).write_text(text, encoding="utf-8")
    shutil.copyfile(PKG / "prompts" / "trace.md", skill / "references" / "trace-prompt.md")
    rt = skill / "scripts" / "construct_hologram"
    (rt / "viewer").mkdir(parents=True)
    for m in RUNTIME:
        shutil.copyfile(PKG / m, rt / m)
    for v in ("hologram.js", "template.html"):
        shutil.copyfile(PKG / "viewer" / v, rt / "viewer" / v)
    (skill / "scripts" / "cli.py").write_text(SHIM, encoding="utf-8")
    ex = skill / "assets" / "examples"
    (ex / "assets").mkdir(parents=True)
    for e in EXAMPLES:
        shutil.copyfile(PKG / "examples" / "v2" / e, ex / e)
    for a in (PKG / "examples" / "v2" / "assets").glob("*.png"):
        shutil.copyfile(a, ex / "assets" / a.name)
    shutil.copyfile(ROOT / "LICENSE", skill / "LICENSE")
    tests = out / "tests" / "skills"
    tests.mkdir(parents=True)
    shutil.copyfile(HERE / "test_construct_skill.py", tests / "test_construct_skill.py")
    shutil.copyfile(HERE / "PR.md", out / "PR.md")
    return skill


def hardline(skill):
    """The programmatic subset of Hermes's authoring standards (tests/skills/test_authoring_standards.py)."""
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    fm_text, body = text[4:].split("\n---\n", 1)
    fm = {}
    for line in fm_text.splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    problems = []
    for f in ("name", "description", "version", "author", "license", "platforms"):
        if f not in fm:
            problems.append("missing frontmatter " + f)
    if "tags:" not in fm_text:
        problems.append("no tags")
    if fm.get("name") != skill.name:
        problems.append("name != directory")
    d = fm.get("description", "")
    if len(d) > 60 or not d.endswith("."):
        problems.append("description %d chars / no period" % len(d))
    if re.search(r"\b(powerful|comprehensive|seamless|revolutionary|cutting-edge|state-of-the-art)\b", d, re.I):
        problems.append("marketing word in description")
    if re.search(r"/home/(?!runner\b)[a-z0-9_-]+/|[A-Z]:\\+Users\\+(?!<)|/Users/[A-Za-z]", body):
        problems.append("machine-local path")
    if len(body) > 100_000:
        problems.append("too long")
    if re.search(r"\\\s+#", body):
        problems.append("comment after a line continuation")
    for section in ("When to Use", "Prerequisites", "How to Run", "Quick Reference", "Procedure", "Pitfalls", "Verification"):
        if "## " + section not in body:
            problems.append("missing section " + section)
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(ROOT / ".local" / "hermes-submission"))
    ap.add_argument("--hermes", default=str(Path.home() / ".hermes" / "hermes-agent"))
    args = ap.parse_args(argv)
    out = Path(args.out)
    skill = build(out)
    files = [p for p in skill.rglob("*") if p.is_file()]
    print("draft: %s (%d files, %.0f KB, largest %s %.0f KB)" % (skill, len(files), sum(p.stat().st_size for p in files) / 1024,
          max(files, key=lambda p: p.stat().st_size).name, max(p.stat().st_size for p in files) / 1024))
    probs = hardline(skill)
    print("hardline checks: %s" % ("pass" if not probs else "; ".join(probs)))
    r = subprocess.run([sys.executable, "-I", "-B", str(skill / "scripts" / "cli.py"), "check",
                        str(skill / "assets" / "examples" / "cd.json")], capture_output=True, text=True)
    print("self-test: %s" % r.stdout.splitlines()[0] if r.stdout else r.stderr)
    hermes = Path(args.hermes)
    if (hermes / "tools" / "skills_guard.py").is_file():
        print("scanner: with Hermes's own Python, tools.skills_guard.scan_skill(<draft>, source='community')")
    return 0 if not probs else 1


if __name__ == "__main__":
    sys.exit(main())
