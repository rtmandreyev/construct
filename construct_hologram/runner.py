"""A minimal author loop for any OpenAI-compatible chat endpoint (standard library only).

    construct author "a 1970s desk fan with a round cage" --base-url https://api.deepseek.com/v1 \
        --model deepseek-chat --key-env DEEPSEEK_API_KEY --out fan.json [--params] [--tier standard] [--vision]

It sends the prompts (system.md, then params.md or scene.md), the request, then the repair
text until the draft is valid and free of visible defects. With `--vision` (the model can see
images) and a browser, it then renders the construct and asks the model for an art-direction
review of its own captures, improving the weakest point each round until the review judges it
genuinely good. The tier (`tiers.py`) bounds the whole run: wall clock, check rounds and review
rounds, plus an optional token or cost ceiling; whichever comes first ends it, and the best
draft so far is written with its `authoring` record (tier, outcome, next improvements).

The key is read from the environment variable you name and is never written anywhere; the
endpoint is the one you give. Works with DeepSeek, OpenRouter, OpenAI, Ollama, llama.cpp and LM
Studio servers. This runner has no web search: research comes from the reference images you
attach (`--reference`); web images count against the tier's reference-image limit.
"""

import json
import os
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import diagnose, prompts, tiers

REVIEW_MARGIN_S = 20  # a review round needs a render and two answers: do not start one with less left


class RunnerError(Exception):
    pass


class LimitReached(Exception):
    pass


def chat(base_url, model, messages, key=None, timeout=300, temperature=0.2):
    url = base_url.rstrip("/") + "/chat/completions"
    body = json.dumps({"model": model, "messages": messages, "temperature": temperature}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    if key:
        req.add_header("Authorization", "Bearer " + key)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RunnerError("the endpoint answered %d: %s" % (exc.code, exc.read()[:300].decode("utf-8", "replace")))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise RunnerError("cannot reach %s: %s" % (url, exc))
    try:
        return data["choices"][0]["message"]["content"] or "", data.get("usage", {})
    except (KeyError, IndexError, TypeError):
        raise RunnerError("unexpected answer from the endpoint")


def image_part(ref):
    """An OpenAI-style image content part: a local file as a data URL, a web image by URL (viewed, not kept)."""
    import base64
    import mimetypes
    if ref.startswith(("http://", "https://")):
        return {"type": "image_url", "image_url": {"url": ref}}
    mime = mimetypes.guess_type(ref)[0] or "image/jpeg"
    if not mime.startswith("image/"):
        raise RunnerError("%s is not an image" % ref)
    with open(ref, "rb") as fh:
        data = base64.b64encode(fh.read()).decode("ascii")
    return {"type": "image_url", "image_url": {"url": "data:%s;base64,%s" % (mime, data)}}


def trace_image(images, what, base_url, model, key=None, features=(), rounds=3, title=None, log=None):
    """The vision step: the model traces `what` in the image(s); checked and repaired like a draft."""
    pack = prompts.build()
    ask = pack["trace.md"] + "\n\nTrace: %s.%s" % (
        what, (" Features to mark: " + ", ".join(features) + ".") if features else "")
    if title:
        ask += " Reference title: %s." % title
    content = [{"type": "text", "text": ask}] + [image_part(i) for i in images]
    messages = [{"role": "system", "content": pack["system.md"]}, {"role": "user", "content": content}]
    report, text = None, ""
    for i in range(rounds + 1):
        text, _ = chat(base_url, model, messages, key)
        report = diagnose.diagnose_text(text)
        if log:
            log("trace round %d: %s" % (i, "clean" if report["ok"] else report["repair_text"].splitlines()[0]))
        if report["ok"]:
            break
        messages += [{"role": "assistant", "content": text}, {"role": "user", "content": report["repair_text"]}]
    return report, text


class Budget:
    """The run's limits as counters: wall clock, check and review rounds, tokens and cost."""

    def __init__(self, lim, max_total_tokens=None, max_cost=None, prices=(0.0, 0.0), clock=time.monotonic):
        self.lim, self.clock = lim, clock
        self.deadline = None if lim["wall_clock_s"] is None else clock() + lim["wall_clock_s"]
        self.max_total_tokens, self.max_cost, self.prices = max_total_tokens, max_cost, prices
        self.checks = self.reviews = 0
        self.tokens = {"prompt_tokens": 0, "completion_tokens": 0}

    def left(self):
        return float("inf") if self.deadline is None else self.deadline - self.clock()

    def cost(self):
        return (self.tokens["prompt_tokens"] * self.prices[0] + self.tokens["completion_tokens"] * self.prices[1]) / 1e6

    def spent(self):
        """The limit already reached, or None."""
        if self.left() <= 0:
            return "wall clock (%gs)" % self.lim["wall_clock_s"]
        if self.max_total_tokens and sum(self.tokens.values()) >= self.max_total_tokens:
            return "token ceiling (%d)" % self.max_total_tokens
        if self.max_cost and self.cost() >= self.max_cost:
            return "cost ceiling ($%g)" % self.max_cost
        return None

    def ask(self, base_url, model, messages, key):
        why = self.spent()
        if why:
            raise LimitReached(why)
        try:
            text, usage = chat(base_url, model, messages, key, timeout=max(5, min(600, self.left())))
        except RunnerError:
            if self.left() <= 0:
                raise LimitReached("wall clock (%gs)" % self.lim["wall_clock_s"])
            raise
        self.count(usage)
        return text

    def count(self, usage):
        for k in self.tokens:
            self.tokens[k] += int((usage or {}).get(k, 0) or 0)


def _rank(report, doc):
    """Higher is better: parsed, valid, free of visible defects, fewest problems."""
    return (doc is not None, report["ok"], not report["needs_repair"], -report["errors"], -report["warnings"])


def _host_note(lim, research, images):
    web = [i for i in images if i.startswith(("http://", "https://"))]
    lines = ["", "Host: the construct author runner. Tier: %s (wall clock %s, %d check rounds, %s review rounds)."
             % (lim["tier"], "none" if lim["wall_clock_s"] is None else "%d s" % lim["wall_clock_s"],
                lim["check_rounds"], "no cap on" if lim["review_rounds"] is None else lim["review_rounds"]),
             "This host has no web search tool. Every answer you send is checked, and the best valid one is "
             "saved at once: send a complete scene first, then improve it."]
    if research == "off":
        lines.append('Research: off (the user said so). Record "authoring": {"tier": "%s", "research": "off"}.' % lim["tier"])
    elif images:
        lines.append("Reference images are attached%s: they are this run's research. Cite each as a source "
                     '(kind reference_image) and record "research": "done" with their ids in authoring.sources.'
                     % (" (%d from the web)" % len(web) if web else ""))
    else:
        lines.append('Research: none is possible here. Record "research": "not_needed" for a generic subject, '
                     'otherwise "unavailable", and say in authoring.next what research would improve.')
    return "\n".join(lines)


def _stamp(doc, lim, budget, outcome, nxt, research, critic_record=None):
    """Record how the construct was made in its authoring block, kept valid against the scene's sources."""
    a = dict(doc.get("authoring") or {}) if isinstance(doc.get("authoring"), dict) else {}
    a["tier"] = lim["tier"]
    known = {s.get("id"): s.get("kind") for s in doc.get("sources", []) if isinstance(s, dict)}
    a["sources"] = [s for s in a.get("sources", []) if isinstance(s, str) and s in known]
    if research == "off":
        a["research"] = "off"
    elif a.get("research") not in tiers.RESEARCH_RECORD:
        a["research"] = "unavailable"
    if a["research"] == "done" and not any(known.get(s) != "user_request" for s in a["sources"]):
        a["research"] = "skipped"  # claimed without a cited source: it came from what the model knew
    if not a["sources"]:
        a.pop("sources")
    a["review_rounds"] = budget.reviews
    a.pop("critic", None)
    if critic_record and critic_record["scene_sha256"] == tiers.critic_hash(doc):
        a["critic"] = dict(critic_record)  # only for the version the critic judged
    elif outcome in ("good", "outstanding"):
        outcome = "self-reviewed"
    a["outcome"] = outcome
    own = a.get("next") if isinstance(a.get("next"), list) else []
    notes = [n for n in own + list(nxt) if isinstance(n, str) and n.strip()]
    if outcome == "limit" and not notes:
        notes = ["another review round" + (" at the showcase tier" if lim["tier"] != "showcase" else "")]
    seen, merged = set(), []
    for n in notes:
        if n.lower() not in seen:
            seen.add(n.lower())
            merged.append(n[:300])
    if merged:
        a["next"] = merged[:tiers.MAX_NEXT]
    else:
        a.pop("next", None)
    doc["authoring"] = a
    return doc


def _captures(text, workdir, log):
    """Render a clean draft and capture what the review looks at; [] when no browser is available."""
    from . import render, studio
    doc, _ = diagnose.parse_text(text)
    folder = Path(tempfile.mkdtemp(prefix="review-", dir=workdir))
    path = folder / "draft.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    try:
        studio.build(str(path), str(folder / "out"))
        render.review(str(folder / "out" / "construct.html"), str(folder / "out" / "review"), 1280, 800,
                      sheets=("views", "assembly"))
    except Exception as exc:  # no browser, or a capture failure: review is skipped, never faked
        if log:
            log("review skipped: %s" % str(exc).splitlines()[0][:160])
        return []
    rv = folder / "out" / "review"
    return [str(p) for p in (rv / "hero.png", rv / "sheet-views.png", rv / "sheet-assembly.png", rv / "view-open.png")
            if p.exists()]


def _verdict(text):
    """The review's verdict: ("good"|"improve", weakest, next list). Good needs every score >= 2."""
    doc, _ = diagnose.parse_text(text)
    if not isinstance(doc, dict):
        return "improve", None, []
    scores = doc.get("scores") if isinstance(doc.get("scores"), dict) else {}
    low = [k for k, v in scores.items() if isinstance(v, (int, float)) and v < 2]
    verdict = "good" if doc.get("verdict") == "good" and not low else "improve"
    nxt = [n for n in doc.get("next", []) if isinstance(n, str)] if isinstance(doc.get("next"), list) else []
    weakest = doc.get("weakest") if isinstance(doc.get("weakest"), str) else (low[0] if low else None)
    return verdict, weakest, nxt


def author(request, base_url, model, key=None, use_params=False, rounds=None, log=None, images=(), tier=None,
           research=None, vision=False, limit_overrides=None, max_total_tokens=None, max_cost=None,
           prices=(0.0, 0.0), workdir=None, clock=time.monotonic, save=None, critic=None, checkpoints=None):
    """Draft, check, repair, then (with vision) review and improve, inside the tier's limits.

    Without a critic the author reviews its own captures (outcome at best "self-reviewed").
    With `critic` ({"base_url", "model", "key"}) each review is an independent critic's: a fresh
    context with the references beside renders from the same views; its ranked defects are the
    next instruction, and only its verdict can make the outcome "good" or "outstanding". The
    masterpiece tier always uses the critic and stops only at "outstanding", a token or cost
    ceiling, or the user (Ctrl-C). `checkpoints` is a folder that gets every clean draft.

    Returns (report, text, token totals, history, meta) for the best draft; meta has the tier,
    outcome, why it stopped and the next improvements.
    `save(text)` is called with every new best valid draft (stamped "unreviewed" until the run
    ends), so a valid construct is on disk even if the host stops the run."""
    from . import critic as critic_mod
    asked = tiers.from_request(request)
    tier = tier or asked.get("tier") or tiers.DEFAULT
    research = research or asked.get("research") or "auto"
    overrides = dict(limit_overrides or {})
    if rounds is not None:
        overrides["check_rounds"] = rounds
    lim = tiers.limits(tier, **overrides)
    uncapped = lim["review_rounds"] is None
    if tier == tiers.UNCAPPED:
        if not critic:
            critic = {"base_url": base_url, "model": model, "key": key}
        vision = True
    refs = critic_mod.parse_references(images)
    images = [r for _, r in refs]
    web = [i for i in images if i.startswith(("http://", "https://"))]
    if research == "off" and web:
        raise RunnerError("research is off: attach only the user's own images, not web references")
    if len(web) > lim["images"]:
        raise RunnerError("%d web reference images is beyond the %s tier's limit of %d (raise it with --max-images)"
                          % (len(web), tier, lim["images"]))
    budget = Budget(lim, max_total_tokens, max_cost, prices, clock)
    workdir = workdir or tempfile.mkdtemp(prefix="construct-author-")
    pack = prompts.build()
    text0 = (pack["params.md"] if use_params else pack["scene.md"]) + "\n\nThe request:\n" + request
    text0 += _host_note(lim, research, images)
    if critic:
        text0 += ("\nAn independent critic will judge each clean draft against the references; its ranked defects "
                  "come back to you. Write authoring.identity (the features that make the subject itself, each "
                  "with its parts) before the parts.")
    messages = [{"role": "system", "content": pack["system.md"]},
                {"role": "user", "content": [{"type": "text", "text": text0}] + [image_part(i) for i in images]
                 if images else text0}]
    history, best, last, stop, nxt = [], None, None, None, []
    critic_record, round_checks = None, [0]

    def checkpoint(text, doc):
        if checkpoints and isinstance(doc, dict):
            Path(checkpoints).mkdir(parents=True, exist_ok=True)
            Path(checkpoints, "round-%02d.json" % budget.reviews).write_text(
                json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def check_loop():
        nonlocal best, last
        while True:
            used = round_checks[0] if uncapped else budget.checks
            if used >= lim["check_rounds"]:
                raise LimitReached("check rounds (%d%s)" % (lim["check_rounds"], " in one round" if uncapped else ""))
            text = budget.ask(base_url, model, messages, key)
            budget.checks += 1
            round_checks[0] += 1
            report = diagnose.diagnose_text(text)
            doc, _ = diagnose.parse_text(text)
            history.append({"round": len(history), "ok": report["ok"], "needs_repair": report["needs_repair"],
                            "errors": report["errors"], "warnings": report["warnings"]})
            if log:
                log("check %d: %s" % (budget.checks, "clean" if not report["needs_repair"]
                                      else report["repair_text"].splitlines()[0]))
            last = (report, text)
            if best is None or _rank(report, doc) >= _rank(best[0], best[2]):
                best = (report, text, doc)
                if save and report["ok"] and isinstance(doc, dict):
                    save(json.dumps(_stamp(json.loads(json.dumps(doc)), lim, budget, "unreviewed", nxt, research),
                                    indent=2, ensure_ascii=False))
            if not report["needs_repair"]:
                checkpoint(text, doc)
                return
            messages.extend([{"role": "assistant", "content": text}, {"role": "user", "content": report["repair_text"]}])

    def critic_round():
        """One independent critique of the last clean draft; returns its verdict or None (no browser)."""
        nonlocal critic_record, nxt
        doc, _ = diagnose.parse_text(last[1])
        folder = Path(workdir, "critique-%02d" % (budget.reviews + 1))
        folder.mkdir(parents=True, exist_ok=True)
        draft = folder / "draft.json"
        draft.write_text(json.dumps(doc), encoding="utf-8")
        why = budget.spent()
        if why:
            raise LimitReached(why)
        try:
            pk = critic_mod.packet(str(draft), str(folder), ["%s=%s" % (v, r) if v else r for v, r in refs], request)
        except Exception as exc:  # no browser: the critic cannot see, so it is not faked
            if log:
                log("critique skipped: %s" % str(exc).splitlines()[0][:160])
            return None
        budget.reviews += 1
        answer, usage = critic_mod.run(pk, str(folder), critic["base_url"], critic["model"], critic.get("key"), log=log)
        budget.count(usage)
        (folder / "critique.json").write_text(json.dumps(answer, indent=2) + "\n", encoding="utf-8")
        _, verdict = critic_mod.record(doc, answer, critic["model"])
        critic_record = {"scene_sha256": answer["scene_sha256"], "verdict": verdict, "scores": dict(answer["scores"]),
                         "round": budget.reviews, "model": str(critic["model"])[:120],
                         "defects": len(answer.get("defects", []))}
        nxt = ["%s: %s" % (d["severity"], d["fix"]) for d in critic_mod.ranked(answer, 5)]
        if log:
            log("critique %d: %s (lowest score %d, %d defects)" % (budget.reviews, verdict,
                                                                   min(answer["scores"].values()), len(answer["defects"])))
        if verdict == "outstanding" or (verdict == "good" and not uncapped):
            return verdict
        messages.extend([{"role": "assistant", "content": last[1]},
                         {"role": "user", "content": critic_mod.defects_text(answer)}])
        return "improve"

    outcome = "unreviewed"
    try:
        check_loop()
        while vision and (uncapped or budget.reviews < lim["review_rounds"]):
            if not uncapped and budget.left() < max(REVIEW_MARGIN_S, lim["wall_clock_s"] * (1 - tiers.WRAP_UP)):
                raise LimitReached("wrap-up at %d%% of the wall clock" % (tiers.WRAP_UP * 100))
            if critic:
                v = critic_round()
                if v is None:
                    break
                if v in ("outstanding", "good"):
                    outcome = v
                    break
                round_checks[0] = 0
                check_loop()
                continue
            shots = _captures(last[1], workdir, log)
            if not shots:
                break
            budget.reviews += 1
            messages.extend([{"role": "assistant", "content": last[1]},
                             {"role": "user", "content": [{"type": "text", "text": pack["vision-review.md"]
                                                           + "\n\nThe request was:\n" + request}]
                              + [image_part(p) for p in shots]}])
            answer = budget.ask(base_url, model, messages, key)
            verdict, weakest, nxt = _verdict(answer)
            if log:
                log("review %d: %s%s" % (budget.reviews, verdict, " (weakest: %s)" % weakest if weakest else ""))
            if verdict == "good":
                outcome = "self-reviewed"
                break
            messages.extend([{"role": "assistant", "content": answer},
                             {"role": "user", "content": "Improve the weakest point%s now. Send the whole corrected "
                              "JSON object only." % (" (%s)" % weakest if weakest else "")}])
            check_loop()
        else:
            if vision and lim["review_rounds"] and budget.reviews >= lim["review_rounds"]:
                raise LimitReached("review rounds (%d)" % lim["review_rounds"])
    except LimitReached as why:
        stop, outcome = str(why), "limit"
        if log:
            log("stopped: %s; delivering the best draft so far" % stop)
    except KeyboardInterrupt:
        stop, outcome = "the user", "limit"
        if log:
            log("stopped by the user; delivering the best draft so far")
    if outcome in ("good", "outstanding") and last is not None:
        rep_, text_ = last
        best = (rep_, text_, diagnose.parse_text(text_)[0])  # the version the critic judged
    report, text, doc = best if best else (None, "", None)
    if isinstance(doc, dict):
        doc = _stamp(doc, lim, budget, outcome, nxt, research, critic_record)
        text = json.dumps(doc, indent=2, ensure_ascii=False)
        report = diagnose.diagnose_text(text)
    meta = {"tier": tier, "limits": lim, "outcome": (doc or {}).get("authoring", {}).get("outcome", outcome),
            "stopped_by": stop, "reviews": budget.reviews, "checks": budget.checks,
            "seconds": round(clock() - (budget.deadline - lim["wall_clock_s"]) if budget.deadline is not None else 0, 1),
            "cost": round(budget.cost(), 6), "next": (doc or {}).get("authoring", {}).get("next", [])}
    return report, text, dict(budget.tokens), history, meta


def _critic_from(args, key):
    """The critic's endpoint: --critic (same endpoint and model), or --critic-model / --critic-base-url."""
    if not (getattr(args, "critic", False) or getattr(args, "critic_model", None) or getattr(args, "critic_base_url", None)):
        return None
    ckey = os.environ.get(args.critic_key_env) if getattr(args, "critic_key_env", None) else key
    return {"base_url": args.critic_base_url or args.base_url, "model": args.critic_model or args.model, "key": ckey}


def _limits_from(args):
    out = {}
    for k, attr in (("wall_clock_s", "max_seconds"), ("review_rounds", "review_rounds"), ("images", "max_images")):
        if getattr(args, attr, None) is not None:
            out[k] = getattr(args, attr)
    return out


def run(args, out):
    key = os.environ.get(args.key_env) if args.key_env else None
    if args.key_env and not key:
        raise RunnerError("the environment variable %s is not set" % args.key_env)
    if args.max_cost and not (args.price_in or args.price_out):
        raise RunnerError("--max-cost needs --price-in and --price-out (USD per million tokens)")
    def save(text):
        tmp = args.out + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        os.replace(tmp, args.out)

    try:
        report, text, totals, history, meta = author(
            args.request, args.base_url, args.model, key, args.params, args.rounds,
            log=lambda m: out.write(m + "\n"), images=args.reference or (), tier=args.tier, research=args.research,
            vision=args.vision, limit_overrides=_limits_from(args), max_total_tokens=args.max_total_tokens,
            max_cost=args.max_cost, prices=(args.price_in or 0.0, args.price_out or 0.0),
            critic=_critic_from(args, key), checkpoints=args.out + ".checkpoints",
            workdir=str(Path(args.out).resolve().parent), save=save)
    except tiers.TierError as exc:
        raise RunnerError(str(exc))
    doc, _ = diagnose.parse_text(text)
    if doc is None:
        raise RunnerError("the model never produced a JSON object" + (" (%s)" % meta["stopped_by"] if meta["stopped_by"] else ""))
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    out.write("wrote %s (%s; %s tier; %d rounds, %d reviews; outcome %s%s; %d prompt + %d completion tokens)\n" % (
        args.out, "valid" if report["ok"] else "NOT valid", meta["tier"], len(history), meta["reviews"],
        meta["outcome"], " — stopped by " + meta["stopped_by"] if meta["stopped_by"] else "",
        totals["prompt_tokens"], totals["completion_tokens"]))
    for n in meta["next"]:
        out.write("next: %s\n" % n)
    return 0 if report["ok"] else 1


def run_trace_image(args, out):
    key = os.environ.get(args.key_env) if args.key_env else None
    if args.key_env and not key:
        raise RunnerError("the environment variable %s is not set" % args.key_env)
    feats = [f for f in (args.features or "").split(",") if f]
    report, text = trace_image(args.image, args.what, args.base_url, args.model, key, feats, title=args.title,
                               log=lambda m: out.write(m + "\n"))
    doc, _ = diagnose.parse_text(text)
    if not report["ok"] or doc is None:
        raise RunnerError("the model did not produce a valid trace:\n" + report["repair_text"])
    from . import trace as trace_mod
    result = trace_mod.fit(doc, args.fit, args.origin, args.points)
    result["trace"] = doc
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    out.write("wrote %s: %d profile points, %.3f x %.3f m, fitted %s\n" % (
        args.out, len(result["profile"]), result["size_m"][0], result["size_m"][1], args.fit))
    return 0
