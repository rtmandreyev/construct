"""Effort tiers and the research policy: how long an author may work, and when it looks things up.

Aim for genuinely good, and always stop within the tier's limits. A tier bounds the whole
authoring run; whichever comes first ends it: the review judges the construct genuinely good,
or a limit is reached. Then the best version so far is delivered with a short "next" list, and
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
}
DEFAULT = "standard"
USE = {"quick": "bulk imports and simple archetypes (the parameter path)",
       "standard": "one entry (the default)",
       "showcase": "only on explicit request: more references, more review rounds"}
# overrides may raise a limit, never remove it
CEILING = {"wall_clock_s": 7200, "review_rounds": 12, "check_rounds": 30, "searches": 40, "sources": 20, "images": 20}
LIMIT_HELP = {"wall_clock_s": "wall clock, seconds", "review_rounds": "review/improve rounds",
              "check_rounds": "check rounds", "searches": "web searches", "sources": "sources read",
              "images": "reference images viewed"}

RESEARCH = ("auto", "on", "off")  # the request: decide by the policy, or the user's override
# what an author records: researched, not needed (a generic subject), skipped (confident without
# looking: nothing verified from it), unavailable (no web tool in the host), off (the user said so)
RESEARCH_RECORD = ("done", "not_needed", "skipped", "unavailable", "off")
OUTCOMES = ("good", "limit", "unreviewed")
MAX_NEXT = 8

# words a host can find in a request: "research: on", "tier: showcase"
_REQUEST_KEYS = {"research": RESEARCH, "tier": tuple(TIERS)}


class TierError(ValueError):
    pass


def limits(tier=DEFAULT, **overrides):
    """The tier's limits with any overrides applied; every limit finite and within CEILING."""
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
        if not lo <= v <= CEILING[k]:
            raise TierError("%s must be within %d..%d: limits can be raised, never removed" % (k, lo, CEILING[k]))
        out[k] = int(v) if k != "wall_clock_s" else float(v)
    out["tier"] = tier
    return out


def from_request(text):
    """`research: on|off|auto` and `tier: quick|standard|showcase` written in a request, if present."""
    import re
    found = {}
    for key, options in _REQUEST_KEYS.items():
        m = re.search(r"\b%s\s*[:=]\s*(%s)\b" % (key, "|".join(options)), text or "", re.I)
        if m:
            found[key] = m.group(1).lower()
    return found


def table():
    """The tiers as a Markdown table (prompts and docs are generated from it)."""
    rows = ["| tier | use | wall clock | review/improve rounds | check rounds | research, when it applies |",
            "|---|---|---|---|---|---|"]
    for name, t in TIERS.items():
        research = ("none beyond the source data" if not t["searches"] else
                    "≤%d searches, ≤%d sources read, ≤%d reference images" % (t["searches"], t["sources"], t["images"]))
        rows.append("| %s | %s | %s | %s | %d | %s |" % (
            name, USE[name], "%d min" % (t["wall_clock_s"] // 60),
            "0 (audit only)" if not t["review_rounds"] else t["review_rounds"], t["check_rounds"], research))
    return "\n".join(rows)


def check(c, a, source_ids, scene_sources, where="scene.authoring"):
    """Validate an `authoring` block with a scene `_Check`."""
    if not c.keys(a, {"tier", "research", "sources", "review_rounds", "outcome", "next"}, {"tier", "research"}, where):
        return
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
        c.num(a["review_rounds"], where + ".review_rounds", 0, CEILING["review_rounds"], True)
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
    if a["research"] == "done" and len(looked_up) > tier["sources"] + tier["images"]:
        add(warnings, "tier-budget", None, "%d researched sources is beyond the %s tier (%d sources, %d images): "
            "keep the few that carry the identity, or record a higher tier" % (
                len(looked_up), a["tier"], tier["sources"], tier["images"]))
    if a["research"] != "done" and looked_up:
        add(warnings, "research", None, "sources %s are listed but research is %r: record \"done\" when you looked "
            "things up" % (", ".join(looked_up), a["research"]))
    if a.get("outcome") == "limit" and not a.get("next"):
        add(warnings, "authoring", None, "stopped at a limit with no \"next\" notes: say what the next improvement would be")
