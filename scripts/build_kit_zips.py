#!/usr/bin/env python3
"""Build the gallery's model kits as zips to attach to a GitHub release, one per kit.

    python3 scripts/build_kit_zips.py [--out dist/] [--only SLUG]

Each kit in examples/kits.json is made with this checkout's `construct kit` (as the gallery makes it) and
zipped as construct-kit-<slug>.zip: its plates (plate-N.3mf, each piece a named object), the booklet to
print, the steps in 3D (both open in a browser, offline) and a README. The pieces one by one are left out
(they are large as STL): delete the other objects on a plate in the slicer, or make them with
`construct kit ... --only N`. The names carry no version, so the gallery and the docs can link to
`releases/latest/download/construct-kit-<slug>.zip`. The kits take a few minutes, made side by side.
"""

import argparse
import importlib.util
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("build_site", ROOT / "scripts" / "build_site.py")
site = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(site)

README = """{title}

{scale} scale, {pieces} pieces on {plates} plate{s}, {steps} steps, about {size} mm built.
From the construct at {page}

What is here
- booklet.html: the instructions to print. Open it in a browser; it reads the pictures in img/.
- assembly.html: the same steps in 3D. Drag to turn it; Previous, Play and Next at the bottom.
- plate-N.3mf: the plates for your slicer (PrusaSlicer, Bambu Studio, Cura), numbered in the order
  they are glued. Each piece is a named object, so you can print one again on its own.
  Clear pieces are on plates of their own, for clear filament or resin.

Not yet built by anyone: the kit is made and checked by software and by AI critics. Print one
small piece first. If you build it, tell us how it went: {issues}

Made with Construct ({repo}), Apache-2.0.
"""


def zip_kit(spec, out_dir):
    """construct-kit-<slug>.zip in `out_dir`, made from examples/kits.json's entry `spec`."""
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp, "kit")
        kit = site.make_kit(spec, work)
        title = next(e["title"] for e in site._load_examples() if e["slug"] == spec["slug"])
        plates = sorted(work.glob("plate-*.3mf"), key=lambda p: int(p.stem.split("-")[1]))
        readme = README.format(
            title=kit["title"], scale=kit["scale"], pieces=len(kit["pieces"]), plates=len(plates),
            s="" if len(plates) == 1 else "s", steps=len(kit["steps"]),
            size=" x ".join("%.0f" % v for v in kit["size_mm"]),
            page="%sexamples/%s/ (%s)" % (site.SITE_URL, spec["slug"], title),
            issues=site.REPO_URL + "/issues", repo=site.REPO_URL)
        path = Path(out_dir) / ("construct-kit-%s.zip" % spec["slug"])
        folder = "construct-kit-%s/" % spec["slug"]
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(folder + "README.txt", readme)
            for f in [work / "booklet.html", work / "assembly.html"] + plates + sorted((work / "img").iterdir()):
                z.write(f, folder + str(f.relative_to(work)))
        return path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(ROOT / "dist"), help="the folder to write the zips into")
    ap.add_argument("--only", metavar="SLUG", help="one kit (its slug in examples/kits.json)")
    args = ap.parse_args(argv)
    kits = [k for k in site._load_kits() if not args.only or k["slug"] == args.only]
    if not kits:
        ap.error("no kit %s in examples/kits.json" % args.only)
    Path(args.out).mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for path in pool.map(lambda spec: zip_kit(spec, args.out), kits):
            print("%s (%.1f MB)" % (path, path.stat().st_size / 1e6))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
