# Using Construct

Construct works the same way wherever you run it. A model, or you, writes a scene; Construct
checks it and the scene is repaired until it is clean; then it is built into a page you can open
in any browser, and reviewed. This page walks through each way to run it, starting with the
simplest. To see what the results look like first, open the
[examples gallery](https://rtmandreyev.github.io/construct/).

## Before you start

You need Python 3.10 or newer, and nothing else to install. For review stills, Construct uses a
Chromium-family browser you already have (Chrome, Chromium, Edge or Brave); if yours is
somewhere unusual, point to it with `HOLOGRAM_CHROME=/path/to/browser`. Videos also need ffmpeg.
Construct never downloads or installs anything.

Get a copy and build the skills:

```sh
git clone https://github.com/rtmandreyev/construct.git
cd construct
python3 construct_hologram/package.py --out dist
```

## Your first construct, by hand

You don't need a model to try Construct. Common things, like a book, a CD case, a guitar or a
bottle, have a ready-made template (an *archetype*) that you fill in with what you know. Here
is a paperback whose title you know and whose author you don't:

```sh
C=construct_hologram/cli.py
python3 $C params book --variant paperback --output book.json
```

Open `book.json` and fill in what you know, and only that. The author is left out rather than
guessed:

```json
{
  "format": "construct-params", "version": 1,
  "archetype": "book", "variant": "paperback",
  "id": "small-hours", "title": "Small Hours", "synthetic": false,
  "facts": [{"key": "title", "value": "Small Hours", "certainty": "user_supplied", "source": "request"}],
  "artwork": {}, "params": {}
}
```

Then check it, build it and look at it:

```text
$ python3 $C check book.json
audit: PASS (0 errors, 0 warnings)

$ python3 $C build book.json --out out
wrote out/construct.html

$ python3 $C review book.json --out out
captured: out/review/sheet-assembly.png, sheet-views.png, ... hero.png
```

Open `out/construct.html` in your browser. The book assembles itself, its cover opens to a
title page set from your title, and its spine carries the title too. With no author, there is
no author line; with no cover image, the cover shows its plain designed face. `out/review/`
holds the stills, and `python3 $C video book.json --out out/small-hours.mp4 --seconds 12`
makes a video.

All the archetypes are listed in [ARCHETYPES.md](ARCHETYPES.md).

## In Claude Code

Load the skill for one session with `claude --plugin-dir dist/claude-code/construct`; nothing is
installed or changed. To keep it in a project, copy `dist/claude-code/construct/skills/construct`
into the project's `.claude/skills/` (or into `~/.claude/skills/` for all your projects).

Then ask in plain words: *"make a construct of a 1970s desk fan"*. The skill picks a mode, tells
you which and why, and does the rest: it looks the subject up if it needs to, writes the scene,
checks it, builds it and reviews it. You can also start it with `/construct:construct`.

## In Hermes

Install it from this repository with `hermes skills install rtmandreyev/construct/skills/construct`
(Hermes scans it and asks before installing), or copy `dist/hermes/construct` into
`~/.hermes/skills/`, or into a project's `.hermes/skills/` and run `hermes skills trust` there. Then ask in plain words: *"Make a construct of my CD: Glass
Harbour by The Lantern Choir, a normal jewel case."* Hermes finds the skill from its description.

**Masterpiece mode in Hermes needs two settings.** Without them a masterpiece run can end early
or stop with an error, so it is worth setting them up before your first one.

- **Allow enough critics.** Masterpiece mode starts a fresh helper agent, the critic, every
  round. A one-shot Hermes run (`hermes chat -q` or `--oneshot`) may start only two helper
  agents in all by default, so the critic stops after two rounds and later rounds go unjudged.
  Raise the limit in Hermes's `config.yaml`, under `delegation:`, with `oneshot_max_children:
  14` (twelve rounds and a margin; `0` means no limit, for unbounded mode). Or run Hermes
  interactively, which has no such limit, or let the critic be a second model you name with
  `rounds run --base-url ... --model ... --key-env ...`.
- **Keep the pictures small.** Hermes sends at most 8 MB in one message. A turn that attaches
  several full-size review stills can pass that and stop the run. Ask for smaller stills
  (`review --size 1280x800`) and only the sheets you need (`--sheets assembly,views`). Because the
  skill saves a valid scene after every round, a stop like this costs at most the round in
  progress.

## In another agent, through MCP

Any agent that speaks MCP can use Construct's tools to check, compile and look up limits. Add the
server to your agent's configuration:

```json
{"mcpServers": {"construct": {"command": "python3", "args": ["/path/to/construct/construct_hologram/server.py"]}}}
```

The tools only read the JSON they are given; they never touch your files or the network. The list
of tools is in [DEVELOPMENT.md](DEVELOPMENT.md#mcp-tools).

## With any OpenAI-compatible model

`construct author` runs the whole loop with any model behind an OpenAI-compatible endpoint:
DeepSeek, OpenRouter, OpenAI, or a local server such as Ollama, llama.cpp or LM Studio. Your key
stays in your shell; Construct reads it from the environment variable you name and never stores it.

```sh
export DEEPSEEK_API_KEY=...
python3 construct_hologram/cli.py author "a 440 ml can of Example Porter, 5.6% ABV" --params \
    --base-url https://api.deepseek.com/v1 --model deepseek-chat --key-env DEEPSEEK_API_KEY --out can.json
```

`--params` asks for a filled-in archetype, which suits small models best. Add `--vision` if the
model can see images, so it reviews its own stills, and `--mode masterpiece` with reference
photos (`--reference side=side.jpg`) for a named subject. Every option is in
[DEVELOPMENT.md](DEVELOPMENT.md#author-the-any-model-runner).

## Choosing a mode

You can name a mode in your request, or say nothing and let the skill choose and explain.
**fast** is one careful pass, about ten minutes, and suits most things. **masterpiece** runs
rounds judged by an independent critic, for a named car, landmark or building whose likeness
matters. **unbounded** is masterpiece without the 12-round cap and the two-hour limit, and the
skill only uses it when you ask. The README's [Modes](../README.md#modes) table has the details,
and [How a construct is made](HOW-IT-IS-MADE.md) explains the rounds.

## Following a masterpiece run

A masterpiece run reports to you after every round: what the critic asked for, what changed,
whether the new version beat the best one so far, and how long the round took. You can stop it
at any point and keep the best version, which is always saved. If a run is interrupted, for
example by a usage limit, `rounds status` in the run's folder says where it stopped, and the
agent picks up from there. `rounds pause` marks a deliberate break, so the time away isn't
counted against the two-hour limit.

## Getting the likeness right

Text gives dimensions, not shapes. For things whose identity is an outline, like a guitar body or
a car's side, a model that can see traces a reference photo into an outline, and Construct fits
that outline to a known dimension. The photo is only looked at; it is never embedded in the
construct. Masterpiece mode also compares each version with the reference photos through the
critic. The commands are in [DEVELOPMENT.md](DEVELOPMENT.md#likeness-from-reference-outlines).

## How long it takes and what it costs

Construct itself runs in seconds on your machine: checking and building take well under a
second for typical objects, review stills 10 to 30 seconds, and a 12-second video about a minute.
The model is where the time and cost go. Measured through Hermes on five small tasks (three
archetypes, a lamp and a fictional creature), both models scored full marks with nothing invented:

| Model | Cost | Time |
| --- | --- | --- |
| DeepSeek V4.1 Flash (1017; `deepseek-flash`) | about $0.003 per archetype, $0.01–0.02 per full scene | 258 s for all five |
| GPT-6.1 Sol (through a ChatGPT plan) | covered by the plan | 357 s for all five |

A masterpiece run uses a frontier model for up to two hours of working time plus the critic's
time, so it costs far more than a fast one.

## Making it look good

- **Start from an archetype** when one fits, or from a similar example in
  `construct_hologram/examples/v2/`.
- **Fix the warnings a viewer notices first:** parts that don't quite touch (`detached`), lines
  too thin to read (`thin`), and main surfaces drawn without their faint outline (`bare-surface`).
- **Research a named subject first:** the maker's pages and specifications, and reference photos
  looked at closely. Then write the scene.
- **Look at the pictures.** Open `review/hero.png`, `sheet-views.png` and `sheet-assembly.png`, or
  have a model that can see do it. The check proves a construct is valid and honest, not that it
  is beautiful or a good likeness.
- **The skill's references** in `construct_hologram/skill/references/` go deeper: the
  vocabulary of shapes, composition, the drawing craft, animation and review.

If something goes wrong, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
