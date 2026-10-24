# Development

This page is for contributors and for people building Construct into their own tools: the
command-line details, the file formats, the programming interfaces and the test suite. If you
just want to make constructs, [USING.md](USING.md) is the page for you.

## The repository

| Path | What it holds |
| --- | --- |
| `construct_hologram/` | the toolkit: the scene compiler (`scene.py`), the audit (`audit.py`), diagnostics (`diagnose.py`), the archetypes (`params.py`), the viewer (`viewer/`), captures (`render.py`), film mode (`film_audio.py`, and the optional three.js loader in `film/`), the command line (`studio.py`, `cli.py`) and the tests |
| `construct_hologram/skill/` | the agent skill: `SKILL.md` and its references (vocabulary, composition, craft, rounds, review, tracing and more) |
| `construct_hologram/prompts/` | the same rules for other models and hosts, generated from `prompts.py` |
| `construct_hologram/examples/v2/` | the skill's own examples and the archetypes' golden documents |
| `examples/` | the example constructs shown in the gallery |
| `hosts/claude-code/` | an optional Claude Code hook that enforces a mode's limits |
| `scripts/` | the gallery builder, the docs pictures, the release video and the Hermes submission draft |

## Tests

```sh
python3 -m unittest discover -s construct_hologram -t . -p 'test_*.py'
```

The suite uses the standard library only and needs no network and no model. A Chromium-family
browser enables the capture tests (review stills, critic packets); without one, or with
`HOLOGRAM_SKIP_CAPTURE=1`, they are skipped. CI (`.github/workflows/tests.yml`) runs the suite
on every push and pull request with the captures skipped. The tests compile every example,
check the prompts against their generator, build the host packages and the gallery, and check
the gallery's links.

## The command line

Every command is `python3 construct_hologram/cli.py <command>`:

| Command | Does |
| --- | --- |
| `new <category>` | a starter scene |
| `params --list`, `params <archetype> --variant <v>` | the archetypes, or a parameter document to fill |
| `check scene.json [--json]` | validate, compile and audit |
| `build scene.json --out out/` | `out/construct.html`, `geometry.json` and the audit |
| `review scene.json --out out/ [--size WxH] [--sheets ...]` | stills and contact sheets in `out/review/` |
| `video scene.json --out out/x.mp4 --seconds 12` | a video (needs ffmpeg) |
| `audio track.wav --out audio.json [--voice stem.wav] [--scale track\|fixed]` | film mode: per-frame audio features ([FILM.md](FILM.md)) |
| `video ... --assembly S --audio audio.json --sound track.wav` | film mode: an assembly of S seconds paced by the music, with the track in the video |
| `author "request" --base-url ... --model ... --key-env ...` | the whole loop with any OpenAI-compatible model |
| `critique scene.json --reference view=photo.jpg` | a packet for an independent critic; `--record answer.json` records its answer |
| `rounds start/change/packet/record/run/pause/status/report` | the masterpiece loop on disk |
| `trace`, `trace-image`, `loft-from-traces`, `compare` | likeness from reference outlines |
| `terrain` | measured terrain from elevation data ([TERRAIN.md](TERRAIN.md)) |
| `prompts --out dir` | regenerate the prompts |

### The check report

`check --json` gives a machine-readable report: `ok`, `needs_repair`, `diagnostics[]` (each with
`severity`, `code`, `path`, `message` and `hint`) and `repair_text`, which a host can send back to
the model as is.

### `author`: the any-model runner

`author` sends `prompts/system.md`, then `params.md` (with `--params`, best for small models) or
`scene.md`, then the request; it checks each answer and sends back the repair text until the
draft is clean. With `--vision` (the model can see images) and a browser, it then renders the
construct and asks for a review of its own captures, improving the weakest point each round.
Every new best valid draft is written to `--out` at once, so a valid construct is on disk even
if the host stops the run.

| Option | Effect |
| --- | --- |
| `--mode fast\|masterpiece\|unbounded` (or `--tier quick\|standard\|showcase\|masterpiece`) | the limits below (default fast; also `mode: ...` or `tier: ...` in the request) |
| `--research auto\|on\|off` | the research policy, or the user's override |
| `--rounds`, `--review-rounds`, `--max-seconds`, `--max-images` | raise or lower one limit |
| `--critic` (or `--critic-model`, `--critic-base-url`, `--critic-key-env`) | an independent critic, a fresh model call, judges each review against the references |
| `--max-total-tokens`, `--max-cost` with `--price-in`/`--price-out` | an optional token or cost ceiling (USD per million tokens) |

| Mode | Tier | Wall clock | Review rounds | Check rounds | Web reference images |
| --- | --- | --- | --- | --- | --- |
| fast | quick | 2 min | 0 (audit only) | 3 | none |
| fast | standard | 10 min | 2 | 6 | 3 |
| fast | showcase | 30 min | 4 | 10 | 6 |
| masterpiece | masterpiece | 2 hours | 12 | 8 per round | 12 |
| unbounded | unbounded | none | no cap | 8 per round | 12 |

In masterpiece and unbounded mode the critic compares renders with your references every round
(`--reference side=side.jpg --reference top=top.jpg`), its ranked defects go back to the
author, and a checkpoint is written to `<out>.checkpoints/`. The runner has no web search:
research is the reference images you attach.

### `rounds`: the masterpiece loop in an agent

`rounds start scene.json --mode masterpiece` (or `unbounded`) starts a run in the scene's folder.
Each round the author works on at most four items from the defect list (`rounds change <id> "what changed"`), writes the critic's packet
(`rounds packet --reference ...`) and records the critic's answer (`rounds record answer.json`).
The packet asks the critic for its own judgement first, then for a blind pick between this
version and the best so far, then for the status of the earlier defects. `rounds run
--base-url ...` runs the critic as one model conversation instead of a helper agent.

The run lives in its folder: `state.json`, the defect list (`ledger.json`), `rounds.md` (one
section per round) and `checkpoints/round-NN/`. `rounds status` says where a run is after any
interruption, and `rounds pause` marks a break. The full procedure is in
[`skill/references/rounds.md`](../construct_hologram/skill/references/rounds.md).

### Likeness from reference outlines

```sh
python3 construct_hologram/cli.py trace body-trace.json --fit nut:bridge=0.648 --out body.json
python3 construct_hologram/cli.py trace-image photo.jpg --what "the guitar body outline, front view" \
    --features nut,bridge --fit nut:bridge=0.648 --base-url ... --model <a vision model> --key-env ... --out body.json
python3 construct_hologram/cli.py loft-from-traces --side side.json --top top.json --front front.json \
    --length 4.14 --height 1.07 --width 1.89 --into car.json --part body --drop glasshouse
python3 construct_hologram/cli.py compare car.json --trace side.json --view side --overlay side.png --record
```

A model that can see traces an outline from a reference into a `construct-trace` document, and
`trace` fits it to a documented dimension; the image itself is never embedded. `loft-from-traces`
turns three traced views into a body, and `compare` measures the construct's silhouette against
a traced outline. See [`skill/references/tracing.md`](../construct_hologram/skill/references/tracing.md).

## MCP tools

`python3 construct_hologram/server.py` is a stdio MCP server:

| Tool | Does |
| --- | --- |
| `construct_diagnose` | checks a draft (raw model text or parsed JSON) and returns the report above |
| `construct_params_template` | a parameter document for an archetype and variant (no arguments: the list) |
| `construct_expand_params` | the full scene a parameter document builds |
| `construct_compile` | compiled `construct-geometry` for a scene or parameter document |
| `construct_limits` | a mode's limits, with overrides or the words in a request, for the host to enforce |
| `hologram_template`, `hologram_validate`, `hologram_compile` | the legacy v0.1 construction sheets |

The tools read only the JSON they are given: no file access, rendering or network. The 0.2
pre-release names (`hologram_diagnose`, `hologram_params_template`, `hologram_expand_params`,
`hologram_compile_scene`) still answer for one release.

## Building your own runner

Use the files in `construct_hologram/prompts/` directly: `system.md`, `params.md` or `scene.md`,
`repair.md` (the loop), `vision-review.md` (a self-review for models that can see images),
`critic.md` and `round.md` (the critic), and `params.schema.json` for endpoints that constrain
output to a JSON Schema. `construct_limits` (or `construct_hologram.tiers.limits`) gives a mode's
limits for your loop to enforce.

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

The compiled geometry and its JSON Schema are described in [CONTRACT.md](../CONTRACT.md).

## The gallery, the docs pictures and the packages

- `python3 scripts/build_site.py --out site` builds the examples gallery (see
  [PUBLISHING.md](../PUBLISHING.md)).
- `python3 scripts/docs_media.py` renders some of the pictures in `docs/media/`.
- `python3 construct_hologram/package.py --out dist` builds the Claude Code and Hermes skills;
  `python3 scripts/hermes_submission.py` assembles a draft submission of the skill to Hermes.
