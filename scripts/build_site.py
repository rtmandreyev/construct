"""Build the examples gallery as a static site (for the gh-pages branch, served from its root).

    python3 scripts/build_site.py --out site                 # build the site into ./site
    python3 scripts/build_site.py --set-url OWNER/REPO       # move every link to another repository

Every example in examples/ (listed in examples/examples.json) is compiled with this checkout's
compiler into a self-contained construct.html, beside its hero image and its own page. The site
uses relative links only, needs no server code and loads nothing from other hosts.

The public addresses come from OWNER and REPO below and nowhere else: `--set-url` rewrites them
here and in the documents that link to the site.
"""

import argparse
import html
import importlib
import json
import re
import shutil
import sys
from pathlib import Path

OWNER = "rtmandreyev"
REPO = "construct"
SITE_URL = "https://%s.github.io/%s/" % (OWNER, REPO)
REPO_URL = "https://github.com/%s/%s" % (OWNER, REPO)

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
LINKED = ["README.md", "PUBLISHING.md", "docs/USING.md", "examples/README.md"]  # documents that link to the site

CSS = """
:root { color-scheme: dark; --bg: #050205; --panel: #0e0810; --line: #2a1d30; --ink: #f1e9f7; --dim: #a597b3;
        --accent: #d16bd0; --glow: rgba(209, 107, 208, .35); }
* { box-sizing: border-box; }
html, body { margin: 0; background: var(--bg); color: var(--ink);
             font: 16px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }
a { color: var(--ink); }
a:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
header.site { padding: 56px 20px 28px; max-width: 1180px; margin: 0 auto; }
header.site .eyebrow { letter-spacing: .22em; font-size: 12px; color: var(--accent); text-transform: uppercase; }
header.site h1 { font-size: clamp(30px, 5vw, 48px); line-height: 1.1; margin: 10px 0 12px; font-weight: 650; }
header.site p { color: var(--dim); max-width: 760px; margin: 0 0 18px; }
.links { display: flex; flex-wrap: wrap; gap: 10px; }
.button { display: inline-block; padding: 9px 16px; border: 1px solid var(--line); border-radius: 999px;
          text-decoration: none; font-size: 14px; background: var(--panel); }
.button:hover { border-color: var(--accent); box-shadow: 0 0 18px var(--glow); }
main { max-width: 1180px; margin: 0 auto; padding: 0 20px 64px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 320px), 1fr)); gap: 18px; }
.card { display: block; text-decoration: none; background: var(--panel); border: 1px solid var(--line);
        border-radius: 14px; overflow: hidden; transition: border-color .15s, box-shadow .15s, transform .15s; }
.card:hover { border-color: var(--accent); box-shadow: 0 0 26px var(--glow); transform: translateY(-2px); }
.card img { display: block; width: 100%; aspect-ratio: 16 / 10; object-fit: cover; background: #000; }
.card .body { padding: 12px 14px 15px; }
.card h2 { font-size: 17px; margin: 0 0 4px; font-weight: 600; }
.card .prov { font-size: 13px; color: var(--dim); margin: 0; }
footer.site { max-width: 1180px; margin: 0 auto; padding: 24px 20px 48px; color: var(--dim); font-size: 13px;
              border-top: 1px solid var(--line); }
.viewer { display: flex; flex-direction: column; min-height: 100vh; }
.bar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 18px; padding: 12px 20px;
       border-bottom: 1px solid var(--line); background: var(--panel); }
.bar h1 { font-size: 18px; margin: 0; font-weight: 600; }
.bar .prov { color: var(--dim); font-size: 13px; margin: 0; flex: 1 1 260px; }
.bar nav { display: flex; gap: 8px; flex-wrap: wrap; }
.stage { position: relative; flex: 1 1 auto; min-height: 62vh; background: #000; }
.stage iframe { position: absolute; inset: 0; width: 100%; height: 100%; border: 0; }
.hint { padding: 10px 20px 18px; color: var(--dim); font-size: 13px; }
.hint kbd { border: 1px solid var(--line); border-radius: 4px; padding: 0 5px; font-size: 12px; color: var(--ink); }
"""


def _load_examples():
    return json.loads((EXAMPLES / "examples.json").read_text(encoding="utf-8"))["examples"]


def provenance(ex):
    """The one-line provenance every card, page and README carries."""
    return "%s · %s · made with %s" % (ex["model"], ex["how"], ex["build"])


def _page(title, body, depth, description):
    up = "../" * depth
    return ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            "<title>%s</title>\n<meta name=\"description\" content=\"%s\">\n"
            "<link rel=\"stylesheet\" href=\"%sassets/site.css\">\n</head>\n<body>\n%s\n</body>\n</html>\n"
            % (html.escape(title), html.escape(description), up, body))


def index_page(examples):
    cards = "\n".join(
        "<a class=\"card\" href=\"examples/%s/\"><img src=\"examples/%s/thumb.jpg\" alt=\"%s, a holographic construct\" "
        "loading=\"lazy\" width=\"720\" height=\"450\"><div class=\"body\"><h2>%s</h2><p class=\"prov\">%s</p></div></a>"
        % (e["slug"], e["slug"], html.escape(e["title"]), html.escape(e["title"]), html.escape(provenance(e)))
        for e in examples)
    body = ("<header class=\"site\"><div class=\"eyebrow\">Construct · examples</div>"
            "<h1>Holographic constructs, built by AI agents</h1>"
            "<p>Each construct was written as a short declarative scene by a model, then validated, audited, compiled "
            "and rendered by Construct. Open one to watch it assemble; drag to orbit, press R to replay and L for "
            "labels.</p><div class=\"links\"><a class=\"button\" href=\"%s\">Construct on GitHub</a>"
            "<a class=\"button\" href=\"%s#three-modes\">How they were made</a></div></header>"
            "<main><div class=\"grid\">\n%s\n</div></main>"
            "<footer class=\"site\">Construct is MIT licensed. Product and place names belong to their owners; each "
            "construct is an independent reconstruction from public references, not an official model. "
            "<a href=\"%s\">Source and documentation</a>.</footer>" % (REPO_URL, REPO_URL, cards, REPO_URL))
    return _page("Construct · examples", body, 0, "A gallery of holographic constructs built by AI agents with Construct.")


def example_page(ex):
    body = ("<div class=\"viewer\"><div class=\"bar\"><h1>%s</h1><p class=\"prov\">%s%s</p><nav>"
            "<a class=\"button\" href=\"../../\">All examples</a>"
            "<a class=\"button\" href=\"construct.html\">Full screen</a>"
            "<a class=\"button\" href=\"scene.json\">Scene</a>"
            "<a class=\"button\" href=\"%s/tree/main/examples/%s\">Source</a></nav></div>"
            "<div class=\"stage\"><iframe src=\"construct.html?ui=0\" title=\"%s, live construct\" "
            "allowfullscreen></iframe></div>"
            "<p class=\"hint\">Drag to orbit, scroll to zoom. Click the construct first, then <kbd>R</kbd> replays the "
            "assembly, <kbd>L</kbd> shows labels, <kbd>P</kbd> shows how each part is known, <kbd>1</kbd>–<kbd>6</kbd> "
            "change the view and <kbd>space</kbd> pauses.</p></div>"
            % (html.escape(ex["title"]), html.escape(provenance(ex)),
               ". " + html.escape(ex["note"]) if ex.get("note") else "", REPO_URL, ex["slug"], html.escape(ex["title"])))
    return _page("%s · Construct" % ex["title"], body, 2, "%s: a holographic construct. %s" % (ex["title"], provenance(ex)))


def build(out):
    sys.path.insert(0, str(ROOT))
    studio = importlib.import_module("construct_hologram.studio")
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    (out / "assets").mkdir(parents=True)
    (out / "assets" / "site.css").write_text(CSS.lstrip(), encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")  # serve every file as it is
    examples = _load_examples()
    for ex in examples:
        src, dst = EXAMPLES / ex["slug"], out / "examples" / ex["slug"]
        dst.mkdir(parents=True)
        if (src / "construct.html").exists():  # an original render kept (see its README)
            shutil.copyfile(src / "construct.html", dst / "construct.html")
        else:
            tmp = out / ".build" / ex["slug"]
            studio.build(str(src / "scene.json"), str(tmp))
            shutil.copyfile(studio.page_in(tmp), dst / "construct.html")
        for name in ("scene.json", "hero.jpg", "thumb.jpg"):
            shutil.copyfile(src / name, dst / name)
        (dst / "index.html").write_text(example_page(ex), encoding="utf-8")
    shutil.rmtree(out / ".build", ignore_errors=True)
    (out / "index.html").write_text(index_page(examples), encoding="utf-8")
    (out / "404.html").write_text(_page("Not found · Construct", "<header class=\"site\"><h1>Not here</h1><p>That page "
                                        "does not exist.</p><a class=\"button\" href=\"%s\">All examples</a></header>"
                                        % SITE_URL, 0, "Page not found."), encoding="utf-8")
    return out


def set_url(owner_repo):
    """Point every public link at OWNER/REPO: the constants above and the documents that link to the site."""
    owner, repo = owner_repo.split("/", 1)
    new_site, new_repo = "https://%s.github.io/%s/" % (owner, repo), "https://github.com/%s/%s" % (owner, repo)
    for rel in LINKED + ["scripts/build_site.py"] + [str(p.relative_to(ROOT)) for p in EXAMPLES.glob("*/README.md")]:
        p = ROOT / rel
        if not p.exists():
            continue
        s = p.read_text(encoding="utf-8")
        t = s.replace(SITE_URL, new_site).replace(REPO_URL, new_repo).replace(
            "github.com/%s/%s.git" % (OWNER, REPO), "github.com/%s/%s.git" % (owner, repo))
        if rel == "scripts/build_site.py":
            t = re.sub(r'^OWNER = ".*"$', 'OWNER = "%s"' % owner, t, flags=re.M)
            t = re.sub(r'^REPO = ".*"$', 'REPO = "%s"' % repo, t, flags=re.M)
        if t != s:
            p.write_text(t, encoding="utf-8")
            print("updated", rel)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="site", help="the folder to build into (it is replaced)")
    ap.add_argument("--set-url", metavar="OWNER/REPO", help="move every public link to another repository")
    args = ap.parse_args(argv)
    if args.set_url:
        set_url(args.set_url)
        return 0
    out = build(args.out)
    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print("site: %s (%d examples, %.1f MB)" % (out, len(_load_examples()), size / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main())
