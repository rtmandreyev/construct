"""Apply the product's final name: python3 scripts/rename.py <new-name> ["New Title"]

Changes NAME and TITLE in the package's product.py, then every mention of the old name and
package folder in the tracked text files (pyproject.toml, docs, licence, notices), and renames
the package folder with git mv (the import name becomes the new name with underscores). The
contract and format ids are not touched.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main(argv):
    if not argv or not re.fullmatch(r"[a-z][a-z0-9-]{1,40}", argv[0]):
        sys.exit("usage: rename.py <new-name: lowercase, digits, hyphens> [\"New Title\"]")
    new = argv[0]
    title = argv[1] if len(argv) > 1 else new.replace("-", " ").title()
    pkg = [p for p in ROOT.iterdir() if (p / "product.py").is_file()]
    if len(pkg) != 1:
        sys.exit("cannot find the package folder (the one holding product.py)")
    pkg = pkg[0]
    prod = pkg / "product.py"
    text = prod.read_text()
    old = re.search(r'^NAME = "([^"]+)"', text, re.M).group(1)
    text = re.sub(r'^NAME = "[^"]+"', 'NAME = "%s"' % new, text, flags=re.M)
    text = re.sub(r'^TITLE = "[^"]+"', 'TITLE = "%s"' % title, text, flags=re.M)
    prod.write_text(text)
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    for name in files:
        f = ROOT / name
        if f.resolve() == Path(__file__).resolve() or not (f.suffix in (".md", ".py", ".toml", ".txt")
                                                           or f.name in ("LICENSE", "NOTICE")):
            continue
        text = f.read_text(encoding="utf-8")
        changed = text.replace(old, new).replace(pkg.name, new.replace("-", "_"))
        if changed != text:
            f.write_text(changed, encoding="utf-8")
    target = ROOT / new.replace("-", "_")
    if target != pkg:
        subprocess.run(["git", "mv", pkg.name, target.name], cwd=ROOT, check=True)
    print("renamed %s -> %s (package folder %s)" % (old, new, target.name))


if __name__ == "__main__":
    main(sys.argv[1:])
