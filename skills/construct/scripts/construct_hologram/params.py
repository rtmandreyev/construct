"""Parametric archetypes: the simple path for models that struggle with full scenes.

A model fills a short parameter document; a deterministic builder draws the object as a
complete scene (format 2) in the house style: real proportions, staged assembly, named
artwork slots, labels set from the facts that exist, anchors and the opening sequence.

    {"format": "construct-params", "version": 1,
     "archetype": "case", "variant": "jewel",
     "id": "example-album", "title": "Example Album",
     "facts": [{"key": "title", "value": "Example Album", "certainty": "user_supplied", "source": "request"},
               {"key": "artist", "value": "Example Artist", "certainty": "user_supplied", "source": "request"}],
     "artwork": {"cover-front": "front"}, "assets": [ ... ],
     "params": {}}

`params` may be empty: every size defaults to the archetype's standard (an inferred fact).
A size given in `params` is inferred too unless `param_certainty` says otherwise
({"height": "user_supplied"}). Unknown facts are left out; nothing is guessed.
"""

import math

from . import product
from . import scene as scene_mod

FORMAT = product.PARAMS_FORMAT
FORMATS = (FORMAT, product.LEGACY_PARAMS_FORMAT)  # the legacy id is read for one release
VERSION = 1
DOC_KEYS = {"format", "version", "archetype", "variant", "id", "title", "summary", "synthetic", "sources",
            "facts", "assets", "artwork", "params", "param_certainty", "authoring"}
DOC_REQUIRED = {"format", "version", "archetype", "variant", "id", "title"}
CREATOR_FIELDS = ("artist", "author", "creator", "composer", "brewery", "maker")

# archetype -> variant -> (category, standard parameters, artwork slots, note)
VARIANTS = {
    "case": {
        "jewel": ("cd", {"width": 0.142, "height": 0.125, "depth": 0.0104}, ("cover-front", "inlay", "disc"),
                  "standard CD jewel case"),
        "slim": ("cd", {"width": 0.142, "height": 0.125, "depth": 0.0052}, ("cover-front", "cover-back", "disc"),
                 "standard slim CD case"),
        "digipak": ("cd", {"width": 0.1395, "height": 0.125, "depth": 0.008}, ("cover-front", "cover-back", "inlay", "disc"),
                    "typical two-panel digipak"),
        "box": ("cd", {"width": 0.145, "height": 0.130, "discs": 3}, ("cover-front", "cover-back"),
                "a slipcase of slim cases"),
    },
    "book": {
        "hardcover": ("book", {"width": 0.156, "height": 0.234, "thickness": 0.036}, ("cover-front", "cover-back"),
                      "a common trade hardcover"),
        "paperback": ("book", {"width": 0.129, "height": 0.198, "thickness": 0.025}, ("cover-front", "cover-back"),
                      "a common mass-market paperback"),
    },
    "object": {
        "electric-guitar": ("object", {"body_style": "double-cut", "scale_length": 0.648, "strings": 6, "frets": 22,
                                       "pickups": 3, "knobs": 3}, (), "a solid-body electric guitar"),
        "acoustic-guitar": ("object", {"scale_length": 0.645, "strings": 6, "frets": 20}, (), "a dreadnought acoustic guitar"),
        "bass-guitar": ("object", {"scale_length": 0.864, "strings": 4, "frets": 20, "pickups": 2, "knobs": 3}, (),
                        "a solid-body electric bass"),
        "synth": ("object", {"keys": 49, "knob_rows": 2, "knobs_per_row": 8, "screen": True, "wheels": True}, (),
                  "a keyboard synthesizer"),
    },
    "vehicle": {
        "wedge": ("vehicle", {"length": 4.14, "width": 1.89, "height": 1.07, "wheelbase": 2.45, "wheel_diameter": 0.64},
                  (), "a mid-engined wedge supercar"),
        "coupe": ("vehicle", {"length": 4.57, "width": 1.68, "height": 1.34, "wheelbase": 2.49, "wheel_diameter": 0.70},
                  (), "a front-engined grand-touring coupe"),
        "sedan": ("vehicle", {"length": 4.80, "width": 1.83, "height": 1.45, "wheelbase": 2.85, "wheel_diameter": 0.68},
                  (), "a four-door sedan"),
    },
    "vessel": {
        "bottle": ("object", {"height": 0.235, "diameter": 0.061}, ("label",), "a 330 ml long-neck bottle"),
        "can": ("object", {"height": 0.115, "diameter": 0.066}, ("label",), "a 330 ml can"),
        "glass": ("object", {"glass_style": "pint", "height": 0.15, "diameter": 0.086, "fill": 0.85}, (),
                  "a pint glass"),
    },
}

# parameter -> (minimum, maximum, integer, help); choices for text parameters
PARAMS = {
    "width": (0.02, 3.0, False, "outer width, metres"),
    "height": (0.02, 3.0, False, "outer height, metres"),
    "depth": (0.002, 1.0, False, "outer depth (thickness) closed, metres"),
    "thickness": (0.003, 0.2, False, "thickness of the closed book, metres"),
    "diameter": (0.02, 0.5, False, "widest diameter, metres"),
    "discs": (1, 12, True, "number of discs"),
    "scale_length": (0.4, 1.0, False, "nut-to-bridge string length, metres"),
    "strings": (4, 12, True, "number of strings"),
    "frets": (12, 27, True, "number of frets"),
    "pickups": (0, 3, True, "number of pickups"),
    "knobs": (0, 6, True, "number of control knobs"),
    "keys": (25, 88, True, "number of keys"),
    "knob_rows": (0, 4, True, "rows of knobs on the panel"),
    "knobs_per_row": (0, 16, True, "knobs in each row"),
    "fill": (0.0, 1.0, False, "how full the glass is"),
    "length": (1.0, 12.0, False, "overall length, metres"),
    "wheelbase": (0.8, 7.0, False, "front to rear axle, metres"),
    "wheel_diameter": (0.3, 1.5, False, "outer tyre diameter, metres"),
}
CHOICES = {
    "body_style": ("double-cut", "single-cut", "offset"),
    "glass_style": ("pint", "tulip", "stange"),
    "screen": (True, False), "wheels": (True, False),
}


# ---------------------------------------------------------------------------- the document

def is_params(doc):
    """Whether a parsed document is a parameter document (current or legacy id)."""
    return isinstance(doc, dict) and doc.get("format") in FORMATS


def template(archetype, variant=None):
    """A complete parameter document for an archetype, ready to fill in."""
    if archetype not in VARIANTS:
        raise scene_mod.SceneError("no archetype %r; choose one of %s" % (archetype, ", ".join(VARIANTS)))
    variant = variant or next(iter(VARIANTS[archetype]))
    if variant not in VARIANTS[archetype]:
        raise scene_mod.SceneError("archetype %s has the variants %s" % (archetype, ", ".join(VARIANTS[archetype])))
    category, defaults, slots, note = VARIANTS[archetype][variant]
    keys = {"case": ("title", "artist"), "book": ("title", "author"), "object": ("maker", "model"),
            "vessel": ("title", "brewery"), "vehicle": ("maker", "model")}[archetype]
    return {
        "format": FORMAT, "version": VERSION, "archetype": archetype, "variant": variant,
        "id": "my-%s" % variant, "title": "Replace with the item's name",
        "synthetic": False,
        "facts": [{"key": k, "value": "replace or delete", "certainty": "user_supplied", "source": "request"} for k in keys],
        "artwork": {},
        "params": {},
    }


def describe():
    """Every archetype, variant, slot and parameter, as text for a prompt."""
    lines = []
    for arch, variants in VARIANTS.items():
        for var, (_, defaults, slots, note) in variants.items():
            ps = ", ".join("%s=%s" % (k, str(v).lower() if isinstance(v, bool) else v) for k, v in defaults.items())
            lines.append("- %s / %s (%s): %s%s" % (arch, var, note, ps, "; slots: " + ", ".join(slots) if slots else ""))
    lines.append("Parameters: " + "; ".join("%s (%s, %g..%g)" % (k, h, lo, hi) for k, (lo, hi, _, h) in PARAMS.items()))
    lines.append("Choices: " + "; ".join("%s: %s" % (k, ", ".join(str(c).lower() for c in v)) for k, v in CHOICES.items()))
    return "\n".join(lines)


def validate_items(doc):
    """Problems in a parameter document as {where, message, code, hint} (paths from `scene`)."""
    c = scene_mod._Check()
    if not c.keys(doc, DOC_KEYS, DOC_REQUIRED, "scene"):
        return c.items
    if doc.get("format") not in FORMATS:
        c.err("scene.format", "must be %r" % FORMAT, "choice", 'Write "format": "%s".' % FORMAT)
    if doc.get("version") != VERSION:
        c.err("scene.version", "must be %d" % VERSION, "choice", '"version": %d' % VERSION)
    arch = doc.get("archetype")
    if not c.choice(arch, tuple(VARIANTS), "scene.archetype"):
        return c.items
    if not c.choice(doc.get("variant"), tuple(VARIANTS[arch]), "scene.variant"):
        return c.items
    _, defaults, slots, _ = VARIANTS[arch][doc["variant"]]
    params = doc.get("params", {})
    if c.keys(params, set(defaults) | ({"depth"} if arch == "case" and "depth" not in defaults else set())
              | ({"width", "height"} if arch in ("case", "book") else set()), set(), "scene.params"):
        for k, v in params.items():
            if k in CHOICES:
                c.choice(v, CHOICES[k], "scene.params." + k)
            elif k in PARAMS:
                lo, hi, integer, _ = PARAMS[k]
                c.num(v, "scene.params." + k, lo, hi, integer)
    pc = doc.get("param_certainty", {})
    if c.keys(pc, set(defaults) | set(params), set(), "scene.param_certainty"):
        for k, v in pc.items():
            c.choice(v, ("verified", "user_supplied", "inferred"), "scene.param_certainty." + k)
    art = doc.get("artwork", {})
    if c.keys(art, set(slots), set(), "scene.artwork"):
        ids = {a.get("id") for a in doc.get("assets", []) if isinstance(a, dict)}
        for slot, asset in art.items():
            if asset not in ids:
                c.err("scene.artwork." + slot, "unknown asset %r" % asset, "reference",
                      "Name one of the document's assets by id, or remove this slot (it stays empty).")
    if "authoring" in doc:
        from . import tiers
        srcs = [x for x in doc.get("sources", []) if isinstance(x, dict)] or [{"id": "request", "kind": "user_request"}]
        tiers.check(c, doc["authoring"], {x.get("id") for x in srcs} | {"request"}, srcs)
    return c.items


def expand(doc):
    """The full scene for a valid parameter document."""
    errors = validate_items(doc)
    if errors:
        raise scene_mod.SceneError("\n".join("%s: %s" % (e["where"], e["message"]) for e in errors))
    arch, var = doc["archetype"], doc["variant"]
    category, defaults, slots, note = VARIANTS[arch][var]
    b = _Builder(doc, category, defaults, note)
    BUILDERS[arch](b, var, b.p)
    return b.scene()


# ---------------------------------------------------------------------------- building blocks

class _Builder:
    def __init__(self, doc, category, defaults, note):
        self.doc, self.category, self.note = doc, category, note
        self.p = dict(defaults)
        self.p.update(doc.get("params", {}))
        self.given = set(doc.get("params", {}))
        self.cert = doc.get("param_certainty", {})
        self.facts = [dict(f) for f in doc.get("facts", [])]
        self.known = {f["key"]: f for f in self.facts if isinstance(f, dict) and f.get("value") is not None}
        self.parts, self.labels, self.arts = [], [], []
        self.anchors, self.views, self.annotations = {}, [], []
        self.framing = {"yaw": 30, "pitch": 14, "fit": 1.0}
        self.atmosphere = {"haze": 0.7, "grid": True, "projector": True, "motes": 0.35}

    def dim(self, key, value, unit="m"):
        """A size as a fact: standard (inferred) unless the parameters gave it with a certainty."""
        if key in self.known:
            return key
        if key in self.given:
            cert = self.cert.get(key, "inferred")
            note = "given in the parameters"
        else:
            cert, note = "inferred", "the standard for %s" % self.note
        f = {"key": key, "value": round(value, 5) if isinstance(value, float) else value, "certainty": cert, "note": note}
        if unit:
            f["unit"] = unit
        if cert in ("verified", "user_supplied"):
            f["source"] = "request"
        self.facts.append(f)
        self.known[key] = f
        return key

    def creator(self):
        return next((k for k in CREATOR_FIELDS if k in self.known), None)

    def part(self, pid, role, shape, at=(0, 0, 0), stage=0, certainty="inferred", **kw):
        p = {"id": pid, "role": role, "certainty": certainty, "stage": stage, "shape": shape,
             "at": [round(x, 6) for x in at]}
        p.update({k: v for k, v in kw.items() if v is not None})
        self.parts.append(p)
        return p

    def slot(self, slot, **kw):
        a = {"slot": slot}
        asset = self.doc.get("artwork", {}).get(slot)
        if asset:
            a["asset"] = asset
        a.update(kw)
        return a

    def art_certainty(self, slot):
        asset = self.doc.get("artwork", {}).get(slot)
        a = next((x for x in self.doc.get("assets", []) if x.get("id") == asset), None)
        if a is None:
            return "inferred"
        return "decorative" if a.get("provenance") in ("generated-decorative", "synthetic") else "user_supplied"

    def label(self, lid, part, field, role, face=None, orientation="horizontal", region=None, align="center"):
        if field is None or field not in self.known:
            return  # an unknown fact has no label
        lb = {"id": lid, "part": part, "field": field, "role": role, "orientation": orientation, "align": align}
        if face:
            lb["face"] = face
        if region:
            lb["region"] = region
        self.labels.append(lb)

    def scene(self):
        # a text carrier nobody writes on draws nothing: leave it out
        used = {lb["part"] for lb in self.labels} | {a.get("part") for a in self.anchors.values() if isinstance(a, dict)}
        self.parts = [p for p in self.parts if p["id"] in used or "artwork" in p
                      or p.get("look", {}).get("line") != "none" or p.get("look", {}).get("fill", "auto") != "none"]
        doc = self.doc
        synthetic = bool(doc.get("synthetic", False))
        sources = [dict(s) for s in doc.get("sources", [])] or [
            {"id": "request", "kind": "user_request", "title": "The request", "rights": "synthetic" if synthetic else "user_private"}]
        if not any(s.get("id") == "request" for s in sources) and any(f.get("source") == "request" for f in self.facts):
            sources.append({"id": "request", "kind": "user_request", "title": "The request",
                            "rights": "synthetic" if synthetic else "user_private"})
        s = {
            "format": scene_mod.FORMAT, "version": scene_mod.VERSION, "id": doc["id"], "title": doc["title"],
            "subject": {"category": self.category, "accuracy": "generic", "synthetic": synthetic,
                        "summary": doc.get("summary") or "%s, built from parameters (%s)." % (doc["title"], self.note)},
            "units": "m", "seed": sum(ord(ch) for ch in doc["id"]) % 9973,
            "sources": sources, "facts": self.facts, "assets": [dict(a) for a in doc.get("assets", [])],
            "parts": self.parts,
        }
        if doc.get("authoring"):
            s["authoring"] = dict(doc["authoring"])
        if self.arts:
            s["articulations"] = self.arts
        if self.labels:
            s["labels"] = self.labels
        if self.anchors:
            s["anchors"] = self.anchors
        if self.annotations:
            s["annotations"] = self.annotations
        s["presentation"] = {"framing": self.framing, "views": self.views, "atmosphere": self.atmosphere,
                             "occlusion": "xray", "still_pose": "open"}
        s["animation"] = {"assembly": {"style": "ceremony", "seconds": 4.5, "interference": True},
                          "idle": {"life": "calm", "events": ["scan", "sweep", "shimmer"], "cadence": [6, 12], "strength": 0.5},
                          "camera": {"drift": 5, "breathe": 0.02}}
        return s


def _box(size, ribs=0, **kw):
    s = {"type": "box", "size": [round(x, 6) for x in size]}
    if ribs:
        s["ribs"] = ribs
    s.update(kw)
    return s


def _disc_profile(radius, hole=0.0075):
    rs = [hole, 0.017, 0.023, 0.025, 0.032, 0.039, 0.046, 0.052, 0.057, 0.06]
    k = radius / 0.06
    return [[round(r * k if i else hole, 5), 0] for i, r in enumerate(rs)]


def _smooth_closed(points, samples=4):
    out, n = [], len(points)
    for i in range(n):
        p0, p1, p2, p3 = points[i - 1], points[i], points[(i + 1) % n], points[(i + 2) % n]
        for s in range(samples):
            t = s / samples
            t2, t3 = t * t, t * t * t
            out.append([round(0.5 * ((2 * p1[k]) + (-p0[k] + p2[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2
                                     + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3), 5) for k in range(2)])
    return out


# ---------------------------------------------------------------------------- case

def _disc(b, at, radius, stage, parts_extra=()):
    b.dim("disc.diameter", 0.12)
    b.part("disc", "identity", {"type": "lathe", "segments": 64, "meridians": 0, "profile": _disc_profile(radius)},
           at, stage, rotate=[90, 0, 0], look={"fill": "glass", "glow": 0.5}, basis=["disc.diameter"],
           artwork=b.slot("disc", mask="circle", inner_radius=0.0075), certainty="inferred")
    k = radius / 0.06
    b.part("disc-shine", "ornament", {"type": "curve", "smooth": True, "points": [
        [-0.045 * k, 0.012 * k, 0], [-0.03 * k, 0.035 * k, 0], [-0.005 * k, 0.05 * k, 0], [0.02 * k, 0.052 * k, 0]]},
        (at[0], at[1], at[2] + 0.0008), stage + 2, certainty="decorative", look={"tone": "bright", "glow": 0.8, "alpha": 0.5})
    b.arts += [{"id": "disc-lift", "type": "lift", "parts": ["disc", "disc-shine"], "axis": [0, 0, 1], "amount": 0.03, "order": 1},
               {"id": "disc-turn", "type": "turn", "parts": ["disc", "disc-shine"], "axis": [0, 0, 1],
                "pivot": [round(x, 6) for x in at], "amount": 360, "order": 2}]


def build_case(b, var, p):
    w, h = p["width"], p["height"]
    size = b.dim("case.size", "%g x %g x %g" % (w, h, p.get("depth", 0)) if var != "box" else "%g x %g" % (w, h), unit="m")
    who = b.creator()
    b.framing = {"yaw": -58, "pitch": 12, "fit": 1.0}
    b.views = [{"id": "spine", "label": "Spine", "yaw": -88, "pitch": 4, "distance": 1.0}]
    if var in ("jewel", "slim"):
        d = p["depth"]
        tray_d, lid_d, z0 = d * 0.6, d * 0.4, -d / 2
        b.part("tray", "mass", _box([w, h, tray_d]), (0, h / 2, z0 + tray_d / 2), 0, basis=[size],
               artwork=b.slot("inlay" if var == "jewel" else "cover-back", face="back"))
        b.part("hinge", "detail", {"type": "cylinder", "radius": 0.0022, "height": 0.022, "segments": 10, "ribs": 2},
               (-w / 2 + 0.0005, 0.012 * h / 0.125, z0 + tray_d), 0, repeat={"count": 2, "step": {"at": [0, round(h - 0.046, 5), 0]}})
        radius = min(0.06, min(w, h) / 2 - 0.002)
        _disc(b, (0.003 * w / 0.142, h / 2, z0 + tray_d + 0.0004), radius, 1)
        b.part("lid", "mass", _box([w, h, lid_d]), (0, h / 2, d / 2 - lid_d / 2), 2, basis=[size], look={"glow": 0.4})
        inner = "booklet" if var == "jewel" else "insert"
        bw = min(0.12, h - 0.005, w - 0.01)
        b.part(inner, "artwork", {"type": "plane", "size": [round(bw, 5), round(bw, 5)]},
               (0.005 * w / 0.142, h / 2, d / 2 - lid_d * 0.15), 2, certainty=b.art_certainty("cover-front"),
               artwork=b.slot("cover-front"))
        b.arts.insert(0, {"id": "lid-open", "type": "hinge", "parts": ["lid"] if var == "jewel" else ["lid", inner],
                          "axis": [0, -1, 0], "pivot": [round(-w / 2, 6), round(h / 2, 6), round(d / 2, 6)],
                          "amount": 108, "order": 0})
        if var == "jewel":
            # the booklet is taken out and laid beside the case, cover to the front (the lid is on the left)
            b.arts.insert(1, {"id": "booklet-lift", "type": "lift", "parts": ["booklet"], "axis": [0, 0, 1],
                              "amount": 0.045, "order": 1})
            b.arts.insert(2, {"id": "booklet-out", "type": "slide", "parts": ["booklet"], "axis": [1, 0, 0],
                              "amount": round(w * 1.09, 4), "order": 2})
        # a slim case prints its spine too (about 5 mm): the rack reads it
        b.label("spine-title", "tray", "title", "title", "left", "vertical-down", [0, 0.04, 1, 0.58])
        b.label("spine-creator", "tray", who, "creator", "left", "vertical-down", [0, 0.62, 1, 0.96])
        b.anchors = {"front": {"part": "lid", "face": "front"}, "spine": {"part": "tray", "face": "left"}}
        b.views.append({"id": "open", "label": "Open", "yaw": -12 if var == "jewel" else -30, "pitch": 12, "distance": 1.0})
    elif var == "digipak":
        d, t = p["depth"], 0.0016
        z0 = -d / 2
        b.part("back-panel", "mass", _box([w, h, t]), (0, h / 2, z0 + t / 2), 0, basis=[size],
               artwork=b.slot("cover-back", face="back"))
        b.part("spine", "structure", _box([t, h, d]), (-w / 2 + t / 2, h / 2, 0), 0, basis=[size])
        tray_d = max(0.002, d - 2 * t - 0.0015)
        b.part("tray", "structure", _box([w - 0.012, h - 0.01, tray_d]), (0.003, h / 2, z0 + t + tray_d / 2), 1,
               look={"fill": "glass"})
        _disc(b, (0.003, h / 2, z0 + t + tray_d + 0.0004), min(0.06, min(w, h) / 2 - 0.004), 2)
        b.part("front-panel", "mass", _box([w, h, t]), (0, h / 2, d / 2 - t / 2), 3, basis=[size],
               artwork=b.slot("cover-front"))
        b.part("inside", "artwork", {"type": "plane", "size": [round(w - 0.004, 5), round(h - 0.004, 5)]},
               (0, h / 2, d / 2 - t - 0.0002), 3, rotate=[0, 180, 0], certainty=b.art_certainty("inlay"),
               artwork=b.slot("inlay"))
        b.arts.insert(0, {"id": "panel-open", "type": "hinge", "parts": ["front-panel", "inside"], "axis": [0, -1, 0],
                          "pivot": [round(-w / 2, 6), round(h / 2, 6), round(d / 2, 6)], "amount": 170, "order": 0})
        b.label("spine-title", "spine", "title", "title", "left", "vertical-down", [0, 0.04, 1, 0.58])
        b.label("spine-creator", "spine", who, "creator", "left", "vertical-down", [0, 0.62, 1, 0.96])
        b.anchors = {"front": {"part": "front-panel", "face": "front"}, "spine": {"part": "spine", "face": "left"}}
        b.views.append({"id": "open", "label": "Open", "yaw": 10, "pitch": 14, "distance": 1.0})
    else:  # box: a slipcase open on its right, holding slim cases that slide out
        n, t, cd = p["discs"], 0.0015, 0.0052
        d = n * cd + 2 * t + 0.001
        b.dim("discs", n, unit=None)
        b.part("sleeve-back", "mass", _box([w, h, t]), (0, h / 2, -d / 2 + t / 2), 0, basis=[size],
               artwork=b.slot("cover-back", face="back"))
        b.part("sleeve-spine", "structure", _box([t, h, d]), (-w / 2 + t / 2, h / 2, 0), 0, basis=[size])
        b.part("sleeve-bottom", "structure", _box([w - t, t, d - 2 * t]), (t / 2, t / 2, 0), 0)
        b.part("sleeve-top", "structure", _box([w - t, t, d - 2 * t]), (t / 2, h - t / 2, 0), 0)
        b.part("cases", "structure", _box([w - 0.006, h - 2 * t - 0.0004, cd - 0.0004]),
               (0.0015, h / 2, -d / 2 + t + 0.0005 + cd / 2), 1, look={"fill": "glass"},
               repeat={"count": n, "step": {"at": [0, 0, cd]}} if n > 1 else None)
        b.part("discs", "identity", {"type": "lathe", "segments": 48, "meridians": 0, "profile": _disc_profile(0.058)},
               (0.0035, h / 2, -d / 2 + t + 0.0005 + cd * 0.75), 2, rotate=[90, 0, 0], look={"fill": "glass", "glow": 0.4},
               repeat={"count": n, "step": {"at": [0, 0, cd]}} if n > 1 else None)
        b.part("sleeve-front", "mass", _box([w, h, t]), (0, h / 2, d / 2 - t / 2), 3, basis=[size],
               artwork=b.slot("cover-front"))
        b.arts = [{"id": "cases-out", "type": "slide", "parts": ["cases", "discs"], "axis": [1, 0, 0],
                   "amount": round(0.62 * w, 4), "order": 0}]
        b.label("spine-title", "sleeve-spine", "title", "title", "left", "vertical-down", [0, 0.04, 1, 0.58])
        b.label("spine-creator", "sleeve-spine", who, "creator", "left", "vertical-down", [0, 0.62, 1, 0.96])
        b.anchors = {"front": {"part": "sleeve-front", "face": "front"}, "spine": {"part": "sleeve-spine", "face": "left"}}
        b.framing = {"yaw": 34, "pitch": 14, "fit": 1.0}
        b.views.append({"id": "open", "label": "Open", "yaw": 40, "pitch": 18, "distance": 1.0})
    b.annotations = []


# ---------------------------------------------------------------------------- book

def build_book(b, var, p):
    W, H, T = p["width"], p["height"], p["thickness"]
    size = b.dim("book.size", "%g x %g x %g" % (W, H, T))
    who = b.creator()
    hard = var == "hardcover"
    bt = 0.003 if hard else 0.0006
    b.part("back-board", "structure", _box([W, H, bt]), (0, H / 2, -T / 2 + bt / 2), 0, basis=[size],
           artwork=b.slot("cover-back", face="back"))
    inset = 0.004 if hard else 0.001
    b.part("pages", "detail", _box([W - 2 * inset, H - 2 * inset, T - 2 * bt], ribs=7 if hard else 5), (inset * 0.75, H / 2, 0), 1,
           look={"tone": "hairline", "fill": "glass"})
    if hard:
        bulge = T * 0.23
        x0 = -W / 2
        prof = [(x0, -T / 2), (x0 - 0.6 * bulge, -0.36 * T), (x0 - 0.95 * bulge, -0.17 * T), (x0 - bulge, 0),
                (x0 - 0.95 * bulge, 0.17 * T), (x0 - 0.6 * bulge, 0.36 * T), (x0, T / 2), (x0 + 0.0025, T / 2), (x0 + 0.0025, -T / 2)]
        b.part("spine", "identity", {"type": "extrude", "axis": "y", "height": round(H, 5),
                                     "profile": [[round(u, 5), round(v, 5)] for u, v in prof]}, (0, 0, 0), 1)
        b.part("spine-face", "detail", {"type": "plane", "size": [round(T * 0.94, 5), round(H - 0.008, 5)]},
               (x0 - bulge - 0.0001, H / 2, 0), 1, rotate=[0, -90, 0], look={"line": "none", "fill": "none"},
               note="the flat of the spine that carries its lettering")
        spine, face = "spine-face", "front"
        b.part("headband", "ornament", {"type": "cylinder", "radius": 0.0016, "height": round(T * 0.83, 5), "segments": 8, "ribs": 2},
               (x0 + 0.0035, H - 0.0065, -T * 0.42), 3, rotate=[90, 0, 0], certainty="decorative")
    else:
        b.part("spine", "identity", _box([0.0008, H, T]), (-W / 2 - 0.0005, H / 2, 0), 1)
        spine, face = "spine", "left"
    b.part("front-board", "mass", _box([W, H, bt]), (0, H / 2, T / 2 - bt / 2), 2, basis=[size])
    has_cover = bool(b.doc.get("artwork", {}).get("cover-front"))
    b.part("cover-art", "artwork", {"type": "plane", "size": [round(W - 0.006, 5), round(H - 0.006, 5)]},
           (0, H / 2, T / 2 + 0.0001), 3, certainty=b.art_certainty("cover-front"), artwork=b.slot("cover-front"),
           look={"line": "none", "fill": "none"} if not has_cover else {})
    b.arts = [{"id": "board-open", "type": "hinge", "parts": ["front-board", "cover-art"], "axis": [0, -1, 0],
               "pivot": [round(-W / 2, 6), round(H / 2, 6), round(T / 2, 6)], "amount": 115 if hard else 125, "order": 0}]
    b.label("spine-title", spine, "title", "title", face, "vertical-down", [0.05, 0.06, 0.95, 0.66])
    b.label("spine-creator", spine, who, "creator", face, "vertical-down", [0.1, 0.7, 0.9, 0.94])
    b.label("title-page", "pages", "title", "title", "front", region=[0.12, 0.26, 0.88, 0.36])
    b.label("title-page-creator", "pages", who, "creator", "front", region=[0.22, 0.42, 0.78, 0.48])
    if not has_cover:  # the designed no-art face: the title and author set on the board
        b.label("cover-title", "front-board", "title", "title", "front", region=[0.1, 0.14, 0.9, 0.3])
        b.label("cover-creator", "front-board", who, "creator", "front", region=[0.18, 0.36, 0.82, 0.44])
    b.anchors = {"front": {"part": "front-board", "face": "front"}, "spine": {"part": spine, "face": face}}
    b.framing = {"yaw": -55, "pitch": 12, "fit": 1.0}
    b.views = [{"id": "spine", "label": "Spine", "yaw": -82, "pitch": 6, "distance": 1.0},
               {"id": "open", "label": "Open", "yaw": 12, "pitch": 10, "distance": 1.0}]


# ---------------------------------------------------------------------------- object: guitars

# right-hand half outlines, (x as a fraction of body width, y as a fraction of body length),
# from the bottom centre up to the top centre; the left half mirrors it unless given
OUTLINES = {
    "double-cut": ([(0, 0), (0.28, 0.02), (0.44, 0.12), (0.5, 0.27), (0.47, 0.42), (0.38, 0.55), (0.4, 0.68),
                    (0.42, 0.82), (0.4, 0.93), (0.34, 1.0), (0.27, 0.95), (0.2, 0.84), (0.1, 0.8), (0, 0.8)], None),
    "offset": ([(0, 0), (0.3, 0.02), (0.46, 0.13), (0.5, 0.3), (0.45, 0.46), (0.36, 0.56), (0.37, 0.7), (0.4, 0.86),
                (0.36, 0.97), (0.3, 0.99), (0.25, 0.9), (0.18, 0.8), (0.1, 0.78), (0, 0.78)],
               [(0, 0), (0.3, 0.02), (0.46, 0.13), (0.5, 0.3), (0.46, 0.45), (0.4, 0.55), (0.42, 0.66), (0.42, 0.74),
                (0.36, 0.8), (0.25, 0.79), (0.1, 0.78), (0, 0.78)]),
    "single-cut": ([(0, 0), (0.3, 0.02), (0.46, 0.14), (0.5, 0.3), (0.46, 0.46), (0.38, 0.56), (0.4, 0.68),
                    (0.36, 0.82), (0.28, 0.9), (0.22, 0.83), (0.14, 0.8), (0, 0.8)],
                   [(0, 0), (0.3, 0.02), (0.46, 0.14), (0.5, 0.3), (0.46, 0.46), (0.38, 0.56), (0.42, 0.7),
                    (0.4, 0.84), (0.3, 0.95), (0.14, 0.99), (0.08, 0.99), (0, 0.98)]),
    "acoustic": ([(0, 0), (0.3, 0.01), (0.45, 0.1), (0.5, 0.26), (0.47, 0.42), (0.4, 0.55), (0.4, 0.66), (0.43, 0.78),
                  (0.4, 0.9), (0.3, 0.98), (0.15, 1.0), (0, 1.0)], None),
}


def _outline(style, width, length):
    right, left = OUTLINES[style]
    left = left or right
    pts = [(x * width, y * length) for x, y in right]
    pts += [(-x * width, y * length) for x, y in reversed(left[1:-1])]
    return _smooth_closed(pts, 2)


def build_guitar(b, var, p):
    acoustic, bass = var == "acoustic-guitar", var == "bass-guitar"
    style = "acoustic" if acoustic else p.get("body_style", "offset" if bass else "double-cut")
    S = p["scale_length"]
    L, W, t = (0.51, 0.40, 0.1) if acoustic else (0.47, 0.34, 0.045) if bass else (0.45, 0.33, 0.045)
    yb = 0.17 if acoustic else 0.11 if bass else 0.12          # bridge height above the bottom of the body
    yn = yb + S                                                  # the nut
    b.dim("scale_length", S)
    b.dim("body.size", "%g x %g x %g" % (W, L, t))
    n, frets = p["strings"], p["frets"]
    b.dim("strings", n, unit=None)
    b.framing = {"yaw": 24, "pitch": 6, "fit": 1.0}
    b.atmosphere = {"haze": 0.7, "grid": True, "projector": False, "motes": 0.3}
    b.part("body", "mass", {"type": "extrude", "axis": "z", "height": t, "profile": _outline(style, W, L)},
           (0, 0, -t / 2), 0, basis=["body.size"], look={"fill": "glass"})
    top = L * (0.8 if style in ("double-cut", "single-cut") else 0.78 if style == "offset" else 1.0)
    heel = top - (0.07 if not acoustic else 0.02)
    wn, wh = (0.045, 0.057) if not bass else (0.038, 0.06)
    nz = t / 2
    neck_t = 0.02
    b.part("neck", "structure", {"type": "extrude", "axis": "z", "height": neck_t, "profile": [
        [-wh / 2, round(heel, 5)], [wh / 2, round(heel, 5)], [wn / 2, round(yn, 5)], [-wn / 2, round(yn, 5)]]},
        (0, 0, nz), 1, basis=["scale_length"], look={"fill": "glass"})
    fz = nz + neck_t + 0.0006
    for k in range(1, frets + 1):
        y = yn - S * (1 - 2 ** (-k / 12.0))
        if y < heel + 0.006:
            break
        wy = wh + (wn - wh) * (y - heel) / (yn - heel)
        b.part("fret-%d" % k, "detail", {"type": "curve", "points": [[round(-wy / 2, 5), 0, 0], [round(wy / 2, 5), 0, 0]]},
               (0, y, fz), 2, look={"weight": 0.8})
    b.part("nut", "detail", _box([wn, 0.005, 0.006]), (0, yn - 0.0025, nz + neck_t + 0.003), 2)
    # headstock: a paddle with tuners on both sides, or all on one side
    hl = 0.19 if not bass else 0.21
    inline = not acoustic and style != "single-cut"
    if inline:
        prof = [(-wn / 2, 0), (wn / 2, 0), (0.016, 0.05), (0.014, hl * 0.82), (0.0, hl), (-0.03, hl), (-0.044, hl * 0.85),
                (-0.036, 0.05)]
    else:
        prof = [(-wn / 2, 0), (wn / 2, 0), (0.043, 0.05), (0.046, hl * 0.88), (0.0, hl), (-0.046, hl * 0.88), (-0.043, 0.05)]
    ht = 0.014
    b.part("headstock", "identity", {"type": "extrude", "axis": "z", "height": ht,
                                     "profile": [[round(u, 5), round(v, 5)] for u, v in prof]},
           (0, yn, nz + 0.004), 2, look={"fill": "glass"})
    hz = nz + 0.004 + ht
    if inline:
        step = (hl * 0.78) / max(1, n)
        b.part("tuners", "detail", {"type": "cylinder", "radius": 0.008 if bass else 0.0055, "height": 0.013,
                                    "segments": 8, "ribs": 0},
               (-0.028, yn + 0.035, hz), 3, rotate=[90, 0, 0],
               repeat={"count": n, "step": {"at": [0, round(step, 5), 0]}})
    else:
        per = n // 2
        step = (hl * 0.7) / max(1, per)
        b.part("tuners", "detail", {"type": "cylinder", "radius": 0.008 if bass else 0.0055, "height": 0.013,
                                    "segments": 8, "ribs": 0},
               (0.032, yn + 0.045, hz), 3, rotate=[90, 0, 0], mirror="x",
               repeat={"count": per, "step": {"at": [0, round(step, 5), 0]}} if per > 1 else None)
    b.part("headstock-face", "detail", {"type": "plane", "size": [0.05, 0.03]}, (0, yn + hl * 0.62, hz), 2,
           look={"line": "none", "fill": "none"}, note="carries the maker's name as a label")
    b.label("maker", "headstock-face", "maker", "title")
    # bridge, pickups, knobs, sound hole
    if acoustic:
        b.part("bridge", "identity", _box([0.15, 0.028, 0.006]), (0, yb, nz + 0.003), 2)
        b.part("soundhole", "identity", {"type": "torus", "major": 0.044, "minor": 0.0018, "segments": 48, "sides": 6, "rings": 0},
               (0, L * 0.66, nz), 1, rotate=[90, 0, 0])
        b.part("rosette", "detail", {"type": "torus", "major": 0.054, "minor": 0.0025, "segments": 48, "sides": 6, "rings": 0},
               (0, L * 0.66, nz), 2, rotate=[90, 0, 0])
        sz = nz + 0.009
    else:
        b.part("bridge", "identity", _box([0.07 if not bass else 0.08, 0.022, 0.012]), (0, yb, nz + 0.006), 2)
        sz = nz + 0.012
        npk = p.get("pickups", 0)
        hum = style == "single-cut"
        for i in range(npk):
            f = (0.5 if npk == 1 else i / (npk - 1))
            y = yb + 0.035 + f * (heel - yb - 0.07)
            b.part("pickup-%d" % (i + 1), "identity", _box([0.07 if hum else 0.085 if not bass else 0.095,
                                                              0.04 if hum else 0.018, 0.008]),
                   (0, y, nz + 0.004), 2, basis=[])
        nk = p.get("knobs", 0)
        if nk:
            b.part("knobs", "detail", {"type": "cylinder", "radius": 0.011, "height": 0.012, "segments": 10, "ribs": 0},
                   (W * 0.24, L * 0.13, nz), 3, rotate=[90, 0, 0],
                   repeat={"count": nk, "step": {"at": [-0.006, 0.034, 0]}} if nk > 1 else None)
    # strings: from the bridge to the nut, spread wider at the bridge
    sb = (0.0105 if not bass else 0.019) * (n - 1)
    snut = wn - 0.008
    for i in range(n):
        f = i / (n - 1) - 0.5
        b.part("string-%d" % (i + 1), "detail", {"type": "curve", "points": [
            [round(f * sb, 5), round(yb, 5), round(sz, 5)], [round(f * snut, 5), round(yn, 5), round(nz + neck_t + 0.006, 5)]]},
            (0, 0, 0), 4, look={"tone": "bright", "alpha": 0.7, "weight": 0.7})
    b.views = [{"id": "headstock", "label": "Headstock", "yaw": 15, "pitch": 4, "distance": 2.2, "target": "headstock"},
               {"id": "body", "label": "Body", "yaw": 28, "pitch": 10, "distance": 1.3, "target": "body"}]
    b.anchors = {"grip": {"part": "neck"}}


# ---------------------------------------------------------------------------- object: synth

def build_synth(b, var, p):
    keys = p["keys"]
    ww = 0.0235                                    # white-key pitch
    nw = len([i for i in range(keys) if i % 12 in (0, 2, 4, 5, 7, 9, 11)])
    side = 0.11 if p["wheels"] else 0.03
    W, D, H, hb, kd = nw * ww + side + 0.03, 0.31, 0.08, 0.035, 0.145
    b.dim("keys", keys, unit=None)
    b.dim("case.size", "%g x %g x %g" % (round(W, 3), D, H))
    b.framing = {"yaw": 18, "pitch": 34, "fit": 1.0}
    b.atmosphere = {"haze": 0.7, "grid": True, "projector": False, "motes": 0.3}
    # a low base the keys rest on, and the raised control panel behind them
    b.part("base", "mass", _box([W, hb, D], anchor="base"), (0, 0, 0), 0, basis=["case.size"])
    dp = D - kd - 0.012
    b.part("panel", "mass", _box([W, H - hb, dp], anchor="base"), (0, hb, -D / 2 + dp / 2), 1, basis=["case.size"])
    x0 = -W / 2 + side + 0.015
    kz = D / 2 - 0.004 - kd / 2
    b.part("white-keys", "identity", _box([ww - 0.0012, 0.018, kd], anchor="base"), (x0 + ww / 2, hb, kz), 2,
           repeat={"count": nw, "step": {"at": [ww, 0, 0]}}, look={"fill": "glass"}, basis=["keys"])
    # black keys: one part per note class, repeated each octave
    offsets = {1: 0.65, 3: 1.75, 6: 3.62, 8: 4.68, 10: 5.74}
    for cls, off in offsets.items():
        count = len([i for i in range(keys) if i % 12 == cls])
        if count:
            b.part("black-keys-%d" % cls, "identity", _box([0.012, 0.016, 0.09], anchor="base"),
                   (x0 + off * ww, hb + 0.01, kz - kd / 2 + 0.045), 3,
                   repeat={"count": count, "step": {"at": [7 * ww, 0, 0]}} if count > 1 else None, look={"fill": "dark"})
    pz0, pz1 = -D / 2, -D / 2 + dp
    rows, per = p["knob_rows"], p["knobs_per_row"]
    if p["screen"]:
        b.part("screen", "data", {"type": "plane", "size": [0.09, 0.045]}, (x0 + 0.05, H + 0.0004, pz0 + dp * 0.4), 3,
               rotate=[-90, 0, 0], look={"glow": 0.6})
        b.label("model", "screen", "model", "title")
    kx0 = x0 + (0.13 if p["screen"] else 0.02)
    span = (W / 2 - 0.03) - kx0
    for r in range(rows if per else 0):
        z = pz0 + 0.025 + (r + 0.5) * (dp - 0.04) / rows
        b.part("knobs-%d" % (r + 1), "detail", {"type": "cylinder", "radius": 0.0085, "height": 0.012, "segments": 14, "ribs": 2},
               (kx0, H, z), 3, repeat={"count": per, "step": {"at": [round(span / max(per - 1, 1), 5), 0, 0]}} if per > 1 else None)
    if p["wheels"]:
        b.part("wheels", "identity", {"type": "cylinder", "radius": 0.024, "height": 0.012, "segments": 24, "ribs": 4},
               (-W / 2 + 0.04, hb + 0.02, kz), 2, rotate=[0, 0, 90], repeat={"count": 2, "step": {"at": [0.032, 0, 0]}})
    b.part("nameplate", "detail", {"type": "plane", "size": [0.12, 0.02]}, (x0 + nw * ww - 0.08, H + 0.0004, pz1 - 0.016), 2,
           rotate=[-90, 0, 0], look={"line": "none", "fill": "none"}, note="carries the maker's name")
    b.label("maker", "nameplate", "maker", "title", align="right")
    b.views = [{"id": "keys", "label": "Keys", "yaw": 0, "pitch": 40, "distance": 1.4, "target": "white-keys"}]
    b.anchors = {"front": {"part": "base", "face": "front"}}


def build_object(b, var, p):
    (build_synth if var == "synth" else build_guitar)(b, var, p)


# ---------------------------------------------------------------------------- vessel

def build_vessel(b, var, p):
    h, d = p["height"], p["diameter"]
    R = d / 2
    b.dim("height", h)
    b.dim("diameter", d)
    b.framing = {"yaw": 22, "pitch": 10, "fit": 1.0}
    who = b.creator()
    if var == "bottle":
        nr = min(0.0135, R * 0.45)
        prof = [(R * 0.86, 0), (R, h * 0.02), (R, h * 0.55), (R * 0.96, h * 0.6), (R * 0.72, h * 0.67), (nr * 1.25, h * 0.76),
                (nr, h * 0.82), (nr, h * 0.955), (nr * 1.12, h * 0.965), (nr * 1.12, h * 0.99), (nr * 0.85, h)]
        b.part("bottle", "mass", {"type": "lathe", "profile": [[round(r, 5), round(y, 5)] for r, y in prof],
                                  "segments": 40, "meridians": 8}, (0, 0, 0), 0, basis=["height", "diameter"])
        b.part("cap", "identity", {"type": "cylinder", "radius": round(nr * 1.18, 5), "height": round(h * 0.03, 5),
                                   "segments": 21, "ribs": 21}, (0, h * 0.975, 0), 2)
        b.part("label", "artwork", {"type": "plane", "size": [round(R * 1.4, 5), round(h * 0.26, 5)]},
               (0, h * 0.3, R + 0.0006), 1, certainty=b.art_certainty("label"), artwork=b.slot("label"),
               look=None if b.doc.get("artwork", {}).get("label") else {"line": "none", "fill": "none"})
    elif var == "can":
        prof = [(R * 0.86, 0), (R * 0.97, h * 0.01), (R, h * 0.04), (R, h * 0.9), (R * 0.84, h * 0.975), (R * 0.82, h),
                (0.0, h)]  # the lid closes the top
        b.part("can", "mass", {"type": "lathe", "profile": [[round(r, 5), round(y, 5)] for r, y in prof],
                               "segments": 48, "meridians": 8}, (0, 0, 0), 0, basis=["height", "diameter"])
        b.part("rim", "identity", {"type": "torus", "major": round(R * 0.83, 5), "minor": 0.0012, "segments": 48, "sides": 6,
                                   "rings": 0}, (0, h, 0), 1)
        b.part("tab", "identity", _box([0.018, 0.0012, 0.026]), (0, h + 0.0006, R * 0.25), 2)
        b.part("label", "artwork", {"type": "plane", "size": [round(R * 1.45, 5), round(h * 0.62, 5)]},
               (0, h * 0.47, R + 0.0006), 1, certainty=b.art_certainty("label"), artwork=b.slot("label"),
               look=None if b.doc.get("artwork", {}).get("label") else {"line": "none", "fill": "none"})
    else:
        style = p.get("glass_style", "pint")
        base = R * (0.7 if style == "pint" else 0.55 if style == "tulip" else 0.92)
        if style == "pint":
            prof = [(base, 0), (base, h * 0.05), (R * 0.9, h * 0.75), (R * 0.97, h * 0.88), (R, h)]
        elif style == "tulip":
            prof = [(base * 1.3, 0), (base * 0.4, h * 0.05), (base * 0.35, h * 0.3), (R * 0.85, h * 0.42), (R, h * 0.7),
                    (R * 0.82, h * 0.92), (R * 0.88, h)]
        else:
            prof = [(base, 0), (base, h * 0.03), (R, h)]
        b.part("glass", "mass", {"type": "lathe", "profile": [[round(r, 5), round(y, 5)] for r, y in prof],
                                 "segments": 40, "meridians": 6}, (0, 0, 0), 0, basis=["height", "diameter"])
        fill = p["fill"]
        y0 = h * (0.05 if style != "tulip" else 0.32)
        top = y0 + (h - y0) * fill * 0.93
        inner = [(r * 0.93, y) for r, y in prof if y0 < y < top]
        inner = [(_radius_at(prof, y0) * 0.93, y0)] + inner + [(_radius_at(prof, top) * 0.93, top)]
        b.part("beer", "data", {"type": "lathe", "profile": [[round(r, 5), round(y, 5)] for r, y in inner],
                                    "segments": 36, "meridians": 8}, (0, 0, 0), 1, look={"fill": "glass", "glow": 0.9})
        foam = min(0.025, h - top)
        if foam > 0.004:
            b.part("foam", "identity", {"type": "cylinder", "radius": round(_radius_at(prof, top) * 0.92, 5),
                                        "height": round(foam, 5), "segments": 36, "ribs": 8, "rings": 3},
                   (0, top, 0), 2, certainty="inferred", look={"tone": "bright", "alpha": 0.8})
        b.part("bubbles", "ornament", {"type": "points", "count": 60, "region": {"box": [round(R * 0.9, 4), round((top - y0) * 0.9, 4),
                                                                                       round(R * 0.9, 4)]},
                                       "sprite": "soft", "size_px": 3}, (0, (y0 + top) / 2, 0), 3, certainty="decorative")
    if var in ("bottle", "can") and not b.doc.get("artwork", {}).get("label"):
        b.label("label-title", "label", "title", "title", region=[0.05, 0.12, 0.95, 0.45])
        b.label("label-creator", "label", who, "creator", region=[0.1, 0.5, 0.9, 0.68])
        b.label("label-style", "label", "style", "meta", region=[0.1, 0.72, 0.9, 0.86])
    b.anchors = {"front": {"part": "label", "face": "front"}} if var in ("bottle", "can") else {}


# ---------------------------------------------------------------------------- vehicle

# Shapes as fractions, from the back (t 0) to the nose (t 1): the lower body's sections
# (t, half-width / width, bottom / height, top / height) give its plan and side profile together;
# the glasshouse's (t, bottom half-width / width, top half-width / width, base / height, roof / height)
# sit on it, narrower at the top; `axle` is where the middle of the wheelbase falls.
CARS = {
    "wedge": {"axle": 0.47,
              "body": [(0.0, 0.40, 0.25, 0.58), (0.03, 0.47, 0.17, 0.62), (0.10, 0.50, 0.13, 0.64), (0.40, 0.50, 0.12, 0.62),
                       (0.60, 0.49, 0.12, 0.53), (0.75, 0.47, 0.12, 0.45), (0.86, 0.43, 0.13, 0.38), (0.94, 0.37, 0.14, 0.32),
                       (0.985, 0.30, 0.16, 0.28), (1.0, 0.24, 0.19, 0.25)],
              "glass": [(0.25, 0.42, 0.28, 0.58, 0.64), (0.32, 0.44, 0.32, 0.58, 0.96), (0.46, 0.45, 0.34, 0.57, 1.0),
                        (0.57, 0.46, 0.38, 0.53, 0.79), (0.65, 0.47, 0.44, 0.49, 0.52)]},
    "coupe": {"axle": 0.45,
              "body": [(0.0, 0.38, 0.22, 0.48), (0.02, 0.45, 0.16, 0.53), (0.08, 0.48, 0.14, 0.55), (0.30, 0.50, 0.13, 0.56),
                       (0.55, 0.50, 0.13, 0.55), (0.78, 0.48, 0.13, 0.53), (0.90, 0.45, 0.14, 0.51), (0.97, 0.39, 0.17, 0.47),
                       (1.0, 0.32, 0.22, 0.42)],
              "glass": [(0.08, 0.44, 0.28, 0.53, 0.56), (0.18, 0.45, 0.33, 0.54, 0.80), (0.30, 0.45, 0.36, 0.55, 0.96),
                        (0.42, 0.45, 0.37, 0.55, 1.0), (0.52, 0.46, 0.40, 0.55, 0.96), (0.60, 0.47, 0.45, 0.54, 0.58)]},
    "sedan": {"axle": 0.48,
              "body": [(0.0, 0.42, 0.21, 0.54), (0.02, 0.47, 0.17, 0.57), (0.08, 0.49, 0.15, 0.58), (0.30, 0.50, 0.14, 0.58),
                       (0.75, 0.50, 0.14, 0.55), (0.92, 0.47, 0.15, 0.52), (0.98, 0.42, 0.18, 0.48), (1.0, 0.36, 0.22, 0.45)],
              "glass": [(0.14, 0.46, 0.33, 0.57, 0.61), (0.24, 0.46, 0.38, 0.58, 0.97), (0.55, 0.46, 0.39, 0.57, 1.0),
                        (0.67, 0.47, 0.44, 0.56, 0.59)]},
}


def build_vehicle(b, var, p):
    car = CARS[var]
    L, W, H, wb, wd = p["length"], p["width"], p["height"], p["wheelbase"], p["wheel_diameter"]
    for k in ("length", "width", "height", "wheelbase", "wheel_diameter"):
        b.dim(k, p[k])
    b.framing = {"yaw": 38, "pitch": 9, "fit": 1.0}
    b.atmosphere = {"haze": 0.6, "grid": True, "projector": False, "motes": 0.2}

    def z(t):
        return -L / 2 + t * L
    # the sides lean in towards the shoulder (tumblehome)
    body = [[round(z(t), 4), round(hw * W, 4), round(y0 * H, 4), round(y1 * H, 4), round(hw * W * 0.9, 4)]
            for t, hw, y0, y1 in car["body"]]
    b.part("body", "mass", {"type": "loft", "sections": body, "round": 0.7}, (0, 0, 0), 1,
           basis=["length", "width", "height"], note="plan and side profile of %s, as fractions of its size" % b.note)
    glass = [[round(z(t), 4), round(hb * W, 4), round(y0 * H, 4), round(y1 * H, 4), round(ht * W, 4)]
             for t, hb, ht, y0, y1 in car["glass"]]
    b.part("glasshouse", "identity", {"type": "loft", "sections": glass, "round": 0.3}, (0, 0, 0), 2,
           basis=["height"], look={"fill": "glass"})
    # wheels on the ground, in arches cut into the body's sides
    R, tw = wd / 2, min(0.32, 0.13 * W)
    zc = z(car["axle"])
    zr, zf = zc - wb / 2, zc + wb / 2

    def half_width(zz):
        prof = [(sec[0], sec[1]) for sec in body]
        for (z0, w0), (z1, w1) in zip(prof, prof[1:]):
            if z0 <= zz <= z1:
                return w0 + (w1 - w0) * (zz - z0) / (z1 - z0)
        return prof[-1][1]
    for name, zz in (("rear", zr), ("front", zf)):
        x = half_width(zz) - tw / 2 - 0.01
        b.part("tyre-" + name, "structure", {"type": "torus", "major": round(R - tw / 2, 4), "minor": round(tw / 2, 4),
                                             "segments": 32, "sides": 8, "rings": 4},
               (round(x, 4), round(R, 4), round(zz, 4)), 0, rotate=[0, 0, 90], mirror="x", basis=["wheel_diameter", "wheelbase"])
        b.part("rim-" + name, "detail", {"type": "cylinder", "radius": round(R * 0.6, 4), "height": round(tw * 0.5, 4),
                                         "segments": 16, "ribs": 5},
               (round(x + tw * 0.25, 4), round(R, 4), round(zz, 4)), 1, rotate=[0, 0, 90], mirror="x")
        # the arch lies on the body's side at axle height (the side leans in above the sill)
        sec = min(body, key=lambda q: abs(q[0] - zz))
        ar = R * 1.12
        xs = half_width(zz) * (1 - 0.1 * min(1.0, max(0.0, (R - sec[2]) / (sec[3] - sec[2])))) - 0.002
        b.part("arch-" + name, "identity", {"type": "curve", "points": [
            [round(xs, 4), round(R + ar * math.sin(math.pi * k / 12), 4), round(zz + ar * math.cos(math.pi * k / 12), 4)]
            for k in range(13)]}, (0, 0, 0), 2, mirror="x", basis=["wheel_diameter"])
    # lights at the nose and the tail
    nose, tail = body[-1], body[0]
    b.part("headlights", "detail", _box([round(W * 0.16, 4), round(H * 0.05, 4), 0.03]),
           (round(nose[1] * 0.6, 4), round((nose[2] + nose[3]) / 2, 4), round(nose[0] - 0.02, 4)), 3, mirror="x")
    b.part("taillights", "detail", _box([round(W * 0.2, 4), round(H * 0.05, 4), 0.03]),
           (round(tail[1] * 0.6, 4), round(tail[3] - H * 0.08, 4), round(tail[0] + 0.02, 4)), 3, mirror="x")
    b.views = [{"id": "side", "label": "Side profile", "yaw": 90, "pitch": 2, "distance": 1.0},
               {"id": "plan", "label": "Plan", "yaw": 0, "pitch": 89, "distance": 1.0},
               {"id": "front", "label": "Nose", "yaw": 20, "pitch": 6, "distance": 1.0}]


BUILDERS = {"case": build_case, "book": build_book, "object": build_object, "vessel": build_vessel,
            "vehicle": build_vehicle}


def _radius_at(prof, y):
    for (r0, y0), (r1, y1) in zip(prof, prof[1:]):
        if y0 <= y <= y1 and y1 > y0:
            return r0 + (r1 - r0) * (y - y0) / (y1 - y0)
    return prof[-1][0]
