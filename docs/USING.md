# Using Construct

Every entry point does the same thing: a model (or you) writes a scene or a parameter
document; Construct checks it, and the draft is repaired until it is clean; then it is built
and, optionally, reviewed and filmed. Paths below are relative to a checkout of
`https://github.com/rtmandreyev/construct`.

## Requirements

Python 3.10 or newer; nothing else to install. For review stills and video: a
Chromium-family browser already on the machine (Chrome, Chromium, Edge or Brave; or set
`HOLOGRAM_CHROME=/path/to/browser`) and ffmpeg. Construct never downloads or installs anything.

## A worked example, end to end (no model)

A paperback whose title you know and whose author you do not:

```sh
C=construct_hologram/cli.py
python3 $C params book --variant paperback --output book.json
```

Fill in what you know — and only that. An unknown author is left out, not guessed:

```json
{
  "format": "construct-params", "version": 1,
  "archetype": "book", "variant": "paperback",
  "id": "small-hours", "title": "Small Hours", "synthetic": false,
  "facts": [{"key": "title", "value": "Small Hours", "certainty": "user_supplied", "source": "request"}],
  "artwork": {}, "params": {}
}
```

```text
$ python3 $C check book.json
audit: PASS (0 errors, 0 warnings)
  size 0.1299 x 0.198 x 0.0251 m
  68 lines, 36 triangles, 0 points, 0 moving copies
  evidence-backed key parts: 0 of 2

$ python3 $C build book.json --out out
wrote out/construct.html

$ python3 $C review book.json --out out
captured: out/review/sheet-assembly.png, sheet-views.png, sheet-life.png, sheet-motion.png,
          sheet-provenance.png, still-reduced-motion.png, view-spine.png, view-open.png, hero.png

$ python3 $C video book.json --out out/small-hours.mp4 --seconds 12
wrote out/small-hours.mp4
```

`out/` now holds `construct.html` (84 KB, self-contained: open it in any browser),
`geometry.json` (for apps), `audit.json`/`audit.txt`, `review/` and the video (2 MB). The book
assembles, its cover opens to a title page set from the `title` fact, and its spine carries
the title. With no author fact there is no author line, and with no cover image the cover
shows its designed no-art face.

`check --json` gives the machine-readable report: `ok`, `needs_repair`, `diagnostics[]`
(`severity, code, path, message, hint`) and `repair_text`.

## Hermes

1. Build the skill: `python3 construct_hologram/package.py --out dist`.
2. Copy `dist/hermes/construct` into `~/.hermes/skills/`, or into a project's
   `.hermes/skills/` and run `hermes skills trust` in that project.
3. Ask in plain words: *"Make a construct of my CD: Glass Harbour by The Lantern Choir, a
   normal jewel case."* Hermes finds the skill from its description; the skill runs the CLI
   above with the right archetype or a full scene, repairs, builds and reviews.

The skill's body refers to its own runtime through `${HERMES_SKILL_DIR}`; nothing else is
configured.

## Claude Code

`claude --plugin-dir dist/claude-code/construct` loads it for one session (nothing is
installed or changed). To keep it in a project, copy `dist/claude-code/construct/skills/construct`
into `.claude/skills/` (or `~/.claude/skills/` for all projects). Ask in plain words, or invoke
`/construct:construct` from the plugin.

## Any MCP agent

Run `python3 construct_hologram/server.py` as a stdio server:

```json
{"mcpServers": {"construct": {"command": "python3", "args": ["/abs/path/construct/construct_hologram/server.py"]}}}
```

| tool | does |
|---|---|
| `construct_diagnose` | checks a draft (raw model text or parsed JSON): `ok`, `needs_repair`, diagnostics with paths and hints, `repair_text` |
| `construct_params_template` | a parameter document for an archetype and variant (no arguments: the list) |
| `construct_expand_params` | the full scene a parameter document builds |
| `construct_compile` | compiled `construct-geometry` for a scene or parameter document |
| `construct_limits` | an effort tier's limits (with overrides, or `tier:`/`research:` read from a request), for the host to enforce |
| `hologram_template`, `hologram_validate`, `hologram_compile` | the legacy v0.1 construction sheets |

The tools read only the JSON they are given: no file access, rendering or network.
The 0.2 pre-release names (`hologram_diagnose`, `hologram_params_template`,
`hologram_expand_params`, `hologram_compile_scene`) still answer for one release.

## Any OpenAI-compatible model

```sh
export DEEPSEEK_API_KEY=...            # your key, in your shell; Construct never stores it
python3 construct_hologram/cli.py author "a 440 ml can of Example Porter, 5.6% ABV" --params \
    --base-url https://api.deepseek.com/v1 --model deepseek-chat --key-env DEEPSEEK_API_KEY --out can.json
```

`author` sends `prompts/system.md`, then `params.md` (with `--params`, best for small models)
or `scene.md`, then your request; checks each answer and sends back the repair text until
`needs_repair` is false. With `--vision` (the model can see images) and a browser, it then
renders the construct and asks the model for an art-direction review of its own captures
(`prompts/vision-review.md`), improving the weakest point each round until the verdict is
"good". Then `build`/`review` it.

The effort tier bounds the whole run, and `author` enforces it: whichever comes first ends
the run — a "good" verdict, or any limit — and the best draft so far is written with its
`authoring` record (tier, outcome, `next` improvements), printed as `next:` lines too. Every
new best valid draft is written to `--out` as soon as it passes the check, so a valid construct
is on disk even if a host stops the run; no review round starts after 80% of the wall clock.

```sh
python3 construct_hologram/cli.py author "a Revox A77 tape recorder" --tier showcase --vision \
    --reference https://example.org/a77-front.jpg --max-cost 0.50 --price-in 0.27 --price-out 1.10 \
    --base-url ... --model ... --key-env ... --out a77.json
```

| option | effect |
|---|---|
| `--tier quick\|standard\|showcase\|masterpiece` | the limits below (default standard; also `tier: ...` in the request) |
| `--research auto\|on\|off` | the research policy, or the user's override (also `research: ...` in the request) |
| `--rounds`, `--review-rounds`, `--max-seconds`, `--max-images` | raise or lower one limit (never remove it) |
| `--critic` (or `--critic-model`, `--critic-base-url`, `--critic-key-env`) | an independent critic, a fresh call, judges each review against the references; only its verdict records "good" or "outstanding" |
| `--max-total-tokens`, `--max-cost` with `--price-in`/`--price-out` | an optional token or cost ceiling (USD per million tokens) |

| tier | wall clock | review/improve rounds | check rounds | web reference images |
|---|---|---|---|---|
| quick | 2 min | 0 (audit only) | 3 | none |
| standard | 10 min | 2 | 6 | 3 |
| showcase | 30 min | 4 | 10 | 6 |

**Masterpiece** (`--tier masterpiece`, for hard subjects on request) has no round cap and a
2-hour safety stop: every round the critic compares renders with your references (`--reference
side=side.jpg --reference top=top.jpg`), its ranked defects go back to the author, and a
checkpoint is written to `<out>.checkpoints/`. It stops when the critic scores every criterion
3, at `--max-cost`, at the safety stop, or when you press Ctrl-C (the best version so far is
written).

**Masterpiece rounds in an agent** (Claude Code, Hermes): `construct rounds` runs the judged
loop on disk: `rounds start scene.json`; each round `rounds change <ledger id> "what"` for at
most 4 ledger items, `rounds packet --reference ...` for ONE critic (blind first, then this
version against the best so far as an unlabelled A/B pair, then the defect ledger), and `rounds
record answer.json`. A version is kept when it wins the pair; otherwise the best comes back.
Its round report, `rounds.md`, `checkpoints/round-NN/`, `ledger.json` and `state.json` make
the run readable and resumable (`rounds status`). See `skill/references/rounds.md`.

**Recommended models.** From the evaluation runs:

- **Hard subjects at Masterpiece** (a named car, a landmark): GPT-6.1 Sol or Claude Opus.
- **Simpler objects at Standard or Showcase:** DeepSeek works as well as those, with no
  regression on objects such as a tape deck, a watch or a camera.
- **Small or free models** (MiniMax, Inkling, Nemotron) are not recommended. In about half of
  their runs they failed to save a scene at all, and they made scale errors.

**The critic in any host:** `construct critique scene.json --reference side=photo.jpg` writes a
packet (instructions, checklist, renders beside references) for a fresh subagent or a second
model (`--base-url --model --key-env`); `--record critique.json` checks the answer, binds it to
the scene's hash and writes the ranked defects. See `skill/references/review.md`.

The runner has no web search: research is the reference images you attach (web images count
against the tier; your own photos are source data). Agents with web tools follow the research
policy and counts in `prompts/system.md` and `skill/references/effort.md`. Hosts add hard
limits on top (a Hermes run budget, an agent harness's timeout and cost ceiling); MCP hosts get
a tier's limits from `construct_limits`. The same works for OpenRouter, OpenAI, and local servers (Ollama
`http://localhost:11434/v1`, llama.cpp, LM Studio).

To build your own runner, use the files in `construct_hologram/prompts/` directly:
`system.md`, `params.md` or `scene.md`, `repair.md` (the loop), `vision-review.md` (an optional
self-review for models that can see images) and `params.schema.json` (for endpoints that
constrain output to a JSON Schema).

## Likeness from reference images

Text gives dimensions, not shapes. For things whose identity is an outline, a model that can
see traces a reference — the user's own photo, or a web image it views without keeping — into
a `construct-trace` document (`prompts/trace.md`), and `construct trace` fits it to a
documented dimension:

```sh
python3 construct_hologram/cli.py trace body-trace.json --fit nut:bridge=0.648 --out body.json
python3 construct_hologram/cli.py trace-image photo.jpg --what "the guitar body outline, front view" \
    --features nut,bridge --fit nut:bridge=0.648 --base-url https://api.openai.com/v1 \
    --model <a vision model> --key-env OPENAI_API_KEY --out body.json
```

The result is an `extrude` profile in metres, the features in metres, a `reference_image`
source and an `inferred` part stub. The image is never embedded. Any model that can see images
works, DeepSeek included; in Hermes enable the vision toolset (`vision_analyze`); in Claude
Code put the photo in the working folder.
See `construct_hologram/skill/references/tracing.md`.

## Likeness: multi-view lofts and silhouette comparison

```sh
python3 construct_hologram/cli.py loft-from-traces --side side.json --top top.json --front front.json \
    --length 4.14 --height 1.07 --width 1.89 --into car.json --part body --drop glasshouse
python3 construct_hologram/cli.py compare car.json --trace side.json --view side --overlay side.png --record
```

`loft-from-traces` turns three traced views into loft stations; `compare` measures the
construct's silhouette from a view against a traced outline (IoU and outline distance; exit
code 2 until it passes). See `construct_hologram/skill/references/tracing.md`.

## Python

```python
from construct_hologram import diagnose, params, scene, render

report = diagnose.diagnose_text(model_output)           # ok, needs_repair, diagnostics, repair_text
if not report["needs_repair"]:
    doc, _ = diagnose.parse_text(model_output)
    if params.is_params(doc):                            # the simple path
        doc = params.expand(doc)
    geometry = scene.compile_scene(doc)                  # construct-geometry, see CONTRACT.md
    html, notes = render.build_html(geometry, asset_root="assets")
```

## Costs and time (live runs)

Measured through Hermes on five synthetic tasks (three parameter entries, a lamp, a fictional
creature); both models scored 15/15 with no invented facts:

| model | cost | time |
|---|---|---|
| DeepSeek (`deepseek-flash`) | about $0.003 per parameter entry, $0.01–0.02 per full scene ($0.038 for all five) | 258 s for all five |
| GPT-6.1 Sol (`gpt-6.1-sol`, through a ChatGPT plan) | covered by the plan | 357 s for all five |

Construct itself runs locally in seconds: `check` and `build` well under a second for typical
objects, `review` 10–30 s, a 12 s video about a minute.

## Making it look good

- Start from an archetype when one fits; otherwise from an example in
  `construct_hologram/examples/v2/`.
- Fix every `detached` and `thin` warning: they are what a viewer notices first.
- For a named subject, research first: the maker's pages and specs, reference photos viewed
  with vision, the identity shape traced. Then author.
- Look at `review/hero.png`, `sheet-views.png` and `sheet-assembly.png` (or have a vision
  model do it with `prompts/vision-review.md`) and score them against the art-direction
  rubric in `skill/references/review.md`. The audit proves validity, not beauty or likeness.
- The skill's references (`construct_hologram/skill/references/`) cover vocabulary,
  composition, animation, review and provenance.
