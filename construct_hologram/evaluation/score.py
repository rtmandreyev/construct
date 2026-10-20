"""Score model outputs for the synthetic evaluation tasks.

    python3 -m <package>.evaluation.score <run folder> [<run folder> ...] [--json]
    (from the repository root, <package> being the toolkit's folder, e.g. construct_hologram)

A run folder holds one answer file per task (named in tasks.json) and, optionally, the
model's own log.json ({"task", "checks", ...}). Nothing is trusted: every answer is
re-checked with the toolkit's diagnostics. No model is called and no key is needed, so the
same scorer serves any provider a host connects (DeepSeek, a local model, Claude ...).
"""

import json
import sys
from pathlib import Path

from .. import diagnose, params as params_mod, scene as scene_mod

HERE = Path(__file__).resolve().parent


def _norm(v):
    return v.strip().lower() if isinstance(v, str) else v


def score_answer(task, path):
    row = {"task": task["id"], "exists": path.is_file()}
    if not row["exists"]:
        return dict(row, valid=False, score=0, problems=["no answer file"])
    text = path.read_text(encoding="utf-8")
    report = diagnose.diagnose_text(text)
    row.update(valid=report["ok"], errors=report["errors"], warnings=report["warnings"],
               error_codes=sorted({d["code"] for d in report["diagnostics"] if d["severity"] == "error"}))
    problems = []
    doc, _ = diagnose.parse_text(text)
    if not isinstance(doc, dict):
        return dict(row, score=0, problems=["not a JSON object"])
    is_params = params_mod.is_params(doc)
    if task["path"] == "params" and not is_params:
        problems.append("expected a parameter document")
    if task["path"] == "params" and is_params:
        if doc.get("archetype") != task["archetype"] or doc.get("variant") != task["variant"]:
            problems.append("archetype/variant %s/%s, expected %s/%s" % (doc.get("archetype"), doc.get("variant"),
                                                                           task["archetype"], task["variant"]))
    facts = {f.get("key"): f for f in doc.get("facts", []) if isinstance(f, dict)}
    for key, want in task["require"].items():
        f = facts.get(key)
        if f is None:
            problems.append("missing fact %r" % key)
        elif _norm(f.get("value")) != _norm(want):
            problems.append("fact %r is %r, the user said %r" % (key, f.get("value"), want))
        elif f.get("certainty") not in ("user_supplied", "verified"):
            problems.append("fact %r marked %s, but the user said it" % (key, f.get("certainty")))
    invented = sorted(k for k in facts if k in task.get("forbid", ()))
    for k in invented:
        problems.append("invented %r = %r (the user did not know it)" % (k, facts[k].get("value")))
    for k, f in facts.items():
        if f.get("certainty") == "verified" and not f.get("source"):
            problems.append("fact %r verified without a source" % k)
        if f.get("value") is None or scene_mod.is_placeholder(f.get("value")):
            problems.append("fact %r written as unknown instead of left out" % k)
    if task.get("forbid_artwork") and (doc.get("artwork") or doc.get("assets")):
        problems.append("artwork declared although the user has no image")
    built = None
    if report["ok"]:
        built = params_mod.expand(doc) if is_params else doc
        g = scene_mod.compile_scene(built)
        size = [g["bounds"]["max"][k] - g["bounds"]["min"][k] for k in range(3)]
        row["size_m"] = [round(x, 3) for x in size]
        lo_hi = task.get("size", {}).get("height")
        if lo_hi and not lo_hi[0] <= size[1] <= lo_hi[1]:
            problems.append("height %.3f m outside the plausible %s" % (size[1], lo_hi))
        if task["path"] == "scene":
            cat = built.get("subject", {}).get("category")
            if cat not in task.get("category", [cat]):
                problems.append("category %r, expected one of %s" % (cat, task["category"]))
            ids = [p for p in built["parts"] if p.get("role") == "identity"]
            if len(ids) < task.get("min_identity", 0):
                problems.append("no identity parts")
            row["parts"] = len(built["parts"])
        row["labels"] = [lb["text"] for lb in g["labels"]]
    # one point each: valid, factual (no problems of fact), plausible (size/category/archetype)
    fact_problems = [p for p in problems if p.startswith(("missing fact", "fact ", "invented", "artwork"))]
    other = [p for p in problems if p not in fact_problems]
    row["score"] = int(row["valid"]) + int(not fact_problems and row["valid"]) + int(not other and row["valid"])
    row["problems"] = problems
    return row


def score_run(folder, tasks=None):
    tasks = tasks or json.loads((HERE / "tasks.json").read_text())["tasks"]
    folder = Path(folder)
    log = {}
    if (folder / "log.json").is_file():
        try:
            log = {e.get("task"): e for e in json.loads((folder / "log.json").read_text())}
        except (ValueError, AttributeError):
            log = {}
    rows = []
    for t in tasks:
        row = score_answer(t, folder / t["file"])
        row["checks_reported"] = (log.get(t["id"]) or {}).get("checks")
        rows.append(row)
    return {"run": folder.name, "rows": rows, "total": sum(r["score"] for r in rows), "max": 3 * len(rows)}


def markdown(runs):
    lines = ["| run | " + " | ".join(r["task"] for r in runs[0]["rows"]) + " | total |",
             "|---|" + "---|" * (len(runs[0]["rows"]) + 1)]
    for run in runs:
        cells = ["%d/3%s" % (r["score"], " (%s checks)" % r["checks_reported"] if r.get("checks_reported") else "")
                 for r in run["rows"]]
        lines.append("| %s | %s | %d/%d |" % (run["run"], " | ".join(cells), run["total"], run["max"]))
    lines.append("")
    for run in runs:
        for r in run["rows"]:
            if r["problems"]:
                lines.append("- %s %s: %s" % (run["run"], r["task"], "; ".join(r["problems"])))
    return "\n".join(lines)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in argv
    folders = [a for a in argv if a != "--json"]
    runs = [score_run(f) for f in folders]
    sys.stdout.write((json.dumps(runs, indent=2, ensure_ascii=False) if as_json else markdown(runs)) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
