"""Assemble the Hermes plugin of Construct as a standalone, publishable package (nothing is installed or sent).

    python3 scripts/hermes_plugin.py [--out hermes]

Writes <out>/construct/ (the folder name is the plugin's id). The default, hermes/construct/, is the committed
plugin that `hermes plugins install rtmandreyev/construct#hermes/construct` and the Hermes catalog install; a test
keeps it equal to a fresh build. It holds:
    the plugin's source from hosts/hermes/construct/ (tools, Desktop half, backend, skill, README)
    _vendor/construct_hologram/   the runtime as Python source (the same modules as the Hermes skill's) and its data
    skills/construct/references/  the skill's references, their commands named as `construct <subcommand>`
    examples/<name>/              the finished constructs construct_start can begin from (hosts/hermes/construct/stock.py):
                                  scene.json, scene.materials.json, thumb.jpg, kit-plan.json; examples/catalog.json
    desktop/plugin.js             the Desktop half, with three.js (hosts/hermes/three/, MIT) bundled in at its marker
    LICENSE, NOTICE
The output is deterministic: the same checkout writes the same bytes.
"""

import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "construct_hologram"
SOURCE = ROOT / "hosts" / "hermes" / "construct"
NAME = "construct"


def _submission():
    """scripts/hermes_submission.py: its RUNTIME list is the runtime the Hermes skill ships; the plugin ships the same."""
    spec = importlib.util.spec_from_file_location("hermes_submission", ROOT / "scripts" / "hermes_submission.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _stock():
    """hosts/hermes/construct/stock.py: the finished constructs the plugin ships."""
    spec = importlib.util.spec_from_file_location("hermes_plugin_stock", SOURCE / "stock.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


VIEWER = ("hologram.js", "film.js", "reading.js", "template.html")
PROMPT_EXAMPLES = ("case-jewel.params.json", "book.json")   # the prompts module quotes these
THREE = ROOT / "hosts" / "hermes" / "three" / "three-bundle.min.js"
THREE_MARK = "/*__THREE_BUNDLE__*/"
SKIP = {"__pycache__", "_vendor", "examples", ".DS_Store"}


def _copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def _source_files():
    """The plugin's own files, in a stable order, without bytecode or generated folders."""
    out = []
    for p in sorted(SOURCE.rglob("*")):
        rel = p.relative_to(SOURCE)
        if p.is_file() and not (set(rel.parts) & SKIP) and p.suffix not in (".pyc", ".pyo") \
                and not (rel.parts[:3] == ("skills", "construct", "references")):
            out.append(rel)
    return out


def reference_text(text):
    """A skill reference as the plugin's skill reads it: commands named as Construct's own, examples by name."""
    text = text.replace("python3 TOOLS ", "construct ").replace("python3 TOOLS", "construct")
    text = text.replace("`prompts/trace.md`", "`references/trace-prompt.md`")
    return text


def build(out):
    pkg = out / NAME
    if pkg.exists():
        shutil.rmtree(pkg)
    pkg.mkdir(parents=True)
    for rel in _source_files():
        _copy(SOURCE / rel, pkg / rel)
    rt = pkg / "_vendor" / "construct_hologram"
    for module in _submission().RUNTIME:
        _copy(PKG / module, rt / module)
    for name in VIEWER:
        _copy(PKG / "viewer" / name, rt / "viewer" / name)
    for name in PROMPT_EXAMPLES:
        _copy(PKG / "examples" / "v2" / name, rt / "examples" / "v2" / name)
    refs = pkg / "skills" / "construct" / "references"
    refs.mkdir(parents=True, exist_ok=True)
    for ref in sorted((PKG / "skill" / "references").glob("*.md")):
        (refs / ref.name).write_text(reference_text(ref.read_text(encoding="utf-8")), encoding="utf-8")
    _copy(PKG / "prompts" / "trace.md", refs / "trace-prompt.md")
    stock = _stock()
    rows = []
    for name in stock.STOCK:
        files = stock.source_files(ROOT, name)
        dst = pkg / "examples" / name
        _copy(files["scene"], dst / "scene.json")
        for key, as_name in (("materials", "scene.materials.json"), ("thumb", "thumb.jpg"), ("kit_plan", "kit-plan.json")):
            if files[key]:
                _copy(files[key], dst / as_name)
        rows.append(dict(stock.describe(name, files["scene"], files["readme"]), has_thumb=bool(files["thumb"])))
    (pkg / "examples" / "catalog.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    js = pkg / "desktop" / "plugin.js"
    text = js.read_text(encoding="utf-8")
    if THREE_MARK not in text:
        raise SystemExit("desktop/plugin.js has no %s line for three.js" % THREE_MARK)
    js.write_text(text.replace(THREE_MARK, THREE.read_text(encoding="utf-8").rstrip("\n"), 1), encoding="utf-8")
    _copy(ROOT / "LICENSE", pkg / "LICENSE")
    _copy(ROOT / "NOTICE", pkg / "NOTICE")   # Apache-2.0: the notice travels with copies
    return pkg


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(ROOT / "hermes"))
    args = ap.parse_args(argv)
    pkg = build(Path(args.out))
    files = [p for p in pkg.rglob("*") if p.is_file()]
    print("plugin: %s (%d files, %.0f KB)" % (pkg, len(files), sum(p.stat().st_size for p in files) / 1024))
    print("check it: hermes plugins validate %s" % pkg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
