"""The geometric and provenance audit of a compiled hologram.

Validation proves a scene is well-formed; the audit asks whether the object stands up
and tells the truth. Errors must be zero before visual review. Warnings are judgment
calls the author resolves or explains. Bounding boxes keep it conservative: contact
between two boxes is necessary for contact between their parts, so the audit never
reports a part as floating when it really touches something.
"""

import math


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
        if not any(int(styles[s][6]) == parts.index(p) for s in range(len(styles))):
            add(warnings, "invisible", p["id"], "produces nothing to draw (line \"none\" and no fill).")

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
