"""The improvement rounds of a Masterpiece (or Showcase) run: a defect ledger, a pairwise gate,
small batches, stop rules and a log a person can read, steer and resume.

One round:

1. Work on at most MAX_ITEMS ledger items, most severe first (regressions first), and tag every
   edit: `construct rounds change D3 "lowered the bonnet 40 mm"`.
2. `construct rounds packet scene.json --reference side=photo.jpg ...` checks the scene in to
   `checkpoints/round-NN/` and writes ONE packet for ONE fresh critic: part 1 judges this version
   alone (it never sees the history before it has written that judgement), part 2 sets it beside
   the best version so far from the same views, unlabelled and in a random A/B order, part 3
   reconciles the ledger.
3. `construct rounds record answer.json` un-blinds the pair and decides: the new version is kept
   when it wins overall (its regressions go to the top of the ledger: repair, don't revert), and
   only a version that loses overall is reverted. It updates the ledger, the state and
   `rounds.md`, prints the round's short report and says whether a stop rule fired.

Absolute scores are recorded but decide nothing: every score below 3 must cite a defect of its
criterion, and a score that moves with no defect added or fixed counts as no change. What the
renderer cannot do (the medium) is seeded as known limits; an ask the critic itself files under
one of them never enters the ledger. Each round's log also says whether a 4-round finish cap
would stop there (log only: it stops nothing).

Files (the run's memory; every command saves them, so a usage limit loses at most one step):
`state.json`, `ledger.json`, `rounds.md`, `checkpoints/round-NN/` (the scene, its renders, the
critic's answer and the A/B key, which the critic never sees).
"""

import json
import random
import shutil
import tempfile
import time
import zlib
from pathlib import Path

from . import tiers

STATE = "state.json"
LEDGER = "ledger.json"
LOG = "rounds.md"
ANSWER = "construct-round"
MAX_ITEMS = 4  # ledger items worked on in one round: small batches say which edit did what
NO_GAIN = 2  # rounds in a row that do not beat the best end the run
KNOWN_LIMIT = 3  # kept rounds that attempted a fix without progress make a known limit
IDLE = 10 * 60  # nothing written for longer than this before a command: the run was left alone
LONG = 45 * 60  # a silence between two writes longer than this is an interruption (a usage limit)
SEVERITY = {"critical": 0, "major": 1, "minor": 2}
STATUSES = ("open", "fixed", "regressed", "known-limit")
# what the renderer cannot do: seeded as known limits; an ask the critic files under one never enters the ledger
MEDIUM = [
    {"id": "L1", "criterion": "depth", "title": "hidden lines show faintly through solid parts (the x-ray style)"},
    {"id": "L2", "criterion": "identity", "title": "glass cannot be tinted or coloured (the house palette)"},
    {"id": "L3", "criterion": "motion", "title": "stills show the closed still pose: an opening never shows in a still"},
]
FINISH_CAP = 4  # logged only: would a cap of this many finish rounds stop the run here?
LIKENESS = ("silhouette", "proportions", "identity")  # finish starts once none has a critical or major item open


class RoundsError(ValueError):
    pass


# ---------------------------------------------------------------------------- the files

def _load(folder, name, default):
    p = Path(folder, name)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def _save(folder, name, doc):
    p = Path(folder, name)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(p)  # never half a file: a usage limit can stop any step


def state(folder):
    st = _load(folder, STATE, None)
    if st is None:
        raise RoundsError("no rounds here: start with `construct rounds start scene.json`")
    return st


def ledger(folder):
    return _load(folder, LEDGER, {"format": "construct-ledger", "version": 1, "items": []})


def _activity(paths, since, now):
    """When anything under these folders (or these files) was last written, between since and now."""
    out = []
    for p in paths:
        p = Path(p)
        files = [p] if p.is_file() else (p.rglob("*") if p.is_dir() else [])
        for f in files:
            try:
                t = f.stat().st_mtime
            except OSError:
                continue
            if since < t <= now:
                out.append(t)
    return sorted(out)


def _worked(since, now, moments):
    """Seconds of work between since and now, from the moments the run's files were written. A
    file shows only its last write (a generator rewrites the scene every few minutes), so a quiet
    stretch BETWEEN writes counts unless it is longer than LONG (a usage limit lasts hours); the
    stretch after the last write counts only up to IDLE: a run left alone (a pause, a stall, an
    unattended wait) stops counting there."""
    points = [since] + [t for t in moments if since < t < now]
    inner = sum(b - a for a, b in zip(points, points[1:]) if 0 <= b - a <= LONG)
    tail = now - points[-1]
    return inner + (tail if 0 <= tail <= IDLE else 0.0)


def tick(st, now=None, folder=None, extra=()):
    """Add the author's time since the last step. With the run's folder, the time between steps
    is measured from the folder's own activity (edits, a generator writing the scene, builds), so
    authoring done between `rounds` commands counts and an interruption does not; without it,
    only a gap of at most IDLE counts. The critic's turn (packet to record) is not the author's."""
    now = time.time() if now is None else now
    last = st.get("last_step_at", now)
    if st.get("step") == "packet" and folder is not None:
        return st  # the critic's turn: `record` measures it, from the packet on
    if st.pop("paused", False):  # `rounds pause`: the time since is an interruption
        st["last_step_at"] = now
        return st
    if folder is not None:
        paths = [folder] + [Path(folder, st["scene"])] + list(extra)
        add = _worked(last, now, _activity(paths, last, now))
    else:
        add = now - last if 0 <= now - last <= IDLE else 0.0
    st["active_seconds"] = round(st.get("active_seconds", 0.0) + max(0.0, add), 1)
    st["last_step_at"] = now
    return st


def step(folder, st, name, now=None):
    tick(st, now, folder)
    st["step"] = name
    _save(folder, STATE, st)


def pause(folder, now=None):
    """Mark an interruption: the time until the next command is not counted."""
    st = state(folder)
    tick(st, now, folder)
    st["paused"] = True
    _save(folder, STATE, st)
    return st


def start(scene_path, tier="masterpiece", folder=None, now=None):
    import os
    scene_path = Path(scene_path).resolve()
    folder = Path(folder or scene_path.parent).resolve()
    if Path(folder, STATE).exists():
        raise RoundsError("%s already holds a run: `construct rounds status` resumes it" % (folder / STATE))
    tier = tiers.tier_of(tier)
    if tier not in tiers.ROUNDS:
        raise RoundsError("the rounds loop is the masterpiece and unbounded modes; %s is fast mode: one pass with "
                          "self-review" % tier)
    lim = tiers.limits(tier)
    now = time.time() if now is None else now
    st = {"format": "construct-rounds", "version": 2, "scene": os.path.relpath(scene_path, folder), "tier": tier, "round": 1,
          "step": "authoring", "active_seconds": 0.0, "critic_seconds": 0.0, "last_step_at": now,
          "limit_seconds": lim["wall_clock_s"], "max_rounds": lim["review_rounds"], "best_round": None, "no_gain": 0, "status": "running", "changes": [],
          "history": []}
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "checkpoints").mkdir(exist_ok=True)
    _save(folder, STATE, st)
    _save(folder, LEDGER, {"format": "construct-ledger", "version": 1, "items": [
        {"id": m["id"], "title": m["title"], "criterion": m["criterion"], "severity": "major", "parts": [],
         "first_round": 0, "status": "known-limit", "medium": True, "rounds_attempted": 0,
         "reason": "the medium: the renderer cannot do it (not a defect of this construct)", "history": []}
        for m in MEDIUM]})
    Path(folder, LOG).write_text("# Rounds: %s\n\nTier %s. One section per round, appended; checkpoints in "
                                 "`checkpoints/round-NN/`.\n" % (scene_path.name, tier), encoding="utf-8")
    return st


# ---------------------------------------------------------------------------- authoring a round

def change(folder, item, text, now=None):
    """Tag one edit of this round with its ledger id (or "draft" in round 1)."""
    st = state(folder)
    if st["status"] != "running":
        raise RoundsError("the run has stopped (%s)" % st.get("stop", st["status"]))
    items = {i["id"]: i for i in ledger(folder)["items"]}
    if item != "draft":
        if item not in items:
            raise RoundsError("%r is not in the ledger (ids: %s)" % (item, ", ".join(sorted(items)) or "none yet"))
        if items[item]["status"] == "known-limit":
            raise RoundsError("%s is a known limit: leave it" % item)
    worked = {c["ledger"] for c in st["changes"]} | {item}
    worked.discard("draft")
    if len(worked) > MAX_ITEMS:
        raise RoundsError("a round works on at most %d ledger items (this one: %s): check it in and let the critic "
                          "judge first" % (MAX_ITEMS, ", ".join(sorted(worked))))
    st["changes"].append({"ledger": item, "change": str(text)[:300]})
    step(folder, st, "authoring", now)
    return st


def _round_dir(folder, n):
    return Path(folder, "checkpoints", "round-%02d" % n)


def packet(folder, scene_path, references=(), request=None, out=None, browser=None, seed=None, now=None):
    """Check the scene in and write the round's one-critic packet. Returns (packet folder, key)."""
    from . import critic, diagnose
    st = state(folder)
    if st["status"] != "running":
        raise RoundsError("the run has stopped (%s)" % st.get("stop", st["status"]))
    n = st["round"]
    rd = _round_dir(folder, n)
    rd.mkdir(parents=True, exist_ok=True)
    text = Path(scene_path).read_text(encoding="utf-8")
    doc, _ = diagnose.parse_text(text)
    if doc is None:
        raise RoundsError("cannot read %s" % scene_path)
    (rd / "scene.json").write_text(text, encoding="utf-8")
    step(folder, st, "checkpointed", now)
    digest = tiers.critic_hash(doc)
    pk_dir = Path(out) if out else Path(tempfile.gettempdir()) / ("round-" + digest[:12])  # a name that says nothing
    if pk_dir.exists():
        shutil.rmtree(pk_dir)
    rng = random.Random(seed if seed is not None else digest)
    # the references travel with the packet: a critic opens only its own folder
    refs = []
    for view, ref in critic.parse_references(references):
        if not ref.startswith(("http://", "https://")) and Path(ref).exists():
            dst = Path(pk_dir, "step-1", "references", Path(ref).name)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ref, dst)
            ref = str(dst)
        refs.append("%s=%s" % (view, ref) if view else ref)
    one = critic.packet(str(rd / "scene.json"), str(pk_dir / "step-1"), refs, request, browser=browser)
    _localise(pk_dir / "step-1")
    for png in Path(pk_dir, "step-1", "renders").glob("*.png"):  # this version's renders, kept with its checkpoint
        shutil.copyfile(png, rd / png.name)
    shutil.rmtree(Path(pk_dir, "step-1", "build"), ignore_errors=True)
    best = st.get("best_round")
    key = None
    if best is not None:
        new_is = rng.choice(("A", "B"))
        key = {"A": "new" if new_is == "A" else "best", "B": "best" if new_is == "A" else "new", "best_round": best,
               "round": n}
        tmp = Path(tempfile.mkdtemp(prefix="construct-pair-"))
        try:
            other = critic.packet(str(_round_dir(folder, best) / "scene.json"), str(tmp), refs, request,
                                  browser=browser)
            two = Path(pk_dir, "step-2")
            two.mkdir(parents=True, exist_ok=True)
            views = sorted({Path(r).name for r in one["renders"]} & {Path(r).name for r in other["renders"]})
            old_is = "B" if new_is == "A" else "A"
            for v in views:  # the same picture in other bytes, under a name that says nothing
                tag = "%04x" % rng.getrandbits(16)
                _reencode(Path(pk_dir, "step-1", "renders", v), two / ("%s-%s-%s" % (new_is, tag, v)), rng)
                _reencode(Path(tmp, "renders", v), two / ("%s-%s-%s" % (old_is, tag, v)), rng)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        _save(rd, "key.json", key)
    led = ledger(folder)
    shown = [i for i in led["items"] if i["status"] != "known-limit"]
    Path(pk_dir, "step-3").mkdir(parents=True, exist_ok=True)
    _save(Path(pk_dir, "step-3"), LEDGER, {"items": [{k: i[k] for k in ("id", "title", "criterion", "severity", "status")}
                                                     for i in shown]})
    from . import prompts
    pairs = [] if key is None else views
    Path(pk_dir, "packet.md").write_text(prompts.build()["round.md"] + "\n## This packet\n\n- scene_sha256 `%s`\n"
                                          "- part 1: step-1/packet.md (this version alone; the references are in "
                                          "step-1/references/)\n- part 2: %s\n"
                                          "- part 3: step-3/ledger.json (%d items)\n" % (
                                              digest, "step-2/: A-*.png and B-*.png, the same views (%s)" % ", ".join(pairs)
                                              if pairs else "none: this is the first version, leave `pairwise` out",
                                              len(shown)), encoding="utf-8")
    st = state(folder)
    st["packet"] = str(pk_dir)
    step(folder, st, "packet", now)
    st["packet_at"] = st["last_step_at"]
    _save(folder, STATE, st)
    return pk_dir, key


def _reencode(src, dst, rng):
    """The same picture in different bytes: the IDAT stream recompressed at another level, plus a
    random comment chunk, so a byte comparison cannot tell which pair image is a step-1 render."""
    import struct
    data = Path(src).read_bytes()
    out, i, idat = bytearray(data[:8]), 8, bytearray()
    chunks = []
    while i < len(data):
        n = struct.unpack(">I", data[i:i + 4])[0]
        kind, body = data[i + 4:i + 8], data[i + 8:i + 8 + n]
        i += 12 + n
        if kind == b"IDAT":
            idat += body
            if not chunks or chunks[-1][0] != b"IDAT":
                chunks.append((b"IDAT", None))
        else:
            chunks.append((kind, body))

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xffffffff)
    raw = zlib.decompress(bytes(idat))
    for kind, body in chunks:
        if kind == b"IDAT":
            out += chunk(b"tEXt", b"Comment\x00" + ("%016x" % rng.getrandbits(64)).encode())
            out += chunk(b"IDAT", zlib.compress(raw, rng.choice((1, 2, 3, 4, 5, 7, 8))))
        else:
            out += chunk(kind, body)
    Path(dst).write_bytes(bytes(out))


def _localise(step_dir):
    """The critic packet's reference paths, relative to its own folder."""
    for name in ("packet.md", "packet.json"):
        p = Path(step_dir, name)
        if p.exists():
            s = p.read_text(encoding="utf-8").replace(str(Path(step_dir).resolve()) + "/", "").replace(str(step_dir) + "/", "")
            p.write_text(s, encoding="utf-8")


# ---------------------------------------------------------------------------- the answer

def validate(doc, first=False, ids=()):
    from . import critic, scene as scene_mod
    c = scene_mod._Check()
    keys = {"format", "version", "scene_sha256", "critique", "pairwise", "reconcile"}
    if not c.keys(doc, keys, {"format", "version", "scene_sha256", "critique", "reconcile"} | (set() if first else {"pairwise"}),
                  "scene"):
        return c.items
    if doc.get("format") != ANSWER:
        c.err("scene.format", "must be %r" % ANSWER, "choice")
    items = list(c.items) + [dict(i, where="critique." + i["where"]) for i in critic.validate_items(doc["critique"])]
    c = scene_mod._Check()
    pw = doc.get("pairwise")
    if pw is not None and c.keys(pw, {"winner", "criteria", "differences", "reasons"}, {"winner", "criteria", "differences"},
                                 "pairwise"):
        c.choice(pw.get("winner"), ("A", "B"), "pairwise.winner")
        if c.keys(pw.get("criteria"), set(tiers.CRITERIA), set(tiers.CRITERIA), "pairwise.criteria"):
            for k, v in pw["criteria"].items():
                c.choice(v, ("A", "B", "same"), "pairwise.criteria." + k)
        for i, d in enumerate(pw.get("differences") if isinstance(pw.get("differences"), list) else []):
            w = "pairwise.differences[%d]" % i
            if c.keys(d, {"better", "criterion", "parts", "evidence"}, {"better", "evidence"}, w):
                c.choice(d.get("better"), ("A", "B"), w + ".better")
                if "criterion" in d:
                    c.choice(d["criterion"], tiers.CRITERIA, w + ".criterion")
                c.text(d.get("evidence"), w + ".evidence", 600)
    rc = doc.get("reconcile")
    if c.keys(rc, {"items", "new", "limits"}, {"items", "new"}, "reconcile"):
        seen = set()
        for i, it in enumerate(rc["items"] if isinstance(rc["items"], list) else []):
            w = "reconcile.items[%d]" % i
            if c.keys(it, {"id", "status", "evidence"}, {"id", "status"}, w):
                c.choice(it.get("status"), ("fixed", "open", "regressed", "inexpressible"), w + ".status")
                if it.get("id") not in ids:
                    c.err(w + ".id", "not an open item of the packet's ledger", "choice")
                seen.add(it.get("id"))
        missing = [i for i in ids if i not in seen]
        if missing:
            c.err("reconcile.items", "judge every ledger item of the packet: missing %s" % ", ".join(missing), "rule")
        n = len(doc["critique"].get("defects", [])) if isinstance(doc.get("critique"), dict) else 0
        if not (isinstance(rc["new"], list) and all(isinstance(r, int) and 1 <= r <= max(n, 0) for r in rc["new"])):
            c.err("reconcile.new", "the ranks (1..%d) of the part-1 defects that are genuinely new" % n, "type")
        if "limits" in rc and not (isinstance(rc["limits"], dict) and all(
                str(r).isdigit() and v in {m["id"] for m in MEDIUM} for r, v in rc["limits"].items())):
            c.err("reconcile.limits", "expected {rank: \"L1\"|\"L2\"|\"L3\"}", "type")
    return items + c.items


def _new_id(led):
    return "D%d" % (1 + max([int(i["id"][1:]) for i in led["items"] if i["id"].startswith("D") and i["id"][1:].isdigit()]
                            or [0]))


def _sorted(items):
    order = {"regressed": 0, "open": 1, "fixed": 2, "known-limit": 3}
    return sorted(items, key=lambda i: (order[i["status"]], SEVERITY.get(i["severity"], 3), i["first_round"]))


def record(folder, answer, scene_path=None, model=None, now=None):
    """Judge the round from the critic's answer; returns the round's summary dict."""
    from . import critic
    st = state(folder)
    if st["status"] != "running":
        raise RoundsError("the run has stopped (%s)" % st.get("stop", st["status"]))
    n = st["round"]
    rd = _round_dir(folder, n)
    if not (rd / "scene.json").exists():
        raise RoundsError("round %d is not checked in: `construct rounds packet` first" % n)
    doc = json.loads((rd / "scene.json").read_text(encoding="utf-8"))
    led = ledger(folder)
    ids = [i["id"] for i in led["items"] if i["status"] != "known-limit"]
    key = _load(rd, "key.json", None)
    items = validate(answer, first=key is None, ids=ids)
    if items:
        raise RoundsError("not a valid round answer:\n" + "\n".join("%s: %s" % (i["where"], i["message"]) for i in items))
    if answer["scene_sha256"] != tiers.critic_hash(doc):
        raise RoundsError("the answer is for another version: make the round's packet again")
    _save(rd, "round.json", answer)
    # the critic's wait is not the author's time: packet to record, measured from the activity in
    # the run and the packet folders, without idle stretches
    now = time.time() if now is None else now
    since = st.get("packet_at", now)
    st.pop("paused", None)
    extra = [Path(st["packet"])] if st.get("packet") else []
    critic_s = _worked(since, now, _activity([folder] + extra, since, now))
    st["critic_seconds"] = round(st.get("critic_seconds", 0.0) + critic_s, 1)
    st["last_step_at"] = now
    crit = answer["critique"]
    worked = sorted({c["ledger"] for c in st["changes"]} - {"draft"})
    if key is None:  # the first version stands
        won, improvements, regressions = True, [], []
    else:
        new = "A" if key["A"] == "new" else "B"
        won = answer["pairwise"]["winner"] == new
        diffs = answer["pairwise"]["differences"]
        improvements = [d for d in diffs if d["better"] == new]
        regressions = [d for d in diffs if d["better"] != new]
    byid = {i["id"]: i for i in led["items"]}
    line = []
    for it in answer["reconcile"]["items"]:
        item = byid[it["id"]]
        before = item["status"]
        if won:  # a lost round is reverted: its verdicts are about a version that is gone
            item["status"] = {"fixed": "fixed", "open": "open", "regressed": "regressed",
                              "inexpressible": "known-limit"}[it["status"]]
            if it["status"] == "inexpressible":
                item["reason"] = "the critic: the tools cannot express it (%s)" % it.get("evidence", "")[:160]
        if won and it["id"] in worked:
            item["rounds_attempted"] = item.get("rounds_attempted", 0) + 1
            if it["status"] == "open":
                item["no_progress"] = item.get("no_progress", 0) + 1
                if item["no_progress"] >= KNOWN_LIMIT:
                    item["status"] = "known-limit"
                    item["reason"] = "%d kept rounds attempted it without progress" % item["no_progress"]
            else:
                item["no_progress"] = 0
        item["history"].append("r%02d %s%s: %s" % (n, it["status"], "" if won else " (round reverted)",
                                                   it.get("evidence", "")[:200]))
        if item["status"] != before:
            line.append("%s %s -> %s" % (item["id"], before, item["status"]))
    added, medium = [], []
    if won:
        defects = crit.get("defects", [])
        said_limit = {int(r): v for r, v in answer["reconcile"].get("limits", {}).items()}
        first = key is None and not [i for i in led["items"] if not i.get("medium")]
        for rank in (range(1, len(defects) + 1) if first else answer["reconcile"]["new"]):
            d = defects[rank - 1]
            if said_limit.get(rank):  # the critic's own word that it asks for the medium's limit
                medium.append("%s (%s)" % (said_limit[rank], d["problem"][:80]))
                continue
            nid = _new_id(led)
            led["items"].append({"id": nid, "title": d["problem"][:200], "criterion": d.get("criterion", "identity"),
                                 "severity": d["severity"], "parts": d.get("parts", []), "fix": d["fix"][:300],
                                 "first_round": n, "status": "open", "rounds_attempted": 0,
                                 "history": ["r%02d new: %s" % (n, d["problem"][:200])]})
            added.append(nid)
        for d in regressions:  # repair, don't revert: the local regression leads the next round
            nid = _new_id(led)
            led["items"].append({"id": nid, "title": "regressed: " + d["evidence"][:190],
                                 "criterion": d.get("criterion", "identity"), "severity": "major",
                                 "parts": d.get("parts", []), "fix": "repair this regression, keep the round's gains",
                                 "first_round": n, "status": "regressed", "rounds_attempted": 0,
                                 "history": ["r%02d regressed against round %d: %s" % (n, key["best_round"], d["evidence"][:200])]})
            added.append(nid)
    led["items"] = _sorted(led["items"])
    _save(folder, LEDGER, led)
    started = st.get("round_started_active", 0.0)
    minutes = round((st["active_seconds"] - started) / 60, 1)
    scores = crit["scores"]
    prev = next((h for h in reversed(st["history"]) if h["kept"]), None)
    moved = {}
    for k in tiers.CRITERIA:  # a score change with no defect added or fixed for its criterion is no change
        if prev and scores[k] != prev["scores"][k]:
            evidence = any(i["criterion"] == k and (i["id"] in added or any(h.startswith("r%02d fixed" % n) for h in i["history"]))
                           for i in led["items"])
            moved[k] = "%d->%d%s" % (prev["scores"][k], scores[k], "" if evidence else " (noise: no defect added or fixed)")
    if won:
        st["best_round"] = n
        st["no_gain"] = 0
        restored = None
    else:
        st["no_gain"] = st.get("no_gain", 0) + 1
        restored = st["best_round"]  # the working scene goes back to the best version (below)
    top = [d["problem"][:160] for d in sorted(crit.get("defects", []), key=lambda d: (SEVERITY[d["severity"]], d["rank"]))[:3]]
    # logged only: finish starts at the first round with no critical or major silhouette,
    # proportions or identity item open; would a FINISH_CAP-round finish cap stop the run here?
    likeness = ["%s %s %s" % (i["id"], i["severity"], i["criterion"]) for i in led["items"]
                if i["status"] in ("open", "regressed") and i.get("criterion") in LIKENESS
                and i.get("severity") in ("critical", "major") and not i.get("medium")]
    if not likeness and st.get("finish_from") is None:
        st["finish_from"] = n
    if st.get("finish_from") is None:
        cap = "finish not started (%s open)" % "; ".join(likeness[:3])
    else:
        k = n - st["finish_from"] + 1
        cap = "finish round %d (finish from round %d): a %d-round finish cap would %s" % (
            k, st["finish_from"], FINISH_CAP, "stop here" if k == FINISH_CAP else "have stopped at round %d" % (
                st["finish_from"] + FINISH_CAP - 1) if k > FINISH_CAP else "not stop yet")
    entry = {"round": n, "kept": won, "baseline": key is None, "minutes": minutes,
             "critic_minutes": round(critic_s / 60, 1), "finish_cap": cap, "medium": medium,
             "active_minutes": round(st["active_seconds"] / 60, 1), "scores": scores, "verdict": crit["verdict"],
             "against": None if key is None else key["best_round"], "changes": st["changes"], "requests": top,
             "improvements": [d["evidence"][:160] for d in improvements][:4],
             "regressions": [d["evidence"][:160] for d in regressions][:4], "ledger": line, "added": added,
             "moved": moved}
    st["history"].append(entry)
    stop = None
    if won and all(v == 3 for v in scores.values()):
        stop = "every criterion at 3"
    elif st["no_gain"] >= NO_GAIN:
        stop = "%d rounds in a row did not beat round %d" % (NO_GAIN, st["best_round"])
    elif st.get("max_rounds") and n >= st["max_rounds"]:
        stop = "the %d-round cap (best: round %d)" % (st["max_rounds"], st["best_round"])
    elif st.get("limit_seconds") and st["active_seconds"] >= st["limit_seconds"]:
        stop = "the %d-minute ceiling on active time" % (st["limit_seconds"] // 60)
    st.update({"round": n + 1, "changes": [], "round_started_active": st["active_seconds"]})
    st.pop("packet_at", None)
    if stop:
        st.update({"status": "stopped", "stop": stop})
    _write_log(folder, entry, led, stop)
    _save(folder, STATE, dict(st, step="recorded"))
    # the working scene is now the judged version (kept) or the best one (reverted), with the critic's
    # record bound to it and the round history (the timeline in construct.html and review)
    if won:
        sc, _ = critic.record(json.loads((rd / "scene.json").read_text(encoding="utf-8")), crit, model)
        (rd / "scene.json").write_text(json.dumps(sc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    else:
        sc = json.loads((_round_dir(folder, restored) / "scene.json").read_text(encoding="utf-8"))
    if scene_path:
        sc.setdefault("authoring", {"tier": st["tier"], "research": "unavailable"})["rounds"] = timeline(st)
        Path(scene_path).write_text(json.dumps(sc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return dict(entry, stop=stop, restored=restored, best_round=st["best_round"])


def timeline(st):
    """The compact round history a page shows: round, kept or not, minutes, what changed."""
    return [{"round": h["round"], "result": "baseline" if h["baseline"] else "kept" if h["kept"] else "reverted",
             "minutes": h["minutes"], "changes": sorted({c["ledger"] for c in h["changes"]})[:8],
             "summary": (h["requests"][0] if h["requests"] else "")[:140]} for h in st["history"]][-40:]


def _write_log(folder, e, led, stop):
    kept = "baseline" if e["baseline"] else "kept (won against round %d)" % e["against"] if e["kept"] else \
        "reverted (lost to round %d)" % e["against"]
    lines = ["", "## Round %02d · %s · %.1f min · %.1f min active · critic %.1f min" % (
        e["round"], kept, e["minutes"], e["active_minutes"], e.get("critic_minutes", 0.0)),
             "Scores: " + ", ".join("%s %d%s" % (k, v, " (%s)" % e["moved"][k] if k in e["moved"] else "")
                                    for k, v in e["scores"].items()),
             "Verdict: %s" % e["verdict"],
             "Changed: " + ("; ".join("[%s] %s" % (c["ledger"], c["change"]) for c in e["changes"]) or "nothing tagged"),
             "Critic asks: " + (" | ".join(e["requests"]) or "nothing")]
    if e["improvements"]:
        lines.append("Better than the best: " + " | ".join(e["improvements"]))
    if e["regressions"]:
        lines.append("Worse than the best: " + " | ".join(e["regressions"]))
    lines.append("Ledger: " + ("; ".join(e["ledger"]) or "no status changed") + ("; new " + ", ".join(e["added"]) if e["added"] else ""))
    lines.append("Asks about the medium (not worked on): " + ("; ".join(e.get("medium", [])) or "none"))
    lines.append("Would a %d-round finish cap stop here? %s (log only)" % (FINISH_CAP, e["finish_cap"]))
    limits = [i["id"] for i in led["items"] if i["status"] == "known-limit" and not i.get("medium")]
    if limits:
        lines.append("Known limits: " + ", ".join(limits))
    if stop:
        lines.append("**Stopped: %s.**" % stop)
    with open(Path(folder, LOG), "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def summary(e):
    """The short chat report after a round."""
    head = "Round %d: %s, %.1f min (%.1f active; critic %.1f min)." % (
        e["round"], "baseline" if e["baseline"] else "kept: won against round %d" % e["against"] if e["kept"]
        else "reverted: lost to round %d (the working scene is round %d again)" % (e["against"], e["best_round"]),
        e["minutes"], e["active_minutes"], e["critic_minutes"])
    out = [head, "Changed: " + (", ".join("[%s] %s" % (c["ledger"], c["change"][:70]) for c in e["changes"]) or "nothing tagged")]
    out.append("The critic asks: " + ("; ".join(r[:110] for r in e["requests"]) or "nothing"))
    if e["regressions"] and e["kept"]:
        out.append("To repair next (top of the ledger): " + "; ".join(r[:100] for r in e["regressions"]))
    elif e["regressions"]:
        out.append("Worse than round %d: %s" % (e["against"], "; ".join(r[:100] for r in e["regressions"])))
    out.append("STOP: %s. `construct rounds report` writes the final report." % e["stop"] if e["stop"]
               else "Next: round %d, at most %d ledger items." % (e["round"] + 1, MAX_ITEMS))
    return "\n".join(out)


def status(folder, now=None):
    st = state(folder)
    tick(st, now, folder)
    _save(folder, STATE, st)
    led = ledger(folder)
    nxt = {"authoring": "edit the scene on at most %d ledger items, tag each edit (`rounds change`), then `rounds packet`"
                        % MAX_ITEMS,
           "checkpointed": "the round is checked in: `rounds packet` again to write its critic packet",
           "packet": "give the packet to ONE fresh critic (or run it as a direct call), then `rounds record answer.json`",
           "recorded": "the next round: edit, tag, `rounds packet`"}
    lines = ["Run: %s, tier %s, %s%s." % (st["scene"], st["tier"], st["status"], " (%s)" % st["stop"] if st.get("stop") else ""),
             "Round %d, step %s; best round %s; %.1f active minutes%s; critic %.1f minutes." % (
                 st["round"], st["step"], st["best_round"], st["active_seconds"] / 60,
                 " of %d" % (st["limit_seconds"] // 60) if st.get("limit_seconds") else " (no time ceiling)",
                 st.get("critic_seconds", 0.0) / 60),
             "Ledger: %s." % ", ".join("%d %s" % (sum(1 for i in led["items"] if i["status"] == s), s) for s in STATUSES)]
    if st["status"] == "running":
        lines.append("Next: " + nxt.get(st["step"], "continue"))
    return "\n".join(lines)


def report(folder):
    """The final report: the best round, the curve, the minutes and the known limits as skill gaps."""
    st = state(folder)
    led = ledger(folder)
    lines = ["## Final report", "",
             "Best: round %s. Stopped: %s. %.1f active minutes (critic %.1f more) over %d rounds." % (
                 st["best_round"], st.get("stop", st["status"]), st["active_seconds"] / 60,
                 st.get("critic_seconds", 0.0) / 60, len(st["history"])), "",
             "| round | result | minutes | min score | sum |", "|---|---|---|---|---|"]
    for h in st["history"]:
        lines.append("| %d | %s | %.1f | %d | %d |" % (h["round"], "baseline" if h["baseline"] else "kept" if h["kept"]
                                                    else "reverted", h["minutes"], min(h["scores"].values()),
                                                    sum(h["scores"].values())))
    open_ = [i for i in led["items"] if i["status"] in ("open", "regressed")]
    limits = [i for i in led["items"] if i["status"] == "known-limit" and not i.get("medium")]
    lines += ["", "Open: " + ("; ".join("%s %s" % (i["id"], i["title"][:100]) for i in open_) or "none"), "",
              "Known limits (skill gaps): " + ("; ".join("%s %s (%s)" % (i["id"], i["title"][:100], i.get("reason", ""))
                                                       for i in limits) or "none"), "",
              "The medium (what the renderer cannot do): " + "; ".join(m["title"] for m in MEDIUM)]
    text = "\n".join(lines) + "\n"
    with open(Path(folder, LOG), "a", encoding="utf-8") as f:
        f.write("\n" + text)
    return text


# ---------------------------------------------------------------------------- the critic as direct calls

def run(pk_dir, base_url, model, key=None, log=None):
    """The round's critic as ONE conversation with a fresh model (no child agent): part 1 is
    asked and answered before parts 2 and 3 are shown, so the blind judgement comes first."""
    from . import critic, diagnose, runner
    pk_dir = Path(pk_dir)
    one = json.loads(Path(pk_dir, "step-1", "packet.json").read_text(encoding="utf-8"))
    content = [{"type": "text", "text": critic.packet_text(one)}]
    for p in one["pairs"]:
        content += [{"type": "text", "text": "Reference, %s view:" % p["view"]}, runner.image_part(p["reference"]),
                    {"type": "text", "text": "Render, %s view:" % p["view"]},
                    runner.image_part(str(pk_dir / "step-1" / p["render"]))]
    for r in ("renders/hero.png", "renders/sheet-views.png"):
        if (pk_dir / "step-1" / r).exists():
            content += [{"type": "text", "text": r + ":"}, runner.image_part(str(pk_dir / "step-1" / r))]
    messages = [{"role": "system", "content": "You are an independent critic. You did not make this construct."},
                {"role": "user", "content": content}]

    def ask(check):
        for attempt in range(3):
            text, _ = runner.chat(base_url, model, messages, key)
            doc, _ = diagnose.parse_text(text)
            items = check(doc) if isinstance(doc, dict) else [{"where": "$", "message": "no JSON object"}]
            messages.append({"role": "assistant", "content": text})
            if not items:
                return doc
            if log:
                log("round critic answer %d invalid: %s" % (attempt, items[0]["message"]))
            messages.append({"role": "user", "content": "Fix these and send the whole JSON again:\n" +
                             "\n".join("- %s: %s" % (i["where"], i["message"]) for i in items)})
        raise RoundsError("the round's critic never produced a valid answer")
    crit = ask(critic.validate_items)
    answer = {"format": ANSWER, "version": 1, "scene_sha256": one["scene_sha256"], "critique": crit}
    two = pk_dir / "step-2"
    if two.exists():
        pics = sorted(two.glob("*.png"))
        content = [{"type": "text", "text": "Part 2. The same views of two versions, A and B, in a random order. Which is "
                    "better overall and more recognisable? Answer {\"winner\": \"A\"|\"B\", \"criteria\": {criterion: "
                    "\"A\"|\"B\"|\"same\"}, \"differences\": [{\"better\", \"criterion\", \"parts\", \"evidence\"}]}."}]
        for p in pics:
            content += [{"type": "text", "text": p.name + ":"}, runner.image_part(str(p))]
        messages.append({"role": "user", "content": content})
        answer["pairwise"] = ask(lambda d: [i for i in validate(dict(answer, pairwise=d, reconcile={"items": [], "new": []}))
                                            if i["where"].startswith("pairwise")])
    led = Path(pk_dir, "step-3", LEDGER).read_text(encoding="utf-8")
    ids = [i["id"] for i in json.loads(led)["items"]]
    messages.append({"role": "user", "content": "Part 3. The ledger of earlier defects:\n" + led + "\nFor each item: fixed, "
                     "open, regressed or inexpressible in the version of part 1, with one line of evidence; then the "
                     "ranks of your part-1 defects that are genuinely new, and which of them ask for the medium's "
                     "limits (hidden lines showing through: L1, tinted glass: L2, an opening in a still: L3). Answer "
                     "{\"items\": [{\"id\", \"status\", \"evidence\"}], \"new\": [ranks], \"limits\": {rank: "
                     "\"L1\"|\"L2\"|\"L3\"}}."})
    answer["reconcile"] = ask(lambda d: [i for i in validate(dict(answer, reconcile=d), first="pairwise" not in answer,
                                                            ids=ids) if i["where"].startswith("reconcile")])
    return answer


def scene_of(folder):
    """The run's working scene."""
    return Path(folder, state(folder)["scene"])
