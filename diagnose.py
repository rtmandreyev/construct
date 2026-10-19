"""Machine-readable diagnostics for a scene draft.

Every problem comes back as {severity, code, path, message, hint}: `path` is a JSON path into
the draft ($.parts[3].shape.size), `hint` says what to write instead. A model of any size
can repair its own draft from this list; `repair_text` is the list as a message to send back
to it. Covers the JSON text itself (fences, comments, trailing commas, duplicate keys),
validation, budgets and the audit (support, assembly order, overclaims, accuracy).

    from hologram import diagnose
    report = diagnose.diagnose_text(open("draft.json").read())
    if not report["ok"]: send(report["repair_text"])
"""

import json
import re

from . import audit as audit_mod
from . import params as params_mod
from . import scene as scene_mod

AUDIT_HINTS = {
    "floating": "Move the part so its box touches what holds it (a centred box sits half its height above "
                "its \"at\"; use \"anchor\": \"base\" to stand it on \"at\"), or set \"floating\": true only if it truly hovers.",
    "stage-order": "Give the part a stage equal to or later than the part it rests on.",
    "overclaim": "Lower the part's certainty to the weakest certainty among its basis facts, or cite a source.",
    "accuracy": "Use subject.accuracy \"generic\" (a typical example) unless key parts rest on evidence.",
    "decorative-identity": "Designed parts of a requested object are \"inferred\", not \"decorative\".",
    "no-mass": "Give the primary volume role \"mass\".",
    "no-identity": "Give the two or three recognisable features role \"identity\".",
    "clutter": "Fewer detail parts, or lower segments/ribs/repeat counts.",
    "duplicates": "Remove the duplicated part, or move it to where it belongs.",
    "tiny": "Make it larger, merge it into a neighbour or delete it; it will not read at this size.",
    "invisible": "Give it lines (look.line \"auto\") or a fill, or delete it.",
}
BUDGET_HINT = ("Simplify: lower segments, meridians, ribs, rings, lat/lon and repeat counts, or set "
               "look.fill \"none\" on thin parts.")


def _path(where):
    """`scene.parts[3].shape` -> `$.parts[3].shape`."""
    if where == "scene":
        return "$"
    return "$" + where[len("scene"):] if where.startswith("scene") else "$." + where


def _diag(severity, code, path, message, hint=None):
    return {"severity": severity, "code": code, "path": path, "message": message, "hint": hint}


def parse_text(text):
    """(scene or None, diagnostics) for a draft's raw text."""
    diags = []
    stripped = text.strip()
    if stripped.startswith("```"):
        diags.append(_diag("error", "json", "$", "the draft is wrapped in a ``` code fence",
                           "Send only the JSON object: no ``` fences and no prose before or after it."))
        stripped = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", stripped)
    dupes = []

    def pairs(items):
        seen = {}
        for k, v in items:
            if k in seen:
                dupes.append(k)
            seen[k] = v
        return seen
    try:
        obj = json.loads(stripped, object_pairs_hook=pairs)
    except json.JSONDecodeError as exc:
        line = stripped.splitlines()[exc.lineno - 1] if 0 < exc.lineno <= len(stripped.splitlines()) else ""
        hint = "Write strict JSON: double-quoted keys and strings, no comments, no trailing commas, no NaN."
        if "//" in line or "/*" in line:
            hint = "Remove the comment: JSON has no comments. Put explanations in a \"note\" field."
        elif re.search(r",\s*[}\]]", stripped[max(0, exc.pos - 3):exc.pos + 2]):
            hint = "Remove the trailing comma before the closing bracket."
        diags.append(_diag("error", "json", "$", "not valid JSON at line %d column %d: %s" % (exc.lineno, exc.colno, exc.msg), hint))
        return None, diags
    for k in sorted(set(dupes)):
        diags.append(_diag("error", "duplicate-key", "$", "the key %r appears twice in one object" % k,
                           "Keep one %r per object; merge the two." % k))
    if not isinstance(obj, dict):
        diags.append(_diag("error", "type", "$", "the draft must be one JSON object", "Send a single {...} scene."))
        return None, diags
    return obj, diags


def diagnose(scene, prior=()):
    """The report for a parsed draft."""
    diags = list(prior)
    items = scene_mod.validate_items(scene)
    for item in items:
        diags.append(_diag("error", item["code"], _path(item["where"]), item["message"], item["hint"]))
    geometry = None
    if not items:  # text-level problems (a fence) do not stop the rest of the check
        try:
            geometry = scene_mod.compile_scene(scene)
        except scene_mod.SceneError as exc:
            diags.append(_diag("error", "budget", "$.parts", str(exc), BUDGET_HINT))
    report = None
    if geometry is not None:
        report = audit_mod.audit(scene, geometry)
        index = {p.get("id"): i for i, p in enumerate(scene.get("parts", []))}
        for sev, rows in (("error", report["errors"]), ("warning", report["warnings"])):
            for r in rows:
                path = "$.parts[%d]" % index[r["part"]] if r.get("part") in index else "$"
                diags.append(_diag(sev, r["code"], path, (("%s: " % r["part"]) if r.get("part") else "") + r["message"],
                                   AUDIT_HINTS.get(r["code"])))
    errors = [d for d in diags if d["severity"] == "error"]
    out = {
        "ok": not errors,
        "contract": "tessera.hologram/0.2",
        "errors": len(errors),
        "warnings": len(diags) - len(errors),
        "diagnostics": diags,
        "stats": dict(geometry["counts"], size_m=[round(geometry["bounds"]["max"][k] - geometry["bounds"]["min"][k], 4)
                                                for k in range(3)]) if geometry else None,
    }
    out["repair_text"] = repair_text(out)
    return out


def diagnose_text(text):
    scene, diags = parse_text(text)
    if isinstance(scene, dict) and scene.get("format") == params_mod.FORMAT:
        return diagnose_params(scene, diags)
    if scene is None:
        out = {"ok": False, "contract": "tessera.hologram/0.2", "errors": len(diags), "warnings": 0,
               "diagnostics": diags, "stats": None}
        out["repair_text"] = repair_text(out)
        return out
    return diagnose(scene, diags)


def repair_text(report, limit=40):
    """The diagnostics as a short message for the model that wrote the draft."""
    if report["ok"] and not report["warnings"]:
        return "The scene is valid and the audit is clean."
    errs = [d for d in report["diagnostics"] if d["severity"] == "error"]
    warns = [d for d in report["diagnostics"] if d["severity"] == "warning"]
    lines = []
    if errs:
        lines.append("Your scene has %d problem%s. Fix every one and send the whole corrected JSON object "
                     "(no prose, no code fences):" % (len(errs), "" if len(errs) == 1 else "s"))
        for d in errs[:limit]:
            lines.append("- %s [%s] %s%s" % (d["path"], d["code"], d["message"], " -> " + d["hint"] if d["hint"] else ""))
        if len(errs) > limit:
            lines.append("- ... and %d more of the same kinds" % (len(errs) - limit))
    if warns:
        lines.append("Warnings (fix them if you can; otherwise explain them when you deliver):")
        for d in warns[:12]:
            lines.append("- %s [%s] %s%s" % (d["path"], d["code"], d["message"], " -> " + d["hint"] if d["hint"] else ""))
    return "\n".join(lines)


def diagnose_params(doc, prior=()):
    """The report for a parameter document: its own problems, then the generated scene's."""
    diags = list(prior)
    for item in params_mod.validate_items(doc):
        diags.append(_diag("error", item["code"], _path(item["where"]), item["message"], item["hint"]))
    if any(d["severity"] == "error" and d["code"] != "json" for d in diags):
        out = {"ok": False, "contract": "tessera.hologram/0.2", "errors": len(diags), "warnings": 0,
               "diagnostics": diags, "stats": None}
        out["repair_text"] = repair_text(out)
        return out
    # facts, sources and assets keep their paths: the builder copies them first, in order
    return diagnose(params_mod.expand(doc), diags)
