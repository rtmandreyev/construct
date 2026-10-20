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


def author(request, base_url, model, key=None, use_params=False, rounds=4, log=None):
    """Draft, check and repair; returns (report, text, usage totals, transcript of reports)."""
    pack = prompts.build()
    messages = [{"role": "system", "content": pack["system.md"]},
                {"role": "user", "content": (pack["params.md"] if use_params else pack["scene.md"])
                 + "\n\nThe request:\n" + request}]
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
                                           log=lambda m: out.write(m + "\n"))
    doc, _ = diagnose.parse_text(text)
    if doc is None:
        raise RunnerError("the model never produced a JSON object")
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    out.write("wrote %s (%s; %d rounds; %d prompt + %d completion tokens)\n" % (
        args.out, "valid" if report["ok"] else "NOT valid", len(history), totals["prompt_tokens"], totals["completion_tokens"]))
    return 0 if report["ok"] else 1
