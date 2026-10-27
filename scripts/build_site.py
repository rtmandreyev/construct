"""Build the examples gallery as a static site (for the gh-pages branch, served from its root).

    python3 scripts/build_site.py --out site --films DIR      # build the site into ./site
    python3 scripts/build_site.py --out site --no-films      # the same, without the film section
    python3 scripts/build_site.py --set-url OWNER/REPO       # move every link to another repository

Every example in examples/ (listed in examples/examples.json) is compiled with this checkout's
compiler into a self-contained construct.html, beside its hero image and its own page. The films
(examples/films.json, their scenes in examples/films/) get a page each, with the video, its poster
and the live construct. The videos are not in the repository: they come from --films DIR, a folder
holding the files films.json names, and go only into the built site. The pictures (each example's
hero.jpg and thumb.jpg, each film's poster.jpg) are framed close to the construct by
scripts/gallery_images.py. "Beyond objects" (examples/beyond.json) lists pages made with Construct
that are more than one construct: each folder is published as it is, beside the construct built from
its scene, and keeps its own licence. The site uses relative links only and needs no server code;
the constructs load nothing from other hosts (a "beyond" page may, as its README says).

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
header.site { padding: 48px 24px 24px; max-width: 1680px; margin: 0 auto; }
header.site p, header.site h1 { max-width: 900px; }
header.site .eyebrow { letter-spacing: .22em; font-size: 12px; color: var(--accent); text-transform: uppercase; }
header.site h1 { font-size: clamp(30px, 5vw, 48px); line-height: 1.1; margin: 10px 0 12px; font-weight: 650; }
header.site p { color: var(--dim); max-width: 760px; margin: 0 0 18px; }
.links { display: flex; flex-wrap: wrap; gap: 10px; }
.button { display: inline-block; padding: 9px 16px; border: 1px solid var(--line); border-radius: 999px;
          text-decoration: none; font-size: 14px; background: var(--panel); }
.button:hover { border-color: var(--accent); box-shadow: 0 0 18px var(--glow); }
main { max-width: 1680px; margin: 0 auto; padding: 0 24px 64px; }
.grid { display: grid; grid-template-columns: 1fr; gap: 18px; }
.grid > * { min-width: 0; }
h1, h2, p, .button { overflow-wrap: anywhere; }
@media (min-width: 700px) { .grid { grid-template-columns: repeat(2, 1fr); } }
@media (min-width: 1100px) { .grid { grid-template-columns: repeat(3, 1fr); } }
@media (min-width: 1700px) { .grid { grid-template-columns: repeat(4, 1fr); } }
@media (min-width: 1100px) { section.films .grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 480px) { header.site, main { padding-left: 16px; padding-right: 16px; } }
.card { display: block; text-decoration: none; background: var(--panel); border: 1px solid var(--line);
        border-radius: 14px; overflow: hidden; transition: border-color .15s, box-shadow .15s, transform .15s; }
.card:hover { border-color: var(--accent); box-shadow: 0 0 26px var(--glow); transform: translateY(-2px); }
.card img { display: block; width: 100%; height: auto; aspect-ratio: 16 / 10; object-fit: contain; background: #050205; }
.card .body { padding: 9px 13px 11px; }
.card h2 { font-size: 16px; margin: 0 0 2px; font-weight: 600; }
.card .prov { font-size: 12.5px; color: var(--dim); margin: 0; }
footer.site { max-width: 1680px; margin: 0 auto; padding: 24px 24px 48px; color: var(--dim); font-size: 13px;
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
.with-legend { display: flex; flex-direction: column; flex: 1 1 auto; }
.legend { display: grid; gap: 11px; align-content: start; padding: 16px 20px; border-top: 1px solid var(--line);
          font-size: 12px; line-height: 1.5; color: var(--dim); }
.legend div { display: grid; grid-template-columns: 26px 1fr; gap: 10px; align-items: start; }
.legend svg { margin-top: 3px; }
.legend b { color: var(--ink); font-weight: 500; }
@media (min-width: 1000px) { .with-legend { flex-direction: row; } .with-legend .stage { flex: 1 1 auto; }
  .legend { width: 300px; flex: 0 0 300px; border-top: 0; border-left: 1px solid var(--line); padding: 22px 22px; } }
.hint kbd { border: 1px solid var(--line); border-radius: 4px; padding: 0 5px; font-size: 12px; color: var(--ink); }
h2.section { font-size: 22px; font-weight: 620; margin: 8px 0 6px; }
p.section { color: var(--dim); max-width: 760px; margin: 0 0 16px; }
section.films { margin-bottom: 44px; }
section.beyond { margin-top: 44px; }
.card.film { cursor: default; }
.card.film:hover { transform: none; }
.card h2 a { text-decoration: none; }
.card h2 a:hover { text-decoration: underline; }
.card .credit { font-size: 12.5px; color: var(--dim); margin: 4px 0 0; }
.card .choose { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
.card .choose .button { font-size: 13px; padding: 7px 13px; }
.button.primary { border-color: var(--accent); }
.film-view { width: 100%; max-width: 1400px; margin: 0 auto; padding: 18px 24px 0; }
.tabs { display: flex; flex-wrap: wrap; gap: 10px; margin: 0 0 14px; }
.tabs input { position: absolute; opacity: 0; pointer-events: none; }
.tabs label { padding: 10px 18px; border: 1px solid var(--line); border-radius: 999px; background: var(--panel);
              cursor: pointer; font-size: 15px; }
.tabs label:hover { border-color: var(--accent); }
.tabs input:focus-visible + label { outline: 2px solid var(--accent); outline-offset: 3px; }
#watch:checked + label, #live:checked + label { border-color: var(--accent); box-shadow: 0 0 18px var(--glow); }
.pane { display: none; width: 100%; }
#watch:checked ~ .panes .pane.film, #live:checked ~ .panes .pane.live { display: block; }
.pane video { display: block; width: 100%; aspect-ratio: 16 / 9; background: #000; border-radius: 12px; }
.pane .stage { min-height: 0; aspect-ratio: 16 / 9; border: 1px solid var(--line); border-radius: 12px; overflow: hidden; }
.pane .hint { padding: 10px 0 0; }
.why { color: var(--dim); font-size: 14px; max-width: 820px; margin: 16px 0 28px; }
section.part { margin: 8px 0 56px; }
section.part .eyebrow, header.site .eyebrow { letter-spacing: .22em; font-size: 12px; color: var(--accent); text-transform: uppercase; }
header.site h1 em { font-style: normal; color: var(--accent); }
.part-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 18px; }
.shelf-nav { display: flex; gap: 8px; flex: 0 0 auto; margin-bottom: 16px; }
.shelf-nav button { width: 40px; height: 40px; border-radius: 50%; border: 1px solid var(--line); background: var(--panel);
                    color: var(--ink); font-size: 18px; cursor: pointer; }
.shelf-nav button:hover { border-color: var(--accent); box-shadow: 0 0 18px var(--glow); }
.shelf { max-height: min(78vh, 760px); overflow-y: auto; scroll-snap-type: y proximity; padding: 4px 6px 8px 2px;
         border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); scrollbar-width: thin;
         -webkit-mask-image: linear-gradient(#000 92%, transparent); mask-image: linear-gradient(#000 92%, transparent); }
.shelf .grid { padding-top: 14px; }
@media (min-width: 1100px) { .shelf .grid { grid-template-columns: repeat(4, 1fr); } }
.shelf .card { scroll-snap-align: start; }
.shelf-count { color: var(--dim); font-size: 13px; margin: 10px 0 0; }
.part p.section kbd { border: 1px solid var(--line); border-radius: 4px; padding: 0 5px; font-size: 12px; color: var(--ink); }
.feature { display: grid; grid-template-columns: 1fr; gap: 22px; align-items: center; background: var(--panel);
           border: 1px solid var(--line); border-radius: 16px; overflow: hidden; }
.feature-img img { display: block; width: 100%; height: auto; }
.feature-text { padding: 4px 22px 22px; }
.feature-text p { color: var(--dim); margin: 0 0 12px; }
.feature-text .credit { font-size: 13px; }
.steps { margin: 0 0 14px; padding-left: 20px; color: var(--dim); }
.steps li { margin: 4px 0; } .steps b { color: var(--ink); font-weight: 600; }
@media (min-width: 1000px) { .feature { grid-template-columns: 1.5fr 1fr; } .feature-text { padding: 22px 26px 22px 0; } }
@media (min-width: 900px) { .grid.models { grid-template-columns: repeat(3, 1fr); } }
.feature.live { margin: 8px 0 34px; }
.feature .kind { letter-spacing: .18em; font-size: 11px; color: var(--accent); text-transform: uppercase; margin-bottom: 6px; }
.feature h3 { margin: 0 0 10px; font-size: 22px; }
h3.sub { margin: 6px 0 4px; font-size: 18px; }
@media (max-width: 600px) { .part-head { align-items: flex-start; } .shelf { max-height: 72vh; } }
"""


def _load_examples():
    return json.loads((EXAMPLES / "examples.json").read_text(encoding="utf-8"))["examples"]


def _load_films():
    path = EXAMPLES / "films.json"
    return json.loads(path.read_text(encoding="utf-8"))["films"] if path.exists() else []


def _load_beyond():
    path = EXAMPLES / "beyond.json"
    return json.loads(path.read_text(encoding="utf-8"))["beyond"] if path.exists() else []


def film_label(film):
    """A film's line: the object, the mode and the model."""
    return "%s · %s · %s" % (film["title"], film["mode"], film["model"])


WHY_FILM = ("Why a film? The film carries the music and plays the long, music-shaped assembly exactly as it was "
            "rendered. The live construct is the construct itself, to orbit, replay and read; but a page doesn't play "
            "the track, so to see the music driving the build, watch the film.")


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


def _beyond_buttons(b):
    """A "beyond" card's buttons: its own (label, path in its folder), or the live model and its construct."""
    buttons = b.get("buttons") or [["Open the live model", ""], ["The construct", "construct.html?rounds=0"]]
    return "".join("<a class=\"button%s\" href=\"examples/%s/%s\">%s</a>" % (" primary" if i == 0 else "", b["slug"],
                                                                         html.escape(href), html.escape(label))
                   for i, (label, href) in enumerate(buttons))


SHELF_JS = ("<script>(function(){var s=document.getElementById('shelf');if(!s)return;"
            "document.querySelectorAll('[data-shelf]').forEach(function(b){b.addEventListener('click',function(){"
            "var c=s.querySelector('.card');var h=c?c.getBoundingClientRect().height+18:300;"
            "s.scrollBy({top:h*Number(b.getAttribute('data-shelf')),behavior:'smooth'});});});})();</script>")


def index_page(examples, films=(), beyond=()):
    """The landing page, in four parts: the full pipeline (from a hologram to a finished 3D model), the
    constructs (a compact scroller), film mode, and models come alive (a live simulation, then recorded runs)."""
    film_cards = [
        "<div class=\"card film\"><a href=\"films/%s/\"><img src=\"films/%s/poster.jpg\" alt=\"%s, the finished construct "
        "of its film\" loading=\"lazy\" width=\"1200\" height=\"750\"></a><div class=\"body\"><h2><a href=\"films/%s/\">%s</a>"
        "</h2><p class=\"prov\">film · %s</p><div class=\"choose\"><a class=\"button primary\" href=\"films/%s/\">Open the live "
        "construct</a><a class=\"button\" href=\"films/%s/#film\">Watch the film</a></div></div></div>"
        % (f["slug"], f["slug"], html.escape(f["title"]), f["slug"], html.escape(f["title"]),
           html.escape("%s · %s" % (f["mode"], f["model"])), f["slug"], f["slug"])
        for f in films]
    cards = [
        "<a class=\"card\" href=\"examples/%s/\"><img src=\"examples/%s/thumb.jpg\" alt=\"%s, a holographic construct\" "
        "loading=\"lazy\" width=\"1200\" height=\"750\"><div class=\"body\"><h2>%s</h2><p class=\"prov\">%s</p></div></a>"
        % (e["slug"], e["slug"], html.escape(e["title"]), html.escape(e["title"]), html.escape(provenance(e)))
        for e in examples]
    shelf = ("<section class=\"part\" id=\"constructs\"><div class=\"part-head\"><div><div class=\"eyebrow\">2 · Constructs"
             "</div><h2 class=\"section\">Anything you can describe</h2><p class=\"section\">Each made by an AI agent from "
             "a description, in fast or masterpiece mode. Open one to watch it build itself; drag to turn it, "
             "<kbd>R</kbd> replays the assembly, <kbd>P</kbd> shows how each part is known.</p></div>"
             "<div class=\"shelf-nav\" aria-hidden=\"true\"><button type=\"button\" data-shelf=\"-1\" title=\"Back\">"
             "&#8593;</button><button type=\"button\" data-shelf=\"1\" title=\"More\">&#8595;</button></div></div>"
             "<div class=\"shelf\" id=\"shelf\" tabindex=\"0\"><div class=\"grid\">\n%s\n</div></div>"
             "<p class=\"shelf-count\">%d constructs · scroll, or use the arrows</p></section>"
             % ("\n".join(cards), len(examples)))
    film_part = ("<section class=\"part films\" id=\"films\"><div class=\"eyebrow\">3 · Film mode</div>"
                 "<h2 class=\"section\">Constructs that assemble to music</h2><p class=\"section\">A construct can "
                 "assemble across a whole piece of music: the build pauses, surges and flares with it, and you get a "
                 "video with the music in it. Each opens on its live construct; the film is one click away. "
                 "<a href=\"%s/blob/main/docs/FILM.md\">Film mode</a>.</p>"
                 "<div class=\"grid\">\n%s\n</div></section>" % (REPO_URL, "\n".join(film_cards))) if films else ""
    pipe = [b for b in beyond if b.get("section") == "pipeline"]
    models = [b for b in beyond if b.get("section") != "pipeline"]
    live = [b for b in models if b.get("kind") == "simulation"]
    recorded = [b for b in models if b.get("kind") != "simulation"]
    pipeline = "".join(
        "<section class=\"part\" id=\"pipeline\"><div class=\"eyebrow\">1 · The full pipeline</div>"
        "<h2 class=\"section\">From light to a finished 3D model</h2>"
        "<div class=\"feature\"><a class=\"feature-img\" href=\"examples/%s/\"><img src=\"examples/%s/hero.jpg\" alt=\"%s\" "
        "loading=\"lazy\" width=\"1440\" height=\"900\"></a><div class=\"feature-text\">"
        "<p>Every construct is also a 3D model. What the agent wrote (named parts in metres, joints, the order "
        "they assemble in) exports as one glTF file, and a material map finishes it.</p>"
        "<ol class=\"steps\"><li><b>Hologram.</b> Lines of light, as the agent built it.</li>"
        "<li><b>Plain model.</b> Every part a solid, named object; joints that open.</li>"
        "<li><b>Finished.</b> Paint, chrome, glass, wood: one map per object, kept beside it.</li></ol>"
        "<p>The page shows four gallery constructs as their exported files: the Land Cruiser FJ62, the James Webb "
        "Space Telescope, the Revox A77 and the MiniFreak. Slide each from hologram to plain to finished, open "
        "its joints, take it apart, and download it.</p>"
        "<p class=\"credit\">%s</p><div class=\"choose\"><a class=\"button primary\" href=\"examples/%s/\">See the four "
        "models in 3D</a><a class=\"button\" href=\"examples/%s/fj62.glb\">Download the FJ62 (.glb)</a>"
        "<a class=\"button\" href=\"%s/blob/main/hosts/blender/README.md\">Blender add-on</a>"
        "<a class=\"button\" href=\"%s/blob/main/docs/EXPORT.md\">3D export</a></div></div></div></section>"
        % (b["slug"], b["slug"], html.escape(b["title"]), html.escape(b["credit"]), b["slug"], b["slug"], REPO_URL, REPO_URL)
        for b in pipe)
    live_features = "".join(
        "<div class=\"feature live\"><a class=\"feature-img\" href=\"examples/%s/\"><img src=\"examples/%s/hero.jpg\" "
        "alt=\"%s running in the browser\" loading=\"lazy\" width=\"1440\" height=\"900\"></a><div class=\"feature-text\">"
        "<div class=\"kind\">A live simulation</div><h3>%s</h3>"
        "<p>The model itself runs on the page: rebuilt rule for rule in JavaScript, so you can build new networks, "
        "change the settings, run it tick by tick and compare a hundred runs with NetLogo's own, while the "
        "construct grows with the run.</p><p class=\"credit\">%s</p><div class=\"choose\">"
        "<a class=\"button primary\" href=\"examples/%s/\">Run the simulation</a>"
        "<a class=\"button\" href=\"examples/%s/construct.html?rounds=0\">The construct</a></div></div></div>"
        % (b["slug"], b["slug"], html.escape(b["title"]), html.escape(b["title"]), html.escape(b["credit"]),
           b["slug"], b["slug"])
        for b in live)
    model_cards = "\n".join(
        "<div class=\"card film\"><a href=\"examples/%s/\"><img src=\"examples/%s/thumb.jpg\" alt=\"%s, a construct of a "
        "model's run\" loading=\"lazy\" width=\"1200\" height=\"750\"></a><div class=\"body\"><h2><a href=\"examples/%s/\">%s</a>"
        "</h2><p class=\"prov\">%s</p><p class=\"credit\">%s</p><div class=\"choose\">%s</div></div></div>"
        % (b["slug"], b["slug"], html.escape(b["title"]), b["slug"], html.escape(b["title"]), html.escape(b["line"]),
           html.escape(b["credit"] + (" · art direction: %s" % b["art"] if b.get("art") else "")), _beyond_buttons(b))
        for b in recorded)
    alive = ("<section class=\"part\" id=\"models\"><div class=\"eyebrow\">4 · Models come alive</div>"
             "<h2 class=\"section\">Agent-based models, two ways</h2><p class=\"section\">A NetLogo model can come "
             "into Construct as a live simulation you run on the page, or as one recorded run, drawn with time as "
             "height.</p>%s"
             "<h3 class=\"sub\">Recorded runs, drawn by the bridge</h3><p class=\"section\">No simulation runs on "
             "these pages. Each is one run, recorded in NetLogo by Construct's bridge and drawn from the "
             "recording, so its assembly replays the run; the data comes from the run, never from an AI. An AI "
             "art-direction pass adds the labels and milestones on top, and a data lock keeps it off the data. "
             "<a href=\"%s/blob/main/docs/NETLOGO.md\">The NetLogo bridge</a>.</p>"
             "<div class=\"grid models\">\n%s\n</div></section>" % (live_features, REPO_URL, model_cards)) if models else ""
    body = ("<header class=\"site\"><div class=\"eyebrow\">Construct · examples</div>"
            "<h1>Describe a thing. Get a hologram, <em>a 3D model and its parts</em>.</h1>"
            "<p>Construct lets any AI agent build an animated holographic model of a thing from a description, and "
            "takes it further: into Blender and game engines as a 3D model with working parts, or, for a "
            "simulation, a model's whole run drawn in time.</p>"
            "<div class=\"links\"><a class=\"button\" href=\"%s\">Construct on GitHub</a>"
            "<a class=\"button\" href=\"#pipeline\">The full pipeline</a><a class=\"button\" href=\"#constructs\">"
            "Constructs</a><a class=\"button\" href=\"#films\">Film mode</a><a class=\"button\" href=\"#models\">"
            "Models come alive</a>"
            "<a class=\"button\" href=\"%s/blob/main/docs/HOW-IT-IS-MADE.md\">How they are made</a></div></header>"
            "<main>%s%s%s%s</main>"
            "<footer class=\"site\">Construct is Apache-2.0 licensed; its Blender add-on is GPL-3.0-or-later. Product and "
            "place names belong to their owners; each construct is an independent reconstruction from public "
            "references, not an official model. %s"
            "<a href=\"%s\">Source and documentation</a>.</footer>%s"
            % (REPO_URL, REPO_URL, pipeline, shelf, film_part, alive,
               "The pages under Models come alive keep their own licences, given on each. " if models else "",
               REPO_URL, SHELF_JS))
    return _page("Construct · examples", body, 0, "Holographic constructs built by AI agents, the 3D models they "
                                               "export, and agent-based models drawn in time.")


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


# a legend's glyphs, drawn in the viewer's own tones (the violet palette), as on the Simple Viral Marketing page
TONE_HEX = {"accent": "#d16bd0", "bright": "#f6eaff", "hairline": "#eadcf3", "structure": "#b7a4c8", "dust": "#9682d7",
            "identity": "#eadcf3", "data": "#8fd3ff", "faint": "#6f6080"}
GLYPHS = {
    "floor": '<rect x="2" y="4" width="22" height="7" fill="none" stroke="{c}"/>',
    "rise": '<line x1="3" y1="12" x2="22" y2="2" stroke="{c}" stroke-width="1.5"/>',
    "tracks": '<path d="M2 12 L9 9 L14 7 M5 13 L12 8 L22 3 M3 9 L10 6 L20 2" fill="none" stroke="{c}" stroke-width="1.1"/>',
    "loop": '<path d="M4 12 C1 6 10 1 14 5 C18 9 25 6 22 2" fill="none" stroke="{c}" stroke-width="1.5"/>',
    "shadow": '<path d="M3 10 C6 6 12 13 16 9 C19 6 23 9 23 9" fill="none" stroke="{c}"/>',
    "wall": '<path d="M2 11 L6 4 L9 10 L13 3 L16 9 L20 4 L24 10" fill="none" stroke="{c}" stroke-width="1.2"/>',
    "front": '<path d="M2 9 C5 4 8 12 12 7 C15 3 19 11 24 6" fill="none" stroke="{c}" stroke-width="1.4"/>',
    "ladder": '<path d="M8 13 L8 1 M18 13 L18 1 M8 10 L18 10 M8 6 L18 6 M8 2 L18 2" fill="none" stroke="{c}"/>',
    "ring": '<ellipse cx="13" cy="7" rx="11" ry="4" fill="none" stroke="{c}" stroke-dasharray="3 2"/>',
    "marker": '<circle cx="13" cy="7" r="3.2" fill="{c}"/>',
    "axis": '<path d="M5 13 L5 1 M5 9 L8 9 M5 5 L8 5" fill="none" stroke="{c}"/>',
}


def _legend(items):
    """A legend: rows of [glyph, tone, lead, text], each glyph drawn in the construct's own tone."""
    rows = "".join(
        "<div><svg width=\"26\" height=\"14\" aria-hidden=\"true\">%s</svg><span><b>%s</b> %s</span></div>"
        % (GLYPHS[g].format(c=TONE_HEX[tone]), html.escape(lead), html.escape(text)) for g, tone, lead, text in items)
    return "<aside class=\"legend\" aria-label=\"Legend\">%s</aside>" % rows


def data_page(item):
    """A "beyond" construct with no page of its own (a recorded NetLogo run): the live construct, its credit.
    An art-directed one (`"art"`: who directed it) opens with its labels on and credits the direction."""
    art = item.get("art")
    q = "rounds=0&amp;labels=1" if art else "rounds=0"
    body = ("<div class=\"viewer\"><div class=\"bar\"><h1>%s</h1><p class=\"prov\">%s · %s%s</p><nav>"
            "<a class=\"button\" href=\"../../\">All examples</a>"
            "<a class=\"button\" href=\"construct.html?%s\">Full screen</a>"
            "<a class=\"button\" href=\"scene.json\">Scene</a>"
            "<a class=\"button\" href=\"%s/tree/main/examples/%s\">Source and licence</a></nav></div>"
            "<div class=\"with-legend\"><div class=\"stage\"><iframe src=\"construct.html?ui=0&amp;%s\" title=\"%s, live "
            "construct\" allowfullscreen></iframe></div>%s</div>"
            "<p class=\"hint\">%s Drag to orbit, scroll to zoom; <kbd>R</kbd> replays the assembly, which rises with the "
            "run's ticks%s.</p></div>"
            % (html.escape(item["title"]), html.escape(item["label"]), html.escape(item["credit"]),
               html.escape(" · art direction: %s" % art) if art else "", q, REPO_URL, item["slug"], q,
               html.escape(item["title"]), _legend(item["legend"]) if item.get("legend") else "", html.escape(item["line"]),
               "; click it, then <kbd>L</kbd> hides the art direction's labels" if art else ""))
    return _page("%s · Construct" % item["title"], body, 2, "%s: %s" % (item["title"], item["line"]))


def film_page(film):
    body = ("<div class=\"viewer\"><div class=\"bar\"><h1>%s</h1><p class=\"prov\">%s</p><nav>"
            "<a class=\"button\" href=\"../../\">All examples</a>"
            "<a class=\"button\" href=\"construct.html?rounds=0\">Live construct, full screen</a>"
            "<a class=\"button\" href=\"scene.json\">Scene</a>"
            "<a class=\"button\" href=\"%s/tree/main/examples/films/%s\">Source</a></nav></div>"
            "<div class=\"film-view\"><div class=\"tabs\">"
            "<input type=\"radio\" name=\"view\" id=\"live\" checked><label for=\"live\">Open the live construct</label>"
            "<input type=\"radio\" name=\"view\" id=\"watch\"><label for=\"watch\">Watch the film</label>"
            "<div class=\"panes\" style=\"width: 100%%\">"
            "<div class=\"pane film\"><video controls preload=\"metadata\" playsinline poster=\"poster.jpg\" src=\"film.mp4\" "
            "aria-label=\"%s, a film\"></video></div>"
            "<div class=\"pane live\"><div class=\"stage\"><iframe src=\"construct.html?ui=0&amp;rounds=0\" "
            "title=\"%s, live construct\" allowfullscreen></iframe></div>"
            "<p class=\"hint\">Drag to orbit, scroll to zoom. Click the construct first, then <kbd>R</kbd> replays the "
            "assembly, <kbd>L</kbd> shows labels and <kbd>P</kbd> shows how each part is known.</p></div>"
            "</div></div><p class=\"why\">%s</p></div></div>"
            "<script>(function () { var v = document.querySelector('video'), live = document.getElementById('live'),"
            " watch = document.getElementById('watch');"
            " live.addEventListener('change', function () { if (v) v.pause(); history.replaceState(null, '', location.pathname); });"
            " watch.addEventListener('change', function () { history.replaceState(null, '', '#film'); });"
            " function pick() { if (location.hash === '#film') watch.checked = true; else if (location.hash === '#live') live.checked = true; }"
            " pick(); addEventListener('hashchange', pick); })();</script>"
            % (html.escape(film["title"]), html.escape("%s · %s" % (film["mode"], film["model"])), REPO_URL, film["slug"],
               html.escape(film["title"]), html.escape(film["title"]), html.escape(WHY_FILM)))
    return _page("%s · film · Construct" % film["title"], body, 2,
                 "%s assembling across a piece of music: a Construct film, and the live construct." % film["title"])


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
    shutil.copyfile(src / "poster.jpg", dst / "poster.jpg")  # framed close by scripts/gallery_images.py
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
    beyond = _load_beyond()
    for item in beyond:  # published as it is (its own licence), beside the construct built from its scene
        src, dst = EXAMPLES / item["slug"], out / "examples" / item["slug"]
        dst.mkdir(parents=True)
        for name in item["files"]:
            (dst / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src / name, dst / name)
        for name, spec in item.get("exports", {}).items():  # 3D models of gallery constructs, exported here
            export = importlib.import_module("construct_hologram.export")
            spec = spec if isinstance(spec, dict) else {"scene": spec}   # a scene folder, and a material map
            public = _public_scene(EXAMPLES / spec["scene"] / "scene.json", out / ".build" / ("export-" + Path(name).stem))
            export.export(studio.load(str(public)), dst / name,
                          materials=str(src / spec["materials"]) if spec.get("materials") else None)
        if (src / "scene.json").exists():
            tmp = out / ".build" / ("beyond-" + item["slug"])
            studio.build(str(_public_scene(src / "scene.json", tmp.parent)), str(tmp), asset_root=str(src))
            shutil.copyfile(studio.page_in(tmp), dst / "construct.html")
        if "index.html" not in item["files"]:
            (dst / "index.html").write_text(data_page(item), encoding="utf-8")
    shutil.rmtree(out / ".build", ignore_errors=True)
    (out / "index.html").write_text(index_page(examples, films, beyond), encoding="utf-8")
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
