"""A minimal author loop for any OpenAI-compatible chat endpoint (standard library only).

    construct author "a 1970s desk fan with a round cage" --base-url https://api.deepseek.com/v1 \
        --model deepseek-chat --key-env DEEPSEEK_API_KEY --out fan.json [--params] [--rounds 4]

It sends the prompts (system.md, then params.md or scene.md), the request, then the repair
text until the draft is valid and free of visible defects, and writes the final JSON. The key is
read from the environment variable you name and is never written anywhere; the endpoint is the
one you give. Works with DeepSeek, OpenRouter, OpenAI, Ollama, llama.cpp and LM Studio servers.
"""

import json
import os
import urllib.error
import urllib.request

from . import diagnose, prompts


class RunnerError(Exception):
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


def author(request, base_url, model, key=None, use_params=False, rounds=4, log=None, images=()):
    """Draft, check and repair; returns (report, text, usage totals, transcript of reports)."""
    pack = prompts.build()
    text0 = (pack["params.md"] if use_params else pack["scene.md"]) + "\n\nThe request:\n" + request
    if images:
        text0 += ("\n\nReference images are attached. Measure proportions and shapes from them; never copy or "
                  "embed them; cite each as a source of kind reference_image (rights reference_only unless the "
                  "user owns it) and keep traced geometry inferred.")
    messages = [{"role": "system", "content": pack["system.md"]},
                {"role": "user", "content": [{"type": "text", "text": text0}] + [image_part(i) for i in images]
                 if images else text0}]
    totals, history, text, report = {"prompt_tokens": 0, "completion_tokens": 0}, [], "", None
    for i in range(rounds + 1):
        text, usage = chat(base_url, model, messages, key)
        for k in totals:
            totals[k] += int(usage.get(k, 0) or 0)
        report = diagnose.diagnose_text(text)
        history.append({"round": i, "ok": report["ok"], "needs_repair": report["needs_repair"],
                        "errors": report["errors"], "warnings": report["warnings"]})
        if log:
            log("round %d: %s" % (i, "clean" if not report["needs_repair"] else report["repair_text"].splitlines()[0]))
        if not report["needs_repair"]:
            break
        messages += [{"role": "assistant", "content": text}, {"role": "user", "content": report["repair_text"]}]
    return report, text, totals, history


def run(args, out):
    key = os.environ.get(args.key_env) if args.key_env else None
    if args.key_env and not key:
        raise RunnerError("the environment variable %s is not set" % args.key_env)
    report, text, totals, history = author(args.request, args.base_url, args.model, key, args.params, args.rounds,
                                           log=lambda m: out.write(m + "\n"), images=args.reference or ())
    doc, _ = diagnose.parse_text(text)
    if doc is None:
        raise RunnerError("the model never produced a JSON object")
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    out.write("wrote %s (%s; %d rounds; %d prompt + %d completion tokens)\n" % (
        args.out, "valid" if report["ok"] else "NOT valid", len(history), totals["prompt_tokens"], totals["completion_tokens"]))
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
