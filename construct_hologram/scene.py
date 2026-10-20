"""Construct scenes (format construct-scene, version 2): validation and deterministic compilation.

A scene is declarative data an agent (or a person) authors: facts with sources and
certainty, semantic parts built from a closed vocabulary of shapes, and presentation
and animation choices from closed sets. The compiler turns it into packed, styled,
phase-annotated geometry for a renderer. No code, shaders, URLs or file reads: the
only file access in this package is reading a scene and (explicitly) hashing assets.

Certainty is the material (the method this toolkit generalises): what is verified is
drawn as crisp light, what is inferred steps back, what is decorative is loose and
faint. Role decides hierarchy: the mass and the identity features carry the object;
structure and detail support them.
"""

import hashlib
import json
import math

from . import product, shapes

FORMAT = product.SCENE_FORMAT
FORMATS = (FORMAT, product.LEGACY_SCENE_FORMAT)  # the legacy id is read for one release
VERSION = 2
GEOMETRY_FORMAT = product.GEOMETRY_FORMAT
GEOMETRY_VERSION = 2
GENERATOR = "%s %s" % (product.NAME, product.VERSION)

# ---------------------------------------------------------------------------- budgets
MAX_PARTS = 256
MAX_INSTANCES = 1024
MAX_REPEAT = 64
MAX_LINES = 24000
MAX_TRIS = 24000
MAX_POINTS = 6000
MAX_MOTIONS = 32
MAX_FACTS = 160
MAX_SOURCES = 64
MAX_ASSETS = 32
MAX_ANNOTATIONS = 32
MAX_VIEWS = 12
MAX_TOUR = 12
MAX_PROFILE = 128
MAX_PATH = 64
MAX_CURVE = 256
MAX_EXTENT = 500.0          # metres from the origin: from a ring to a cathedral
MIN_SIZE = 1e-4             # 0.1 mm

# ---------------------------------------------------------------------------- vocabularies
CATEGORIES = ("architecture", "object", "machine", "vehicle", "organism", "fictional",
              "cd", "book", "artwork-carrier", "other")
ACCURACY = ("generic", "approximate", "documented")
CERTAINTIES = ("verified", "user_supplied", "inferred", "decorative")
SOURCE_KINDS = ("user_request", "user_supplied", "document", "measurement", "observation",
                "dataset", "generated", "drawing", "reference_image")
# sources that can verify a shape itself (coordinates, a measured outline, elevation data), not just its dimensions
SHAPE_EVIDENCE = ("drawing", "measurement", "dataset")
SOURCE_RIGHTS = ("synthetic", "user_private", "permitted", "public_domain", "reference_only")
ASSET_PROVENANCE = ("authentic", "synthetic", "generated-decorative", "user_photo")
ASSET_RIGHTS = ("synthetic", "user_private", "permitted")
MEDIA_TYPES = ("image/png", "image/jpeg", "image/webp")
ROLES = ("mass", "structure", "detail", "identity", "data", "ornament", "ground", "artwork")
TONES = ("accent", "bright", "hairline", "structure", "dust", "identity", "data", "faint")
LINES = ("auto", "solid", "dashed", "dotted", "none")
FILLS = ("auto", "none", "glass", "dark")
SPRITES = ("disc", "ring", "square", "soft")
HOUSE_STYLE = {"palette": "violet", "identity": "none",
               "note": "the house palette; only a host option chosen by a person changes it"}
PALETTES = ("violet", "cyan", "amber", "green", "ice", "rose")
IDENTITIES = ("none", "warm-wood", "stone", "steel", "brass", "bio", "ember", "ice", "paper")
MOTIONS = ("spin", "swing", "bob", "pulse")
EVENTS = ("scan", "sweep", "wave", "shimmer", "glitch", "brownout", "propagate", "tear", "burst")
ASSEMBLY = ("ceremony", "build", "cut")
LIFE = ("off", "calm", "alive")
SHAPE_TYPES = ("box", "cylinder", "cone", "sphere", "torus", "lathe", "extrude", "tube",
               "curve", "plane", "grid", "points", "marker", "terrain", "globe")
MAX_TERRAIN = 128
MAX_GLOBE_POINTS = 20000
ARTICULATIONS = ("hinge", "slide", "lift", "turn")
MAX_ARTICULATIONS = 16
MAX_JOINTS = 16
MAX_LABELS = 48
# the faces a label, an artwork or an anchor can sit on, by shape
FACES = {"box": ("front", "back", "left", "right", "top", "bottom"), "plane": ("front", "back"),
         "cylinder": ("top", "bottom"), "lathe": ("top", "bottom")}
DEFAULT_FACE = {"box": "front", "plane": "front", "cylinder": "top", "lathe": "top"}
LABEL_ROLES = ("title", "creator", "meta", "catalog", "body", "decorative")
ALIGNS = ("left", "center", "right")
ORIENTATIONS = ("horizontal", "vertical-down", "vertical-up")
ARTWORK_SLOTS = ("cover-front", "cover-back", "inlay", "disc", "label", "booklet-page-N")
MASKS = ("rect", "circle")
STILL_POSES = ("open", "closed")

# Role defaults: tone, alpha, width (logical px), glow (px), fill, depth fade (0 none … 2 strong)
ROLE_STYLE = {
    "mass":      ("hairline", 0.92, 1.35, 1.2, "glass", 0),
    "structure": ("structure", 0.78, 1.0, 0.0, "none", 1),
    "detail":    ("structure", 0.6, 0.8, 0.0, "none", 2),
    "identity":  ("identity", 0.95, 1.25, 2.2, "glass", 0),
    "data":      ("accent", 1.0, 1.6, 3.0, "none", 0),
    "ornament":  ("dust", 0.55, 0.8, 0.8, "none", 2),
    "ground":    ("faint", 0.4, 0.8, 0.0, "none", 2),
    "artwork":   ("hairline", 0.9, 1.0, 0.0, "dark", 0),
}
# Certainty: alpha factor and the line it implies (subtle style); explicit style dashes inferred
CERTAINTY_STYLE = {"verified": (1.0, "solid"), "user_supplied": (0.95, "solid"),
                   "inferred": (0.82, "solid"), "decorative": (0.6, "dotted")}
# Edge class: width and alpha factors
CLASS_STYLE = {shapes.OUTLINE: (1.0, 1.0), shapes.CONTOUR: (0.72, 0.62), shapes.DETAIL: (0.6, 0.46)}
DASH_CODE = {"solid": 0, "dashed": 1, "dotted": 2}
SPRITE_CODE = {"disc": 0, "ring": 1, "square": 2, "soft": 3}

SCENE_KEYS = {"format", "version", "id", "title", "subject", "units", "seed", "sources", "facts",
              "parts", "assets", "annotations", "articulations", "labels", "anchors", "presentation",
              "animation", "authoring"}
SCENE_REQUIRED = {"format", "version", "id", "title", "subject", "units", "seed", "sources", "facts", "parts"}


class SceneError(Exception):
    """A scene that cannot be compiled; the message lists every problem found."""


# ---------------------------------------------------------------------------- checks

def _closest(word, options):
    import difflib
    word = str(word)
    m = difflib.get_close_matches(word, [str(o) for o in options], n=1, cutoff=0.5)
    return m[0] if m else None


def _slug(v):
    out = "".join(ch if ch.isalnum() else "-" for ch in str(v).lower()).strip("-")
    while "--" in out:
        out = out.replace("--", "-")
    return (out or "part")[:64]


# what to write for a missing key, so a model can repair its draft without reading the docs
KEY_HELP = {
    "certainty": 'one of "verified" (cite a source), "user_supplied", "inferred", "decorative"',
    "stage": "an integer 0..7, foundation first",
    "role": "one of " + ", ".join(ROLES),
    "shape": '{"type": "box", "size": [w, h, d]} or another shape (see vocabulary)',
    "id": "a lowercase id such as \"lid\"",
    "value": "the known value; delete the whole fact if it is unknown",
    "units": '"m"', "seed": "an integer, e.g. 7", "format": '"construct-scene"', "version": "2",
    "subject": '{"category": "object", "accuracy": "generic", "synthetic": false}',
    "sources": '[{"id": "request", "kind": "user_request", "title": "The request", "rights": "user_private"}]',
    "facts": "[] or facts with key, value and certainty", "parts": "at least one part",
    "slot": "cover-front, cover-back, inlay, disc, label or booklet-page-N",
    "pivot": "a world point [x, y, z] on the hinge or turning axis",
    "axis": "a direction [x, y, z], e.g. [0, 1, 0]",
}
# values that stand for "not known"; such a fact is left out instead ("none" is not here: it is
# a real catalogue number in Discogs exports)
PLACEHOLDERS = {"", "unknown", "n/a", "na", "n.a.", "?", "??", "???", "tbd", "tba", "-", "--", "—", "not known",
                "unspecified", "unknown year", "unknown author", "unknown artist"}


def is_placeholder(v):
    return isinstance(v, str) and v.strip().lower() in PLACEHOLDERS


# words models reach for, and the option they mean
SYNONYMS = {"creature": ("organism", "fictional"), "animal": ("organism",), "monster": ("fictional",),
            "plant": ("organism",), "building": ("architecture",), "house": ("architecture",),
            "device": ("machine", "object"), "instrument": ("object",), "album": ("cd",), "disc": ("cd",),
            "car": ("vehicle",), "body": ("mass",), "main": ("mass",), "feature": ("identity",),
            "decoration": ("ornament",), "estimated": ("inferred",), "guess": ("inferred",), "user": ("user_supplied",),
            "given": ("user_supplied",), "exact": ("documented",), "typical": ("generic",)}
SIZE_KEYS = ("size", "radius", "height", "radii", "major", "minor", "radius_top", "radius_bottom", "at", "distance",
             "width", "depth", "thickness", "diameter", "scale_length", "inner_radius", "amount")


class _Check:
    """Collects problems as {where, message, code, hint}; `errors` gives the classic strings."""

    def __init__(self):
        self.items = []
        self.known = {}       # kind -> ids defined so far (part, fact, asset, source, view)
        self.part_names = {}  # parts index -> id, for readable messages

    def err(self, where, message, code="rule", hint=None):
        if hint is None and code == "rule":
            import re
            m = re.match(r"unknown (part|fact|asset|source|view) '(.*?)'", message)
            if m:
                code = "reference"
                known = sorted(self.known.get(m.group(1), ()))
                near = _closest(m.group(2), known)
                hint = ("Use one of the scene's %s ids: %s." % (m.group(1), ", ".join(known[:24]) or "(none yet)")
                        + (" Did you mean %r?" % near if near else ""))
        self.items.append({"where": where, "message": message, "code": code, "hint": hint})

    @property
    def errors(self):
        out = []
        for e in self.items:
            where = e["where"]
            for i, pid in self.part_names.items():
                pre = "scene.parts[%d]" % i
                if where == pre or where.startswith(pre + ".") or where.startswith(pre + "["):
                    where = "part %r" % pid + where[len(pre):]
                    break
            out.append("%s: %s" % (where, e["message"]))
        return out

    def keys(self, obj, allowed, required, where):
        if not isinstance(obj, dict):
            self.err(where, "expected an object", "type", "Write a JSON object {...} here.")
            return False
        for k in sorted(set(obj) - set(allowed)):
            if any(w in k.lower() for w in ("colo", "palette", "hue", "rgb", "shader", "material")):
                self.err(where, "unknown key %r" % k, "style",
                         "Remove %r: the renderer owns colour and material; describe the part's role "
                         "(mass, identity, detail...) instead." % k)
                continue
            near = _closest(k, allowed)
            self.err(where, "unknown key %r" % k, "unknown-key",
                     "Remove %r%s. Allowed here: %s." % (k, " (did you mean %r?)" % near if near else "",
                                                       ", ".join(sorted(allowed))))
        for k in sorted(set(required) - set(obj)):
            self.err(where, "missing key %r" % k, "missing-key",
                     "Add %r%s." % (k, ": " + KEY_HELP[k] if k in KEY_HELP else ""))
        return True

    def num(self, v, where, lo=None, hi=None, integer=False):
        ok = isinstance(v, int if integer else (int, float)) and not isinstance(v, bool)
        if ok and isinstance(v, float) and not math.isfinite(v):
            ok = False
        if not ok:
            hint = "Write a plain JSON %s (no quotes, no units)." % ("integer" if integer else "number")
            if isinstance(v, str):
                try:
                    hint += " Here: %s." % json.dumps(int(v) if integer else float(v.strip().rstrip("m ")))
                except ValueError:
                    pass
            self.err(where, "expected %s" % ("an integer" if integer else "a finite number"), "type", hint)
            return False
        if lo is not None and v < lo or hi is not None and v > hi:
            hint = "Use a value between %s and %s." % (lo, hi)
            key = where.rsplit(".", 1)[-1].split("[")[0]
            if key in SIZE_KEYS and hi is not None and v > hi and lo is not None and lo <= v / 1000.0 <= hi:
                hint += " Sizes are metres: %s mm is %g." % (v, v / 1000.0)
            self.err(where, "must be within %s..%s" % (lo, hi), "range", hint)
            return False
        return True

    def vec(self, v, where, n=3, lo=-MAX_EXTENT, hi=MAX_EXTENT):
        if not isinstance(v, list) or len(v) != n:
            self.err(where, "expected an array of %d numbers" % n, "type",
                     "Write [x, y, z] in metres." if n == 3 else "Write an array of %d numbers." % n)
            return False
        return all([self.num(x, "%s[%d]" % (where, i), lo, hi) for i, x in enumerate(v)])

    def text(self, v, where, maxlen, required=True):
        if v is None and not required:
            return True
        if not isinstance(v, str) or (required and not v.strip()) or len(v) > maxlen:
            self.err(where, "expected a non-blank string of at most %d characters" % maxlen, "type",
                     "Write a short text in double quotes (at most %d characters)." % maxlen)
            return False
        return True

    def choice(self, v, options, where):
        if v not in options:
            near = _closest(v, options) if isinstance(v, str) else None
            syn = SYNONYMS.get(str(v).lower())
            if syn and all(x in options for x in syn):
                near = " or ".join(syn)
            self.err(where, "must be one of %s" % ", ".join(options), "choice",
                     "Use one of: %s.%s" % (", ".join(options), " Did you mean %r?" % near if near else ""))
            return False
        return True

    def ident(self, v, where):
        ok = (isinstance(v, str) and 0 < len(v) <= 64 and v[0].isalnum()
              and all(c.isalnum() or c in "-_." for c in v) and v == v.lower())
        if not ok:
            self.err(where, "expected a lowercase id (letters, digits, - _ .; at most 64)", "id",
                     "Use something like %r." % _slug(v))
        return ok


def _shape_check(c, shape, where):
    if not c.keys(shape, _SHAPE_KEYS.get(shape.get("type") if isinstance(shape, dict) else None, {"type"}) ,
                  {"type"}, where):
        return
    t = shape.get("type")
    if not c.choice(t, SHAPE_TYPES, where + ".type"):
        return
    pos = dict(lo=MIN_SIZE, hi=MAX_EXTENT)
    if t == "box":
        c.vec(shape.get("size"), where + ".size", 3, **pos)
        if "ribs" in shape:
            c.num(shape["ribs"], where + ".ribs", 0, 32, True)
        if "anchor" in shape:
            c.choice(shape["anchor"], ("center", "base"), where + ".anchor")
    elif t in ("cylinder", "cone"):
        if t == "cylinder":
            c.num(shape.get("radius"), where + ".radius", **pos)
        else:
            ok = c.num(shape.get("radius_bottom"), where + ".radius_bottom", 0, MAX_EXTENT)
            ok = c.num(shape.get("radius_top"), where + ".radius_top", 0, MAX_EXTENT) and ok
            if ok and shape["radius_bottom"] <= 0 and shape["radius_top"] <= 0:
                c.err(where, "a cone needs a non-zero radius at one end")
        c.num(shape.get("height"), where + ".height", **pos)
        for k, lo, hi in (("segments", 6, 96), ("ribs", 0, 48), ("rings", 0, 32)):
            if k in shape:
                c.num(shape[k], "%s.%s" % (where, k), lo, hi, True)
        if "caps" in shape and not isinstance(shape["caps"], bool):
            c.err(where + ".caps", "expected true or false")
    elif t == "sphere":
        if ("radius" in shape) == ("radii" in shape):
            c.err(where, "give exactly one of radius or radii")
        elif "radius" in shape:
            c.num(shape["radius"], where + ".radius", **pos)
        else:
            c.vec(shape["radii"], where + ".radii", 3, **pos)
        for k, lo, hi in (("lat", 2, 24), ("lon", 3, 48), ("segments", 8, 96)):
            if k in shape:
                c.num(shape[k], "%s.%s" % (where, k), lo, hi, True)
        if "anchor" in shape:
            c.choice(shape["anchor"], ("center", "base"), where + ".anchor")
    elif t == "torus":
        ok = c.num(shape.get("major"), where + ".major", **pos)
        ok = c.num(shape.get("minor"), where + ".minor", **pos) and ok
        if ok and shape["minor"] >= shape["major"]:
            c.err(where, "minor radius must be smaller than major radius")
        for k, lo, hi in (("segments", 8, 96), ("sides", 3, 32), ("rings", 0, 48)):
            if k in shape:
                c.num(shape[k], "%s.%s" % (where, k), lo, hi, True)
    elif t == "lathe":
        prof = shape.get("profile")
        if not isinstance(prof, list) or not 2 <= len(prof) <= MAX_PROFILE:
            c.err(where + ".profile", "expected 2..%d [radius, y] points" % MAX_PROFILE)
        else:
            for i, p in enumerate(prof):
                if c.vec(p, "%s.profile[%d]" % (where, i), 2) and p[0] < 0:
                    c.err("%s.profile[%d]" % (where, i), "radius must not be negative")
        for k, lo, hi in (("segments", 6, 96), ("meridians", 0, 48)):
            if k in shape:
                c.num(shape[k], "%s.%s" % (where, k), lo, hi, True)
    elif t == "extrude":
        prof = shape.get("profile")
        if not isinstance(prof, list) or not 3 <= len(prof) <= MAX_PROFILE:
            c.err(where + ".profile", "expected 3..%d [u, v] points of a simple polygon" % MAX_PROFILE)
        else:
            ok = all([c.vec(p, "%s.profile[%d]" % (where, i), 2) for i, p in enumerate(prof)])
            if ok and abs(shapes._polygon_area2(prof)) < 1e-9:
                c.err(where + ".profile", "polygon has no area")
        c.num(shape.get("height"), where + ".height", **pos)
        if "axis" in shape:
            c.choice(shape["axis"], ("y", "z", "x"), where + ".axis")
        if "ribs" in shape:
            c.num(shape["ribs"], where + ".ribs", 0, 16, True)
    elif t == "tube":
        path = shape.get("path")
        if not isinstance(path, list) or not 2 <= len(path) <= MAX_PATH:
            c.err(where + ".path", "expected 2..%d points" % MAX_PATH)
            path = None
        else:
            for i, p in enumerate(path):
                c.vec(p, "%s.path[%d]" % (where, i))
        r = shape.get("radius")
        if isinstance(r, list):
            if path is not None and len(r) != len(path):
                c.err(where + ".radius", "a radius list needs one radius per path point")
            for i, x in enumerate(r):
                c.num(x, "%s.radius[%d]" % (where, i), MIN_SIZE, MAX_EXTENT)
        else:
            c.num(r, where + ".radius", **pos)
        for k, lo, hi in (("sides", 3, 24), ("samples", 1, 16), ("longitudinal", 0, 12), ("ring_every", 0, 16)):
            if k in shape:
                c.num(shape[k], "%s.%s" % (where, k), lo, hi, True)
        for k in ("smooth", "caps"):
            if k in shape and not isinstance(shape[k], bool):
                c.err("%s.%s" % (where, k), "expected true or false")
    elif t == "curve":
        pts = shape.get("points")
        if not isinstance(pts, list) or not 2 <= len(pts) <= MAX_CURVE:
            c.err(where + ".points", "expected 2..%d points" % MAX_CURVE)
        else:
            for i, p in enumerate(pts):
                c.vec(p, "%s.points[%d]" % (where, i))
        for k in ("smooth", "closed"):
            if k in shape and not isinstance(shape[k], bool):
                c.err("%s.%s" % (where, k), "expected true or false")
    elif t == "plane":
        c.vec(shape.get("size"), where + ".size", 2, **pos)
        if "divisions" in shape:
            c.num(shape["divisions"], where + ".divisions", 0, 16, True)
    elif t == "grid":
        c.vec(shape.get("size"), where + ".size", 2, **pos)
        c.num(shape.get("divisions"), where + ".divisions", 1, 64, True)
    elif t == "globe":
        c.num(shape.get("radius"), where + ".radius", **pos)
        ps = shape.get("paths")
        ok = isinstance(ps, list) and all(isinstance(q, list) and len(q) >= 2 for q in ps)
        if not ok or sum(len(q) for q in ps) > MAX_GLOBE_POINTS:
            c.err(where + ".paths", "expected lines of 2 or more [longitude, latitude] points (degrees), at most %d "
                  "points in all" % MAX_GLOBE_POINTS, "type", "construct globe reads them from a GeoJSON file.")
        else:
            bad = next(((i, j) for i, q in enumerate(ps) for j, pt in enumerate(q)
                        if not (isinstance(pt, list) and len(pt) == 2
                                and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in pt)
                                and -180 <= pt[0] <= 180 and -90 <= pt[1] <= 90)), None)
            if bad:
                c.err("%s.paths[%d][%d]" % (where, bad[0], bad[1]), "expected [longitude -180..180, latitude -90..90]",
                      "range")
        if "graticule" in shape:
            c.choice(shape["graticule"], (0, 10, 15, 20, 30, 45), where + ".graticule")
        if "faces" in shape and not isinstance(shape["faces"], bool):
            c.err(where + ".faces", "expected true or false")
    elif t == "terrain":
        c.vec(shape.get("size"), where + ".size", 2, **pos)
        hs = shape.get("heights")
        if not isinstance(hs, list) or not 2 <= len(hs) <= MAX_TERRAIN or not all(
                isinstance(r, list) and len(r) == len(hs[0]) for r in hs) or not 2 <= len(hs[0]) <= MAX_TERRAIN:
            c.err(where + ".heights", "expected 2..%d rows of 2..%d heights, all rows the same length" % (MAX_TERRAIN, MAX_TERRAIN),
                  "type", "Sample the elevation onto a regular grid (construct terrain does it from a DEM).")
        else:
            bad = next(((i, j) for i, r in enumerate(hs) for j, v in enumerate(r)
                        if not (isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                                and 0 <= v <= MAX_EXTENT)), None)
            if bad:
                c.err("%s.heights[%d][%d]" % (where, bad[0], bad[1]), "expected a height in metres, 0..%g" % MAX_EXTENT, "range",
                      "Heights are stage metres above the base: subtract the lowest point and scale.")
        if "contour" in shape:
            c.num(shape["contour"], where + ".contour", 0, MAX_EXTENT)
        if "grid_every" in shape:
            c.num(shape["grid_every"], where + ".grid_every", 0, 32, True)
        if "index" in shape:
            c.num(shape["index"], where + ".index", 1, 20, True)
        if "skirt" in shape and not isinstance(shape["skirt"], bool):
            c.err(where + ".skirt", "expected true or false")
    elif t == "points":
        c.num(shape.get("count"), where + ".count", 1, 2000, True)
        region = shape.get("region")
        if not isinstance(region, dict) or len(region) != 1 or not set(region) <= {"box", "sphere", "shell"}:
            c.err(where + ".region", 'expected {"box": [w, h, d]}, {"sphere": r} or {"shell": r}')
        elif "box" in region:
            c.vec(region["box"], where + ".region.box", 3, **pos)
        else:
            c.num(next(iter(region.values())), where + ".region", **pos)
        if "sprite" in shape:
            c.choice(shape["sprite"], SPRITES, where + ".sprite")
        if "size_px" in shape:
            c.num(shape["size_px"], where + ".size_px", 1, 24)
    elif t == "marker":
        if "sprite" in shape:
            c.choice(shape["sprite"], SPRITES, where + ".sprite")
        if "size_px" in shape:
            c.num(shape["size_px"], where + ".size_px", 2, 48)


_SHAPE_KEYS = {
    "box": {"type", "size", "ribs", "anchor"},
    "cylinder": {"type", "radius", "height", "segments", "ribs", "rings", "caps"},
    "cone": {"type", "radius_bottom", "radius_top", "height", "segments", "ribs", "rings", "caps"},
    "sphere": {"type", "radius", "radii", "lat", "lon", "segments", "anchor"},
    "torus": {"type", "major", "minor", "segments", "sides", "rings"},
    "lathe": {"type", "profile", "segments", "meridians"},
    "extrude": {"type", "profile", "height", "axis", "ribs"},
    "tube": {"type", "path", "radius", "sides", "smooth", "samples", "longitudinal", "ring_every", "caps"},
    "curve": {"type", "points", "smooth", "closed"},
    "plane": {"type", "size", "divisions"},
    "grid": {"type", "size", "divisions"},
    "terrain": {"type", "size", "heights", "contour", "index", "grid_every", "skirt"},
    "globe": {"type", "radius", "paths", "graticule", "faces"},
    "points": {"type", "count", "region", "sprite", "size_px"},
    "marker": {"type", "sprite", "size_px"},
}
PART_KEYS = {"id", "label", "role", "shape", "at", "rotate", "scale", "certainty", "basis", "source",
             "look", "stage", "repeat", "mirror", "motion", "floating", "artwork", "note"}
PART_REQUIRED = {"id", "role", "shape", "certainty", "stage"}


def validate(scene):
    """Every problem in a scene, as readable strings; empty when it compiles."""
    return _validate(scene).errors


def validate_items(scene):
    """Every problem as {where, message, code, hint}: `where` is a dotted path from `scene`."""
    return _validate(scene).items


def _validate(scene):
    c = _Check()
    if not c.keys(scene, SCENE_KEYS | {"style"}, SCENE_REQUIRED, "scene"):
        return c
    if scene.get("format") not in FORMATS:
        c.err("scene.format", "must be %r" % FORMAT)
    if scene.get("version") != VERSION or isinstance(scene.get("version"), bool):
        c.err("scene.version", "must be %d" % VERSION)
    c.ident(scene.get("id"), "scene.id")
    c.text(scene.get("title"), "scene.title", 200)
    if scene.get("units") != "m":
        c.err("scene.units", "must be 'm' (metres, Y up)")
    c.num(scene.get("seed"), "scene.seed", 0, 2 ** 31 - 1, True)

    subject = scene.get("subject")
    if c.keys(subject, {"category", "summary", "accuracy", "synthetic"}, {"category", "accuracy", "synthetic"}, "scene.subject"):
        c.choice(subject.get("category"), CATEGORIES, "scene.subject.category")
        c.choice(subject.get("accuracy"), ACCURACY, "scene.subject.accuracy")
        if not isinstance(subject.get("synthetic"), bool):
            c.err("scene.subject.synthetic", "expected true or false")
        if "summary" in subject:
            c.text(subject["summary"], "scene.subject.summary", 600)

    source_ids = set()
    c.known["source"] = source_ids
    sources = scene.get("sources")
    if not isinstance(sources, list) or len(sources) > MAX_SOURCES:
        c.err("scene.sources", "expected an array of at most %d sources" % MAX_SOURCES)
        sources = []
    for i, s in enumerate(sources):
        w = "scene.sources[%d]" % i
        if not c.keys(s, {"id", "kind", "title", "rights", "ref"}, {"id", "kind", "title", "rights"}, w):
            continue
        if c.ident(s.get("id"), w + ".id"):
            if s["id"] in source_ids:
                c.err(w + ".id", "duplicate %r" % s["id"])
            source_ids.add(s["id"])
        c.choice(s.get("kind"), SOURCE_KINDS, w + ".kind")
        c.text(s.get("title"), w + ".title", 300)
        c.choice(s.get("rights"), SOURCE_RIGHTS, w + ".rights")
        if "ref" in s:
            c.text(s["ref"], w + ".ref", 600)

    if "authoring" in scene:
        from . import tiers
        tiers.check(c, scene["authoring"], source_ids, sources)

    fact_cert = {}
    c.known["fact"] = fact_cert
    facts = scene.get("facts")
    if not isinstance(facts, list) or len(facts) > MAX_FACTS:
        c.err("scene.facts", "expected an array of at most %d facts" % MAX_FACTS)
        facts = []
    for i, f in enumerate(facts):
        w = "scene.facts[%d]" % i
        if not c.keys(f, {"key", "value", "unit", "certainty", "source", "note"}, {"key", "value", "certainty"}, w):
            continue
        key = f.get("key")
        if c.text(key, w + ".key", 120):
            if key in fact_cert:
                c.err(w + ".key", "duplicate %r" % key)
            fact_cert[key] = f.get("certainty")
        v = f.get("value")
        if v is None or is_placeholder(v):
            c.err(w + ".value", "an unknown fact is absent: delete this fact rather than writing %s or a guess"
                  % ("null" if v is None else json.dumps(v)),
                  "unknown-fact", "Delete this fact (and any label or basis that uses it). Never fill it with a guess.")
        elif isinstance(v, float) and not math.isfinite(v):
            c.err(w + ".value", "non-finite number")
        elif not (isinstance(v, (bool, int, float)) or (isinstance(v, str) and len(v) <= 2000)):
            c.err(w + ".value", "expected a scalar (string of at most 2000 characters, number or boolean)")
        if "unit" in f:
            c.text(f["unit"], w + ".unit", 24)
        if "note" in f:
            c.text(f["note"], w + ".note", 600)
        c.choice(f.get("certainty"), CERTAINTIES, w + ".certainty")
        src = f.get("source")
        if f.get("certainty") == "verified" and src not in source_ids:
            c.err(w + ".source", "a verified fact must cite one of the scene's sources by id", "certainty",
                  "Add \"source\": \"<source id>\" naming where it was checked, or lower certainty to "
                  "\"user_supplied\" (the user said it) or \"inferred\" (your estimate).")
        elif src is not None and src not in source_ids:
            c.err(w + ".source", "unknown source %r" % src)

    asset_ids = set()
    c.known["asset"] = asset_ids
    assets = scene.get("assets", [])
    if not isinstance(assets, list) or len(assets) > MAX_ASSETS:
        c.err("scene.assets", "expected an array of at most %d assets" % MAX_ASSETS)
        assets = []
    for i, a in enumerate(assets):
        w = "scene.assets[%d]" % i
        if not c.keys(a, {"id", "path", "sha256", "media_type", "rights", "provenance", "source"},
                      {"id", "path", "sha256", "media_type", "rights", "provenance"}, w):
            continue
        if c.ident(a.get("id"), w + ".id"):
            if a["id"] in asset_ids:
                c.err(w + ".id", "duplicate %r" % a["id"])
            asset_ids.add(a["id"])
        _asset_path(a.get("path"), w + ".path", c)
        sha = a.get("sha256")
        if not isinstance(sha, str) or len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
            c.err(w + ".sha256", "expected 64 lowercase hexadecimal characters")
        c.choice(a.get("media_type"), MEDIA_TYPES, w + ".media_type")
        c.choice(a.get("rights"), ASSET_RIGHTS, w + ".rights")
        c.choice(a.get("provenance"), ASSET_PROVENANCE, w + ".provenance")
        if a.get("provenance") == "authentic" and (a.get("rights") == "synthetic" or a.get("source") not in source_ids):
            c.err(w, "authentic artwork needs permitted or user-private rights and a cited source")
        if a.get("source") is not None and a.get("source") not in source_ids:
            c.err(w + ".source", "unknown source %r" % a.get("source"))

    if "style" in scene:
        c.err("scene.style", "colours belong to the renderer: move it to presentation.style_hint "
              "(a hint a host may ignore) or delete it", "style",
              "Delete \"style\". Describe roles and certainty; the renderer chooses colours.")

    part_ids, instances, motions, slots = set(), 0, 0, set()
    c.known["part"] = part_ids
    parts = scene.get("parts")
    if not isinstance(parts, list) or not 1 <= len(parts) <= MAX_PARTS:
        c.err("scene.parts", "expected 1..%d parts" % MAX_PARTS)
        parts = []
    for i, p in enumerate(parts):
        w = "scene.parts[%d]" % i
        if not c.keys(p, PART_KEYS, PART_REQUIRED, w):
            continue
        if c.ident(p.get("id"), w + ".id"):
            if p["id"] in part_ids:
                c.err(w + ".id", "duplicate %r" % p["id"])
            part_ids.add(p["id"])
            c.part_names[i] = p["id"]
        if "label" in p:
            c.text(p["label"], w + ".label", 80)
        if "note" in p:
            c.text(p["note"], w + ".note", 600)
        c.choice(p.get("role"), ROLES, w + ".role")
        _shape_check(c, p.get("shape"), w + ".shape")
        for k in ("at", "rotate"):
            if k in p:
                c.vec(p[k], "%s.%s" % (w, k), 3, -720 if k == "rotate" else -MAX_EXTENT, 720 if k == "rotate" else MAX_EXTENT)
        if "scale" in p:
            sc = p["scale"]
            if isinstance(sc, list):
                c.vec(sc, w + ".scale", 3, 0.001, 1000)
            else:
                c.num(sc, w + ".scale", 0.001, 1000)
        c.choice(p.get("certainty"), CERTAINTIES, w + ".certainty")
        c.num(p.get("stage"), w + ".stage", 0, 7, True)
        basis = p.get("basis", [])
        if not isinstance(basis, list) or len(basis) > 16:
            c.err(w + ".basis", "expected an array of at most 16 fact keys")
        else:
            for b in basis:
                if b not in fact_cert:
                    c.err(w + ".basis", "unknown fact %r" % b)
        if p.get("source") is not None and p.get("source") not in source_ids:
            c.err(w + ".source", "unknown source %r" % p.get("source"))
        if p.get("certainty") == "verified":
            backed = p.get("source") in source_ids or any(fact_cert.get(b) == "verified" for b in basis if isinstance(basis, list))
            if not backed:
                c.err(w, "a verified part needs a cited source or a verified basis fact", "certainty",
                      "Cite a source id in \"source\", list a verified fact in \"basis\", or use \"inferred\".")
        look = p.get("look", {})
        if c.keys(look, {"tone", "line", "fill", "glow", "weight", "alpha"}, set(), w + ".look"):
            if "tone" in look:
                c.choice(look["tone"], TONES, w + ".look.tone")
            if "line" in look:
                c.choice(look["line"], LINES, w + ".look.line")
            if "fill" in look:
                c.choice(look["fill"], FILLS, w + ".look.fill")
            if "glow" in look:
                c.num(look["glow"], w + ".look.glow", 0, 1)
            if "weight" in look:
                c.num(look["weight"], w + ".look.weight", 0.25, 3)
            if "alpha" in look:
                c.num(look["alpha"], w + ".look.alpha", 0.05, 1)
        count = 1
        rep = p.get("repeat")
        if rep is not None:
            if c.keys(rep, {"count", "step", "radial", "phase_step"}, {"count"}, w + ".repeat"):
                if c.num(rep.get("count"), w + ".repeat.count", 2, MAX_REPEAT, True):
                    count = rep["count"]
                if ("step" in rep) == ("radial" in rep):
                    c.err(w + ".repeat", "give exactly one of step or radial")
                elif "step" in rep:
                    st = rep["step"]
                    if c.keys(st, {"at", "rotate"}, set(), w + ".repeat.step"):
                        if "at" in st:
                            c.vec(st["at"], w + ".repeat.step.at")
                        if "rotate" in st:
                            c.vec(st["rotate"], w + ".repeat.step.rotate", 3, -360, 360)
                else:
                    ra = rep["radial"]
                    if c.keys(ra, {"axis", "center", "span"}, set(), w + ".repeat.radial"):
                        if "axis" in ra:
                            c.choice(ra["axis"], ("x", "y", "z"), w + ".repeat.radial.axis")
                        if "center" in ra:
                            c.vec(ra["center"], w + ".repeat.radial.center")
                        if "span" in ra:
                            c.num(ra["span"], w + ".repeat.radial.span", 1, 360)
                if "phase_step" in rep:
                    c.num(rep["phase_step"], w + ".repeat.phase_step", -1, 1)
        mirror = p.get("mirror")
        if mirror is not None:
            if c.choice(mirror, ("x", "y", "z"), w + ".mirror"):
                count *= 2
        instances += count
        mo = p.get("motion")
        if mo is not None:
            _motion_check(c, mo, w + ".motion")
            motions += count
        if "floating" in p and not isinstance(p["floating"], bool):
            c.err(w + ".floating", "expected true or false")
        if "artwork" in p:
            _artwork_check(c, p, asset_ids, slots, w + ".artwork")
    if instances > MAX_INSTANCES:
        c.err("scene.parts", "%d instances after repeats and mirrors exceed %d" % (instances, MAX_INSTANCES), "budget",
              "Lower repeat counts or drop mirrors on small parts.")
    if motions > MAX_MOTIONS:
        c.err("scene.parts", "%d moving instances exceed %d" % (motions, MAX_MOTIONS), "budget",
              "Animate fewer copies: move the motion to one part, or drop it from repeated parts.")

    anns = scene.get("annotations", [])
    if not isinstance(anns, list) or len(anns) > MAX_ANNOTATIONS:
        c.err("scene.annotations", "expected at most %d annotations" % MAX_ANNOTATIONS)
        anns = []
    for i, a in enumerate(anns):
        w = "scene.annotations[%d]" % i
        if c.keys(a, {"id", "text", "part", "offset", "certainty"}, {"id", "text", "part"}, w):
            c.ident(a.get("id"), w + ".id")
            c.text(a.get("text"), w + ".text", 80)
            if a.get("part") not in part_ids:
                c.err(w + ".part", "unknown part %r" % a.get("part"))
            if "offset" in a:
                c.vec(a["offset"], w + ".offset")
            if "certainty" in a:
                c.choice(a["certainty"], CERTAINTIES, w + ".certainty")

    shapes_by_part = {p["id"]: p.get("shape") for p in parts if isinstance(p, dict) and isinstance(p.get("id"), str)}
    _articulation_check(c, scene.get("articulations", []), shapes_by_part)
    _label_check(c, scene.get("labels", []), shapes_by_part, scene.get("facts") if isinstance(scene.get("facts"), list) else [])
    _anchor_check(c, scene.get("anchors", {}), shapes_by_part)
    _presentation_check(c, scene.get("presentation", {}), part_ids)
    c.known["view"] = {"hero", "front", "side", "back", "top", "three-quarter"} | {
        v.get("id") for v in (scene.get("presentation", {}) or {}).get("views", []) or [] if isinstance(v, dict)}
    _animation_check(c, scene.get("animation", {}), scene.get("presentation", {}))
    return c


def _motion_check(c, mo, w):
    if not c.keys(mo, {"type", "axis", "pivot", "rpm", "degrees", "distance", "period", "phase", "amount"}, {"type"}, w):
        return
    t = mo.get("type")
    if not c.choice(t, MOTIONS, w + ".type"):
        return
    if t in ("spin", "swing", "bob"):
        if c.vec(mo.get("axis"), w + ".axis", 3, -1, 1) and sum(x * x for x in mo["axis"]) < 1e-6:
            c.err(w + ".axis", "must not be zero")
    if "pivot" in mo:
        c.vec(mo["pivot"], w + ".pivot")
    if t == "spin":
        c.num(mo.get("rpm"), w + ".rpm", -120, 120)
    if t == "swing":
        c.num(mo.get("degrees"), w + ".degrees", 0, 90)
    if t == "bob":
        c.num(mo.get("distance"), w + ".distance", 0, 50)
    if t in ("swing", "bob", "pulse"):
        c.num(mo.get("period"), w + ".period", 0.2, 120)
    if t == "pulse":
        c.num(mo.get("amount"), w + ".amount", 0, 1)
    if "phase" in mo:
        c.num(mo["phase"], w + ".phase", 0, 1)


def _presentation_check(c, pr, part_ids):
    w = "scene.presentation"
    if not c.keys(pr, {"framing", "views", "atmosphere", "occlusion", "certainty_style", "background", "float",
                       "style_hint", "still_pose"}, set(), w):
        return
    hint = pr.get("style_hint", {})
    if c.keys(hint, {"palette", "identity"}, set(), w + ".style_hint"):
        if "palette" in hint:
            c.choice(hint["palette"], PALETTES, w + ".style_hint.palette")
        if "identity" in hint:
            c.choice(hint["identity"], IDENTITIES, w + ".style_hint.identity")
    if "still_pose" in pr:
        c.choice(pr["still_pose"], STILL_POSES, w + ".still_pose")
    if "float" in pr:
        c.num(pr["float"], w + ".float", 0, MAX_EXTENT)
    fr = pr.get("framing", {})
    if c.keys(fr, {"yaw", "pitch", "fit", "target"}, set(), w + ".framing"):
        if "yaw" in fr:
            c.num(fr["yaw"], w + ".framing.yaw", -360, 360)
        if "pitch" in fr:
            c.num(fr["pitch"], w + ".framing.pitch", -89, 89)
        if "fit" in fr:
            c.num(fr["fit"], w + ".framing.fit", 0.3, 3)
        if "target" in fr and fr["target"] not in part_ids:
            c.err(w + ".framing.target", "unknown part %r" % fr["target"])
    views = pr.get("views", [])
    seen = set()
    if not isinstance(views, list) or len(views) > MAX_VIEWS:
        c.err(w + ".views", "expected at most %d views" % MAX_VIEWS)
        views = []
    for i, v in enumerate(views):
        vw = "%s.views[%d]" % (w, i)
        if c.keys(v, {"id", "label", "yaw", "pitch", "distance", "target"}, {"id", "yaw", "pitch"}, vw):
            if c.ident(v.get("id"), vw + ".id"):
                if v["id"] in seen:
                    c.err(vw + ".id", "duplicate %r" % v["id"])
                seen.add(v["id"])
            if "label" in v:
                c.text(v["label"], vw + ".label", 40)
            c.num(v.get("yaw"), vw + ".yaw", -360, 360)
            c.num(v.get("pitch"), vw + ".pitch", -89, 89)
            if "distance" in v:
                c.num(v["distance"], vw + ".distance", 0.1, 5)
            if "target" in v and v["target"] not in part_ids:
                c.err(vw + ".target", "unknown part %r" % v["target"])
    at = pr.get("atmosphere", {})
    if c.keys(at, {"haze", "scanlines", "vignette", "grid", "projector", "motes"}, set(), w + ".atmosphere"):
        for k in ("haze", "motes"):
            if k in at:
                c.num(at[k], "%s.atmosphere.%s" % (w, k), 0, 1)
        for k in ("scanlines", "vignette", "grid", "projector"):
            if k in at and not isinstance(at[k], bool):
                c.err("%s.atmosphere.%s" % (w, k), "expected true or false")
    if "occlusion" in pr:
        c.choice(pr["occlusion"], ("xray", "none"), w + ".occlusion")
    if "certainty_style" in pr:
        c.choice(pr["certainty_style"], ("subtle", "explicit"), w + ".certainty_style")
    if "background" in pr:
        c.choice(pr["background"], ("deep", "transparent"), w + ".background")


def _animation_check(c, an, pr):
    w = "scene.animation"
    if not c.keys(an, {"assembly", "idle", "camera", "reduced_motion"}, set(), w):
        return
    asm = an.get("assembly", {})
    if c.keys(asm, {"style", "seconds", "interference"}, set(), w + ".assembly"):
        if "style" in asm:
            c.choice(asm["style"], ASSEMBLY, w + ".assembly.style")
        if "seconds" in asm:
            c.num(asm["seconds"], w + ".assembly.seconds", 0, 20)
        if "interference" in asm and not isinstance(asm["interference"], bool):
            c.err(w + ".assembly.interference", "expected true or false")
    idle = an.get("idle", {})
    if c.keys(idle, {"life", "events", "cadence", "strength"}, set(), w + ".idle"):
        if "life" in idle:
            c.choice(idle["life"], LIFE, w + ".idle.life")
        ev = idle.get("events", [])
        if not isinstance(ev, list) or len(ev) > len(EVENTS):
            c.err(w + ".idle.events", "expected a list of events")
        else:
            for e in ev:
                c.choice(e, EVENTS, w + ".idle.events")
        if "cadence" in idle:
            cad = idle["cadence"]
            if c.vec(cad, w + ".idle.cadence", 2, 1, 120) and cad[0] > cad[1]:
                c.err(w + ".idle.cadence", "minimum above maximum")
        if "strength" in idle:
            c.num(idle["strength"], w + ".idle.strength", 0, 1)
    cam = an.get("camera", {})
    view_ids = {v.get("id") for v in pr.get("views", []) if isinstance(v, dict)} if isinstance(pr, dict) and isinstance(pr.get("views", []), list) else set()
    view_ids |= {"hero", "front", "side", "back", "top", "three-quarter"}
    if c.keys(cam, {"drift", "breathe", "tour"}, set(), w + ".camera"):
        if "drift" in cam:
            c.num(cam["drift"], w + ".camera.drift", -90, 90)
        if "breathe" in cam:
            c.num(cam["breathe"], w + ".camera.breathe", 0, 0.25)
        tour = cam.get("tour", [])
        if not isinstance(tour, list) or len(tour) > MAX_TOUR:
            c.err(w + ".camera.tour", "expected at most %d stops" % MAX_TOUR)
            tour = []
        last = -1.0
        for i, s in enumerate(tour):
            sw = "%s.camera.tour[%d]" % (w, i)
            if c.keys(s, {"view", "at", "fly"}, {"view", "at"}, sw):
                if s.get("view") not in view_ids:
                    c.err(sw + ".view", "unknown view %r" % s.get("view"))
                if c.num(s.get("at"), sw + ".at", 0, 600):
                    if s["at"] < last:
                        c.err(sw + ".at", "tour stops must be in time order")
                    last = s["at"]
                if "fly" in s:
                    c.num(s["fly"], sw + ".fly", 0.2, 20)
    if "reduced_motion" in an:
        c.choice(an["reduced_motion"], ("still",), w + ".reduced_motion")


def _face_of(c, shape, face, where):
    """The face a label/artwork/anchor uses; reports an error and returns None when the
    shape has no such face."""
    t = shape.get("type") if isinstance(shape, dict) else None
    if t not in FACES:
        c.err(where, "only %s parts have faces" % ", ".join(sorted(FACES)))
        return None
    face = DEFAULT_FACE[t] if face is None else face
    if face not in FACES[t]:
        c.err(where, "a %s has the faces %s" % (t, ", ".join(FACES[t])))
        return None
    return face


def _region_check(c, region, where):
    if c.vec(region, where, 4, 0, 1) and (region[0] >= region[2] or region[1] >= region[3]):
        c.err(where, "expected [u0, v0, u1, v1] with u0 < u1 and v0 < v1 (0..1 across the face, v down)")


def _artwork_check(c, p, asset_ids, slots, w):
    a = p["artwork"]
    if not c.keys(a, {"slot", "asset", "face", "mask", "inner_radius", "region"}, {"slot"}, w):
        return
    slot = a.get("slot")
    ok = slot in ARTWORK_SLOTS[:-1]
    if isinstance(slot, str) and slot.startswith("booklet-page-"):
        n = slot[len("booklet-page-"):]
        ok = n.isdigit() and 1 <= int(n) <= 64 and str(int(n)) == n
    if not ok:
        c.err(w + ".slot", "must be one of cover-front, cover-back, inlay, disc, label, booklet-page-1..64")
    elif slot in slots:
        c.err(w + ".slot", "duplicate slot %r: each slot names one place" % slot)
    else:
        slots.add(slot)
    if "asset" in a and a["asset"] not in asset_ids:
        c.err(w + ".asset", "unknown asset %r (leave asset out for an empty slot)" % a["asset"])
    face = _face_of(c, p.get("shape"), a.get("face"), w + ".face")
    mask = a.get("mask", "rect")
    c.choice(mask, MASKS, w + ".mask")
    if "inner_radius" in a:
        if mask != "circle":
            c.err(w + ".inner_radius", "only a circle mask has an inner radius (the hole of a disc)")
        elif face is not None and c.num(a["inner_radius"], w + ".inner_radius", MIN_SIZE, MAX_EXTENT):
            half = _face_half_width(p["shape"], face)
            if a["inner_radius"] >= half:
                c.err(w + ".inner_radius", "must be smaller than the face's half width (%g m)" % half)
    if "region" in a:
        _region_check(c, a["region"], w + ".region")


def _articulation_check(c, arts, shapes_by_part):
    w = "scene.articulations"
    if not isinstance(arts, list) or len(arts) > MAX_ARTICULATIONS:
        c.err(w, "expected at most %d articulations" % MAX_ARTICULATIONS)
        return
    seen = set()
    chains = {}
    for i, a in enumerate(arts):
        aw = "%s[%d]" % (w, i)
        if not c.keys(a, {"id", "parts", "type", "axis", "pivot", "amount", "order", "note"},
                      {"id", "parts", "type", "amount"}, aw):
            continue
        if c.ident(a.get("id"), aw + ".id"):
            if a["id"] in seen:
                c.err(aw + ".id", "duplicate %r" % a["id"])
            seen.add(a["id"])
        t = a.get("type")
        c.choice(t, ARTICULATIONS, aw + ".type")
        ps = a.get("parts")
        if not isinstance(ps, list) or not 1 <= len(ps) <= 64 or len(set(map(str, ps))) != len(ps):
            c.err(aw + ".parts", "expected 1..64 distinct part ids")
        else:
            for pid in ps:
                if pid not in shapes_by_part:
                    c.err(aw + ".parts", "unknown part %r" % pid)
                else:
                    chains.setdefault(pid, []).append(i)
        if "axis" in a:
            if c.vec(a["axis"], aw + ".axis", 3, -1, 1) and sum(x * x for x in a["axis"]) < 1e-6:
                c.err(aw + ".axis", "the axis needs a direction")
        elif t != "lift":
            c.err(aw + ".axis", "missing key 'axis' (a world direction; lift defaults to up)", "missing-key",
                  "Add \"axis\": " + KEY_HELP["axis"] + ".")
        if t in ("hinge", "turn"):
            if "pivot" not in a:
                c.err(aw + ".pivot", "missing key 'pivot' (a world point on the hinge or turning axis)", "missing-key",
                      "Add \"pivot\": " + KEY_HELP["pivot"] + " in the closed pose (for a hinge, a point on the hinge line).")
            else:
                c.vec(a["pivot"], aw + ".pivot")
            c.num(a.get("amount"), aw + ".amount", -180 if t == "hinge" else -1080, 180 if t == "hinge" else 1080)
        elif t in ("slide", "lift"):
            if "pivot" in a:
                c.err(aw + ".pivot", "a %s moves along its axis and has no pivot" % t)
            c.num(a.get("amount"), aw + ".amount", -MAX_EXTENT, MAX_EXTENT)
        if "order" in a:
            c.num(a["order"], aw + ".order", 0, 15, True)
        if "note" in a:
            c.text(a["note"], aw + ".note", 300)
    if len({tuple(v) for v in chains.values()}) > MAX_JOINTS:
        c.err(w, "more than %d different combinations of articulations" % MAX_JOINTS)


def _label_check(c, labels, shapes_by_part, facts):
    w = "scene.labels"
    if not isinstance(labels, list) or len(labels) > MAX_LABELS:
        c.err(w, "expected at most %d labels" % MAX_LABELS)
        return
    known = {f.get("key") for f in facts if isinstance(f, dict) and f.get("value") is not None}
    seen = set()
    for i, lb in enumerate(labels):
        lw = "%s[%d]" % (w, i)
        if not c.keys(lb, {"id", "part", "face", "field", "text", "role", "align", "orientation", "region"},
                      {"id", "part"}, lw):
            continue
        if c.ident(lb.get("id"), lw + ".id"):
            if lb["id"] in seen:
                c.err(lw + ".id", "duplicate %r" % lb["id"])
            seen.add(lb["id"])
        if lb.get("part") not in shapes_by_part:
            c.err(lw + ".part", "unknown part %r" % lb.get("part"))
        else:
            _face_of(c, shapes_by_part[lb["part"]], lb.get("face"), lw + ".face")
        if ("field" in lb) == ("text" in lb):
            c.err(lw, "give exactly one of field (a fact key; the host sets its value) or text (decorative words)")
        elif "field" in lb and lb["field"] not in known:
            c.err(lw + ".field", "no fact %r: add the fact with its certainty, or delete the label "
                  "(an unknown fact has no label; never guess)" % lb["field"], "unknown-fact",
                  "Delete this label, or add a fact {\"key\": %s, ...} only if its value is actually known."
                  % json.dumps(lb["field"]))
        elif "text" in lb:
            c.text(lb["text"], lw + ".text", 120)
        for k, opts in (("role", LABEL_ROLES), ("align", ALIGNS), ("orientation", ORIENTATIONS)):
            if k in lb:
                c.choice(lb[k], opts, "%s.%s" % (lw, k))
        if "region" in lb:
            _region_check(c, lb["region"], lw + ".region")


def _anchor_check(c, anchors, shapes_by_part):
    w = "scene.anchors"
    if not c.keys(anchors, {"base", "front", "spine", "grip"}, set(), w):
        return
    if "base" in anchors:
        b = anchors["base"]
        if c.keys(b, {"point", "up"}, {"point"}, w + ".base"):
            c.vec(b.get("point"), w + ".base.point")
            if "up" in b and c.vec(b["up"], w + ".base.up", 3, -1, 1) and sum(x * x for x in b["up"]) < 1e-6:
                c.err(w + ".base.up", "the up vector needs a direction")
    for k in ("front", "spine"):
        if k in anchors:
            a = anchors[k]
            if c.keys(a, {"part", "face"}, {"part"}, "%s.%s" % (w, k)):
                if a.get("part") not in shapes_by_part:
                    c.err("%s.%s.part" % (w, k), "unknown part %r" % a.get("part"))
                else:
                    _face_of(c, shapes_by_part[a["part"]], a.get("face"), "%s.%s.face" % (w, k))
    if "grip" in anchors:
        g = anchors["grip"]
        if c.keys(g, {"part", "point"}, set(), w + ".grip"):
            if ("part" in g) == ("point" in g):
                c.err(w + ".grip", "give exactly one of part or point")
            elif "part" in g and g["part"] not in shapes_by_part:
                c.err(w + ".grip.part", "unknown part %r" % g["part"])
            elif "point" in g:
                c.vec(g["point"], w + ".grip.point")


def _asset_path(path, where, c):
    if not isinstance(path, str) or not path or len(path) > 512:
        c.err(where, "expected a relative path of at most 512 characters", "type", "Write e.g. \"assets/cover.png\".")
        return
    bad = ("\\" in path or "%" in path or "\x00" in path or path.startswith("/") or "://" in path
           or (len(path) > 1 and path[1] == ":"))
    if bad or any(seg in ("", ".", "..") for seg in path.split("/")):
        c.err(where, "must be a plain relative path inside the asset folder", "path",
              "Write a path relative to the scene's folder, e.g. \"assets/cover.png\"; no URLs, no absolute paths, no \"..\".")


# ---------------------------------------------------------------------------- transforms

def _rot(deg):
    rx, ry, rz = (math.radians(a) for a in deg)
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    return [[cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx],
            [sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx],
            [-sy, cy * sx, cy * cx]]


def _axis_rot(axis, deg):
    a = math.radians(deg)
    x, y, z = axis
    n = math.sqrt(x * x + y * y + z * z)
    x, y, z = x / n, y / n, z / n
    c, s, t = math.cos(a), math.sin(a), 1 - math.cos(a)
    return [[t * x * x + c, t * x * y - s * z, t * x * z + s * y],
            [t * x * y + s * z, t * y * y + c, t * y * z - s * x],
            [t * x * z - s * y, t * y * z + s * x, t * z * z + c]]


def _mul(m, v):
    return (m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
            m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
            m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2])


def _instances(part):
    """Each copy of a part as a function point -> world point, its motion pivot offset
    and its motion phase. Order: the part's own scale/rotate/translate, then the repeat,
    then the mirror."""
    sc = part.get("scale", 1)
    scale = sc if isinstance(sc, list) else [sc, sc, sc]
    rot = _rot(part.get("rotate", [0, 0, 0]))
    at = part.get("at", [0, 0, 0])

    def base(p):
        q = _mul(rot, (p[0] * scale[0], p[1] * scale[1], p[2] * scale[2]))
        return (q[0] + at[0], q[1] + at[1], q[2] + at[2])

    steps = [(lambda p: p, 0.0)]
    rep = part.get("repeat")
    if rep:
        n = rep["count"]
        dphase = rep.get("phase_step", 0.0)
        steps = []
        if "step" in rep:
            st = rep["step"]
            for i in range(n):
                r = _rot([a * i for a in st.get("rotate", [0, 0, 0])])
                d = [a * i for a in st.get("at", [0, 0, 0])]

                def f(p, r=r, d=d):
                    q = _mul(r, (p[0] - at[0], p[1] - at[1], p[2] - at[2]))
                    return (q[0] + at[0] + d[0], q[1] + at[1] + d[1], q[2] + at[2] + d[2])
                steps.append((f, dphase * i))
        else:
            ra = rep["radial"]
            axis = {"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1)}[ra.get("axis", "y")]
            centre = ra.get("center", [0, 0, 0])
            span = ra.get("span", 360)
            div = n if span >= 360 else max(1, n - 1)
            for i in range(n):
                r = _axis_rot(axis, span * i / div)

                def f(p, r=r):
                    q = _mul(r, (p[0] - centre[0], p[1] - centre[1], p[2] - centre[2]))
                    return (q[0] + centre[0], q[1] + centre[1], q[2] + centre[2])
                steps.append((f, dphase * i))
    # each copy: (shape point -> world point, motion phase, mirrored, carry) where `carry` maps a
    # world point of the first copy to this copy (the repeat and mirror only, not the part's own
    # rotate/scale): it moves a motion pivot and axis with the copy
    out = [(lambda p, s=s: s(base(p)), ph, False, s) for s, ph in steps]
    mirror = part.get("mirror")
    if mirror:
        k = "xyz".index(mirror)

        def flip(p, k=k):
            return tuple(-p[j] if j == k else p[j] for j in range(3))
        out += [(lambda p, g=g: flip(g(p)), ph + 0.5, True, lambda p, c=c: flip(c(p))) for g, ph, _, c in out]
    return out


def _local_mesh(shape, seed):
    t = shape["type"]
    if t == "box":
        m = shapes.box(shape["size"], shape.get("ribs", 0))
        if shape.get("anchor") == "base":
            m = _shift(m, (0, shape["size"][1] / 2, 0))
        return m
    if t == "cylinder":
        r = shape["radius"]
        return shapes.frustum(r, r, shape["height"], shape.get("segments", 32), shape.get("ribs", 6),
                              shape.get("caps", True), shape.get("rings", 0))
    if t == "cone":
        return shapes.frustum(shape["radius_bottom"], shape["radius_top"], shape["height"], shape.get("segments", 32),
                              shape.get("ribs", 6), shape.get("caps", True), shape.get("rings", 0))
    if t == "sphere":
        radii = shape.get("radii") or [shape["radius"]] * 3
        m = shapes.ellipsoid(radii, shape.get("lat", 8), shape.get("lon", 12), shape.get("segments", 32))
        if shape.get("anchor") == "base":
            m = _shift(m, (0, radii[1], 0))
        return m
    if t == "torus":
        return shapes.torus(shape["major"], shape["minor"], shape.get("segments", 32), shape.get("sides", 10),
                            shape.get("rings", 8))
    if t == "lathe":
        return shapes.lathe([tuple(p) for p in shape["profile"]], shape.get("segments", 32), shape.get("meridians", 8))
    if t == "extrude":
        return shapes.extrude([tuple(p) for p in shape["profile"]], shape["height"], shape.get("axis", "y"),
                              shape.get("ribs", 0))
    if t == "tube":
        return shapes.tube([tuple(p) for p in shape["path"]], shape["radius"], shape.get("sides", 8),
                           shape.get("smooth", True), shape.get("samples", 8), shape.get("ring_every", 2),
                           shape.get("longitudinal", 4), shape.get("caps", False))
    if t == "curve":
        return shapes.curve([tuple(p) for p in shape["points"]], shape.get("smooth", False), shape.get("closed", False))
    if t == "plane":
        return shapes.plane(shape["size"][0], shape["size"][1], shape.get("divisions", 0))
    if t == "grid":
        return shapes.grid(shape["size"][0], shape["size"][1], shape["divisions"])
    if t == "globe":
        return shapes.globe(shape["radius"], shape["paths"], shape.get("graticule", 30), shape.get("faces", True))
    if t == "terrain":
        return shapes.terrain(shape["size"][0], shape["size"][1], shape["heights"], shape.get("contour", 0.0),
                              shape.get("grid_every", 4), shape.get("skirt", True), shape.get("index", 5))
    if t == "points":
        region = shape["region"]
        if "box" in region:
            reg = ("box",) + tuple(region["box"])
        elif "sphere" in region:
            reg = ("sphere", region["sphere"], 0.0)
        else:
            reg = ("sphere", region["shell"], 0.15)
        return shapes.scatter(shape["count"], reg, 0, seed, SPRITE_CODE[shape.get("sprite", "soft")])
    if t == "marker":
        m = shapes.Mesh()
        m.points.append(((0.0, 0.0, 0.0), SPRITE_CODE[shape.get("sprite", "disc")]))
        return m
    raise SceneError("unknown shape %r" % t)


def _shift(m, d):
    out = shapes.Mesh()
    mv = lambda p: (p[0] + d[0], p[1] + d[1], p[2] + d[2])
    out.lines = [(mv(a), mv(b), c) for a, b, c in m.lines]
    out.tris = [(mv(a), mv(b), mv(c)) for a, b, c in m.tris]
    out.points = [(mv(p), s) for p, s in m.points]
    return out


def _face_local(shape, face):
    """A face's corners in the part's own frame, as seen from outside it: top-left,
    top-right, bottom-right, bottom-left (a box's top is seen with the front at the bottom)."""
    t = shape["type"]
    if t in ("box", "plane"):
        w, h = shape["size"][0], shape["size"][1]
        d = shape["size"][2] if t == "box" else 0.0
        y0 = h / 2 if t == "box" and shape.get("anchor") == "base" else 0.0
        x, y, z = w / 2, h / 2, d / 2
        quad = {"front": [(-x, y, z), (x, y, z), (x, -y, z), (-x, -y, z)],
                "back": [(x, y, -z), (-x, y, -z), (-x, -y, -z), (x, -y, -z)],
                "left": [(-x, y, -z), (-x, y, z), (-x, -y, z), (-x, -y, -z)],
                "right": [(x, y, z), (x, y, -z), (x, -y, -z), (x, -y, z)],
                "top": [(-x, y, -z), (x, y, -z), (x, y, z), (-x, y, z)],
                "bottom": [(-x, -y, z), (x, -y, z), (x, -y, -z), (-x, -y, -z)]}[face]
        return [(a, b + y0, c) for a, b, c in quad]
    if t == "cylinder":
        r, top, bot = shape["radius"], shape["height"], 0.0
    else:  # lathe: the disc spanned by its widest radius at its highest/lowest profile point
        r = max(q[0] for q in shape["profile"])
        top, bot = max(q[1] for q in shape["profile"]), min(q[1] for q in shape["profile"])
    if face == "top":
        return [(-r, top, -r), (r, top, -r), (r, top, r), (-r, top, r)]
    return [(-r, bot, r), (r, bot, r), (r, bot, -r), (-r, bot, -r)]


def _face_half_width(shape, face):
    c = _face_local(shape, face)
    return 0.5 * math.dist(c[0], c[1])


def _sub_quad(q, region=None, orientation="horizontal"):
    """The region [u0, v0, u1, v1] of a quad (u across, v down), turned so that its first
    edge is the direction text runs."""
    if region:
        tl, tr, _, bl = q
        at = lambda u, v: tuple(tl[k] + u * (tr[k] - tl[k]) + v * (bl[k] - tl[k]) for k in range(3))
        u0, v0, u1, v1 = region
        q = [at(u0, v0), at(u1, v0), at(u1, v1), at(u0, v1)]
    if orientation == "vertical-down":
        q = [q[1], q[2], q[3], q[0]]
    elif orientation == "vertical-up":
        q = [q[3], q[0], q[1], q[2]]
    return q


def _world_face(part, face, region=None, orientation="horizontal", lift=0.0):
    """A face of a part's first copy in world space (rest pose), lifted along its outward
    normal so an image or text sits just in front of the surface."""
    xf = _instances(part)[0][0]
    q = [xf(c) for c in _face_local(part["shape"], face)]
    if lift:
        tl, tr, _, bl = q
        a = [bl[k] - tl[k] for k in range(3)]
        b = [tr[k] - tl[k] for k in range(3)]
        n = (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
        ln = math.sqrt(sum(x * x for x in n)) or 1.0
        q = [tuple(c[k] + lift * n[k] / ln for k in range(3)) for c in q]
    return _sub_quad(q, region, orientation)


def _articulate(art, p, u=1.0):
    """One articulation applied to a world point at opening u (0 closed, 1 open)."""
    amount = art["amount"] * u
    if art["type"] in ("hinge", "turn"):
        piv = art["pivot"]
        q = _mul(_axis_rot(art["axis"], amount), (p[0] - piv[0], p[1] - piv[1], p[2] - piv[2]))
        return (q[0] + piv[0], q[1] + piv[1], q[2] + piv[2])
    return tuple(p[k] + art["axis"][k] * amount for k in range(3))


def _chain_apply(chain, arts, p, u=1.0):
    # a later articulation rides on the earlier ones: the first in order is outermost
    for ai in reversed(chain):
        p = _articulate(arts[ai], p, u)
    return p


def _r(x):
    return round(x, 5) + 0.0


def _hash_part(seed, pid):
    return (seed * 1000003 + int(hashlib.sha256(pid.encode()).hexdigest()[:8], 16)) % 2147483647


# ---------------------------------------------------------------------------- compile

def canonical_sha256(scene):
    return hashlib.sha256(json.dumps(scene, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def cross_section(p):
    """The smallest cross-section of a linear part in metres, or None when it is not linear."""
    sh, t = p["shape"], p["shape"]["type"]
    sc = p.get("scale", 1)
    k = min(sc) if isinstance(sc, list) else sc
    if t == "tube":
        r = sh["radius"]
        return 2 * (max(r) if isinstance(r, list) else r) * k  # a tapered tube is as thick as its widest point
    if t == "curve":
        return 0.0
    if t in ("cylinder", "cone"):
        d = 2 * (sh["radius"] if t == "cylinder" else max(sh["radius_bottom"], sh["radius_top"]))
        return d * k if sh["height"] > 4 * d else None
    if t == "torus":
        return 2 * sh["minor"] * k
    if t == "box":
        dims = sorted(sh["size"])
        return dims[1] * k if dims[2] > 4 * dims[1] else None
    return None


def compile_scene(scene):
    """Validate and compile; raises SceneError listing every problem."""
    errors = validate(scene)
    if errors:
        raise SceneError("\n".join(errors))
    pr = _normal_presentation(scene)
    explicit = pr["certainty_style"] == "explicit"
    seed = scene["seed"]

    stages = sorted({p["stage"] for p in scene["parts"]})
    stage_index = {s: i for i, s in enumerate(stages)}

    # articulations, in order; each part's chain of them is its joint (a shared transform slot)
    raw = sorted(enumerate(scene.get("articulations", [])), key=lambda x: (x[1].get("order", 0), x[0]))
    arts = []
    for _, a in raw:
        axis = a.get("axis", [0, 1, 0])
        n = math.sqrt(sum(x * x for x in axis))
        arts.append({"id": a["id"], "type": a["type"], "axis": [_r(x / n) for x in axis],
                     "pivot": [_r(x) for x in a["pivot"]] if "pivot" in a else None,
                     "amount": a["amount"], "unit": "deg" if a["type"] in ("hinge", "turn") else "m",
                     "order": a.get("order", 0), "parts": list(a["parts"]), "instances": []})
    joints, joint_of = [], {}
    for part in scene["parts"]:
        chain = tuple(i for i, a in enumerate(arts) if part["id"] in a["parts"])
        if chain:
            if chain not in joints:
                joints.append(chain)
            joint_of[part["id"]] = joints.index(chain)

    styles, style_key = [], {}
    lines, fills, points, motions, artwork = [], [], [], [], []
    part_out = []
    # per stage height range for the build phase (filled in a first pass)
    built = []
    for pi, part in enumerate(scene["parts"]):
        mesh = _local_mesh(part["shape"], _hash_part(seed, part["id"]))
        tone, alpha, width, glow, fill, fade = ROLE_STYLE[part["role"]]
        look = part.get("look", {})
        tone = look.get("tone", tone)
        cert_alpha, cert_line = CERTAINTY_STYLE[part["certainty"]]
        if explicit and part["certainty"] == "inferred":
            cert_line = "dashed"
        line_kind = look.get("line", "auto")
        line_kind = cert_line if line_kind == "auto" else line_kind
        fill = fill if look.get("fill", "auto") == "auto" else look["fill"]
        alpha = look.get("alpha", alpha) * cert_alpha
        width = width * look.get("weight", 1.0)
        if "glow" in look:
            glow = 3.0 * look["glow"]
        pinfo = {"id": part["id"], "label": part.get("label", part["id"]), "role": part["role"],
                 "certainty": part["certainty"], "basis": list(part.get("basis", [])),
                 "source": part.get("source"), "stage": part["stage"], "floating": part.get("floating", False),
                 "shape": part["shape"]["type"], "instances": [], "motion": None,
                 "joint": joint_of.get(part["id"], -1)}
        sprite_px = part["shape"].get("size_px", 5 if part["shape"]["type"] == "points" else 9)
        for inst_i, (xf, phase, mirrored, carry) in enumerate(_instances(part)):
            slot = -1
            if part.get("motion"):
                mo = part["motion"]
                # the pivot is a world point and the axis a world direction for the first copy
                # (default pivot: the part's `at`); every repeat/mirror copy carries them along
                at = tuple(part.get("at", (0.0, 0.0, 0.0)))
                p0 = tuple(mo.get("pivot", at))
                pivot = carry(p0)
                d = mo.get("axis", [0, 1, 0])
                tip = carry((p0[0] + d[0], p0[1] + d[1], p0[2] + d[2]))
                axis = [tip[k] - pivot[k] for k in range(3)]
                norm = math.sqrt(sum(x * x for x in axis)) or 1.0
                axis = [x / norm for x in axis]
                if mirrored and mo["type"] in ("spin", "swing"):
                    axis = [-x for x in axis]  # a rotation axis is a pseudovector: a mirror turns it round
                slot = len(motions)
                motions.append({"type": mo["type"], "axis": [_r(a) for a in axis], "pivot": [_r(a) for a in pivot],
                                "rpm": mo.get("rpm", 0.0), "degrees": mo.get("degrees", 0.0),
                                "distance": mo.get("distance", 0.0), "period": mo.get("period", 1.0),
                                "amount": mo.get("amount", 0.0),
                                "phase": (mo.get("phase", 0.0) + phase) % 1.0, "part": part["id"]})
            inst_lines = [(xf(a), xf(b), cls) for a, b, cls in mesh.lines]
            inst_tris = [(xf(a), xf(b), xf(c)) for a, b, c in mesh.tris] if fill in ("glass", "dark") else []
            inst_pts = [(xf(p), s) for p, s in mesh.points]
            lo, hi = [math.inf] * 3, [-math.inf] * 3
            for seq in ([p for a, b, _ in inst_lines for p in (a, b)], [p for t in inst_tris for p in t],
                        [p for p, _ in inst_pts]):
                for p in seq:
                    for k in range(3):
                        lo[k], hi[k] = min(lo[k], p[k]), max(hi[k], p[k])
            if lo[0] == math.inf:
                lo = hi = list(xf((0.0, 0.0, 0.0)))
            joint = joint_of.get(part["id"], -1)
            inst = {"min": [_r(x) for x in lo], "max": [_r(x) for x in hi], "motion_slot": slot, "joint": joint}
            if joint >= 0:
                # where the copy reaches when fully open (its rest box carried through the chain)
                corners = [_chain_apply(joints[joint], arts, (lo[0] if i & 1 else hi[0], lo[1] if i & 2 else hi[1],
                                                              lo[2] if i & 4 else hi[2])) for i in range(8)]
                inst["open_min"] = [_r(min(c[k] for c in corners)) for k in range(3)]
                inst["open_max"] = [_r(max(c[k] for c in corners)) for k in range(3)]
                for ai in joints[joint]:
                    arts[ai]["instances"].append([part["id"], inst_i])
            pinfo["instances"].append(inst)
            built.append((pi, part, inst_lines, inst_tris, inst_pts, slot,
                          (tone, alpha, width, glow, line_kind, fade, fill, sprite_px)))
        if part.get("motion"):
            pinfo["motion"] = dict(part["motion"])
        part_out.append(pinfo)

    # build phase: within its stage, a point's height decides when it appears (bottom-up)
    yr = {}
    for pi, part, ls, ts, ps, slot, st in built:
        s = part["stage"]
        ys = [p[1] for a, b, _ in ls for p in (a, b)] + [p[1] for p, _ in ps]
        if ys:
            lo, hi = yr.get(s, (math.inf, -math.inf))
            yr[s] = (min(lo, min(ys)), max(hi, max(ys)))
    nst = max(1, len(stages))

    def phase(stage, y):
        lo, hi = yr.get(stage, (0.0, 1.0))
        f = 0.0 if hi - lo < 1e-9 else (y - lo) / (hi - lo)
        return round((stage_index[stage] + 0.82 * f) / nst, 4)

    # legibility: a small mass or structure part (an arm, a handle, a stem) is drawn with a
    # minimum visual weight, so it does not read as a gap next to dense parts
    olo, ohi = [math.inf] * 3, [-math.inf] * 3
    for pinfo in part_out:
        for ins in pinfo["instances"]:
            for k in range(3):
                olo[k], ohi[k] = min(olo[k], ins["min"][k]), max(ohi[k], ins["max"][k])
    obj_diag = math.sqrt(sum((ohi[k] - olo[k]) ** 2 for k in range(3))) or 1.0
    obj_size = max(ohi[k] - olo[k] for k in range(3)) or 1.0
    small = set()
    for i, pinfo in enumerate(part_out):
        b = pinfo["instances"][0]
        if pinfo["role"] not in ("mass", "structure"):
            continue
        cs = cross_section(scene["parts"][i])
        if (cs is not None and cs < 0.04 * obj_size) or \
                math.sqrt(sum((b["max"][k] - b["min"][k]) ** 2 for k in range(3))) < 0.35 * obj_diag:
            small.add(i)

    def style_of(pi, cls, slot, st, kind, part=None):
        tone, alpha, width, glow, line_kind, fade, fill, _ = st
        wf, af = CLASS_STYLE.get(cls, (1.0, 1.0))
        if pi in small and kind == "line" and cls != shapes.DETAIL:
            wf, af = max(wf, 1.0) * 1.2, max(af, 0.9) * 1.3
        jt = joint_of.get(scene["parts"][pi]["id"], -1)
        if kind == "fill":
            key = ("f", pi, slot, fill)
            # glass whispers, a dark fill hides what is behind it (xray)
            glass = {"identity": 0.14, "mass": 0.09, "data": 0.1}.get(part["role"], 0.07)
            entry = [TONES.index(tone), round(glass if fill == "glass" else 0.55, 4), 0, 0, 0, fade, pi, slot,
                     1 if fill == "dark" else 0, jt]
        elif kind == "point":
            key = ("p", pi, slot)
            entry = [TONES.index(tone), round(min(1.0, alpha * 1.05), 4), 0, 0, 0, fade, pi, slot, 0, jt]
        else:
            key = ("l", pi, cls, slot)
            entry = [TONES.index(tone), round(min(1.0, alpha * af), 4), round(width * wf, 3),
                     round(glow * (1.0 if cls == shapes.OUTLINE else 0.4), 3),
                     DASH_CODE.get(line_kind, 0), fade + (1 if cls == shapes.DETAIL else 0), pi, slot, 0, jt]
        if key not in style_key:
            style_key[key] = len(styles)
            styles.append(entry)
        return style_key[key]

    art_done = set()
    for pi, part, ls, ts, ps, slot, st in built:
        if st[4] != "none":
            for a, b, cls in ls:
                si = style_of(pi, cls, slot, st, "line")
                lines.extend([_r(a[0]), _r(a[1]), _r(a[2]), _r(b[0]), _r(b[1]), _r(b[2]), si,
                              phase(part["stage"], a[1]), phase(part["stage"], b[1])])
        for tri in ts:
            si = style_of(pi, 0, slot, st, "fill", part)
            for p in tri:
                fills.extend([_r(p[0]), _r(p[1]), _r(p[2]), si, phase(part["stage"], p[1])])
        for p, shape in ps:
            si = style_of(pi, 0, slot, st, "point")
            points.extend([_r(p[0]), _r(p[1]), _r(p[2]), st[7], si, shape, phase(part["stage"], p[1])])
        art = part.get("artwork")
        if art and part["id"] not in art_done:
            art_done.add(part["id"])
            face = art.get("face", DEFAULT_FACE[part["shape"]["type"]])
            corners = _world_face(part, face, art.get("region"), lift=0.0005)
            half = _face_half_width(part["shape"], face)
            artwork.append({"part": part["id"], "slot": art["slot"], "asset_id": art.get("asset"), "face": face,
                            "corners": [[_r(x) for x in c] for c in corners], "uv": [[0, 0], [1, 0], [1, 1], [0, 1]],
                            "mask": art.get("mask", "rect"),
                            "inner_ratio": _r(art.get("inner_radius", 0.0) / half) if half else 0.0,
                            "certainty": part["certainty"], "motion_slot": slot,
                            "joint": joint_of.get(part["id"], -1),
                            "phase": phase(part["stage"], min(c[1] for c in corners))})

    n_lines, n_tris, n_points = len(lines) // 9, len(fills) // 15, len(points) // 7
    if n_lines > MAX_LINES or n_tris > MAX_TRIS or n_points > MAX_POINTS:
        raise SceneError("geometry budget exceeded: %d lines (max %d), %d triangles (max %d), %d points (max %d)"
                         % (n_lines, MAX_LINES, n_tris, MAX_TRIS, n_points, MAX_POINTS))

    lo, hi = [math.inf] * 3, [-math.inf] * 3
    for pinfo in part_out:
        for inst in pinfo["instances"]:
            for k in range(3):
                lo[k], hi[k] = min(lo[k], inst["min"][k]), max(hi[k], inst["max"][k])
    centre = [_r((lo[k] + hi[k]) / 2) for k in range(3)]
    radius = _r(0.5 * math.sqrt(sum((hi[k] - lo[k]) ** 2 for k in range(3))))

    anns = []
    by_id = {p["id"]: p for p in part_out}
    for a in scene.get("annotations", []):
        inst = by_id[a["part"]]["instances"][0]
        anchor = [(inst["min"][k] + inst["max"][k]) / 2 for k in range(3)]
        anchor[1] = inst["max"][1]
        off = a.get("offset", [0, 0, 0])
        anns.append({"id": a["id"], "text": a["text"], "part": a["part"],
                     "anchor": [_r(anchor[k] + off[k]) for k in range(3)], "joint": inst["joint"],
                     "certainty": a.get("certainty", by_id[a["part"]]["certainty"])})

    facts = {f["key"]: f for f in scene["facts"]}
    labels = []
    parts_by_id = {p["id"]: p for p in scene["parts"]}
    for lb in scene.get("labels", []):
        part = parts_by_id[lb["part"]]
        face = lb.get("face", DEFAULT_FACE[part["shape"]["type"]])
        orient = lb.get("orientation", "horizontal")
        q = _world_face(part, face, lb.get("region"), orient, lift=0.0006)
        if "field" in lb:
            f = facts[lb["field"]]
            v = f["value"]
            text = ("yes" if v else "no") if isinstance(v, bool) else (
                str(int(v)) if isinstance(v, float) and v.is_integer() else str(v))
            if f.get("unit") and not isinstance(v, (bool, str)):
                text += f["unit"] if f["unit"] in ("%", "°") else " " + f["unit"]
            cert, field = f["certainty"], lb["field"]
        else:
            text, cert, field = lb["text"], "decorative", None
        inst = by_id[part["id"]]["instances"][0]
        labels.append({"id": lb["id"], "part": part["id"], "face": face, "corners": [[_r(x) for x in c] for c in q],
                       "field": field, "text": text, "certainty": cert,
                       "role": lb.get("role", "decorative" if field is None else "meta"),
                       "align": lb.get("align", "center"), "orientation": orient,
                       "motion_slot": inst["motion_slot"], "joint": inst["joint"],
                       "phase": phase(part["stage"], min(c[1] for c in q))})

    anchors = _anchors(scene, parts_by_id, by_id, lo, hi)
    open_lo, open_hi = list(lo), list(hi)
    for pinfo in part_out:
        for inst in pinfo["instances"]:
            if "open_min" in inst:
                for k in range(3):
                    open_lo[k], open_hi[k] = min(open_lo[k], inst["open_min"][k]), max(open_hi[k], inst["open_max"][k])

    return {
        "format": GEOMETRY_FORMAT, "version": GEOMETRY_VERSION, "generator": GENERATOR,
        "contract": product.CONTRACT,
        "frame": {"up": "+y", "forward": "+z", "note": "metres; the front faces +Z; a viewer's yaw 0 looks at the front"},
        "id": scene["id"], "title": scene["title"], "subject": dict(scene["subject"]),
        "scene_sha256": canonical_sha256(scene),
        "provenance": {"sources": [dict(s) for s in scene["sources"]], "facts": [dict(f) for f in scene["facts"]],
                       "assets": [dict(a) for a in scene.get("assets", [])],
                       **({"authoring": json.loads(json.dumps(scene["authoring"]))} if scene.get("authoring") else {})},
        "bounds": {"min": [_r(x) for x in lo], "max": [_r(x) for x in hi], "center": centre, "radius": radius,
                   "open_min": [_r(x) for x in open_lo], "open_max": [_r(x) for x in open_hi]},
        "anchors": anchors,
        "stages": [{"stage": s, "index": i} for i, s in enumerate(stages)],
        "parts": part_out, "styles": styles,
        "style_fields": ["tone", "alpha", "width_px", "glow_px", "dash", "fade", "part", "motion_slot", "occluder",
                         "joint"],
        "lines": lines, "line_stride": 9, "line_fields": ["ax", "ay", "az", "bx", "by", "bz", "style", "phase_a", "phase_b"],
        "fills": fills, "fill_stride": 5, "fill_fields": ["x", "y", "z", "style", "phase"],
        "points": points, "point_stride": 7, "point_fields": ["x", "y", "z", "size_px", "style", "sprite", "phase"],
        "motions": motions, "articulations": arts, "joints": [list(j) for j in joints],
        "artwork": artwork, "labels": labels, "annotations": anns,
        "presentation": pr, "animation": _normal_animation(scene),
        "counts": {"lines": n_lines, "triangles": n_tris, "points": n_points, "motions": len(motions),
                   "articulations": len(arts), "labels": len(labels),
                   "instances": sum(len(p["instances"]) for p in part_out)},
    }


def _anchors(scene, parts_by_id, info_by_id, lo, hi):
    """Where a host holds and shelves the object (rest pose): base point and up, the front
    and spine faces (top-left, top-right, bottom-right, bottom-left as seen from outside),
    and an optional grip point. Unstated ones come from the bounds."""
    an = scene.get("anchors", {})
    rq = lambda q: [[_r(x) for x in c] for c in q]
    base = an.get("base")
    out = {"base": {"point": [_r(x) for x in base["point"]], "up": list(base.get("up", [0, 1, 0])), "from": "scene"}
           if base else {"point": [_r((lo[0] + hi[0]) / 2), _r(lo[1]), _r((lo[2] + hi[2]) / 2)], "up": [0, 1, 0],
                         "from": "bounds"}}
    bounds_faces = {
        "front": [(lo[0], hi[1], hi[2]), (hi[0], hi[1], hi[2]), (hi[0], lo[1], hi[2]), (lo[0], lo[1], hi[2])],
        "spine": [(lo[0], hi[1], lo[2]), (lo[0], hi[1], hi[2]), (lo[0], lo[1], hi[2]), (lo[0], lo[1], lo[2])],
    }
    for k in ("front", "spine"):
        if k in an:
            part = parts_by_id[an[k]["part"]]
            face = an[k].get("face", DEFAULT_FACE[part["shape"]["type"]])
            out[k] = {"corners": rq(_world_face(part, face)), "part": part["id"], "face": face, "from": "scene"}
        else:
            out[k] = {"corners": rq(bounds_faces[k]), "part": None, "face": "+z" if k == "front" else "-x",
                      "from": "bounds"}
    grip = an.get("grip")
    if grip and "part" in grip:
        b = info_by_id[grip["part"]]["instances"][0]
        out["grip"] = {"point": [_r((b["min"][k] + b["max"][k]) / 2) for k in range(3)], "part": grip["part"], "from": "scene"}
    elif grip:
        out["grip"] = {"point": [_r(x) for x in grip["point"]], "part": None, "from": "scene"}
    else:
        out["grip"] = None
    return out


def _normal_presentation(scene):
    pr = scene.get("presentation", {})
    at = pr.get("atmosphere", {})
    fr = pr.get("framing", {})
    return {
        "framing": {"yaw": fr.get("yaw", 35.0), "pitch": fr.get("pitch", 18.0), "fit": fr.get("fit", 1.0),
                    "target": fr.get("target")},
        "views": [dict(v) for v in pr.get("views", [])],
        "atmosphere": {"haze": at.get("haze", 0.7), "scanlines": at.get("scanlines", True),
                       "vignette": at.get("vignette", True), "grid": at.get("grid", True),
                       "projector": at.get("projector", False), "motes": at.get("motes", 0.4)},
        "occlusion": pr.get("occlusion", "xray"),
        "certainty_style": pr.get("certainty_style", "subtle"),
        "background": pr.get("background", "deep"),
        "float": pr.get("float", 0.0),
        # one house palette whatever the model wrote: a scene's style_hint is ignored, and only
        # the person can choose another colour, through a host option (build --palette)
        "style_hint": dict(HOUSE_STYLE),
        "still_pose": pr.get("still_pose", "open"),
    }


def _normal_animation(scene):
    an = scene.get("animation", {})
    asm, idle, cam = an.get("assembly", {}), an.get("idle", {}), an.get("camera", {})
    return {
        "assembly": {"style": asm.get("style", "ceremony"), "seconds": asm.get("seconds", 6.0),
                     "interference": asm.get("interference", True)},
        "idle": {"life": idle.get("life", "alive"), "events": list(idle.get("events", ["scan", "sweep", "shimmer"])),
                 "cadence": list(idle.get("cadence", [5, 11])), "strength": idle.get("strength", 0.6)},
        "camera": {"drift": cam.get("drift", 6.0), "breathe": cam.get("breathe", 0.03),
                   "tour": [dict(s) for s in cam.get("tour", [])]},
        "reduced_motion": an.get("reduced_motion", "still"),
    }


# ---------------------------------------------------------------------------- v1 adapter

V1_TONE = {"accent": "accent", "bright": "bright", "hairline": "bright", "structure": "structure",
           "dust": "dust", "identity": "identity", "data": "accent", "faint": "faint"}


def to_v1(geometry, limit=20000):
    """The richer geometry as the version-1 segment list ("tessera-geometry") existing
    consumers read: tones folded to the v1 six, stages clamped to 0..5, and at most
    `limit` segments (the faintest, most distance-faded lines are dropped first)."""
    styles = geometry["styles"]
    stride = geometry["line_stride"]
    data = geometry["lines"]
    order = sorted(range(len(data) // stride),
                   key=lambda i: (styles[int(data[i * stride + 6])][5], -styles[int(data[i * stride + 6])][1], i))
    keep = sorted(order[:limit])
    parts = geometry["parts"]
    stage_of = {p["id"]: min(5, next(s["index"] for s in geometry["stages"] if s["stage"] == p["stage"])) for p in parts}
    segs = []
    for i in keep:
        row = data[i * stride:(i + 1) * stride]
        st = styles[int(row[6])]
        part = parts[int(st[6])]
        segs.append({"a": row[0:3], "b": row[3:6], "tone": V1_TONE[TONES[int(st[0])]],
                     "certainty": part["certainty"], "stage": stage_of[part["id"]], "part_id": part["id"]})
    lo, hi = geometry["bounds"]["min"], geometry["bounds"]["max"]
    return {"format": "tessera-geometry", "version": 1, "id": geometry["id"], "title": geometry["title"],
            "kind": "custom", "source_sheet_sha256": geometry["scene_sha256"],
            "facts": [{"key": f["key"], "value": f["value"], "certainty": f["certainty"],
                       "source": f.get("source")} for f in geometry["provenance"]["facts"]],
            "part_sources": {p["id"]: {"certainty": p["certainty"], "source": p["source"]} for p in parts},
            "segments": segs, "bounds": {"min": lo, "max": hi}, "assets": [], "artwork_quads": [],
            "motion": {"assembly_ms": int(min(5000, geometry["animation"]["assembly"]["seconds"] * 1000)),
                       "ambient": "scan" if geometry["animation"]["idle"]["life"] != "off" else "off",
                       "strength": geometry["animation"]["idle"]["strength"]},
            "downgraded_from": {"format": GEOMETRY_FORMAT, "version": GEOMETRY_VERSION,
                                "dropped_segments": len(order) - len(keep)}}


# ---------------------------------------------------------------------------- output frame

def reframe(geometry, frame="z-up"):
    """The same geometry in a Z-up frame for consumers that use one: (x, y, z) Y-up becomes
    (x, -z, y), a proper rotation (handedness kept). Positions, motion pivots and axes,
    artwork corners, annotation anchors and bounds are converted; nothing else changes."""
    if frame in ("y-up", None):
        return geometry
    if frame != "z-up":
        raise SceneError("unknown frame %r (y-up or z-up)" % frame)
    import copy as _copy
    g = _copy.deepcopy(geometry)

    def p(v):
        return [v[0], _r(-v[2]), v[1]]

    def flat(data, stride, offsets):
        for i in range(0, len(data), stride):
            for o in offsets:
                x, y, z = data[i + o:i + o + 3]
                data[i + o:i + o + 3] = [x, _r(-z), y]

    flat(g["lines"], g["line_stride"], (0, 3))
    flat(g["fills"], g["fill_stride"], (0,))
    flat(g["points"], g["point_stride"], (0,))
    for m in g["motions"]:
        m["pivot"], m["axis"] = p(m["pivot"]), p(m["axis"])
    for a in g["articulations"]:
        a["axis"] = p(a["axis"])
        if a["pivot"] is not None:
            a["pivot"] = p(a["pivot"])
    for a in g["artwork"] + g["labels"]:
        a["corners"] = [p(c) for c in a["corners"]]
    an = g["anchors"]
    an["base"]["point"], an["base"]["up"] = p(an["base"]["point"]), p(an["base"]["up"])
    for k in ("front", "spine"):
        an[k]["corners"] = [p(c) for c in an[k]["corners"]]
    if an["grip"]:
        an["grip"]["point"] = p(an["grip"]["point"])
    for a in g["annotations"]:
        a["anchor"] = p(a["anchor"])

    def box(lo, hi):
        a, b = p(lo), p(hi)
        return [min(a[k], b[k]) for k in range(3)], [max(a[k], b[k]) for k in range(3)]
    for part in g["parts"]:
        for inst in part["instances"]:
            inst["min"], inst["max"] = box(inst["min"], inst["max"])
            if "open_min" in inst:
                inst["open_min"], inst["open_max"] = box(inst["open_min"], inst["open_max"])
    lo, hi = box(g["bounds"]["min"], g["bounds"]["max"])
    olo, ohi = box(g["bounds"]["open_min"], g["bounds"]["open_max"])
    g["bounds"] = {"min": lo, "max": hi, "center": p(g["bounds"]["center"]), "radius": g["bounds"]["radius"],
                   "open_min": olo, "open_max": ohi}
    g["frame"] = {"up": "+z", "forward": "-y", "note": "converted from the authoring frame (Y up): (x, y, z) -> (x, -z, y)"}
    return g
