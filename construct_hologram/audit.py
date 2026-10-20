"""The geometric and provenance audit of a compiled construct.

Validation proves a scene is well-formed; the audit asks whether the object stands up
and tells the truth. Errors must be zero before visual review. Warnings are judgment
calls the author resolves or explains. Bounding boxes keep it conservative: contact
between two boxes is necessary for contact between their parts, so the audit never
reports a part as floating when it really touches something.
"""

import math

from . import scene as scene_mod


def _touch(a, b, tol):
    return all(a["min"][k] <= b["max"][k] + tol and b["min"][k] <= a["max"][k] + tol for k in range(3))


def audit(scene, geometry):
    errors, warnings, info = [], [], {}

    def add(target, code, part, message):
        target.append({"code": code, "part": part, "message": message})

    parts = geometry["parts"]
    radius = max(geometry["bounds"]["radius"], 1e-6)
    tol = max(0.001, 0.004 * radius)
    by_id = {p["id"]: p for p in parts}
    scene_parts = {p["id"]: p for p in scene["parts"]}
    source_kind = {s["id"]: s["kind"] for s in scene.get("sources", [])}
    facts_by_key = {f["key"]: f for f in scene.get("facts", [])}

    # ---- support: every part rests on the ground or on something that does
    # the ground and every declared-floating part are anchors: what touches them, transitively,
    # is held up (a creature's tentacles hang from its floating bell)
    inst = [(p["id"], i, b) for p in parts for i, b in enumerate(p["instances"])]
    solid = [x for x in inst if not by_id[x[0]]["floating"]]
    ground = min((b["min"][1] for _, _, b in solid), default=0.0)
    supported = {(pid, i) for pid, i, b in solid if b["min"][1] <= ground + tol}
    supported |= {(pid, i) for pid, i, b in inst if by_id[pid]["floating"]}
    solid = inst
    frontier = list(supported)
    while frontier:
        pid, i = frontier.pop()
        box = by_id[pid]["instances"][i]
        for qid, j, other in solid:
            if (qid, j) not in supported and _touch(box, other, tol):
                supported.add((qid, j))
                frontier.append((qid, j))
    for p in parts:
        if p["floating"]:
            continue
        loose = [i for i in range(len(p["instances"])) if (p["id"], i) not in supported]
        if loose:
            add(errors, "floating", p["id"],
                "%d of %d copies touch nothing that reaches the ground. Move them onto their support, "
                "or declare \"floating\": true if they truly hover (a halo, a beam, particles)."
                % (len(loose), len(p["instances"])))

    # ---- assembly order: nothing should appear before what holds it up
    for p in parts:
        if p["floating"]:
            continue
        for i, b in enumerate(p["instances"]):
            if b["min"][1] <= ground + tol:
                continue
            holders = [by_id[q] for q, j, o in solid if q != p["id"] and _touch(b, o, tol)]
            if holders and all(h["stage"] > p["stage"] for h in holders):
                add(warnings, "stage-order", p["id"],
                    "appears (stage %d) before everything it rests on (stages %s): it will float during assembly."
                    % (p["stage"], ", ".join(sorted({str(h["stage"]) for h in holders}))))
                break

    # ---- provenance: a part never claims more than its evidence
    facts = {f["key"]: f for f in scene["facts"]}
    rank = {"verified": 3, "user_supplied": 2, "inferred": 1, "decorative": 0}
    for p in parts:
        basis = [facts[k] for k in p["basis"]]
        if basis and p["certainty"] in ("verified", "user_supplied"):
            best = max(rank[f["certainty"]] for f in basis)
            if best < rank[p["certainty"]] and not p["source"]:
                add(errors, "overclaim", p["id"],
                    "is %s but its basis facts are at most %s and it cites no source."
                    % (p["certainty"], [k for k, v in rank.items() if v == best][0]))
        sp = scene_parts[p["id"]]
        if sp["certainty"] == "verified" and _freeform_points(sp["shape"]) >= 6:
            kinds = {source_kind.get(sp.get("source"))} | {source_kind.get(facts_by_key.get(b, {}).get("source"))
                                                           for b in sp.get("basis", [])}
            if not kinds & set(scene_mod.SHAPE_EVIDENCE):
                add(warnings, "shape-overclaim", p["id"],
                    "is verified, but no cited source gives its shape (a spec page verifies dimensions, not an "
                    "outline or profile).")
        if p["role"] in ("mass", "identity") and p["certainty"] == "decorative" and scene["subject"]["category"] != "fictional":
            add(warnings, "decorative-identity", p["id"],
                "a %s part is decorative: say so when delivering, it is not evidence." % p["role"])
    accuracy = scene["subject"]["accuracy"]
    key_parts = [p for p in parts if p["role"] in ("mass", "identity")]
    backed = [p for p in key_parts if p["certainty"] in ("verified", "user_supplied")]
    info["evidence_backed_key_parts"] = "%d of %d" % (len(backed), len(key_parts))
    if accuracy == "documented" and key_parts and len(backed) < len(key_parts) / 2:
        add(errors, "accuracy", None,
            "subject.accuracy is \"documented\" but most mass/identity parts are inferred or decorative: "
            "use \"approximate\" or \"generic\", or cite the evidence.")
    if accuracy == "generic" and any(p["certainty"] == "verified" for p in parts):
        add(warnings, "accuracy", None, "verified parts in a generic reconstruction: consider \"approximate\".")

    # ---- recognition: hierarchy and identity
    roles = {p["role"] for p in parts}
    if "mass" not in roles:
        add(warnings, "no-mass", None, "no part has role \"mass\": the silhouette has no primary volume.")
    if "identity" not in roles and scene["subject"]["category"] not in ("cd", "book", "artwork-carrier"):
        add(warnings, "no-identity", None,
            "no part has role \"identity\": which two or three features make this recognisably itself?")
    if geometry.get("articulations") and not any(v.get("id") == "open" for v in geometry["presentation"]["views"]):
        add(warnings, "no-open-view", None,
            "it opens but has no view named \"open\": from the hero the opened pose may look closed.")
    styles = geometry["styles"]
    stride = geometry["line_stride"]
    lines = geometry["lines"]
    n = len(lines) // stride
    quiet = sum(1 for i in range(n) if parts[int(styles[int(lines[i * stride + 6])][6])]["role"] in ("detail", "ornament"))
    if n and quiet / n > 0.55:
        add(warnings, "clutter", None,
            "%.0f%% of lines are detail or ornament: the primary structure may drown. Reduce rings/ribs or repeats."
            % (100.0 * quiet / n))
    seen, dup = set(), 0
    for i in range(n):
        a = tuple(lines[i * stride:i * stride + 3])
        b = tuple(lines[i * stride + 3:i * stride + 6])
        key = (a, b) if a <= b else (b, a)
        if key in seen:
            dup += 1
        seen.add(key)
    if n and dup / n > 0.02:
        add(warnings, "duplicates", None,
            "%d duplicate segments (%.1f%%): repeats or mirrors overlap themselves." % (dup, 100.0 * dup / n))
    for p in parts:
        b = p["instances"][0]
        diag = math.sqrt(sum((b["max"][k] - b["min"][k]) ** 2 for k in range(3)))
        if diag < 0.015 * 2 * radius and p["shape"] not in ("marker", "points"):
            add(warnings, "tiny", p["id"],
                "is %.1f%% of the object's size: it may vanish at the hero framing." % (100.0 * diag / (2 * radius)))
        carriers = {x["part"] for x in geometry.get("labels", []) + geometry.get("artwork", [])}
        carriers |= {a["part"] for a in geometry.get("anchors", {}).values() if isinstance(a, dict) and a.get("part")}
        if p["id"] not in carriers and not any(int(styles[s][6]) == parts.index(p) for s in range(len(styles))):
            add(warnings, "invisible", p["id"], "produces nothing to draw (line \"none\" and no fill).")

    _contact_and_thickness(scene, geometry, add, warnings)

    lo, hi = geometry["bounds"]["min"], geometry["bounds"]["max"]
    dims = [round(hi[k] - lo[k], 4) for k in range(3)]
    info.update({"dimensions_m": {"width": dims[0], "height": dims[1], "depth": dims[2]},
                 "counts": geometry["counts"], "parts": len(parts),
                 "stages": [s["stage"] for s in geometry["stages"]]})
    return {"ok": not errors, "errors": errors, "warnings": warnings, "info": info}


def format_report(report):
    out = ["audit: %s (%d errors, %d warnings)" % ("PASS" if report["ok"] else "FAIL",
                                                  len(report["errors"]), len(report["warnings"]))]
    for label, items in (("ERROR", report["errors"]), ("warn", report["warnings"])):
        for it in items:
            out.append("  %s [%s]%s %s" % (label, it["code"], " " + it["part"] if it["part"] else "", it["message"]))
    i = report["info"]
    out.append("  size %(width)g x %(height)g x %(depth)g m" % i["dimensions_m"])
    out.append("  %(lines)d lines, %(triangles)d triangles, %(points)d points, %(motions)d moving copies" % i["counts"])
    out.append("  evidence-backed key parts: %s" % i["evidence_backed_key_parts"])
    return "\n".join(out)


# ---------------------------------------------------------------------------- real contact and thickness
#
# The support check above works on bounding boxes, which is safe but blind to a part that only
# appears to touch: the box of a diagonal arm covers the whole lamp, so a shade floating off its
# end still "touches" it. These two checks look at the actual surfaces and segments, rebuilt
# from the scene in rest pose.

THIN = 0.006      # a structural part thinner than this share of the object's largest size is a hairline
GAP = 0.01        # parts further apart than this share of the object's largest size do not touch


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _seg_dist2(p, a, b):
    ab, ap = _sub(b, a), _sub(p, a)
    d = _dot(ab, ab)
    t = 0.0 if d <= 1e-18 else max(0.0, min(1.0, _dot(ap, ab) / d))
    q = (a[0] + ab[0] * t - p[0], a[1] + ab[1] * t - p[1], a[2] + ab[2] * t - p[2])
    return _dot(q, q)


def _tri_dist2(p, a, b, c):
    """Squared distance from p to triangle abc (closest point by region)."""
    ab, ac, ap = _sub(b, a), _sub(c, a), _sub(p, a)
    d1, d2 = _dot(ab, ap), _dot(ac, ap)
    if d1 <= 0 and d2 <= 0:
        return _dot(ap, ap)
    bp = _sub(p, b)
    d3, d4 = _dot(ab, bp), _dot(ac, bp)
    if d3 >= 0 and d4 <= d3:
        return _dot(bp, bp)
    cp = _sub(p, c)
    d5, d6 = _dot(ab, cp), _dot(ac, cp)
    if d6 >= 0 and d5 <= d6:
        return _dot(cp, cp)
    vc, vb, va = d1 * d4 - d3 * d2, d5 * d2 - d1 * d6, d3 * d6 - d5 * d4
    if vc <= 0 and d1 >= 0 and d3 <= 0:
        return _seg_dist2(p, a, b)
    if vb <= 0 and d2 >= 0 and d6 <= 0:
        return _seg_dist2(p, a, c)
    if va <= 0 and (d4 - d3) >= 0 and (d5 - d6) >= 0:
        return _seg_dist2(p, b, c)
    den = 1.0 / (va + vb + vc)
    v, w = vb * den, vc * den
    q = (a[0] + ab[0] * v + ac[0] * w - p[0], a[1] + ab[1] * v + ac[1] * w - p[1], a[2] + ab[2] * v + ac[2] * w - p[2])
    return _dot(q, q)


def _part_geometry(scene):
    """Per part id: (samples, primitives) in world space, rest pose; primitives are segments
    (2 points) and triangles (3 points). Sprites (points, markers) are left out."""
    out = {}
    for part in scene["parts"]:
        if part["shape"]["type"] in ("points", "marker"):
            continue
        mesh = scene_mod._local_mesh(part["shape"], scene_mod._hash_part(scene["seed"], part["id"]))
        samples, prims = [], []
        for xf, _, _, _ in scene_mod._instances(part):
            for a, b, _ in mesh.lines:
                a, b = xf(a), xf(b)
                prims.append((a, b))
                samples += [a, b, tuple((a[k] + b[k]) / 2 for k in range(3))]
            for a, b, c in mesh.tris:
                a, b, c = xf(a), xf(b), xf(c)
                prims.append((a, b, c))
                samples += [a, b, c, tuple((a[k] + b[k] + c[k]) / 3 for k in range(3))]
        out[part["id"]] = (samples, prims)
    return out


def _contact_and_thickness(scene, geometry, add, warnings):
    lo, hi = geometry["bounds"]["min"], geometry["bounds"]["max"]
    size = max(hi[k] - lo[k] for k in range(3)) or 1e-6
    gap = max(0.0015, GAP * size)
    parts = {p["id"]: p for p in scene["parts"]}

    # ---- thickness: a mass or structure part that is a hairline barely renders
    for p in scene["parts"]:
        if p["role"] not in ("mass", "structure") or p.get("floating"):
            continue
        thin = _thickness(p)
        if thin is None or thin >= THIN * size:
            continue
        need = THIN * size
        what = {"tube": "radius %.4g m" % (need / 2), "cylinder": "radius %.4g m" % (need / 2),
                "cone": "radii of %.4g m" % (need / 2), "torus": "minor radius %.4g m" % (need / 2),
                "box": "%.4g m on its two thin sides" % need,
                "curve": "a tube of radius %.4g m (a curve has no thickness)" % (need / 2)}.get(p["shape"]["type"], "%.4g m across" % need)
        add(warnings, "thin", p["id"],
            "is %s thick, a hairline next to the object's %.3g m: it will barely render. Use at least %s, "
            "or give it role \"detail\" if it is meant to be fine." % ("%.4g m" % thin if thin else "zero", size, what))

    # ---- contact: a part whose real geometry comes near no other part's (and not the ground)
    geo = _part_geometry(scene)
    cell = max(gap * 4, size / 48)
    grid = {}
    for pid, (_, prims) in geo.items():
        for idx, pr in enumerate(prims):
            lo_c = [int(math.floor((min(v[k] for v in pr) - gap) / cell)) for k in range(3)]
            hi_c = [int(math.floor((max(v[k] for v in pr) + gap) / cell)) for k in range(3)]
            if (hi_c[0] - lo_c[0] + 1) * (hi_c[1] - lo_c[1] + 1) * (hi_c[2] - lo_c[2] + 1) > 4096:
                continue  # an enormous triangle: its vertices are samples of their own
            for x in range(lo_c[0], hi_c[0] + 1):
                for y in range(lo_c[1], hi_c[1] + 1):
                    for z in range(lo_c[2], hi_c[2] + 1):
                        grid.setdefault((x, y, z), []).append((pid, idx))
    gap2 = gap * gap
    ground = lo[1]

    def touches(pid):
        samples, _ = geo[pid]
        for sp in samples:
            if sp[1] <= ground + gap:
                return True
            for qid, idx in grid.get(tuple(int(math.floor(sp[k] / cell)) for k in range(3)), ()):
                if qid == pid:
                    continue
                pr = geo[qid][1][idx]
                d = _seg_dist2(sp, *pr) if len(pr) == 2 else _tri_dist2(sp, *pr)
                if d <= gap2:
                    return True
        return False

    connected = {pid for pid in geo if touches(pid)}
    # touching is mutual: a part another part touches is connected too
    for pid in list(geo):
        if pid not in connected and any(_near(geo[q][0], pid, geo, grid, cell, gap2) for q in connected if q != pid):
            connected.add(pid)
    for pid in geo:
        p = parts[pid]
        if pid in connected or p.get("floating") or p["role"] in ("ornament", "ground") or len(geo) < 2:
            continue
        near, dist = _nearest(pid, geo)
        add(warnings, "detached", pid,
            "touches no other part: its nearest is %r, %.3g m away (the object is %.3g m). Move it onto %r, "
            "or set \"floating\": true if it truly hovers." % (near, dist, size, near))


def _near(samples, target, geo, grid, cell, gap2):
    for sp in samples:
        for qid, idx in grid.get(tuple(int(math.floor(sp[k] / cell)) for k in range(3)), ()):
            if qid != target:
                continue
            pr = geo[qid][1][idx]
            if (_seg_dist2(sp, *pr) if len(pr) == 2 else _tri_dist2(sp, *pr)) <= gap2:
                return True
    return False


def _nearest(pid, geo):
    mine = geo[pid][0][::max(1, len(geo[pid][0]) // 400)]
    best, best_d = None, math.inf
    for qid, (samples, _) in geo.items():
        if qid == pid:
            continue
        theirs = samples[::max(1, len(samples) // 400)]
        d = min((_dot(_sub(a, b), _sub(a, b)) for a in mine for b in theirs), default=math.inf)
        if d < best_d:
            best, best_d = qid, d
    return best, math.sqrt(best_d)


def _freeform_points(shape):
    """How many authored points shape a free-form part (0 for primitives)."""
    for k in ("profile", "path", "points"):
        if isinstance(shape.get(k), list):
            return len(shape[k])
    return 0


def _thickness(p):
    return scene_mod.cross_section(p)
