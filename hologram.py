"""Deterministic compiler for tessera-hologram construction sheets.

Standard library only. No inference, no network, no file reads except the
optional asset-root hash verification and read_sheet. Sheets are declarative;
this module validates them and expands parts into line segments.
"""

import hashlib
import json
import math
import os
import re

FORMAT = "tessera-hologram"
VERSION = 1
GEOMETRY_FORMAT = "tessera-geometry"
GEOMETRY_VERSION = 1

MAX_INPUT_BYTES = 1024 * 1024
MAX_OUTPUT_BYTES = 4 * 1024 * 1024
MAX_PARTS = 128
MAX_ASSETS = 32
MAX_FACTS = 128
MAX_SEGMENTS = 20000
MAX_POLYLINE_POINTS = 256
MAX_ASSET_BYTES = 20 * 1024 * 1024

KINDS = ("cd", "book", "structure", "custom")
CERTAINTIES = ("verified", "user_supplied", "inferred", "decorative")
TONES = ("accent", "bright", "structure", "dust", "identity", "faint")
SHAPES = ("box", "disc", "ring", "polyline")
AMBIENT = ("off", "scan", "breathe")
MEDIA_TYPES = ("image/png", "image/jpeg", "image/webp")
RIGHTS = ("synthetic", "user_private", "permitted")

SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,78}[a-z0-9])?$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

SHEET_KEYS = {
    "format", "version", "id", "title", "kind", "seed", "units",
    "facts", "parts", "assets", "motion",
}
FACT_KEYS = {"key", "value", "certainty", "source"}
PART_KEYS = {
    "id", "shape", "position", "size", "rotation", "tone",
    "certainty", "stage", "points",
}
ASSET_KEYS = {"id", "path", "sha256", "media_type", "rights"}
MOTION_KEYS = {"assembly_ms", "ambient", "strength"}


class SheetError(Exception):
    """Raised for sheet-level failures that are not plain validation errors."""


# ---------------------------------------------------------------------------
# Primitive checks
# ---------------------------------------------------------------------------

def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _finite(v):
    if isinstance(v, float):
        return math.isfinite(v)
    return True


def _check_keys(obj, allowed, where, errors, optional=()):
    if not isinstance(obj, dict):
        errors.append("%s: expected object" % where)
        return False
    unknown = sorted(set(obj.keys()) - allowed)
    missing = sorted(allowed - set(obj.keys()) - set(optional))
    for k in unknown:
        errors.append("%s: unknown key %r" % (where, k))
    for k in missing:
        errors.append("%s: missing key %r" % (where, k))
    return not unknown and not missing


def _check_vec3(v, where, errors, *, positive=False, abs_max=100.0):
    if not isinstance(v, list) or len(v) != 3:
        errors.append("%s: expected array of 3 numbers" % where)
        return False
    ok = True
    for i, x in enumerate(v):
        if not _is_number(x):
            errors.append("%s[%d]: expected number" % (where, i))
            ok = False
            continue
        if not _finite(x):
            errors.append("%s[%d]: non-finite number" % (where, i))
            ok = False
            continue
        if positive:
            if x <= 0:
                errors.append("%s[%d]: must be positive" % (where, i))
                ok = False
            elif x > abs_max:
                errors.append("%s[%d]: exceeds %g" % (where, i, abs_max))
                ok = False
        else:
            if abs(x) > abs_max:
                errors.append("%s[%d]: magnitude exceeds %g" % (where, i, abs_max))
                ok = False
    return ok


def _check_rotation(v, where, errors):
    if not isinstance(v, list) or len(v) != 3:
        errors.append("%s: expected array of 3 numbers" % where)
        return False
    ok = True
    for i, x in enumerate(v):
        if not _is_number(x):
            errors.append("%s[%d]: expected number" % (where, i))
            ok = False
            continue
        if not _finite(x):
            errors.append("%s[%d]: non-finite number" % (where, i))
            ok = False
            continue
        if abs(x) > 360:
            errors.append("%s[%d]: magnitude exceeds 360" % (where, i))
            ok = False
    return ok


def _check_certainty(certainty, source, where, errors):
    if certainty not in CERTAINTIES:
        errors.append("%s: invalid certainty %r" % (where, certainty))
        return
    if certainty == "verified":
        if not isinstance(source, str) or not source.strip():
            errors.append("%s: verified certainty requires nonblank source" % where)
    else:
        if source is not None and not isinstance(source, str):
            errors.append("%s: source must be string or null" % where)


def _check_asset_path(path, where, errors):
    if not isinstance(path, str) or not path:
        errors.append("%s: path must be nonempty string" % where)
        return
    if len(path) > 512:
        errors.append("%s: path too long" % where)
        return
    if "\\" in path:
        errors.append("%s: backslash not allowed" % where)
        return
    if "%" in path:
        errors.append("%s: percent-encoding not allowed" % where)
        return
    if path.startswith("/"):
        errors.append("%s: absolute path not allowed" % where)
        return
    if re.match(r"^[A-Za-z]:", path):
        errors.append("%s: drive letter not allowed" % where)
        return
    if "://" in path or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", path):
        errors.append("%s: scheme not allowed" % where)
        return
    if "\x00" in path:
        errors.append("%s: NUL not allowed" % where)
        return
    segments = path.split("/")
    for seg in segments:
        if seg in ("", ".", ".."):
            errors.append("%s: unsafe path segment %r" % (where, seg))
            return


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(sheet):
    """Return a list of human-readable error strings (empty when valid)."""
    errors = []
    if not isinstance(sheet, dict):
        return ["sheet: expected object"]
    if not _check_keys(sheet, SHEET_KEYS, "sheet", errors):
        # Continue where possible to gather more errors.
        pass

    if sheet.get("format") != FORMAT:
        errors.append("sheet.format: must be %r" % FORMAT)
    ver = sheet.get("version")
    if not _is_int(ver) or ver != VERSION:
        errors.append("sheet.version: must be integer %d" % VERSION)

    sid = sheet.get("id")
    if not isinstance(sid, str) or not SLUG_RE.match(sid):
        errors.append("sheet.id: must be slug of 1..80 lowercase alnum/hyphen")

    title = sheet.get("title")
    if not isinstance(title, str) or not title.strip():
        errors.append("sheet.title: must be nonblank string")
    elif len(title) > 500:
        errors.append("sheet.title: exceeds 500 characters")

    if sheet.get("kind") not in KINDS:
        errors.append("sheet.kind: must be one of %s" % ", ".join(KINDS))

    seed = sheet.get("seed")
    if not _is_int(seed) or seed < 0 or seed > 2 ** 31 - 1:
        errors.append("sheet.seed: must be integer in 0..2147483647")

    if sheet.get("units") != "m":
        errors.append("sheet.units: must be 'm'")

    _validate_facts(sheet.get("facts"), errors)
    _validate_parts(sheet.get("parts"), errors)
    _validate_assets(sheet.get("assets"), errors)
    _validate_motion(sheet.get("motion"), errors)
    assets = {asset.get("id") for asset in sheet.get("assets", []) if isinstance(asset, dict) and isinstance(asset.get("id"), str)} if isinstance(sheet.get("assets"), list) else set()
    if isinstance(sheet.get("parts"), list):
        for part in sheet["parts"][:MAX_PARTS]:
            if not isinstance(part, dict): continue
            artwork = part.get("artwork_asset_id")
            if artwork is not None and (not isinstance(artwork, str) or artwork not in assets or part.get("shape") != "box"):
                errors.append("artwork_asset_id must reference a known asset on a box part")
            if part.get("shape") in ("disc", "ring") and isinstance(part.get("size"), list) and len(part["size"]) == 3:
                outer, inner, _ = part["size"]
                if _is_number(outer) and _is_number(inner) and inner >= outer:
                    errors.append("disc/ring inner radius must be less than outer radius")
    return errors


def _validate_facts(facts, errors):
    if not isinstance(facts, list):
        errors.append("sheet.facts: expected array")
        return
    if len(facts) > MAX_FACTS:
        errors.append("sheet.facts: exceeds %d entries" % MAX_FACTS)
        return
    seen = set()
    for i, fact in enumerate(facts):
        where = "sheet.facts[%d]" % i
        if not _check_keys(fact, FACT_KEYS, where, errors):
            continue
        key = fact.get("key")
        if not isinstance(key, str) or not key.strip():
            errors.append("%s.key: must be nonblank string" % where)
        elif len(key) > 200:
            errors.append("%s.key: too long" % where)
        elif key in seen:
            errors.append("%s.key: duplicate %r" % (where, key))
        else:
            seen.add(key)
        value = fact.get("value")
        if isinstance(value, bool):
            pass
        elif isinstance(value, (int, float)):
            if not _finite(value):
                errors.append("%s.value: non-finite number" % where)
        elif isinstance(value, str):
            if len(value) > 2000:
                errors.append("%s.value: too long" % where)
        elif value is not None:
            errors.append("%s.value: must be scalar" % where)
        _check_certainty(fact.get("certainty"), fact.get("source"), where, errors)


def _validate_parts(parts, errors):
    if not isinstance(parts, list):
        errors.append("sheet.parts: expected array")
        return
    if len(parts) > MAX_PARTS:
        errors.append("sheet.parts: exceeds %d entries" % MAX_PARTS)
        return
    seen = set()
    for i, part in enumerate(parts):
        where = "sheet.parts[%d]" % i
        if not isinstance(part, dict):
            errors.append("%s: expected object" % where)
            continue
        shape = part.get("shape")
        allowed = set(PART_KEYS)
        if shape != "polyline":
            allowed.discard("points")
        if not _check_keys(part, allowed | {"source", "artwork_asset_id"}, where, errors, optional={"source", "artwork_asset_id"}):
            continue
        pid = part.get("id")
        if not isinstance(pid, str) or not pid.strip():
            errors.append("%s.id: must be nonblank string" % where)
        elif len(pid) > 80:
            errors.append("%s.id: too long" % where)
        elif pid in seen:
            errors.append("%s.id: duplicate %r" % (where, pid))
        else:
            seen.add(pid)
        if shape not in SHAPES:
            errors.append("%s.shape: must be one of %s" % (where, ", ".join(SHAPES)))
        _check_vec3(part.get("position"), where + ".position", errors)
        _check_vec3(part.get("size"), where + ".size", errors, positive=True)
        _check_rotation(part.get("rotation"), where + ".rotation", errors)
        if part.get("tone") not in TONES:
            errors.append("%s.tone: invalid tone %r" % (where, part.get("tone")))
        _check_certainty(part.get("certainty"), part.get("source"), where, errors)
        stage = part.get("stage")
        if not _is_int(stage) or stage < 0 or stage > 5:
            errors.append("%s.stage: must be integer 0..5" % where)
        if shape == "polyline":
            pts = part.get("points")
            if not isinstance(pts, list):
                errors.append("%s.points: expected array" % where)
            elif len(pts) < 2 or len(pts) > MAX_POLYLINE_POINTS:
                errors.append("%s.points: must have 2..%d points" % (where, MAX_POLYLINE_POINTS))
            else:
                for j, p in enumerate(pts):
                    _check_vec3(p, "%s.points[%d]" % (where, j), errors)


def _validate_assets(assets, errors):
    if not isinstance(assets, list):
        errors.append("sheet.assets: expected array")
        return
    if len(assets) > MAX_ASSETS:
        errors.append("sheet.assets: exceeds %d entries" % MAX_ASSETS)
        return
    seen = set()
    for i, asset in enumerate(assets):
        where = "sheet.assets[%d]" % i
        if not _check_keys(asset, ASSET_KEYS, where, errors):
            continue
        aid = asset.get("id")
        if not isinstance(aid, str) or not aid.strip():
            errors.append("%s.id: must be nonblank string" % where)
        elif len(aid) > 80:
            errors.append("%s.id: too long" % where)
        elif aid in seen:
            errors.append("%s.id: duplicate %r" % (where, aid))
        else:
            seen.add(aid)
        _check_asset_path(asset.get("path"), where + ".path", errors)
        sha = asset.get("sha256")
        if not isinstance(sha, str) or not SHA256_RE.match(sha):
            errors.append("%s.sha256: must be 64 lowercase hex characters" % where)
        if asset.get("media_type") not in MEDIA_TYPES:
            errors.append("%s.media_type: invalid" % where)
        if asset.get("rights") not in RIGHTS:
            errors.append("%s.rights: invalid" % where)


def _validate_motion(motion, errors):
    where = "sheet.motion"
    if not _check_keys(motion, MOTION_KEYS, where, errors):
        return
    ms = motion.get("assembly_ms")
    if not _is_int(ms) or ms < 0 or ms > 5000:
        errors.append("%s.assembly_ms: must be integer 0..5000" % where)
    if motion.get("ambient") not in AMBIENT:
        errors.append("%s.ambient: invalid" % where)
    strength = motion.get("strength")
    if not _is_number(strength) or not _finite(strength) or strength < 0 or strength > 1:
        errors.append("%s.strength: must be number 0..1" % where)


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

def _rot_matrix(rot):
    rx, ry, rz = (math.radians(a) for a in rot)
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    # Rz * Ry * Rx
    m = [
        [cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx],
        [sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx],
        [-sy, cy * sx, cy * cx],
    ]
    return m


def _apply(m, v):
    return [
        m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
        m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
        m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2],
    ]


def _add(a, b):
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]


def _round(v):
    return [round(x, 9) + 0.0 for x in v]


def _box_edges(size):
    hx, hy, hz = size[0] / 2.0, size[1] / 2.0, size[2] / 2.0
    corners = [
        [-hx, -hy, -hz], [hx, -hy, -hz], [hx, hy, -hz], [-hx, hy, -hz],
        [-hx, -hy, hz], [hx, -hy, hz], [hx, hy, hz], [-hx, hy, hz],
    ]
    pairs = [
        (0, 1), (1, 2), (2, 3), (3, 0),
        (4, 5), (5, 6), (6, 7), (7, 4),
        (0, 4), (1, 5), (2, 6), (3, 7),
    ]
    return [(corners[a], corners[b]) for a, b in pairs]


def _circle_points(radius, segments, z=0.0):
    pts = []
    for i in range(segments):
        ang = 2.0 * math.pi * i / segments
        pts.append([radius * math.cos(ang), radius * math.sin(ang), z])
    return pts


def _loop_edges(pts):
    n = len(pts)
    return [(pts[i], pts[(i + 1) % n]) for i in range(n)]


def _disc_edges(size):
    # size = [outer_radius, inner_radius, thickness]
    outer, inner, thick = size[0], size[1], size[2]
    seg = 48
    edges = []
    z0, z1 = -thick / 2.0, thick / 2.0
    for z in (z0, z1):
        edges.extend(_loop_edges(_circle_points(outer, seg, z)))
    if inner > 0:
        for z in (z0, z1):
            edges.extend(_loop_edges(_circle_points(inner, seg, z)))
    # spindle: center axis
    edges.append(([0.0, 0.0, z0], [0.0, 0.0, z1]))
    # thickness connectors on outer rim
    for i in range(0, seg, max(1, seg // 8)):
        ang = 2.0 * math.pi * i / seg
        x, y = outer * math.cos(ang), outer * math.sin(ang)
        edges.append(([x, y, z0], [x, y, z1]))
    return edges


def _ring_edges(size):
    # Same radius convention as disc: [outer_radius, inner_radius, thickness].
    radius, inner, thick = size[0], size[1], size[2]
    seg = 48
    edges = []
    z0, z1 = -thick / 2.0, thick / 2.0
    for z in (z0, z1):
        edges.extend(_loop_edges(_circle_points(radius, seg, z)))
        edges.extend(_loop_edges(_circle_points(inner, seg, z)))
    for i in range(0, seg, max(1, seg // 8)):
        ang = 2.0 * math.pi * i / seg
        x, y = radius * math.cos(ang), radius * math.sin(ang)
        edges.append(([x, y, z0], [x, y, z1]))
    return edges


def _polyline_edges(points):
    return [(points[i], points[i + 1]) for i in range(len(points) - 1)]


def _part_edges(part):
    shape = part["shape"]
    size = part["size"]
    if shape == "box":
        return _box_edges(size)
    if shape == "disc":
        return _disc_edges(size)
    if shape == "ring":
        return _ring_edges(size)
    if shape == "polyline":
        return _polyline_edges(part["points"])
    return []


def _transform_point(p, part, m):
    # polyline points are already in part-local space; size acts as scale
    if part["shape"] == "polyline":
        scaled = [p[0] * part["size"][0], p[1] * part["size"][1], p[2] * part["size"][2]]
    else:
        scaled = p
    rotated = _apply(m, scaled)
    return _add(rotated, part["position"])


def compile_sheet(sheet):
    """Validate and compile a sheet into tessera-geometry. Raises SheetError."""
    errors = validate(sheet)
    if errors:
        raise SheetError("; ".join(errors))

    segments = []
    bounds_min = [math.inf, math.inf, math.inf]
    bounds_max = [-math.inf, -math.inf, -math.inf]

    for part in sheet["parts"]:
        m = _rot_matrix(part["rotation"])
        for a, b in _part_edges(part):
            ta = _round(_transform_point(a, part, m))
            tb = _round(_transform_point(b, part, m))
            segments.append({
                "a": ta,
                "b": tb,
                "tone": part["tone"],
                "certainty": part["certainty"],
                "stage": part["stage"],
                "part_id": part["id"],
            })
            for pt in (ta, tb):
                for k in range(3):
                    if pt[k] < bounds_min[k]:
                        bounds_min[k] = pt[k]
                    if pt[k] > bounds_max[k]:
                        bounds_max[k] = pt[k]

    if len(segments) > MAX_SEGMENTS:
        raise SheetError("compiled segment count %d exceeds %d" % (len(segments), MAX_SEGMENTS))

    if not segments:
        bounds_min = [0.0, 0.0, 0.0]
        bounds_max = [0.0, 0.0, 0.0]

    artwork_quads = []
    for part in sheet["parts"]:
        if part.get("artwork_asset_id"):
            x,y,z = part["size"]
            matrix = _rot_matrix(part["rotation"])
            corners = [[-x/2,y/2,z/2],[x/2,y/2,z/2],[x/2,-y/2,z/2],[-x/2,-y/2,z/2]]
            artwork_quads.append({"part_id":part["id"], "asset_id":part["artwork_asset_id"], "corners":[_round(_transform_point(c,part,matrix)) for c in corners], "uv":[[0,0],[1,0],[1,1],[0,1]]})
    compiled = {
        "format": GEOMETRY_FORMAT,
        "artwork_quads": artwork_quads,
        "version": GEOMETRY_VERSION,
        "id": sheet["id"],
        "title": sheet["title"],
        "kind": sheet["kind"],
        "source_sheet_sha256": hashlib.sha256(json.dumps(sheet, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest(),
        "facts": [dict(f) for f in sheet["facts"]],
        "part_sources": {part["id"]: {"certainty": part["certainty"], "source": part.get("source")} for part in sheet["parts"]},
        "segments": segments,
        "bounds": {"min": bounds_min, "max": bounds_max},
        "assets": [dict(a) for a in sheet["assets"]],
        "motion": dict(sheet["motion"]),
    }
    encoded = json.dumps(compiled, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > MAX_OUTPUT_BYTES:
        raise SheetError("compiled output exceeds %d bytes" % MAX_OUTPUT_BYTES)
    return compiled


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

def _base_sheet(kind, title, seed):
    return {
        "format": FORMAT,
        "version": VERSION,
        "id": "synthetic-%s-template" % kind,
        "title": title,
        "kind": kind,
        "seed": seed,
        "units": "m",
        "facts": [],
        "parts": [],
        "assets": [],
        "motion": {"assembly_ms": 1200, "ambient": "scan", "strength": 0.4},
    }


def _part(pid, shape, position, size, rotation, tone, stage, points=None):
    p = {
        "id": pid,
        "shape": shape,
        "position": position,
        "size": size,
        "rotation": rotation,
        "tone": tone,
        "certainty": "decorative",
        "stage": stage,
    }
    if points is not None:
        p["points"] = points
    return p


def template(kind, title=None):
    """Return a synthetic starter sheet for the given kind."""
    if kind not in KINDS:
        raise SheetError("unknown template kind %r" % (kind,))
    if title is None:
        title = "Synthetic %s template" % kind
    if not isinstance(title, str) or not title.strip() or len(title) > 500:
        raise SheetError("title must be a nonblank string of at most 500 characters")

    if kind == "cd":
        sheet = _base_sheet(kind, title, 142)
        sheet["facts"] = [{"key": "representation", "value": "Generic CD jewel case; artwork and exact edition geometry not supplied", "certainty": "decorative", "source": None}]
        sheet["parts"] = [
            _part("case", "box", [0,0,0], [.142,.125,.010], [0,0,0], "structure", 0),
            _part("inlay", "box", [.005,0,.0055], [.127,.119,.0008], [0,0,0], "bright", 1),
            _part("spine", "box", [-.065,0,0], [.010,.125,.012], [0,0,0], "identity", 1),
            _part("disc", "disc", [.004,0,.006], [.059,.0075,.0012], [0,0,0], "structure", 2),
            _part("hub", "ring", [.004,0,.007], [.012,.002,.001], [0,0,0], "accent", 3),
            _part("hinge-top", "box", [-.069,.046,.001], [.005,.014,.012], [0,0,0], "faint", 4),
            _part("hinge-bottom", "box", [-.069,-.046,.001], [.005,.014,.012], [0,0,0], "faint", 4),
        ]
        for part in sheet["parts"]:
            part["certainty"] = "inferred"
        return sheet

    if kind == "book":
        sheet = _base_sheet(kind, title, 230)
        sheet["facts"] = [
            {"key": "width_m", "value": 0.15, "certainty": "decorative", "source": None},
            {"key": "height_m", "value": 0.23, "certainty": "decorative", "source": None},
            {"key": "thickness_m", "value": 0.03, "certainty": "decorative", "source": None},
        ]
        sheet["parts"] = [
            _part("block", "box", [0.0, 0.0, 0.0], [0.15, 0.23, 0.03], [0.0, 0.0, 0.0], "structure", 0),
            _part("spine", "box", [-0.075, 0.0, 0.0], [0.004, 0.23, 0.032], [0.0, 0.0, 0.0], "accent", 1),
            _part("title-line", "polyline", [0.0, 0.06, 0.016], [1.0, 1.0, 1.0], [0.0, 0.0, 0.0], "identity", 2,
                  points=[[-0.05, 0.0, 0.0], [0.05, 0.0, 0.0]]),
        ]
        return sheet

    if kind == "structure":
        sheet = _base_sheet(kind, title, 314)
        sheet["facts"] = [
            {"key": "footprint_m", "value": 0.4, "certainty": "decorative", "source": None},
        ]
        sheet["parts"] = [
            _part("base", "box", [0.0, 0.0, 0.0], [0.4, 0.02, 0.4], [0.0, 0.0, 0.0], "structure", 0),
            _part("column-a", "box", [-0.15, 0.15, -0.15], [0.03, 0.3, 0.03], [0.0, 0.0, 0.0], "structure", 1),
            _part("column-b", "box", [0.15, 0.15, -0.15], [0.03, 0.3, 0.03], [0.0, 0.0, 0.0], "structure", 1),
            _part("column-c", "box", [-0.15, 0.15, 0.15], [0.03, 0.3, 0.03], [0.0, 0.0, 0.0], "structure", 1),
            _part("column-d", "box", [0.15, 0.15, 0.15], [0.03, 0.3, 0.03], [0.0, 0.0, 0.0], "structure", 1),
            _part("roof", "box", [0.0, 0.31, 0.0], [0.4, 0.02, 0.4], [0.0, 0.0, 0.0], "accent", 2),
            _part("axis", "polyline", [0.0, 0.0, 0.0], [1.0, 1.0, 1.0], [0.0, 0.0, 0.0], "faint", 3,
                  points=[[0.0, 0.0, 0.0], [0.0, 0.35, 0.0]]),
        ]
        return sheet

    # custom
    sheet = _base_sheet(kind, title, 7)
    sheet["parts"] = [
        _part("marker", "box", [0.0, 0.0, 0.0], [0.05, 0.05, 0.05], [0.0, 0.0, 0.0], "accent", 0),
    ]
    return sheet


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def _reject_duplicate_keys(pairs):
    seen = {}
    for k, v in pairs:
        if k in seen:
            raise SheetError("duplicate JSON key %r" % (k,))
        seen[k] = v
    return seen


def _reject_constant(name):
    raise SheetError("non-finite JSON constant %r" % (name,))


def read_sheet(path):
    """Read and parse a sheet JSON file with strict duplicate-key rejection."""
    try:
        with open(path, "rb") as fh:
            data = fh.read(MAX_INPUT_BYTES + 1)
    except OSError as exc:
        raise SheetError("cannot read sheet: %s" % exc.__class__.__name__)
    if len(data) > MAX_INPUT_BYTES:
        raise SheetError("sheet exceeds %d bytes" % MAX_INPUT_BYTES)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise SheetError("sheet is not valid UTF-8")
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except SheetError:
        raise
    except (ValueError, RecursionError) as exc:
        raise SheetError("invalid JSON: %s" % exc.__class__.__name__)


# ---------------------------------------------------------------------------
# Asset root verification
# ---------------------------------------------------------------------------

def verify_assets(sheet, asset_root):
    """Verify asset files under asset_root. Returns list of error strings."""
    errors = []
    root = os.path.realpath(asset_root)
    if not os.path.isdir(root):
        return ["asset root is not a directory"]
    for i, asset in enumerate(sheet.get("assets", [])):
        where = "sheet.assets[%d]" % i
        rel = asset.get("path")
        if not isinstance(rel, str):
            continue
        candidate = os.path.join(root, *rel.split("/"))
        real = os.path.realpath(candidate)
        if real != root and not real.startswith(root + os.sep):
            errors.append("%s: path escapes asset root" % where)
            continue
        cursor = root
        has_symlink = False
        for component in rel.split("/"):
            cursor = os.path.join(cursor, component)
            has_symlink = has_symlink or os.path.islink(cursor)
        if has_symlink:
            errors.append("%s: symlink not allowed" % where)
            continue
        if not os.path.isfile(real):
            errors.append("%s: file missing" % where)
            continue
        try:
            size = os.path.getsize(real)
        except OSError:
            errors.append("%s: cannot stat file" % where)
            continue
        if size > MAX_ASSET_BYTES:
            errors.append("%s: file exceeds %d bytes" % (where, MAX_ASSET_BYTES))
            continue
        digest = hashlib.sha256()
        try:
            with open(real, "rb") as fh:
                while True:
                    chunk = fh.read(65536)
                    if not chunk:
                        break
                    digest.update(chunk)
        except OSError:
            errors.append("%s: cannot read file" % where)
            continue
        if digest.hexdigest() != asset.get("sha256"):
            errors.append("%s: sha256 mismatch" % where)
    return errors
