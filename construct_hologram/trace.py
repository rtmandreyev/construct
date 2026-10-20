"""Shapes traced from reference images: measured by a model that can see, fitted here.

A vision-capable model looks at a reference image — the user's own photo, or an image it views
on the web without keeping it — and returns a `construct-trace` document: the silhouette as
points in the image's pixels and the positions of named features. `fit()` turns that into
geometry deterministically: it checks the outline, flips it to Y-up, resamples it, and scales
it so a documented dimension holds (the distance between two features, or the outline's
height or width). The result is ready for an `extrude` (axis "z": a front elevation) and
cites the image as a `reference_image` source; the geometry it makes is `inferred`, never
`verified`. The image itself is never embedded or stored.

    {"format": "construct-trace", "version": 1,
     "reference": {"id": "ref-front", "title": "Maker's product photo, front", "ref": "https://... or 'user photo'",
                   "rights": "reference_only", "view": "front"},
     "image": {"width": 1200, "height": 1600},
     "outline": [[x, y], ...],                      # pixels, y down, the silhouette edge, 24..400 points
     "features": {"nut": [x, y], "bridge": [x, y]}} # pixels, optional
"""

import math

FORMAT = "construct-trace"
VERSION = 1


class TraceError(Exception):
    pass


def _items(c, doc):
    """Problems in a trace document as {where, message, code, hint} (paths from `scene`)."""
    if not c.keys(doc, {"format", "version", "reference", "image", "outline", "features", "notes"},
                  {"format", "version", "reference", "image", "outline"}, "scene"):
        return
    if doc.get("format") != FORMAT:
        c.err("scene.format", "must be %r" % FORMAT, "choice", 'Write "format": "%s".' % FORMAT)
    ref = doc.get("reference")
    if c.keys(ref, {"id", "title", "ref", "rights", "view"}, {"id", "title"}, "scene.reference"):
        c.ident(ref.get("id"), "scene.reference.id")
        c.text(ref.get("title"), "scene.reference.title", 300)
        if "rights" in ref:
            c.choice(ref["rights"], ("reference_only", "user_private", "permitted", "public_domain"), "scene.reference.rights")
        if "view" in ref:
            c.choice(ref["view"], ("front", "back", "side", "top", "three-quarter"), "scene.reference.view")
    img = doc.get("image")
    if c.keys(img, {"width", "height"}, {"width", "height"}, "scene.image"):
        c.num(img.get("width"), "scene.image.width", 16, 20000)
        c.num(img.get("height"), "scene.image.height", 16, 20000)
    out = doc.get("outline")
    if not isinstance(out, list) or not 12 <= len(out) <= 400:
        c.err("scene.outline", "expected 12..400 [x, y] points around the silhouette", "type",
              "Trace the whole silhouette edge once, 40-120 points, in image pixels.")
        return
    for i, p in enumerate(out):
        c.vec(p, "scene.outline[%d]" % i, 2, -1e5, 1e5)
    feats = doc.get("features", {})
    if isinstance(feats, dict):
        for k, p in feats.items():
            c.vec(p, "scene.features.%s" % k, 2, -1e5, 1e5)
    else:
        c.err("scene.features", "expected an object of named [x, y] points", "type", '{"nut": [x, y], "bridge": [x, y]}')


def validate_items(doc):
    from . import scene as scene_mod
    c = scene_mod._Check()
    _items(c, doc)
    if not c.items and _self_intersects([tuple(p) for p in doc["outline"]]):
        c.err("scene.outline", "the outline crosses itself", "rule",
              "Trace the edge in one direction without doubling back; drop points where it loops.")
    return c.items


def _area2(poly):
    return sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
               for i in range(len(poly)))


def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _segments_cross(p1, p2, p3, p4):
    d1, d2, d3, d4 = _cross(p3, p4, p1), _cross(p3, p4, p2), _cross(p1, p2, p3), _cross(p1, p2, p4)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)) and 0 not in (d1, d2, d3, d4)


def _self_intersects(poly):
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            if _segments_cross(a, b, poly[j], poly[(j + 1) % n]):
                return True
    return False


def _resample(poly, n):
    """n points evenly spaced along the closed outline, starting at its first point."""
    pts = poly + [poly[0]]
    seg = [math.dist(pts[i], pts[i + 1]) for i in range(len(poly))]
    total = sum(seg)
    out, acc, i = [], 0.0, 0
    for k in range(n):
        target = total * k / n
        while i < len(seg) - 1 and acc + seg[i] < target:
            acc += seg[i]
            i += 1
        f = 0.0 if seg[i] == 0 else (target - acc) / seg[i]
        a, b = pts[i], pts[i + 1]
        out.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
    return out


def fit(doc, fit_spec, origin="bottom-center", points=96):
    """Scale a validated trace so a documented dimension holds.

    fit_spec: "a:b=0.648" (metres between features a and b), "height=0.98" or "width=0.33"
    (of the outline). origin: "bottom-center", "center", or "feature:<name>" (that feature at 0, 0).
    """
    items = validate_items(doc)
    if items:
        raise TraceError("\n".join("%s: %s" % (i["where"], i["message"]) for i in items))
    try:
        what, metres = fit_spec.split("=")
        metres = float(metres)
    except ValueError:
        raise TraceError("--fit is a:b=metres, height=metres or width=metres")
    if not 0 < metres < 1000:
        raise TraceError("the fitted dimension must be between 0 and 1000 m")
    poly = [(float(x), -float(y)) for x, y in doc["outline"]]  # pixels, y up
    feats = {k: (float(v[0]), -float(v[1])) for k, v in doc.get("features", {}).items()}
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    if what == "height":
        px = max(ys) - min(ys)
    elif what == "width":
        px = max(xs) - min(xs)
    elif ":" in what:
        a, b = what.split(":", 1)
        if a not in feats or b not in feats:
            raise TraceError("features %r and %r must both be traced" % (a, b))
        px = math.dist(feats[a], feats[b])
    else:
        raise TraceError("--fit is a:b=metres, height=metres or width=metres")
    if px <= 0:
        raise TraceError("the fitted dimension has no length in the image")
    s = metres / px
    if origin == "bottom-center":
        ox, oy = (min(xs) + max(xs)) / 2, min(ys)
    elif origin == "center":
        ox, oy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    elif origin.startswith("feature:") and origin[8:] in feats:
        ox, oy = feats[origin[8:]]
    else:
        raise TraceError("origin is bottom-center, center or feature:<name of a traced feature>")
    poly = [((x - ox) * s, (y - oy) * s) for x, y in poly]
    if _area2(poly) < 0:
        poly = poly[::-1]
    n = max(12, min(int(points), 128))
    if len(poly) > n:
        # thin the outline evenly, but keep its extremes: they carry the fitted size
        ext = {min(poly, key=lambda q: q[0]), max(poly, key=lambda q: q[0]),
               min(poly, key=lambda q: q[1]), max(poly, key=lambda q: q[1])}
        thin = _resample(poly, n)
        for e in ext:
            k = min(range(len(thin)), key=lambda i: math.dist(thin[i], e))
            thin[k] = e
        poly = thin
    profile = [[round(x, 5), round(y, 5)] for x, y in poly]
    ref = doc["reference"]
    size = [round(max(p[0] for p in profile) - min(p[0] for p in profile), 4),
            round(max(p[1] for p in profile) - min(p[1] for p in profile), 4)]
    return {
        "profile": profile,
        "features": {k: [round((x - ox) * s, 5), round((y - oy) * s, 5)] for k, (x, y) in feats.items()},
        "size_m": size,
        "metres_per_pixel": round(s, 8),
        "fitted": {"to": what, "metres": metres},
        "source": {"id": ref["id"], "kind": "reference_image", "title": ref["title"],
                   "rights": ref.get("rights", "reference_only"), **({"ref": ref["ref"]} if ref.get("ref") else {})},
        "part": {"certainty": "inferred", "source": ref["id"],
                 "note": "outline traced from %s and scaled so %s = %g m" % (ref["title"], what, metres)},
    }


# ---------------------------------------------------------------------------- stations

def _crossings(poly, axis, at):
    """Where a closed polygon crosses the line x = at (axis 0) or y = at (axis 1): the other coordinates."""
    out = []
    o = 1 - axis
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        if (a[axis] <= at) != (b[axis] <= at) and a[axis] != b[axis]:
            t = (at - a[axis]) / (b[axis] - a[axis])
            out.append(a[o] + (b[o] - a[o]) * t)
    return out


def stations(side, top, length, front=None, height=None, width=None, count=24, nose_side="left", nose_top="up",
             sill=None, rnd=0.5):
    """Loft sections for a body from traced views: the side outline gives each station's bottom
    and top, the top (plan) outline its half-width, and the front outline (optional) how wide the
    body still is at that station's top height, so a cabin narrows and a bonnet stays wide.
    Every view is scaled to the documented `length`; stations crowd towards the nose and tail,
    where the shape changes fastest. Returns a dict with the `loft` shape and checks."""
    for name, doc in (("side", side), ("top", top), ("front", front)):
        if doc is not None:
            items = validate_items(doc)
            if items:
                raise TraceError("%s trace: %s" % (name, "; ".join("%s: %s" % (i["where"], i["message"]) for i in items)))
    if not 0.2 <= length <= 100:
        raise TraceError("length must be within 0.2..100 m")
    count = max(6, min(int(count), 60))
    sp = [(float(x), float(y)) for x, y in side["outline"]]
    xs, ys = [p[0] for p in sp], [p[1] for p in sp]
    s = length / (max(xs) - min(xs))
    H = (max(ys) - min(ys)) * s

    def side_at(z):  # z from the tail (0) to the nose (length)
        x = (max(xs) - z / s) if nose_side == "left" else (min(xs) + z / s)
        c = _crossings(sp, 0, x)
        if len(c) < 2:
            return None
        return (max(ys) - max(c)) * s, (max(ys) - min(c)) * s
    tp = [(float(x), float(y)) for x, y in top["outline"]]
    along = 1 if nose_top in ("up", "down") else 0
    lo_t, hi_t = min(p[along] for p in tp), max(p[along] for p in tp)
    st = length / (hi_t - lo_t)

    def half_at(z):
        a = (hi_t - z / st) if nose_top in ("up", "left") else (lo_t + z / st)
        c = _crossings(tp, along, a)
        return (max(c) - min(c)) / 2 * st if len(c) >= 2 else None
    front_half = None
    if front is not None:
        fp = [(float(x), float(y)) for x, y in front["outline"]]
        fy = [p[1] for p in fp]
        sf = H / (max(fy) - min(fy))

        def front_half(y):
            c = _crossings(fp, 1, max(fy) - y / sf)
            return (max(c) - min(c)) / 2 * sf if len(c) >= 2 else None
    sill = 0.1 * H if sill is None else sill
    sections, widest = [], 0.0
    for k in range(count):
        t = min(0.996, max(0.004, (1 - math.cos(math.pi * k / (count - 1))) / 2))
        z = t * length
        sv, hw = side_at(z), half_at(z)
        if sv is None or hw is None or hw <= 0:
            continue
        y0, y1 = max(sv[0], min(sill, sv[1] * 0.5)), sv[1]
        if y1 - y0 < 0.005 * H:
            continue
        if front_half is not None:
            fw = front_half(y1 * 0.97)  # how wide the body still is at this station's top
            top_w = min(hw, fw) if fw else hw * 0.9
        else:
            top_w = hw * (0.92 - 0.25 * max(0.0, (y1 - 0.6 * H) / (0.4 * H)))
        widest = max(widest, hw)
        sections.append([round(z - length / 2, 4), round(hw, 4), round(y0, 4), round(y1, 4), round(max(0.2 * hw, top_w), 4)])
    if len(sections) < 4:
        raise TraceError("the traces overlap in fewer than 4 stations: check the nose directions")
    refs = [d["reference"] for d in (side, top, front) if d is not None]
    checks = {"length": length, "height_traced": round(H, 4), "width_traced": round(2 * widest, 4)}
    if height:
        checks["height_given"], checks["height_ratio"] = height, round(H / height, 3)
    if width:
        checks["width_given"], checks["width_ratio"] = width, round(2 * widest / width, 3)
    return {
        "loft": {"type": "loft", "sections": sections, "round": rnd},
        "size_m": [round(2 * widest, 4), round(H, 4), round(length, 4)],
        "checks": checks,
        "sources": [{"id": r["id"], "kind": "reference_image", "title": r["title"],
                     "rights": r.get("rights", "reference_only"), **({"ref": r["ref"]} if r.get("ref") else {})}
                    for r in refs],
        "part": {"certainty": "inferred", "source": refs[0]["id"],
                 "note": "lofted through %d stations traced from the %s views and scaled to the %g m length"
                         % (len(sections), ", ".join(n for n, d in (("side", side), ("top", top), ("front", front)) if d),
                            length)},
    }
