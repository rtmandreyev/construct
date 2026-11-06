#!/usr/bin/env python3
"""Build the Construct extension for NetLogo 7 as a zip, the form NetLogo's Extensions Manager installs.

    python3 scripts/build_netlogo_extension.py --netlogo "/Applications/NetLogo 7.0.4" [--javac PATH] [--out dist/]

Compiles hosts/netlogo/ (Java 17) against the NetLogo you point to, and zips construct.jar with the
part of Construct that construct:draw runs (the construct_hologram package as committed, standard library
only, without its tests, test data, examples or skill), its LICENSE and NOTICE. Unzipped into NetLogo's extensions folder as construct/, a model can say
`extensions [construct]`. The draw needs Python 3.10 or newer on the computer; recording does not.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from construct_hologram import product  # noqa: E402

SRC = ROOT / "hosts" / "netlogo" / "src"
SKIP = {"__pycache__", "examples", "evaluation", "testdata", "skill", ".DS_Store"}   # folders the draw never reads
MANIFEST = """Manifest-Version: 1.0
Extension-Name: construct
Class-Manager: construct.netlogo.ConstructExtension
NetLogo-Extension-API-Version: 7.0
Implementation-Title: Construct for NetLogo
Implementation-Version: {version}
"""


def javac_default():
    home = os.environ.get("JAVA_HOME")
    if home and Path(home, "bin", "javac").exists():
        return str(Path(home, "bin", "javac"))
    return shutil.which("javac") or "javac"


def netlogo_jar(netlogo):
    """NetLogo's own jar, in app/ (macOS, Windows, Linux bundles alike)."""
    found = sorted(Path(netlogo).glob("**/app/netlogo-*.jar")) or sorted(Path(netlogo).glob("**/netlogo-*.jar"))
    if not found:
        sys.exit("no netlogo-*.jar under %s: point --netlogo at the NetLogo 7 folder" % netlogo)
    return found[0]


def compile_jar(netlogo, javac, into):
    jar = netlogo_jar(netlogo)
    classes = into / "classes"
    classes.mkdir(parents=True)
    cp = os.pathsep.join([str(jar), str(jar.parent / "*")])
    sources = [str(p) for p in sorted(SRC.rglob("*.java"))]
    subprocess.run([javac, "--release", "17", "-cp", cp, "-d", str(classes)] + sources, check=True)
    out = into / "construct.jar"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(fixed("META-INF/MANIFEST.MF"), MANIFEST.format(version=product.VERSION))
        for f in sorted(classes.rglob("*.class")):
            z.writestr(fixed(str(f.relative_to(classes))), f.read_bytes())
    return out


def fixed(name):
    info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def runtime_files():
    """The construct_hologram files the zip carries, from git (what is committed, never a stray file in the
    working tree): not the folders in SKIP, nor the tests."""
    listed = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z", "construct_hologram"], check=True,
                            capture_output=True).stdout.decode("utf-8").split("\0")
    out = []
    for name in sorted(n for n in listed if n):
        rel = Path(name)
        if SKIP.intersection(rel.parts) or rel.name.startswith("test_") or rel.name == "package.py":   # it packs skill/
            continue
        out.append(rel)
    return out


def build(netlogo, javac, out_dir):
    """The extension zip: construct.jar, construct_hologram/, LICENSE and NOTICE at its root. Returns its path."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / ("construct-%s.zip" % product.VERSION)
    with tempfile.TemporaryDirectory() as tmp:
        jar = compile_jar(netlogo, javac, Path(tmp))
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(fixed("construct.jar"), jar.read_bytes())
            for rel in runtime_files():
                z.writestr(fixed(rel.as_posix()), (ROOT / rel).read_bytes())
            for name in ("LICENSE", "NOTICE"):
                z.writestr(fixed(name), (ROOT / name).read_bytes())
            z.writestr(fixed("README.md"), (ROOT / "hosts" / "netlogo" / "README.md").read_bytes())
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--netlogo", required=True, help="the NetLogo 7 folder (its app/netlogo-*.jar is compiled against)")
    ap.add_argument("--javac", default=javac_default(), help="a Java 17 or newer javac (default: JAVA_HOME's, else PATH's)")
    ap.add_argument("--out", default=str(ROOT / "dist"), help="the folder for the zip (default: dist/)")
    a = ap.parse_args()
    print(build(a.netlogo, a.javac, a.out))


if __name__ == "__main__":
    main()
