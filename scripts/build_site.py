"""Build the examples gallery as a static site (for the gh-pages branch, served from its root).

    python3 scripts/build_site.py --out site --films DIR      # build the site into ./site
    python3 scripts/build_site.py --out site --no-films      # the same, without the film section
    python3 scripts/build_site.py --set-url OWNER/REPO       # move every link to another repository

Every example in examples/ (listed in examples/examples.json) is compiled with this checkout's
compiler into a self-contained construct.html, beside its hero image and its own page. The films
(examples/films.json, their scenes in examples/films/) get a page each, with the video, its poster
and the live construct. The videos are not in the repository: they come from --films DIR, a folder
holding the files films.json names, and go only into the built site. ffmpeg draws each poster
from the film's last frame. The site uses relative links only, needs no server code and loads
nothing from other hosts.

The public addresses come from OWNER and REPO below and nowhere else: `--set-url` rewrites them
here and in the documents that link to the site.
"""

import argparse
import html
import importlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

OWNER = "rtmandreyev"
REPO = "construct"
SITE_URL = "https://%s.github.io/%s/" % (OWNER, REPO)
REPO_URL = "https://github.com/%s/%s" % (OWNER, REPO)

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
LINKED = ["README.md", "PUBLISHING.md", "examples/README.md"]  # documents that link to the site, and docs/**/*.md
FILM_MAX_MB = 25  # a film larger than this is refused: re-encode it (see docs/FILM.md)

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
h2.section { font-size: 22px; font-weight: 620; margin: 8px 0 6px; }
p.section { color: var(--dim); max-width: 760px; margin: 0 0 16px; }
section.films { margin-bottom: 44px; }
.card.film { cursor: default; }
.card.film:hover { transform: none; }
.card video, .film-player video { display: block; width: 100%; aspect-ratio: 16 / 9; background: #000; }
.card h2 a { text-decoration: none; }
.card h2 a:hover { text-decoration: underline; }
.credit { font-size: 12.5px; color: var(--dim); margin: 6px 0 0; }
.film-player { width: 100%; max-width: 1180px; margin: 0 auto; padding: 18px 20px 6px; }
.film-player .credit { font-size: 13.5px; margin: 10px 0 0; }
.live { width: 100%; max-width: 1180px; margin: 0 auto; padding: 22px 20px 0; }
.film-hint { width: 100%; max-width: 1180px; margin: 0 auto; }
.live .stage { min-height: 0; aspect-ratio: 16 / 9; border: 1px solid var(--line); border-radius: 12px; overflow: hidden; }
"""


def _load_examples():
    return json.loads((EXAMPLES / "examples.json").read_text(encoding="utf-8"))["examples"]


def _load_films():
    path = EXAMPLES / "films.json"
    return json.loads(path.read_text(encoding="utf-8"))["films"] if path.exists() else []


def film_label(film):
    """A film's line: the object, the mode, the model and the track."""
    return "%s · %s · %s · %s" % (film["title"], film["mode"], film["model"], film["track"])


def film_credit(film):
    return 'Music: "%s" by Artyom Andreyev, used with permission.' % film["track"]


def provenance(ex):
    """The one line every card, page and README carries: the mode and the model."""
    return "%s · %s" % (ex["mode"], ex["model"])


def _page(title, body, depth, description):
    up = "../" * depth
    return ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            "<title>%s</title>\n<meta name=\"description\" content=\"%s\">\n"
            "<link rel=\"stylesheet\" href=\"%sassets/site.css\">\n</head>\n<body>\n%s\n</body>\n</html>\n"
            % (html.escape(title), html.escape(description), up, body))


def index_page(examples, films=()):
    film_cards = "\n".join(
        "<div class=\"card film\"><video controls preload=\"none\" playsinline poster=\"films/%s/poster.jpg\" "
        "src=\"films/%s/film.mp4\" aria-label=\"%s, a film\"></video><div class=\"body\"><h2><a href=\"films/%s/\">%s</a>"
        "</h2><p class=\"prov\">%s</p><p class=\"credit\">%s</p></div></div>"
        % (f["slug"], f["slug"], html.escape(f["title"]), f["slug"], html.escape(f["title"]), html.escape(film_label(f)),
           html.escape(film_credit(f)))
        for f in films)
    film_section = ("<section class=\"films\" id=\"films\"><h2 class=\"section\">Films</h2><p class=\"section\">Constructs "
                    "assembling across a track of music with film mode: the build follows the music's pace, flares on "
                    "its attacks and moves on with its sections. Play one, or open it to see the construct live.</p>"
                    "<div class=\"grid\">\n%s\n</div></section><h2 class=\"section\">Constructs</h2>" % film_cards
                    if films else "")
    cards = "\n".join(
        "<a class=\"card\" href=\"examples/%s/\"><img src=\"examples/%s/thumb.jpg\" alt=\"%s, a holographic construct\" "
        "loading=\"lazy\" width=\"720\" height=\"450\"><div class=\"body\"><h2>%s</h2><p class=\"prov\">%s</p></div></a>"
        % (e["slug"], e["slug"], html.escape(e["title"]), html.escape(e["title"]), html.escape(provenance(e)))
        for e in examples)
    body = ("<header class=\"site\"><div class=\"eyebrow\">Construct · examples</div>"
            "<h1>Holographic constructs, built by AI agents</h1>"
            "<p>Each of these was made by an AI agent with Construct, in fast or masterpiece mode, and drawn in the "
            "Measured Light style. Open one to watch it build itself: drag to turn it around, press R to replay the "
            "assembly and L to read its labels. Some were made with earlier versions of Construct.</p>"
            "<div class=\"links\"><a class=\"button\" href=\"%s\">Construct on GitHub</a>"
            "<a class=\"button\" href=\"%s/blob/main/docs/HOW-IT-IS-MADE.md\">How they were made</a>%s</div></header>"
            "<main>%s<div class=\"grid\">\n%s\n</div></main>"
            "<footer class=\"site\">Construct is MIT licensed. Product and place names belong to their owners; each "
            "construct is an independent reconstruction from public references, not an official model. "
            "<a href=\"%s\">Source and documentation</a>.</footer>"
            % (REPO_URL, REPO_URL, ("<a class=\"button\" href=\"%s/blob/main/docs/FILM.md\">Film mode</a>" % REPO_URL)
               if films else "", film_section, cards, REPO_URL))
    return _page("Construct · examples", body, 0, "A gallery of holographic constructs built by AI agents with Construct.")


def example_page(ex):
    body = ("<div class=\"viewer\"><div class=\"bar\"><h1>%s</h1><p class=\"prov\">%s</p><nav>"
            "<a class=\"button\" href=\"../../\">All examples</a>"
            "<a class=\"button\" href=\"construct.html?rounds=0\">Full screen</a>"
            "<a class=\"button\" href=\"scene.json\">Scene</a>"
            "<a class=\"button\" href=\"%s/tree/main/examples/%s\">Source</a></nav></div>"
            "<div class=\"stage\"><iframe src=\"construct.html?ui=0&amp;rounds=0\" title=\"%s, live construct\" "
            "allowfullscreen></iframe></div>"
            "<p class=\"hint\">Drag to orbit, scroll to zoom. Click the construct first, then <kbd>R</kbd> replays the "
            "assembly, <kbd>L</kbd> shows labels, <kbd>P</kbd> shows how each part is known, <kbd>1</kbd>–<kbd>6</kbd> "
            "change the view and <kbd>space</kbd> pauses.</p></div>"
            % (html.escape(ex["title"]), html.escape(provenance(ex)), REPO_URL, ex["slug"], html.escape(ex["title"])))
    return _page("%s · Construct" % ex["title"], body, 2, "%s: a holographic construct. %s" % (ex["title"], provenance(ex)))


def film_page(film):
    body = ("<div class=\"viewer\"><div class=\"bar\"><h1>%s</h1><p class=\"prov\">%s</p><nav>"
            "<a class=\"button\" href=\"../../\">All examples</a>"
            "<a class=\"button\" href=\"construct.html?rounds=0\">Live construct, full screen</a>"
            "<a class=\"button\" href=\"scene.json\">Scene</a>"
            "<a class=\"button\" href=\"%s/tree/main/examples/films/%s\">Source</a></nav></div>"
            "<div class=\"film-player\"><video controls preload=\"metadata\" playsinline poster=\"poster.jpg\" "
            "src=\"film.mp4\" aria-label=\"%s, a film\"></video><p class=\"credit\">%s</p></div>"
            "<div class=\"live\"><h2 class=\"section\">The construct, live</h2><p class=\"section\">The same construct "
            "as a page: it assembles in its own short time here, without the music.</p>"
            "<div class=\"stage\"><iframe src=\"construct.html?ui=0&amp;rounds=0\" title=\"%s, live construct\" "
            "allowfullscreen loading=\"lazy\"></iframe></div></div>"
            "<p class=\"hint film-hint\">Drag to orbit, scroll to zoom. Click the construct first, then <kbd>R</kbd> replays the "
            "assembly, <kbd>L</kbd> shows labels and <kbd>P</kbd> shows how each part is known.</p></div>"
            % (html.escape(film["title"]), html.escape(film_label(film)), REPO_URL, film["slug"], html.escape(film["title"]),
               html.escape(film_credit(film)), html.escape(film["title"])))
    return _page("%s · film · Construct" % film["title"], body, 2,
                 "%s assembling across \"%s\": a Construct film. %s" % (film["title"], film["track"], film_credit(film)))


def _film(film, films_dir, out, studio):
    """One film's folder on the site: the video as given, its poster, the live construct and the scene."""
    src, dst = EXAMPLES / "films" / film["slug"], out / "films" / film["slug"]
    video = Path(films_dir) / film["video"]
    if not video.is_file():
        raise SystemExit("missing film: %s" % video)
    if video.stat().st_size > FILM_MAX_MB * 1e6:
        raise SystemExit("%s is %.1f MB, more than %d MB: re-encode it" % (video, video.stat().st_size / 1e6, FILM_MAX_MB))
    dst.mkdir(parents=True)
    shutil.copyfile(video, dst / "film.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-sseof", "-0.5", "-i", str(video), "-frames:v", "1",
                    "-vf", "scale=1280:-2", "-q:v", "4", str(dst / "poster.jpg")], check=True)
    tmp = out / ".build" / ("film-" + film["slug"])
    studio.build(str(_public_scene(src / "scene.json", tmp.parent)), str(tmp), asset_root=str(src))
    shutil.copyfile(studio.page_in(tmp), dst / "construct.html")
    shutil.copyfile(src / "scene.json", dst / "scene.json")
    (dst / "index.html").write_text(film_page(film), encoding="utf-8")


def _public_scene(path, tmp):
    """The scene the gallery compiles: the approved scene without its round history
    (`authoring.rounds`), so a published construct page never shows the round timeline, whatever
    its URL. The scene file in examples/ (and its copy on the site) stays as approved."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if not (doc.get("authoring") or {}).pop("rounds", None):
        return path
    tmp.mkdir(parents=True, exist_ok=True)
    scene = tmp / ("%s.scene.json" % Path(path).parent.name)
    scene.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return scene


def build(out, films_dir=None):
    """The site in `out`; with `films_dir` (the folder holding the videos films.json names) also the films."""
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
            studio.build(str(_public_scene(src / "scene.json", tmp.parent)), str(tmp), asset_root=str(src))
            shutil.copyfile(studio.page_in(tmp), dst / "construct.html")
        for name in ("scene.json", "hero.jpg", "thumb.jpg"):
            shutil.copyfile(src / name, dst / name)
        (dst / "index.html").write_text(example_page(ex), encoding="utf-8")
    films = _load_films() if films_dir else []
    for film in films:
        _film(film, films_dir, out, studio)
    shutil.rmtree(out / ".build", ignore_errors=True)
    (out / "index.html").write_text(index_page(examples, films), encoding="utf-8")
    (out / "404.html").write_text(_page("Not found · Construct", "<header class=\"site\"><h1>Not here</h1><p>That page "
                                        "does not exist.</p><a class=\"button\" href=\"%s\">All examples</a></header>"
                                        % SITE_URL, 0, "Page not found."), encoding="utf-8")
    return out


def set_url(owner_repo):
    """Point every public link at OWNER/REPO: the constants above and the documents that link to the site."""
    owner, repo = owner_repo.split("/", 1)
    new_site, new_repo = "https://%s.github.io/%s/" % (owner, repo), "https://github.com/%s/%s" % (owner, repo)
    docs = [str(p.relative_to(ROOT)) for p in list(EXAMPLES.glob("*/README.md")) + list((ROOT / "docs").rglob("*.md"))]
    for rel in LINKED + ["scripts/build_site.py"] + docs:
        p = ROOT / rel
        if not p.exists():
            continue
        s = p.read_text(encoding="utf-8")
        t = s.replace(SITE_URL, new_site).replace(REPO_URL, new_repo).replace(
            "github.com/%s/%s.git" % (OWNER, REPO), "github.com/%s/%s.git" % (owner, repo)).replace(
            "raw.githubusercontent.com/%s/%s/" % (OWNER, REPO), "raw.githubusercontent.com/%s/%s/" % (owner, repo))
        if rel == "scripts/build_site.py":
            t = re.sub(r'^OWNER = ".*"$', 'OWNER = "%s"' % owner, t, flags=re.M)
            t = re.sub(r'^REPO = ".*"$', 'REPO = "%s"' % repo, t, flags=re.M)
        if t != s:
            p.write_text(t, encoding="utf-8")
            print("updated", rel)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="site", help="the folder to build into (it is replaced)")
    ap.add_argument("--films", metavar="DIR", help="the folder holding the film videos (kept outside the repository)")
    ap.add_argument("--no-films", action="store_true", help="build without the film section")
    ap.add_argument("--set-url", metavar="OWNER/REPO", help="move every public link to another repository")
    args = ap.parse_args(argv)
    if args.set_url:
        set_url(args.set_url)
        return 0
    if _load_films() and not (args.films or args.no_films):
        ap.error("examples/films.json lists films: give --films DIR (the videos), or --no-films")
    out = build(args.out, None if args.no_films else args.films)
    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print("site: %s (%d examples, %d films, %.1f MB)" % (out, len(_load_examples()), 0 if args.no_films else len(_load_films()),
                                                          size / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main())
