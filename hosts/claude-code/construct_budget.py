#!/usr/bin/env python3
"""Hard limits for Construct inside Claude Code: a command hook (standard library only).

The skill states its tier's limits, but an agent can overrun them. This hook enforces two of
them from outside the model, per session:

- review rounds: every `construct review` (or `cli.py review`) counts; once the tier's rounds
  are used, further review commands are denied with the reason;
- wall clock: at 80% the agent is told once that it is the wrap-up point; past 100% every tool
  is denied except reading and `check`/`build`, so the saved scene can still be made valid and
  delivered.

Configure it in the project's .claude/settings.json (see hosts/claude-code/README.md):

    python3 construct_budget.py session-start | pre | post

Limits come from CONSTRUCT_TIER (quick, standard, showcase; default standard), overridden by
CONSTRUCT_MAX_SECONDS and CONSTRUCT_MAX_REVIEWS. State lives in <project>/.construct-budget/
(one small JSON file per session; delete the folder to reset).
"""

import json
import os
import re
import sys
import time
from pathlib import Path

# the tiers' wall clock (seconds) and review rounds; kept equal to construct_hologram/tiers.py
TIERS = {"quick": (120, 0), "standard": (600, 2), "showcase": (1800, 4)}
WRAP_UP = 0.8
REVIEW = re.compile(r"(\bconstruct|cli\.py)\s+review\b")
DELIVER = re.compile(r"(\bconstruct|cli\.py)\s+(check|build)\b")
READ_ONLY = {"Read", "Glob", "Grep", "LS"}


def limits(env=os.environ):
    tier = env.get("CONSTRUCT_TIER", "standard").lower()
    seconds, reviews = TIERS.get(tier, TIERS["standard"])
    try:
        seconds = float(env.get("CONSTRUCT_MAX_SECONDS", seconds))
        reviews = int(env.get("CONSTRUCT_MAX_REVIEWS", reviews))
    except ValueError:
        pass
    return tier, max(1.0, seconds), max(0, reviews)


def _state_path(event):
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or ".")
    sid = re.sub(r"[^A-Za-z0-9_-]", "", str(event.get("session_id", "session")))[:80] or "session"
    return root / ".construct-budget" / (sid + ".json")


def _load(path, now):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"start": now, "reviews": 0, "wrapped": False}


def _save(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state), encoding="utf-8")
    os.replace(tmp, path)


def handle(mode, event, now=None, env=os.environ):
    """(exit code, stdout text, stderr text) for one hook call."""
    now = time.time() if now is None else now
    tier, seconds, reviews = limits(env)
    path = _state_path(event)
    state = _load(path, now)
    elapsed = now - state["start"]
    command = str((event.get("tool_input") or {}).get("command", "")) if event.get("tool_name") == "Bash" else ""
    if mode == "session-start":
        if event.get("source") in (None, "startup", "clear"):
            state = {"start": now, "reviews": 0, "wrapped": False}
        _save(path, state)
        return 0, ("Construct budget (%s tier): %d s of wall clock and %d review rounds for this session. A hook "
                   "enforces them: review commands past the rounds are refused, and past the wall clock only "
                   "reading, check and build run." % (tier, seconds, reviews)), ""
    if mode == "pre":
        if REVIEW.search(command) and state["reviews"] >= reviews:
            return 2, "", ("Construct budget: all %d review rounds of the %s tier are used. Deliver the saved scene "
                           "with its authoring.next notes." % (reviews, tier))
        if elapsed > seconds and event.get("tool_name") not in READ_ONLY and not DELIVER.search(command):
            return 2, "", ("Construct budget: the %s tier's wall clock (%d s) is used. Only reading, check and build "
                           "run now: make the saved scene valid, build it and deliver it with its next notes."
                           % (tier, seconds))
        return 0, "", ""
    if mode == "post":
        notes = []
        if REVIEW.search(command):
            state["reviews"] += 1
            notes.append("Construct budget: review round %d of %d used." % (state["reviews"], reviews))
        if elapsed >= WRAP_UP * seconds and not state["wrapped"]:
            state["wrapped"] = True
            notes.append("Construct budget: %d of %d s used, the wrap-up point. The plan from here: stop adding, "
                         "make the saved scene valid, build it and deliver." % (elapsed, seconds))
        _save(path, state)
        if notes:
            return 0, json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                                         "additionalContext": " ".join(notes)}}), ""
        return 0, "", ""
    return 0, "", ""


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        event = {}
    code, out, err = handle(argv[0] if argv else "", event)
    if out:
        sys.stdout.write(out + "\n")
    if err:
        sys.stderr.write(err + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
