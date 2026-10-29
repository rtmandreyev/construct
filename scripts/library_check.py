#!/usr/bin/env python3
"""The machine checks: NetLogo's Models Library through `construct:run`, with no AI and no judgement of taste.

    python3 scripts/library_check.py --netlogo "/Applications/NetLogo 7.0.4" --javac PATH --out DIR [--only NAME ...] [--software]

For each two-dimensional model (3D models and Code Examples left out), one at a time: a copy with
`extensions [construct]` added runs `random-seed 5` then `construct:run` headless (Drive.java), and
the construct it draws is checked:
- the audit passes and the data lock holds;
- the replay's clock ends at the run's last tick, and its counts are numbers;
- in headless Chrome, how many labels leave the window, overlap another label, or sit under the
  reading panel or the replay bar.

Writes DIR/check.jsonl (a line per model, as it goes) and prints a summary. A model that needs a
player, a classroom or an extension NetLogo doesn't bundle fails to record; that is reported, not
an error of Construct's. One NetLogo and one browser at a time: about 2 GB of memory at most.
"""

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from construct_hologram import netlogo, render  # noqa: E402

PROBE = """new Promise(done => { if (window.HOLO && HOLO.renderAt) HOLO.renderAt(30); setTimeout(() => {   // a frame drawn now, labels and all
  const W = innerWidth, H = innerHeight, box = e => e.getBoundingClientRect();
  const tags = [...document.querySelectorAll('#overlay .labels .label')].map(box);
  const blocks = [...document.querySelectorAll('.rd-how, .rd-bar')].map(box);
  const hit = (a, b) => a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
  let overlap = 0;
  for (let i = 0; i < tags.length; i++) for (let j = i + 1; j < tags.length; j++) if (hit(tags[i], tags[j])) overlap++;
  done({legend: ((window.HOLOGRAM_GEOMETRY || {}).annotations || []).length, shown: !!(window.HOLO && HOLO.hologram && HOLO.hologram.opt.labels),
        page: location.pathname.split('/').slice(-2, -1)[0], labels: tags.length, out: tags.filter(r => r.left < 0 || r.top < 0 || r.right > W || r.bottom > H).length,
        overlap, under: tags.filter(r => blocks.some(b => hit(r, b))).length});
}, 300); })"""


def models(netlogo_dir, only):
    base = Path(netlogo_dir) / "models"
    out = [p for p in sorted(base.rglob("*.nlogox")) if "3D" not in p.parts and "Code Examples" not in str(p)]
    return [p for p in out if not only or p.stem in only]


def prepared(model, work, zip_path):
    """A copy of the model with `extensions [construct]`, its data beside it, the extension unzipped."""
    shutil.rmtree(work, ignore_errors=True)
    (work / "construct").mkdir(parents=True)
    zipfile.ZipFile(zip_path).extractall(work / "construct")
    for extra in model.parent.iterdir():
        if extra.is_file() and extra.suffix.lower() not in (".nlogox", ".nlogo", ".png", ".jsonl"):
            shutil.copyfile(extra, work / extra.name)
        elif extra.is_dir() and not any(extra.rglob("*.nlogox")) and not extra.name.endswith("-construct"):
            shutil.copytree(extra, work / extra.name)
    t = model.read_text(encoding="utf-8", errors="replace")
    code = re.search(r"<code><!\[CDATA\[(.*?)\]\]></code>", t, re.S) or re.search(r"<code>(.*?)</code>", t, re.S)
    src = code.group(1)
    m = re.search(r"(?mi)^\s*extensions\s*\[([^\]]*)\]", src)
    src = (src[:m.start()] + "extensions [%s construct]" % m.group(1).strip() + src[m.end():]) if m \
        else "extensions [construct]\n" + src
    (work / model.name).write_text(t[:code.start(1)] + src + t[code.end(1):], encoding="utf-8")
    return work / model.name


def run_model(netlogo_dir, drive_dir, copy, timeout):
    nl = Path(netlogo_dir)
    jar = next(nl.glob("**/app/netlogo-*.jar"))
    java = next((p for p in (nl / "runtime/Contents/Home/bin/java", nl / "lib/runtime/bin/java", nl / "runtime/bin/java.exe")
                 if p.exists()), "java")
    bundled = ["-Dnetlogo.extensions.dir=" + str(nl / "extensions")] if (nl / "extensions").is_dir() else []
    proc = subprocess.Popen([str(java), "-Xmx1536m", "-Djava.awt.headless=true"] + bundled + ["-cp", os.pathsep.join([str(jar), str(drive_dir)]),
                             "Drive", str(copy), "random-seed 5", "construct:run"], cwd=copy.parent,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        out = (proc.communicate()[0] or "") + "\nTIMEOUT"
    return [l for l in out.splitlines() if l.startswith(("construct:", "ERROR", "TIMEOUT"))]


def check(built, run_file):
    """The data checks: audit, lock, clock, counts."""
    found = {}
    audit = json.loads((built / "audit.json").read_text())
    found["audit"] = "pass" if not audit.get("errors") else "fail: " + "; ".join(e.get("code", "?") for e in audit["errors"])[:200]
    scene = json.loads((built / "scene.json").read_text())
    found["view"] = next((f["value"] for f in scene["facts"] if f["key"] == "view"), None)
    found["window"] = next((f["value"] for f in scene["facts"] if f["key"] == "window"), None)
    found["lock"] = "holds" if netlogo.lock_problem(scene) is None else "broken"
    run = netlogo.read_run(run_file)
    clock = (scene.get("reading") or {}).get("clock") or {}
    last = run["end"] if run["end"] is not None else run["frames"][-1]["t"]
    problems = []
    if clock and abs(clock.get("to", 0) - max(1, last)) > 1e-6:
        problems.append("clock ends at %s, the run at %s" % (clock.get("to"), last))
    for s in (scene.get("reading") or {}).get("series", []):
        if not all(isinstance(v[1], (int, float)) for v in s["values"]):
            problems.append("a count that is not a number: " + s["name"])
    found["data"] = "ok" if not problems else "; ".join(problems)
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--netlogo", required=True)
    ap.add_argument("--javac", default=shutil.which("javac") or "javac")
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", nargs="*", default=[], help="model names (stems) to check, instead of the whole library")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--software", action="store_true", help="software WebGL for the label probe, leaving the GPU free")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="construct-check-"))
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_netlogo_extension.py"), "--netlogo", a.netlogo,
                    "--javac", a.javac, "--out", str(tmp)], check=True, capture_output=True)
    zip_path = next(tmp.glob("construct-*.zip"))
    jar = next(Path(a.netlogo).glob("**/app/netlogo-*.jar"))
    subprocess.run([a.javac, "--release", "17", "-cp", str(jar), "-d", str(tmp / "drive"),
                    str(ROOT / "hosts" / "netlogo" / "test" / "Drive.java")], check=True)
    browser = None
    log = (out / "check.jsonl").open("w", encoding="utf-8")
    results = []
    try:
        for model in models(a.netlogo, a.only):
            slug = re.sub(r"[^a-z0-9]+", "-", model.stem.lower()).strip("-") or "netlogo-run"
            work = tmp / "work"
            t0 = time.time()
            said = run_model(a.netlogo, tmp / "drive", prepared(model, work, zip_path), a.timeout)
            entry = {"model": str(model.relative_to(Path(a.netlogo) / "models")), "seconds": round(time.time() - t0, 1),
                     "said": said[:3]}
            built, run_file = work / (slug + "-construct"), work / (slug + "-run.jsonl")
            if (built / "construct.html").exists() and run_file.exists():
                entry.update(check(built, run_file))
                try:
                    if browser is None and a.software:
                        browser = render.Browser(1280, 800, 1.0, gpu=False)
                        browser.open(render._url(built / "construct.html", t=30, m=slug))
                    elif browser is None:
                        browser = render.open_browser(render._url(built / "construct.html", t=30, m=slug), 1280, 800, 1.0)
                    else:
                        browser.open(render._url(built / "construct.html", t=30, m=slug))
                    url = render._url(built / "construct.html", t=30, m=slug)
                    for _ in range(200):   # the new page itself, ready: not the last one, still on screen
                        if browser.evaluate("location.href + '|' + ((document.body && document.body.getAttribute('data-ready')) || '')") == url + "|1":
                            break
                        time.sleep(0.05)
                    entry["labels"] = browser.evaluate(PROBE)
                except Exception as exc:   # a page that will not open is a finding too
                    entry["labels"] = {"error": str(exc)[:160]}
                    if browser is not None:
                        browser.close()
                    browser = None
            else:
                entry["drawn"] = False
            results.append(entry)
            log.write(json.dumps(entry) + "\n")
            log.flush()
            print(json.dumps(entry)[:220], flush=True)
    finally:
        log.close()
        if browser is not None:
            browser.close()
        shutil.rmtree(tmp, ignore_errors=True)
    drawn = [r for r in results if r.get("drawn", True)]
    bad = lambda k, ok: [r for r in drawn if r.get(k) != ok]
    labels = [r["labels"] for r in drawn if isinstance(r.get("labels"), dict) and "error" not in r["labels"]]
    print("\n%d models; drawn %d; audit failures %d; lock broken %d; data problems %d; pages with labels out of the "
          "window %d, overlapping %d, under the panel or bar %d" % (
              len(results), len(drawn), len(bad("audit", "pass")), len(bad("lock", "holds")), len(bad("data", "ok")),
              sum(1 for l in labels if l["out"]), sum(1 for l in labels if l["overlap"]), sum(1 for l in labels if l["under"])))


if __name__ == "__main__":
    main()
