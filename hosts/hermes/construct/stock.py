"""The constructs the plugin ships to start from (construct_start example=..., the Constructs page's "Start from").

Each is a finished construct from Construct's gallery (or a showcase), copied whole into a new project when chosen.
In the published package they sit in examples/<name>/ (scene.json, its material map as scene.materials.json, a
still as thumb.jpg, a kit plan when it has one) with examples/catalog.json describing them; in a source checkout
they are read where the repository keeps them. scripts/hermes_plugin.py writes the package's copies from STOCK.
"""

import json
import os
import re
import shutil
from pathlib import Path

# name -> the folder (from the repository's root) holding scene.json, and maps/finish.json, thumb.jpg, kit-plan.json
STOCK = {
    "toyota-land-cruiser-fj62": "examples/toyota-land-cruiser-fj62",
    "volkswagen-t1-samba": "examples/volkswagen-t1-samba",
    "vespa-gs150": "examples/vespa-gs150",
    "eames-lounge-chair": "examples/eames-lounge-chair-chatgpt",   # the stronger of the two builds (critic: good)
    "braun-sk4": "examples/braun-sk4",
    "braun-sk4-knob": "examples/braun-sk4-knob",
    "revox-a77": "examples/revox-a77",
    "tompion-year-going-clock": "examples/tompion-year-going-clock",
    "garden-shed": "examples/garden-shed",
    "garden-shed-planned": "examples/garden-shed-planned",
    "sainte-chapelle": "examples/sainte-chapelle",
    "duomo-di-milano": "examples/duomo-di-milano",
    "neuschwanstein": "examples/neuschwanstein",
    "kestrel-v2": "examples/kestrel-v2",
    "villa-savoye": "examples/villa-savoye",
    "serum-2-61": "examples/serum-2-61",
    "leica-m3": "examples/leica-m3",
    "jackson-juggernaut-et7": "examples/jackson-juggernaut-et7",
    "state-bench": "examples/state-bench",
    "saturn": "examples/saturn",
    "aston-martin-db5": "examples/aston-martin-db5",
    "sagrada-familia": "examples/sagrada-familia",
    "james-webb-space-telescope": "examples/films/james-webb-space-telescope",
    "rietveld-red-blue-chair": "examples/rietveld-red-blue-chair",
}
# what each one is good to start from (shown with it; the tutorials name them too)
USE = {
    "toyota-land-cruiser-fj62": "a vehicle from published sizes and photos",
    "volkswagen-t1-samba": "a vehicle with doors, lids and a folding roof that open",
    "vespa-gs150": "a scooter, with a model kit plan",
    "eames-lounge-chair": "furniture copied from two photos",
    "braun-sk4": "a product from published dimensions and photographs",
    "braun-sk4-knob": "a missing part, to print or to send as CAD",
    "revox-a77": "a machine with moving reels",
    "tompion-year-going-clock": "an antique with opening doors, with a model kit plan",
    "garden-shed": "a building from one photograph",
    "garden-shed-planned": "the same shed with a planned change built on",
    "sainte-chapelle": "architecture, from plans and published heights",
    "duomo-di-milano": "a cathedral of spires",
    "neuschwanstein": "a castle on its rock",
    "kestrel-v2": "an original design invented from real hardware (a game brief), refined for close-ups",
    "villa-savoye": "a house to furnish: a world's host (made in Hermes, with a desktop kit plan)",
    "serum-2-61": "a product designed from a software manual (unaffiliated concept)",
    "leica-m3": "a camera, small and exact",
    "jackson-juggernaut-et7": "an electric guitar",
    "state-bench": "an invented instrument with a sliding service drawer",
    "saturn": "a planet: in a world's sky at its real angular size",
    "aston-martin-db5": "a grand tourer from published dimensions and photographs",
    "sagrada-familia": "a basilica's completed design, from published heights",
    "james-webb-space-telescope": "a spacecraft at L2, from NASA's own figures",
    "rietveld-red-blue-chair": "a design classic from a museum's sizes and a dimensioned drawing",
}
NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


def _first_sentence(text, n=170):
    text = " ".join(str(text or "").split())
    m = re.match(r"^(.+?[.!?])(\s|$)", text)
    line = m.group(1) if m and len(m.group(1)) >= 40 else text
    return line if len(line) <= n else line[:n - 1].rstrip() + "…"


def describe(name, scene_path, readme=None):
    """The catalog row of one: title, parts (and with copies), one line, its category, how it was made."""
    doc = json.loads(Path(scene_path).read_text(encoding="utf-8"))
    parts = doc.get("parts") or []
    copies = 0
    for p in parts:
        n = 2 if p.get("mirror") else 1
        if isinstance(p.get("repeat"), dict):
            n *= int(p["repeat"].get("count", 1) or 1)
        copies += n
    subject = doc.get("subject") or {}
    made = ""
    if readme and Path(readme).is_file():
        m = re.search(r"^\*\*(.+?)\*\*", Path(readme).read_text(encoding="utf-8"), re.M)
        made = m.group(1).strip() if m else ""
    elif isinstance(doc.get("authoring"), dict) and doc["authoring"].get("tier"):
        made = str(doc["authoring"]["tier"])
    return {"name": name, "title": str(doc.get("title") or name)[:160], "parts": len(parts), "with_copies": copies,
            "line": _first_sentence(subject.get("summary") or ""), "category": subject.get("category") or "",
            "accuracy": subject.get("accuracy") or "", "made": made, "use": USE.get(name, "")}


def source_files(root, name):
    """The repository's files of one stock construct: {"scene", "materials", "thumb", "kit_plan", "readme"} (absent ones
    are None)."""
    folder = Path(root) / STOCK[name]

    def have(rel):
        p = folder / rel
        return p if p.is_file() else None
    return {"scene": folder / "scene.json", "materials": have("maps/finish.json") or have("materials.json"),
            "thumb": have("thumb.jpg"),
            "kit_plan": have("kit-plan.json"), "readme": have("README.md")}


def package_files(folder):
    """The package's files of one stock construct, in examples/<name>/."""
    folder = Path(folder)

    def have(rel):
        p = folder / rel
        return p if p.is_file() else None
    return {"scene": folder / "scene.json", "materials": have("scene.materials.json"), "thumb": have("thumb.jpg"),
            "kit_plan": have("kit-plan.json"), "readme": None}


# ---------------------------------------------------------------------------- the gallery, on demand

GALLERY_RAW = "https://raw.githubusercontent.com/rtmandreyev/construct/%s/%s"


def gallery_index(root):
    """The repository's gallery constructs (examples/examples.json and films.json): name, title, where its files are.
    Written into the package as examples/gallery.json; a construct not shipped is fetched by name when wanted."""
    root = Path(root)
    rows = []
    for index, base in (("examples/examples.json", "examples"), ("examples/films.json", "examples/films")):
        try:
            doc = json.loads((root / index).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for e in doc.get("examples", doc.get("films", [])):
            slug = e.get("slug")
            folder = root / base / str(slug)
            if not slug or not NAME.match(slug) or not (folder / "scene.json").is_file():
                continue
            files = {"scene": "%s/%s/scene.json" % (base, slug)}
            for rel in ("maps/finish.json", "materials.json"):
                if (folder / rel).is_file():
                    files["materials"] = "%s/%s/%s" % (base, slug, rel)
                    break
            rows.append({"name": slug, "title": e.get("title", slug), "model": e.get("model"), "files": files})
    return {"format": "construct-gallery", "version": 1, "constructs": rows}


def _tls():
    """Certificate checks on: the system's store, or certifi's when this Python has none (python.org's macOS build)."""
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


# what curl is given of the environment: what it needs to start, find its certificates and use a proxy
CURL_ENV = ("PATH", "HOME", "TMPDIR", "TEMP", "TMP", "SYSTEMROOT", "SSL_CERT_FILE", "SSL_CERT_DIR", "CURL_CA_BUNDLE",
            "HTTPS_PROXY", "https_proxy", "NO_PROXY", "no_proxy")


def fetch_gallery(name, dest, version, index):
    """Fetch one gallery construct's scene (and its material map) into `dest`, from this version's release tag (JSON
    data only, at most 8 MiB a file). Returns {"scene", "materials"} paths. Raises OSError/ValueError."""
    import urllib.request
    row = next((r for r in index.get("constructs", []) if r["name"] == name), None)
    if row is None:
        raise ValueError("no gallery construct %r" % name)
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    out = {}
    for key, as_name in (("scene", "scene.json"), ("materials", "scene.materials.json")):
        rel = row["files"].get(key)
        if not rel:
            continue
        data, last = None, None
        for ref in ("v" + version,):   # this release's tag only: what was reviewed, never a moving branch
            try:
                req = urllib.request.Request(GALLERY_RAW % (ref, rel), headers={"User-Agent": "construct-hermes-plugin"})
                with urllib.request.urlopen(req, timeout=30, context=_tls()) as r:
                    data = r.read(8 * 1024 * 1024 + 1)
                break
            except OSError as exc:
                last = exc
                if "CERTIFICATE" in str(exc) and shutil.which("curl"):   # a Python without CA certificates: curl has them
                    import subprocess
                    env = {k: os.environ.get(k) for k in CURL_ENV if os.environ.get(k) is not None}   # never keys
                    r = subprocess.run(["curl", "-fsSL", "--max-time", "30", GALLERY_RAW % (ref, rel)], capture_output=True,
                                       env=env)
                    if r.returncode == 0:
                        data = r.stdout
                        break
        if data is None:
            if key == "scene":
                raise OSError("could not fetch %s from GitHub: %s" % (rel, last))
            continue
        if len(data) > 8 * 1024 * 1024:
            raise ValueError("%s is larger than 8 MiB" % rel)
        doc = json.loads(data.decode("utf-8"))   # it must be JSON; it is checked again when it is built
        (dest / as_name).write_text(json.dumps(doc, ensure_ascii=False) + "\n", encoding="utf-8")
        out[key] = dest / as_name
    return out
