"""Likeness, measured: a construct's silhouette from a named view against a traced reference.

    construct compare car.json --trace side-trace.json --view side [--fit width] [--record]

The silhouette is computed from the compiled geometry (no browser): every surface triangle and
line is projected orthographically along the view and filled into a grid. The reference is a
`construct-trace` outline (`trace.md`). Both are aligned on their bounding boxes and scaled so
the documented dimension (the width in the view by default: a car's length from the side) is
the same, then measured:

- `iou`: intersection over union of the two filled silhouettes (1 = identical);
- `edge`: the mean distance between the two outlines, as a fraction of the fitted dimension
  (0.01 = 1% of the car's length), and `edge_p95`, the 95th percentile;
- the better of the reference as traced and mirrored (a photo may face the other way).

Vehicles and landmark buildings must pass (`THRESHOLDS`) to be called recognisable exactly: an
outstanding critic verdict needs a passing comparison bound to the same scene. An overlay PNG
shows both outlines (the reference amber, the construct violet, both white).
"""

import math
from collections import deque

VIEWS = {"front": (0.0, 0.0), "side": (90.0, 0.0), "back": (180.0, 0.0), "top": (0.0, 90.0),
         "three-quarter": (38.0, 26.0)}
# (minimum IoU, maximum mean edge distance as a fraction of the fitted dimension)
THRESHOLDS = {"vehicle": (0.88, 0.012), "landmark": (0.82, 0.02), "object": (0.80, 0.025)}
GRID = 400
FILL = 0.8  # the fitted dimension spans this share of the grid


class CompareError(Exception):
    pass


def kind_of(scene):
    cat = (scene.get("subject") or {}).get("category")
    return "vehicle" if cat == "vehicle" else "landmark" if cat == "architecture" else "object"


def needs_likeness(scene):
    """Vehicles, and architecture that claims more than a generic likeness, must pass a comparison."""
    sub = scene.get("subject") or {}
    return sub.get("category") == "vehicle" or (sub.get("category") == "architecture" and sub.get("accuracy") != "generic")


def _axes(yaw, pitch):
    y, p = math.radians(yaw), math.radians(pitch)
    back = (math.sin(y) * math.cos(p), math.sin(p), math.cos(y) * math.cos(p))
    up0 = (0.0, 0.0, -1.0) if abs(pitch) > 88 else (0.0, 1.0, 0.0)
    right = (up0[1] * back[2] - up0[2] * back[1], up0[2] * back[0] - up0[0] * back[2], up0[0] * back[1] - up0[1] * back[0])
    n = math.sqrt(sum(c * c for c in right)) or 1.0
    right = tuple(c / n for c in right)
    up = (back[1] * right[2] - back[2] * right[1], back[2] * right[0] - back[0] * right[2], back[0] * right[1] - back[1] * right[0])
    return right, up


def project(geometry, yaw, pitch):
    """(triangles, segments) in view coordinates (u to the right, v up), metres."""
    right, up = _axes(yaw, pitch)

    def uv(x, y, z):
        return (x * right[0] + y * right[1] + z * right[2], x * up[0] + y * up[1] + z * up[2])
    f, fs = geometry["fills"], geometry["fill_stride"]
    verts = [uv(f[i], f[i + 1], f[i + 2]) for i in range(0, len(f), fs)]
    tris = [verts[i:i + 3] for i in range(0, len(verts) - 2, 3)]
    ln, ls = geometry["lines"], geometry["line_stride"]
    segs = [(uv(ln[i], ln[i + 1], ln[i + 2]), uv(ln[i + 3], ln[i + 4], ln[i + 5])) for i in range(0, len(ln), ls)]
    return tris, segs


def _frame(points, fit, fit_px=None):
    """A mapping to grid pixels (y down) that centres the shape and scales its fitted dimension
    to `fit_px` (by default: so the longer side fills FILL of the grid); returns (map, fit_px)."""
    us, vs = [p[0] for p in points], [p[1] for p in points]
    w, h = max(us) - min(us), max(vs) - min(vs)
    length = w if fit == "width" else h
    if length <= 0:
        raise CompareError("the silhouette has no %s in this view" % fit)
    if fit_px is None:
        fit_px = FILL * GRID * length / max(w, h)
    s = fit_px / length
    cu, cv = (max(us) + min(us)) / 2, (max(vs) + min(vs)) / 2
    return (lambda u, v: ((u - cu) * s + GRID / 2, GRID / 2 - (v - cv) * s)), fit_px


def _fill_triangle(mask, a, b, c):
    xs, ys = (a[0], b[0], c[0]), (a[1], b[1], c[1])
    x0, x1 = max(0, int(min(xs))), min(GRID - 1, int(max(xs)) + 1)
    y0, y1 = max(0, int(min(ys))), min(GRID - 1, int(max(ys)) + 1)
    d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    if abs(d) < 1e-12:
        return
    for y in range(y0, y1 + 1):
        py = y + 0.5
        row = mask[y]
        for x in range(x0, x1 + 1):
            px = x + 0.5
            l1 = ((b[1] - c[1]) * (px - c[0]) + (c[0] - b[0]) * (py - c[1])) / d
            l2 = ((c[1] - a[1]) * (px - c[0]) + (a[0] - c[0]) * (py - c[1])) / d
            if l1 >= -1e-9 and l2 >= -1e-9 and l1 + l2 <= 1 + 1e-9:
                row[x] = 1


def _stroke(mask, a, b):
    n = int(max(abs(b[0] - a[0]), abs(b[1] - a[1]))) + 1
    for k in range(n + 1):
        t = k / n
        x, y = int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t)
        if 0 <= x < GRID and 0 <= y < GRID:
            mask[y][x] = 1


def silhouette(geometry, yaw, pitch, fit="width", fit_px=None):
    tris, segs = project(geometry, yaw, pitch)
    pts = [p for t in tris for p in t] + [p for s in segs for p in s]
    if not pts:
        raise CompareError("the construct draws nothing")
    to, _ = _frame(pts, fit, fit_px)
    mask = [[0] * GRID for _ in range(GRID)]
    for t in tris:
        _fill_triangle(mask, *(to(*p) for p in t))
    for a, b in segs:
        _stroke(mask, to(*a), to(*b))
    return mask


def reference_mask(outline, fit="width", mirror=""):
    """A traced outline (pixels, y down) filled into the grid, mirrored across "x", "y" or both
    when asked; returns (mask, fitted pixels)."""
    pts = [(-x if "x" in mirror else x, y if "y" in mirror else -y) for x, y in outline]
    to, fit_px = _frame(pts, fit)
    poly = [to(*p) for p in pts]
    mask = [[0] * GRID for _ in range(GRID)]
    n = len(poly)
    for y in range(GRID):
        py = y + 0.5
        xs = []
        for i in range(n):
            (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
            if (y1 <= py) != (y2 <= py):
                xs.append(x1 + (py - y1) * (x2 - x1) / (y2 - y1))
        xs.sort()
        for a, b in zip(xs[0::2], xs[1::2]):
            for x in range(max(0, int(math.ceil(a - 0.5))), min(GRID, int(math.floor(b - 0.5)) + 1)):
                mask[y][x] = 1
    return mask, fit_px


def _boundary(mask):
    out = []
    for y in range(GRID):
        row = mask[y]
        for x in range(GRID):
            if row[x] and (x == 0 or y == 0 or x == GRID - 1 or y == GRID - 1 or not row[x - 1] or not row[x + 1]
                           or not mask[y - 1][x] or not mask[y + 1][x]):
                out.append((x, y))
    return out


def _distance_to(points):
    """Distance in pixels from every cell to the nearest of `points` (8-connected BFS, near-Euclidean)."""
    inf = float("inf")
    dist = [[inf] * GRID for _ in range(GRID)]
    near = [[None] * GRID for _ in range(GRID)]
    q = deque()
    for x, y in points:
        dist[y][x], near[y][x] = 0.0, (x, y)
        q.append((x, y))
    while q:
        x, y = q.popleft()
        sx, sy = near[y][x]
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nx, ny = x + dx, y + dy
                if (dx or dy) and 0 <= nx < GRID and 0 <= ny < GRID:
                    d = math.hypot(nx - sx, ny - sy)
                    if d < dist[ny][nx]:
                        dist[ny][nx], near[ny][nx] = d, (sx, sy)
                        q.append((nx, ny))
    return dist


def measure(a, b, fit_px=FILL * GRID):
    """(iou, mean edge distance and p95 as a fraction of the fitted dimension) of two masks."""
    inter = union = 0
    for ra, rb in zip(a, b):
        for x, y in zip(ra, rb):
            inter += x & y
            union += x | y
    ba, bb = _boundary(a), _boundary(b)
    if not ba or not bb:
        raise CompareError("an empty silhouette")
    da, db = _distance_to(ba), _distance_to(bb)
    ds = sorted([db[y][x] for x, y in ba] + [da[y][x] for x, y in bb])
    scale = fit_px
    return (inter / union if union else 0.0, sum(ds) / len(ds) / scale, ds[int(0.95 * (len(ds) - 1))] / scale)


def overlay(construct, reference):
    from . import png
    return png.encode(GRID, GRID, lambda x, y: (
        (245, 245, 255) if construct[y][x] and reference[y][x] else (150, 95, 255) if construct[y][x]
        else (255, 176, 64) if reference[y][x] else (12, 8, 18)))


def compare(scene, trace_doc, view="side", fit="width", yaw=None, pitch=None):
    """Measure a scene (or parameter document) against a traced reference; returns a result dict
    and the overlay PNG bytes."""
    from . import params, tiers, trace
    from . import scene as scene_mod
    items = trace.validate_items(trace_doc)
    if items:
        raise CompareError("not a valid trace: " + "; ".join("%s: %s" % (i["where"], i["message"]) for i in items))
    full = params.expand({k: v for k, v in scene.items() if k != "authoring"}) if params.is_params(scene) else scene
    geometry = scene_mod.compile_scene(full)
    if yaw is None or pitch is None:
        if view in VIEWS:
            yaw, pitch = VIEWS[view]
        else:
            v = next((x for x in (geometry["presentation"].get("views") or []) if x.get("id") == view), None)
            if v is None:
                raise CompareError("unknown view %r: front, side, back, top, three-quarter or one of the scene's views" % view)
            yaw, pitch = v["yaw"], v["pitch"]
    best = None
    # a photo may face either way, and a plan may have its nose up or down
    for mirror in (("", "x", "y", "xy") if view == "top" or pitch > 60 else ("", "x")):
        ref, fit_px = reference_mask([tuple(p) for p in trace_doc["outline"]], fit, mirror)
        mine = silhouette(geometry, yaw, pitch, fit, fit_px)
        iou, edge, p95 = measure(mine, ref, fit_px)
        if best is None or iou > best[0]:
            best = (iou, edge, p95, mirror, ref, mine)
    iou, edge, p95, mirror, ref, mine = best
    kind = kind_of(full)
    lo_iou, hi_edge = THRESHOLDS[kind]
    result = {"view": view, "yaw": yaw, "pitch": pitch, "fit": fit, "reference": trace_doc["reference"]["id"],
              "iou": round(iou, 4), "edge": round(edge, 4), "edge_p95": round(p95, 4), "mirrored": mirror or None,
              "kind": kind, "threshold": {"iou": lo_iou, "edge": hi_edge},
              "pass": iou >= lo_iou and edge <= hi_edge, "scene_sha256": tiers.critic_hash(scene)}
    return result, overlay(mine, ref)


def record(scene, result, trace_doc):
    """The comparison in the scene's authoring block (and its reference among the sources)."""
    import json
    from . import tiers
    scene = json.loads(json.dumps(scene))
    ref = trace_doc["reference"]
    if not any(s.get("id") == ref["id"] for s in scene.get("sources", [])):
        scene.setdefault("sources", []).append({"id": ref["id"], "kind": "reference_image", "title": ref["title"],
                                                "rights": ref.get("rights", "reference_only"),
                                                **({"ref": ref["ref"]} if ref.get("ref") else {})})
    a = scene.get("authoring") or {"tier": tiers.DEFAULT, "research": "done", "sources": [ref["id"]]}
    keep = [c for c in a.get("compare", []) if not (c["view"] == result["view"] and c["reference"] == result["reference"])]
    entry = {k: result[k] for k in ("view", "reference", "iou", "edge", "pass")}
    # citing the reference adds a source, not geometry: the comparison holds for the cited scene
    entry["scene_sha256"] = tiers.critic_hash({k: v for k, v in scene.items() if k != "authoring"})
    keep.append(entry)
    a["compare"] = keep[-8:]
    if a.get("research") == "done" and ref["id"] not in a.get("sources", []):
        a.setdefault("sources", []).append(ref["id"])
    scene["authoring"] = a
    return scene
