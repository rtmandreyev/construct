#!/usr/bin/env python3
"""Build the Construct add-on for Blender (an extension, Blender 4.2 and later) as a zip.

    python3 scripts/build_blender_extension.py [--out dist/]

The zip holds the add-on (hosts/blender/construct/), its manifest and the part of Construct it
needs to compile a scene and export it (standard library only). Install it in Blender with
Edit > Preferences > Get Extensions > Install from Disk, or drag it into Blender's window.
"""

import argparse
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from construct_hologram import product  # noqa: E402

ADDON = ROOT / "hosts" / "blender" / "construct"
RUNTIME = ["product.py", "shapes.py", "scene.py", "archkit.py", "params.py", "tiers.py", "export.py"]
MANIFEST = """schema_version = "1.0.0"

id = "construct"
version = "{version}"
name = "Construct"
tagline = "Import constructs as 3D models with parts, joints and build"
maintainer = "Artyom Andreyev"
type = "add-on"
website = "{repo}"
tags = ["Import-Export", "Animation"]
blender_version_min = "4.2.0"
license = ["SPDX:MIT"]
copyright = ["2026 The Construct authors"]

[permissions]
files = "Import construct scenes and models from disk"
"""
RUNTIME_INIT = '"""The part of Construct the Blender add-on bundles: the scene compiler and the 3D export."""\n'


def stage(into):
    """Lay out the extension's files in a folder."""
    into.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ADDON / "__init__.py", into / "__init__.py")
    shutil.copyfile(ROOT / "LICENSE", into / "LICENSE")
    (into / "blender_manifest.toml").write_text(MANIFEST.format(version=product.VERSION, repo=product.REPO),
                                                encoding="utf-8")
    rt = into / "construct_hologram"
    rt.mkdir(exist_ok=True)
    (rt / "__init__.py").write_text(RUNTIME_INIT, encoding="utf-8")
    for m in RUNTIME:
        shutil.copyfile(ROOT / "construct_hologram" / m, rt / m)
    return into


def build(out_dir):
    """The extension zip, files at its root as Blender expects. Returns its path."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / ("construct-blender-%s.zip" % product.VERSION)
    with tempfile.TemporaryDirectory() as tmp:
        src = stage(Path(tmp, "construct"))
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(src.rglob("*")):
                if f.is_file() and "__pycache__" not in f.parts:
                    info = zipfile.ZipInfo(str(f.relative_to(src)), date_time=(2026, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    z.writestr(info, f.read_bytes())
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(ROOT / "dist"), help="the folder for the zip (default: dist/)")
    print(build(ap.parse_args().out))


if __name__ == "__main__":
    main()
