"""Effort tiers and the research policy: how long an author may work, and when it looks things up.

Aim for genuinely good, and always stop within the tier's limits. A tier bounds the whole
authoring run; whichever comes first ends it: the review judges the construct genuinely good,
or a limit is reached. The masterpiece tier is the one exception, for hard subjects on request:
no wall clock and no round cap; it stops only when an independent critic scores every criterion
outstanding, when the user stops it, or at an optional cost ceiling, and it saves a checkpoint
every round. Then the best version so far is delivered with a short "next" list, and
the tier and that list are recorded in the scene's `authoring` block so it can be regenerated
at a higher tier later. A host or user may pick a tier or override single limits, but every
limit stays finite: nothing runs unbounded. Hosts add their own hard limits on top (a Hermes
run budget, an agent timeout, a cost ceiling).

    {"authoring": {"tier": "standard", "research": "done", "sources": ["maker-specs", "ref-front"],
                   "review_rounds": 2, "outcome": "good", "next": ["trace the headstock from a side photo"]}}
"""

TIERS = {
    # wall clock in seconds; rounds; research counts apply only when research applies
    "quick": {"wall_clock_s": 120, "review_rounds": 0, "check_rounds": 3, "searches": 0, "sources": 0, "images": 0},
    "standard": {"wall_clock_s": 600, "review_rounds": 2, "check_rounds": 6, "searches": 5, "sources": 3, "images": 3},
    "showcase": {"wall_clock_s": 1800, "review_rounds": 4, "check_rounds": 10, "searches": 10, "sources": 6, "images": 6},
    # no round cap: the critic's all-3, two rounds in a row that do not beat the best, the user, or a
    # 2-hour safety stop on ACTIVE time (an interruption does not count) ends it; check rounds per round
    "masterpiece": {"wall_clock_s": 7200, "review_rounds": None, "check_rounds": 8, "searches": 20, "sources": 12,
                    "images": 12},
}
UNCAPPED = "masterpiece"
CRITERIA = ("silhouette", "proportions", "identity", "depth", "composition", "assembly", "motion", "density", "honesty")
DEFAULT = "standard"
# shares of the wall clock: research ends by RESEARCH_SHARE, a complete valid draft is on disk by
# DRAFT_BY, and at WRAP_UP nothing new is added: the saved draft is made valid and delivered
RESEARCH_SHARE = 0.4
DRAFT_BY = 0.4
WRAP_UP = 0.8
USE = {"quick": "bulk imports and simple archetypes (the parameter path)",
       "standard": "one entry (the default)",
       "showcase": "only on explicit request: more references, more review rounds",
       "masterpiece": "hard subjects, only on explicit request: rounds judged pairwise against the best, until every "
                      "criterion is 3, two rounds without a win, or the 2-hour safety stop"}
# overrides may raise a limit, never remove it
CEILING = {"wall_clock_s": 7200, "review_rounds": 12, "check_rounds": 30, "searches": 40, "sources": 20, "images": 20}
LIMIT_HELP = {"wall_clock_s": "wall clock, seconds", "review_rounds": "review/improve rounds",
              "check_rounds": "check rounds", "searches": "web searches", "sources": "sources read",
              "images": "reference images viewed"}

RESEARCH = ("auto", "on", "off")  # the request: decide by the policy, or the user's override
# what an author records: researched, not needed (a generic subject), skipped (confident without
# looking: nothing verified from it), unavailable (no web tool in the host), off (the user said so)
RESEARCH_RECORD = ("done", "not_needed", "skipped", "unavailable", "off")
# outstanding and good are an independent critic's verdicts; self-reviewed is the author's own
OUTCOMES = ("outstanding", "good", "self-reviewed", "limit", "unreviewed")
VERDICTS = ("outstanding", "good", "improve")
MAX_IDENTITY = 16
MAX_NEXT = 8

# words a host can find in a request: "research: on", "tier: showcase"
_REQUEST_KEYS = {"research": RESEARCH, "tier": tuple(TIERS)}


class TierError(ValueError):
    pass


def limits(tier=DEFAULT, **overrides):
    """The tier's limits with any overrides applied; every limit finite and within CEILING, except
    the masterpiece tier's wall clock and review rounds, which are None (uncapped) unless set."""
    if tier not in TIERS:
        raise TierError("tier is one of %s" % ", ".join(TIERS))
    out = dict(TIERS[tier])
    for k, v in overrides.items():
        if v is None:
            continue
        if k not in out:
            raise TierError("unknown limit %r (one of %s)" % (k, ", ".join(out)))
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v:
            raise TierError("%s must be a number" % k)
        lo = 1 if k in ("wall_clock_s", "check_rounds") else 0
        top = float("inf") if tier == UNCAPPED else CEILING[k]
        if not lo <= v <= top or v == float("inf"):
            raise TierError("%s must be within %d..%d: limits can be raised, never removed" % (k, lo, CEILING[k]))
        out[k] = int(v) if k != "wall_clock_s" else float(v)
    out["tier"] = tier
    return out


def from_request(text):
    """`research: on|off|auto` and `tier: quick|standard|showcase|masterpiece` written in a request."""
    import re
    found = {}
    for key, options in _REQUEST_KEYS.items():
        m = re.search(r"\b%s\s*[:=]\s*(%s)\b" % (key, "|".join(options)), text or "", re.I)
        if m:
            found[key] = m.group(1).lower()
    return found


def clock_rule(lim=None):
    """The time shares as one sentence (prompts and docs carry it)."""
    t = "Research takes at most %d%% of the time and ends in a first draft: a complete scene that passes " \
        "`check`, saved to disk by %d%% of the time (draft early; never hold the only copy in context). Then " \
        "improve it in place, re-checking and saving after every round, so a valid scene is always on disk. " \
        "At %d%% stop adding: make the saved scene valid and deliver it." % (
            RESEARCH_SHARE * 100, DRAFT_BY * 100, WRAP_UP * 100)
    if lim and (lim["wall_clock_s"] is None or lim.get("tier") == UNCAPPED):
        return ("Rounds, not a schedule: save a complete scene that passes `check` after the first round and a "
                "checkpoint every round after that (`construct rounds`), so the best version is always on disk; the "
                "%s is a safety stop on active time." % ("no wall clock" if lim["wall_clock_s"] is None else
                                                          "%d-minute limit" % (lim["wall_clock_s"] // 60)))
    if lim:
        w = lim["wall_clock_s"]
        t += " (This run: research by %d s, a saved draft by %d s, wrap up at %d s.)" % (
            w * RESEARCH_SHARE, w * DRAFT_BY, w * WRAP_UP)
    return t


def table():
    """The tiers as a Markdown table (prompts and docs are generated from it)."""
    rows = ["| tier | use | wall clock | review/improve rounds | check rounds | research, when it applies |",
            "|---|---|---|---|---|---|"]
    for name, t in TIERS.items():
        research = ("none beyond the source data" if not t["searches"] else
                    "≤%d searches, ≤%d sources read, ≤%d reference images" % (t["searches"], t["sources"], t["images"]))
        rows.append("| %s | %s | %s | %s | %s | %s |" % (
            name, USE[name], "none" if t["wall_clock_s"] is None else "%d min%s" % (
                t["wall_clock_s"] // 60, " active (a safety stop)" if name == UNCAPPED else ""),
            "until the stop rules" if t["review_rounds"] is None else
            "0 (audit only)" if not t["review_rounds"] else t["review_rounds"],
            "%d per round" % t["check_rounds"] if name == UNCAPPED else t["check_rounds"], research))
    return "\n".join(rows)


def check(c, a, source_ids, scene_sources, where="scene.authoring"):
    """Validate an `authoring` block with a scene `_Check`."""
    if not c.keys(a, {"tier", "research", "sources", "review_rounds", "outcome", "next", "identity", "critic", "compare",
                      "rounds"}, {"tier", "research"}, where):
        return
    if "rounds" in a:  # the round timeline (`construct rounds` writes it)
        r = a["rounds"]
        if not isinstance(r, list) or len(r) > 40:
            c.err(where + ".rounds", "expected a list of at most 40 rounds")
        else:
            for i, e in enumerate(r):
                w = "%s.rounds[%d]" % (where, i)
                if c.keys(e, {"round", "result", "minutes", "changes", "summary"}, {"round", "result"}, w):
                    c.num(e.get("round"), w + ".round", 0, 1000, True)
                    c.choice(e.get("result"), ("baseline", "kept", "reverted"), w + ".result")
                    if "minutes" in e:
                        c.num(e["minutes"], w + ".minutes", 0, 100000)
                    if "summary" in e:
                        c.text(e["summary"], w + ".summary", 200)
                    if "changes" in e and not (isinstance(e["changes"], list) and all(isinstance(x, str) for x in e["changes"])):
                        c.err(w + ".changes", "expected ledger ids")
    c.choice(a.get("tier"), tuple(TIERS), where + ".tier")
    c.choice(a.get("research"), RESEARCH_RECORD, where + ".research")
    used = a.get("sources", [])
    if not isinstance(used, list) or len(used) > CEILING["sources"] + CEILING["images"]:
        c.err(where + ".sources", "expected a list of source ids", "type", '["maker-specs", "ref-front"]')
        used = []
    kinds = {s.get("id"): s.get("kind") for s in scene_sources if isinstance(s, dict)}
    for i, sid in enumerate(used):
        if sid not in source_ids:
            c.err("%s.sources[%d]" % (where, i), "unknown source %r" % (sid,), "reference",
                  "List the ids of the scene's sources that research found.")
    looked_up = [s for s in used if kinds.get(s) not in (None, "user_request")]
    if a.get("research") == "done" and not looked_up:
        c.err(where + ".research", "research is \"done\" but no researched source is listed", "research",
              'List the sources you read or viewed in "sources" (each also in the scene\'s sources), or record '
              '"skipped" when you worked from what you already knew.')
    if "review_rounds" in a:
        c.num(a["review_rounds"], where + ".review_rounds", 0, 1000, True)
    ident = a.get("identity", [])
    if not isinstance(ident, list) or len(ident) > MAX_IDENTITY:
        c.err(where + ".identity", "expected a list of at most %d identity features" % MAX_IDENTITY, "type",
              '[{"feature": "periscope roof channel", "parts": ["roof-channel"], "source": "ref-top"}]')
        ident = []
    for i, item in enumerate(ident):
        w = "%s.identity[%d]" % (where, i)
        if c.keys(item, {"feature", "parts", "source", "note"}, {"feature", "parts"}, w):
            c.text(item.get("feature"), w + ".feature", 200)
            if not isinstance(item.get("parts"), list) or not all(isinstance(x, str) for x in item["parts"]):
                c.err(w + ".parts", "expected the ids of the parts that build this feature", "type", '["roof-channel"]')
            if "source" in item and item["source"] not in source_ids:
                c.err(w + ".source", "unknown source %r" % (item["source"],), "reference")
    comps = a.get("compare", [])
    if not isinstance(comps, list) or len(comps) > 8:
        c.err(where + ".compare", "expected at most 8 comparison records (construct compare --record writes them)", "type")
        comps = []
    for i, cp in enumerate(comps):
        w = "%s.compare[%d]" % (where, i)
        if c.keys(cp, {"view", "reference", "iou", "edge", "pass", "scene_sha256"},
                  {"view", "reference", "iou", "edge", "pass", "scene_sha256"}, w):
            c.text(cp.get("view"), w + ".view", 64)
            if cp.get("reference") not in source_ids:
                c.err(w + ".reference", "unknown source %r" % (cp.get("reference"),), "reference")
            c.num(cp.get("iou"), w + ".iou", 0, 1)
            c.num(cp.get("edge"), w + ".edge", 0, 10)
            if not isinstance(cp.get("pass"), bool):
                c.err(w + ".pass", "expected true or false")
    if "critic" in a:
        cr, w = a["critic"], where + ".critic"
        if c.keys(cr, {"scene_sha256", "verdict", "scores", "round", "model", "defects"}, {"scene_sha256", "verdict", "scores"}, w):
            if not (isinstance(cr.get("scene_sha256"), str) and len(cr["scene_sha256"]) == 64):
                c.err(w + ".scene_sha256", "expected the 64-hex hash of the scene the critic judged", "type")
            c.choice(cr.get("verdict"), VERDICTS, w + ".verdict")
            sc = cr.get("scores")
            if c.keys(sc, set(CRITERIA), set(CRITERIA), w + ".scores") and all(k in sc for k in CRITERIA):
                for k in CRITERIA:
                    c.num(sc[k], "%s.scores.%s" % (w, k), 0, 3, True)
            if "round" in cr:
                c.num(cr["round"], w + ".round", 0, 1000, True)
            if "model" in cr:
                c.text(cr["model"], w + ".model", 120)
            if "defects" in cr:
                c.num(cr["defects"], w + ".defects", 0, 1000, True)
    if "outcome" in a:
        c.choice(a["outcome"], OUTCOMES, where + ".outcome")
    nxt = a.get("next", [])
    if not isinstance(nxt, list) or len(nxt) > MAX_NEXT:
        c.err(where + ".next", "expected at most %d short improvement notes" % MAX_NEXT, "type",
              '["trace the headstock from a side photo"]')
    else:
        for i, n in enumerate(nxt):
            c.text(n, "%s.next[%d]" % (where, i), 300)


def audit(scene, add, warnings):
    """Audit warnings about an `authoring` block (validation already passed)."""
    a = scene.get("authoring")
    if not a:
        return
    kinds = {s["id"]: s["kind"] for s in scene.get("sources", [])}
    looked_up = [s for s in a.get("sources", []) if kinds.get(s) not in ("user_request", "user_supplied")]
    tier = TIERS[a["tier"]]
    parts = {p["id"] for p in scene.get("parts", [])}
    for item in a.get("identity", []):
        missing = [x for x in item["parts"] if x not in parts]
        if not item["parts"] or missing:
            add(warnings, "identity-unbuilt", None, "identity feature %r has %s: build it, or say in next why it is "
                "missing" % (item["feature"], "no part" if not item["parts"] else "unknown parts " + ", ".join(missing)))
    if a["tier"] in ("showcase", UNCAPPED) and not a.get("identity"):
        add(warnings, "no-checklist", None, "no identity checklist: write the features that make the subject itself "
            "(from research) in authoring.identity, each with the parts that build it")
    critic = a.get("critic")
    if critic:
        if critic["scene_sha256"] != critic_hash(scene):
            add(warnings, "critic-stale", None, "the critic judged another version of this scene: run the critic again")
        best = min(critic["scores"].values())
        if critic["verdict"] == "outstanding" and best < 3 or critic["verdict"] == "good" and best < 2:
            add(warnings, "critic-claim", None, "the critic's verdict %r does not match its scores (lowest %d)" % (
                critic["verdict"], best))
    from . import compare as compare_mod
    current = critic_hash(scene)
    for cp in a.get("compare", []):
        if cp["scene_sha256"] != current:
            add(warnings, "compare-stale", None, "the %s comparison was made on another version: compare again" % cp["view"])
    passing = [cp for cp in a.get("compare", []) if cp["pass"] and cp["scene_sha256"] == current]
    if compare_mod.needs_likeness(scene) and a.get("outcome") == "outstanding" and not passing:
        add(warnings, "likeness", None, "an outstanding %s needs a passing silhouette comparison with a traced "
            "reference (construct compare --record)" % ("vehicle" if scene["subject"]["category"] == "vehicle"
                                                        else "landmark"))
    outcome = a.get("outcome")
    if outcome in ("outstanding", "good") and (not critic or critic["verdict"] != outcome):
        add(warnings, "self-graded", None, "outcome %r is an independent critic's verdict, and there is no matching "
            "critic record: run construct critique, or record \"self-reviewed\"" % outcome)
    if a["research"] == "done" and len(looked_up) > tier["sources"] + tier["images"]:
        add(warnings, "tier-budget", None, "%d researched sources is beyond the %s tier (%d sources, %d images): "
            "keep the few that carry the identity, or record a higher tier" % (
                len(looked_up), a["tier"], tier["sources"], tier["images"]))
    if a["research"] != "done" and looked_up:
        add(warnings, "research", None, "sources %s are listed but research is %r: record \"done\" when you looked "
            "things up" % (", ".join(looked_up), a["research"]))
    rounds = a.get("review_rounds")
    if isinstance(rounds, int) and tier["review_rounds"] is not None and rounds > tier["review_rounds"]:
        add(warnings, "tier-rounds", None, "%d review rounds is beyond the %s tier's %d: stop at the cap and deliver "
            "the saved scene with its next notes (or record a higher tier the user asked for)" % (
                rounds, a["tier"], tier["review_rounds"]))
    if a.get("outcome") == "limit" and not a.get("next"):
        add(warnings, "authoring", None, "stopped at a limit with no \"next\" notes: say what the next improvement would be")


def critic_hash(doc):
    """The hash a critic records: the scene (a parameter document is expanded first) without its
    authoring block, which the critic's own record changes."""
    from . import params
    from . import scene as scene_mod
    d = {k: v for k, v in doc.items() if k != "authoring"}
    if params.is_params(d):
        d = params.expand(d)
    return scene_mod.canonical_sha256(d)


def authoring_schema():
    """JSON Schema of the authoring block (the parameter schema and geometry schema carry it)."""
    return {
        "type": "object", "additionalProperties": False, "required": ["tier", "research"],
        "description": "How the construct was authored: the effort tier, whether research was done and from which "
                       "sources, the identity checklist, the independent critic's record and what would improve it next.",
        "properties": {
            "tier": {"enum": list(TIERS)}, "research": {"enum": list(RESEARCH_RECORD)},
            "sources": {"type": "array", "items": {"type": "string"}},
            "review_rounds": {"type": "integer", "minimum": 0, "maximum": 1000},
            "outcome": {"enum": list(OUTCOMES)},
            "next": {"type": "array", "maxItems": MAX_NEXT, "items": {"type": "string", "maxLength": 300}},
            "identity": {"type": "array", "maxItems": MAX_IDENTITY, "items": {
                "type": "object", "additionalProperties": False, "required": ["feature", "parts"],
                "properties": {"feature": {"type": "string", "maxLength": 200},
                               "parts": {"type": "array", "items": {"type": "string"}},
                               "source": {"type": "string"}, "note": {"type": "string"}}}},
            "rounds": {"type": "array", "maxItems": 40, "items": {
                "type": "object", "additionalProperties": False, "required": ["round", "result"],
                "properties": {"round": {"type": "integer", "minimum": 0}, "result": {"enum": ["baseline", "kept", "reverted"]},
                               "minutes": {"type": "number", "minimum": 0},
                               "changes": {"type": "array", "items": {"type": "string"}},
                               "summary": {"type": "string", "maxLength": 200}}}},
            "compare": {"type": "array", "maxItems": 8, "items": {
                "type": "object", "additionalProperties": False,
                "required": ["view", "reference", "iou", "edge", "pass", "scene_sha256"],
                "properties": {"view": {"type": "string"}, "reference": {"type": "string"},
                               "iou": {"type": "number", "minimum": 0, "maximum": 1},
                               "edge": {"type": "number", "minimum": 0}, "pass": {"type": "boolean"},
                               "scene_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"}}}},
            "critic": {"type": "object", "additionalProperties": False, "required": ["scene_sha256", "verdict", "scores"],
                       "properties": {"scene_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                                      "verdict": {"enum": list(VERDICTS)},
                                      "scores": {"type": "object", "additionalProperties": False,
                                                 "required": list(CRITERIA),
                                                 "properties": {k: {"type": "integer", "minimum": 0, "maximum": 3}
                                                                for k in CRITERIA}},
                                      "round": {"type": "integer", "minimum": 0},
                                      "model": {"type": "string", "maxLength": 120},
                                      "defects": {"type": "integer", "minimum": 0}}},
        },
    }
