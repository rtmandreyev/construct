"""The independent critic: fresh eyes on a construct, beside the real thing.

An author grading its own work is lenient (seen in live runs: two unfinished castles graded
"good"). The critic is someone else, a subagent, a delegated task or a second model call with a
fresh context, that sees only the request, the identity checklist, the reference photos and
renders taken from the matching views, and answers a `construct-critique`:

    {"format": "construct-critique", "version": 1, "scene_sha256": "<from the packet>",
     "scores": {"silhouette": 2, ...every criterion 0..3},
     "checklist": [{"feature": "periscope roof channel", "present": true, "quality": 2, "comment": "..."}],
     "defects": [{"rank": 1, "severity": "critical", "criterion": "proportions", "parts": ["body"],
                  "view": "side", "problem": "...", "fix": "..."}],
     "verdict": "improve"}

The verdict is recomputed here from the scores, the defects and the checklist, so a critic can
not call something outstanding that its own scores do not support: outstanding is every score
3, no critical or major defect and every checklist feature present at quality 3; good is every
score at least 2 and no critical defect; anything else is improve. Recording a critique writes
`authoring.critic` (bound to the scene's hash) and, for good or outstanding, the outcome; the
author can never write those outcomes without it (the audit's `self-graded`).
"""

import json
from pathlib import Path

from . import tiers

FORMAT = "construct-critique"
VERSION = 1
SEVERITIES = ("critical", "major", "minor")
VIEWS = ("front", "side", "back", "top", "three-quarter", "hero")


class CriticError(Exception):
    pass


def validate_items(doc):
    from . import scene as scene_mod
    c = scene_mod._Check()
    if not c.keys(doc, {"format", "version", "scene_sha256", "scores", "checklist", "defects", "verdict", "summary"},
                  {"format", "version", "scene_sha256", "scores", "defects", "verdict"}, "scene"):
        return c.items
    if doc.get("format") != FORMAT:
        c.err("scene.format", "must be %r" % FORMAT, "choice")
    if not (isinstance(doc.get("scene_sha256"), str) and len(doc["scene_sha256"]) == 64):
        c.err("scene.scene_sha256", "copy the scene hash from the packet", "type")
    sc = doc.get("scores")
    if c.keys(sc, set(tiers.CRITERIA), set(tiers.CRITERIA), "scene.scores") and all(k in sc for k in tiers.CRITERIA):
        for k in tiers.CRITERIA:
            c.num(sc[k], "scene.scores." + k, 0, 3, True)
    for i, item in enumerate(doc.get("checklist", []) if isinstance(doc.get("checklist", []), list) else []):
        w = "scene.checklist[%d]" % i
        if c.keys(item, {"feature", "present", "quality", "comment"}, {"feature", "present"}, w):
            if not isinstance(item.get("present"), bool):
                c.err(w + ".present", "expected true or false")
            if "quality" in item:
                c.num(item["quality"], w + ".quality", 0, 3, True)
    defects = doc.get("defects")
    if not isinstance(defects, list):
        c.err("scene.defects", "expected a ranked list (empty when there is nothing to fix)", "type")
        defects = []
    for i, d in enumerate(defects):
        w = "scene.defects[%d]" % i
        if c.keys(d, {"rank", "severity", "criterion", "parts", "view", "problem", "fix"},
                  {"rank", "severity", "problem", "fix"}, w):
            c.choice(d.get("severity"), SEVERITIES, w + ".severity")
            if "criterion" in d:
                c.choice(d["criterion"], tiers.CRITERIA, w + ".criterion")
            c.text(d.get("problem"), w + ".problem", 600)
            c.text(d.get("fix"), w + ".fix", 600)
    c.choice(doc.get("verdict"), tiers.VERDICTS, "scene.verdict")
    if isinstance(sc, dict) and isinstance(defects, list):  # a score below 3 names what is wrong
        cited = {d.get("criterion") for d in defects if isinstance(d, dict)}
        for k in tiers.CRITERIA:
            if isinstance(sc.get(k), int) and sc[k] < 3 and k not in cited:
                c.err("scene.scores." + k, "a score below 3 must cite a defect for %s (a defect with \"criterion\": "
                      "\"%s\"); a score with no named defect is noise" % (k, k), "rule")
    return c.items


def verdict(doc):
    """The verdict the scores, defects and checklist support (a critic's claim is not enough)."""
    low = min(doc["scores"].values())
    sev = {d.get("severity") for d in doc.get("defects", [])}
    checks = doc.get("checklist", [])
    if low == 3 and not sev & {"critical", "major"} and all(
            i.get("present") and i.get("quality", 3) == 3 for i in checks):
        return "outstanding"
    if low >= 2 and "critical" not in sev and all(i.get("present") for i in checks):
        return "good"
    return "improve"


def ranked(doc, top=None):
    order = {s: k for k, s in enumerate(SEVERITIES)}
    out = sorted(doc.get("defects", []), key=lambda d: (order.get(d.get("severity"), 9), d.get("rank", 99)))
    return out[:top] if top else out


def defects_text(doc, top=5):
    """The ranked defects as the author's next instruction."""
    lines = ["An independent critic compared your construct with the references (verdict: %s; lowest score %d)."
             % (verdict(doc), min(doc["scores"].values())),
             "Fix these, most severe first, then send the whole corrected JSON object:"]
    for i, d in enumerate(ranked(doc, top), 1):
        where = " / ".join(x for x in (d.get("view"), ", ".join(d.get("parts", []))) if x)
        lines.append("%d. [%s%s] %s Fix: %s" % (i, d["severity"], (" " + where) if where else "", d["problem"], d["fix"]))
    missing = [i["feature"] for i in doc.get("checklist", []) if not i.get("present")]
    if missing:
        lines.append("Missing identity features: %s." % ", ".join(missing))
    return "\n".join(lines)


def record(scene, doc, model=None):
    """Write the critique into the scene's authoring block; returns (scene, verdict)."""
    items = validate_items(doc)
    if items:
        raise CriticError("not a valid critique:\n" + "\n".join("%s: %s" % (i["where"], i["message"]) for i in items))
    if doc["scene_sha256"] != tiers.critic_hash(scene):
        raise CriticError("the critique is for another version of this scene: build a new packet and critique again")
    v = verdict(doc)
    from . import compare as compare_mod
    from . import params
    full = params.expand({k: x for k, x in scene.items() if k != "authoring"}) if params.is_params(scene) else scene
    current = tiers.critic_hash(scene)
    passing = [cp for cp in (scene.get("authoring") or {}).get("compare", [])
               if cp.get("pass") and cp.get("scene_sha256") == current]
    if v == "outstanding" and compare_mod.needs_likeness(full) and not passing:
        v = "good"  # "recognisable exactly" is measured, not only seen: compare first
    a = dict(scene.get("authoring") or {"tier": tiers.DEFAULT, "research": "unavailable"})
    prev = (a.get("critic") or {}).get("round", 0)
    a["critic"] = {"scene_sha256": doc["scene_sha256"], "verdict": v, "scores": dict(doc["scores"]),
                   "round": prev + 1, "defects": len(doc.get("defects", []))}
    if model:
        a["critic"]["model"] = str(model)[:120]
    if v in ("outstanding", "good"):
        a["outcome"] = v
    elif a.get("outcome") in ("outstanding", "good"):
        a["outcome"] = "self-reviewed"
    scene = json.loads(json.dumps(scene))
    scene["authoring"] = a
    return scene, v


# ---------------------------------------------------------------------------- the packet

def parse_references(refs):
    """["side=photo.jpg", "front=https://...", "photo.jpg"] -> [(view or None, ref)]."""
    out = []
    for r in refs or ():
        view, sep, path = r.partition("=")
        if sep and view in VIEWS and not view.startswith(("http", "/")):
            out.append((view, path))
        else:
            out.append((None, r))
    return out


def packet(scene_path, out_dir, references=(), request=None, width=1280, height=800, browser=None):
    """Render what the critic looks at and write packet.md / packet.json; returns the packet dict.

    Renders: the hero, the views and assembly sheets, and a still from each reference's view."""
    from . import diagnose, params, render, studio
    out = Path(out_dir)
    renders = out / "renders"
    renders.mkdir(parents=True, exist_ok=True)
    text = Path(scene_path).read_text(encoding="utf-8")
    doc, _ = diagnose.parse_text(text)
    if doc is None:
        raise CriticError("cannot read %s" % scene_path)
    scene = params.expand(doc) if params.is_params(doc) else doc
    if params.is_params(doc) and doc.get("authoring"):
        scene["authoring"] = doc["authoring"]
    build_dir = out / "build"
    studio.build(str(scene_path), str(build_dir))
    html = studio.page_in(build_dir)
    refs = parse_references(references)
    views = sorted({v for v, _ in refs if v and v != "hero"} | {"front", "side", "top"})
    shots = render.review(html, str(renders), width, height, sheets=("views", "assembly"), browser=browser)
    shots += render.stills(html, str(renders), views, width, height, browser=browser)
    names = {Path(p).name for p in shots}
    pairs = [{"view": v or "hero", "reference": r, "render": "renders/%s" % ("hero.png" if (v or "hero") == "hero"
                                                                             else "still-%s.png" % v)}
             for v, r in refs]
    a = scene.get("authoring") or {}
    pk = {"format": "construct-critique-packet", "version": 1, "scene_sha256": tiers.critic_hash(scene),
          "title": scene.get("title"), "request": request or (scene.get("subject") or {}).get("summary", ""),
          "identity": [{"feature": i["feature"], "parts": i["parts"]} for i in a.get("identity", [])],
          "pairs": pairs, "renders": sorted("renders/" + n for n in names if n.endswith(".png"))}
    (out / "packet.json").write_text(json.dumps(pk, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "packet.md").write_text(packet_text(pk), encoding="utf-8")
    return pk


def packet_text(pk):
    from . import prompts
    lines = [prompts.build()["critic.md"], "", "## This packet", "",
             "- Scene: %s (scene_sha256 `%s`: copy it into your answer)" % (pk["title"], pk["scene_sha256"]),
             "- The request: %s" % (pk["request"] or "(not given)")]
    if pk["identity"]:
        lines.append("- Identity checklist (check every item):")
        lines += ["  - %s (parts: %s)" % (i["feature"], ", ".join(i["parts"]) or "none") for i in pk["identity"]]
    else:
        lines.append("- No identity checklist was written: list the features you expected and did not find.")
    if pk["pairs"]:
        lines.append("- Compare each reference with the render from the same view:")
        lines += ["  - %s: reference %s beside %s" % (p["view"], p["reference"], p["render"]) for p in pk["pairs"]]
    else:
        lines.append("- No reference images: judge against what you know of the subject, and say so.")
    lines.append("- Renders: " + ", ".join(pk["renders"]))
    return "\n".join(lines) + "\n"


def run(pk, out_dir, base_url, model, key=None, log=None):
    """The critic as a second model call with a fresh context: the packet text and its images."""
    from . import diagnose, runner
    out = Path(out_dir)
    content = [{"type": "text", "text": packet_text(pk)}]
    for p in pk["pairs"]:
        content.append({"type": "text", "text": "Reference, %s view:" % p["view"]})
        content.append(runner.image_part(p["reference"]))
        content.append({"type": "text", "text": "Render, %s view:" % p["view"]})
        content.append(runner.image_part(str(out / p["render"])))
    for r in ("renders/hero.png", "renders/sheet-views.png", "renders/sheet-assembly.png"):
        if (out / r).exists():
            content.append({"type": "text", "text": r + ":"})
            content.append(runner.image_part(str(out / r)))
    messages = [{"role": "system", "content": "You are an independent critic. You did not make this construct."},
                {"role": "user", "content": content}]
    text, usage = "", {}
    for attempt in range(3):
        text, usage = runner.chat(base_url, model, messages, key)
        doc, _ = diagnose.parse_text(text)
        items = validate_items(doc) if isinstance(doc, dict) else [{"where": "$", "message": "no JSON object"}]
        if not items:
            return doc, usage
        if log:
            log("critic answer %d invalid: %s" % (attempt, items[0]["message"]))
        messages += [{"role": "assistant", "content": text},
                     {"role": "user", "content": "Fix these and send the whole critique JSON again:\n" +
                      "\n".join("- %s: %s" % (i["where"], i["message"]) for i in items)}]
    raise CriticError("the critic never produced a valid critique")
