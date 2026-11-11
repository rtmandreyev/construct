#!/usr/bin/env python3
"""Build Construct's MCP server as an MCP Bundle (.mcpb) and its entry for the official MCP Registry.

    python3 scripts/build_mcpb.py [--out dist/]

Writes `construct-mcp-<version>.mcpb` (a zip: manifest.json, the committed construct_hologram/ runtime without
its tests, LICENSE and NOTICE) and `server.json` (the registry entry: the bundle's release URL and its SHA-256).
Claude Desktop installs the bundle with a double-click. The build is reproducible: the same commit gives the same
bytes, so the hash in server.json holds for the file attached to the release. Standard library only.
"""

import argparse
import hashlib
import importlib.util
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from construct_hologram import mcp_server, product  # noqa: E402

_spec = importlib.util.spec_from_file_location("bne", ROOT / "scripts" / "build_netlogo_extension.py")
bne = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bne)

REGISTRY_NAME = "io.github.rtmandreyev/construct"
SCHEMA = "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json"
HOMEPAGE = "https://rtmandreyev.github.io/construct/"
DESCRIPTION = "Checks an agent's part-by-part description of a thing and builds it as glTF, OBJ, 3MF or STL."
LONG_DESCRIPTION = (
    "Construct checks an agent's description of a thing: its named parts at their real sizes, its joints, and how "
    "each part is known. Each problem comes back with a JSON path, a code and a fix hint. It then builds a glTF model "
    "with named parts, materials by role and the open and idle animations, an OBJ, or one watertight 3MF or STL body "
    "to print, checked to fit the print bed and for overhangs. It can also start from a template for a case, book, "
    "object or vessel. The server works only on the JSON in each request: it reads and writes no files, spawns no "
    "processes and makes no network requests. The animated web page and worlds come from the full skill in the "
    "repository.")


def name():
    return "construct-mcp-%s.mcpb" % product.VERSION        # the registry asks for "mcp" in the bundle's URL


def url():
    return "%s/releases/download/v%s/%s" % (product.REPO, product.VERSION, name())


def manifest():
    """The bundle's manifest.json (MCPB manifest 0.3)."""
    return {
        "manifest_version": "0.3",
        "name": product.NAME,
        "display_name": "Construct",
        "version": product.VERSION,
        "description": DESCRIPTION,
        "long_description": LONG_DESCRIPTION,
        "author": {"name": "The Construct authors", "url": product.REPO},
        "repository": {"type": "git", "url": product.REPO + ".git"},
        "homepage": HOMEPAGE,
        "documentation": product.REPO + "#readme",
        "support": product.REPO + "/issues",
        "license": "Apache-2.0",
        "keywords": ["3d", "gltf", "3d-printing", "hologram", "webgl", "construct"],
        "server": {
            "type": "python",
            "entry_point": "construct_hologram/server.py",
            "mcp_config": {"command": "python3", "args": ["${__dirname}/construct_hologram/server.py"],
                           "platform_overrides": {"win32": {"command": "python"}}},
        },
        "tools": [{"name": t["name"], "description": t["description"].split(". ")[0].rstrip(".") + "."}
                  for t in mcp_server.TOOLS],
        "compatibility": {"platforms": ["darwin", "win32", "linux"], "runtimes": {"python": ">=3.10"}},
    }


def server_json(sha256):
    """The official MCP Registry's entry for this release's bundle."""
    return {
        "$schema": SCHEMA,
        "name": REGISTRY_NAME,
        "title": "Construct",
        "description": DESCRIPTION,
        "repository": {"url": product.REPO, "source": "github"},
        "websiteUrl": HOMEPAGE,
        "version": product.VERSION,
        "packages": [{"registryType": "mcpb", "identifier": url(), "fileSha256": sha256,
                      "transport": {"type": "stdio"}}],
    }


def build(out_dir):
    """The bundle and server.json in `out_dir`. Returns (bundle path, its SHA-256)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(bne.fixed("manifest.json"), json.dumps(manifest(), indent=2) + "\n")
        for f in ("LICENSE", "NOTICE"):
            z.writestr(bne.fixed(f), (ROOT / f).read_bytes())
        for rel in bne.runtime_files():
            z.writestr(bne.fixed(rel.as_posix()), (ROOT / rel).read_bytes())
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    (out_dir / "server.json").write_text(json.dumps(server_json(sha), indent=2) + "\n", encoding="utf-8")
    return path, sha


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(ROOT / "dist"), help="the folder for the bundle and server.json (default: dist/)")
    path, sha = build(ap.parse_args().out)
    print(path)
    print("sha256", sha)


if __name__ == "__main__":
    main()
