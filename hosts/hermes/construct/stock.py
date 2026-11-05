"""The constructs the plugin ships to start from (construct_start example=..., the Constructs page's "Start from").

Each is a finished construct from Construct's gallery (or a showcase), copied whole into a new project when chosen.
In the published package they sit in examples/<name>/ (scene.json, its material map as scene.materials.json, a
still as thumb.jpg, a kit plan when it has one) with examples/catalog.json describing them; in a source checkout
they are read where the repository keeps them. scripts/hermes_plugin.py writes the package's copies from STOCK.
"""

import json
import re
from pathlib import Path

# name -> the folder (from the repository's root) holding scene.json, and maps/finish.json, thumb.jpg, kit-plan.json
STOCK = {
    "toyota-land-cruiser-fj62": "examples/toyota-land-cruiser-fj62",
    "volkswagen-t1-samba": "examples/volkswagen-t1-samba",
    "vespa-gs150": "examples/vespa-gs150",
    "eames-lounge-chair": "examples/eames-lounge-chair",
    "braun-sk4": "examples/braun-sk4",
    "braun-sk4-knob": "examples/braun-sk4-knob",
    "revox-a77": "examples/revox-a77",
    "yamaha-cfx": "examples/yamaha-cfx",
    "tompion-year-going-clock": "examples/tompion-year-going-clock",
    "garden-shed": "examples/garden-shed",
    "garden-shed-planned": "examples/garden-shed-planned",
    "sainte-chapelle": "examples/sainte-chapelle",
    "duomo-di-milano": "examples/duomo-di-milano",
    "neuschwanstein": "examples/neuschwanstein",
    "kestrel": "hosts/hermes/examples/kestrel",
    "kestrel-v2": "hosts/hermes/examples/kestrel-v2",
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
    "yamaha-cfx": "an instrument, with a model kit plan",
    "tompion-year-going-clock": "an antique with opening doors, with a model kit plan",
    "garden-shed": "a building from one photograph",
    "garden-shed-planned": "the same shed with a planned change built on",
    "sainte-chapelle": "architecture, from plans and published heights",
    "duomo-di-milano": "a cathedral of spires",
    "neuschwanstein": "a castle on its rock",
    "kestrel": "an original design invented from real hardware (a game brief)",
    "kestrel-v2": "the same ship, refined with 242 more parts",
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
    return {"scene": folder / "scene.json", "materials": have("maps/finish.json"), "thumb": have("thumb.jpg"),
            "kit_plan": have("kit-plan.json"), "readme": have("README.md")}


def package_files(folder):
    """The package's files of one stock construct, in examples/<name>/."""
    folder = Path(folder)

    def have(rel):
        p = folder / rel
        return p if p.is_file() else None
    return {"scene": folder / "scene.json", "materials": have("scene.materials.json"), "thumb": have("thumb.jpg"),
            "kit_plan": have("kit-plan.json"), "readme": None}
