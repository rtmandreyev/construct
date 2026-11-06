# Construct for Hermes

**Construct turns everything that can be found out about a thing into one exact, checked description of it: its
named parts at their real sizes, how they fit together, open and move, and how each one is known, measured or
guessed.** Hermes does the research and writes the description; Construct checks it and builds from it, the same
description always into the same result. Everything else comes from that one description.

**Describe a thing. Get a hologram, a 3D model, a print and a kit.** Ask Hermes for a thing in plain words and it
builds an animated model of it in lines of light, shown live in the chat and honest about what is known. The same
construct becomes a 3D model with named parts and working joints, a print, a model kit, a CAD file or a film. A
NetLogo model's run becomes one too.

See it used, from the request to a printable kit:
[Villa Savoye in Hermes, step by step](https://github.com/rtmandreyev/construct/blob/main/docs/for/hermes-walkthrough.md).

This is the Hermes plugin of [Construct](https://github.com/rtmandreyev/construct) (Apache-2.0). It runs
Construct's own engine, bundled as Python source; nothing is downloaded.

## What it does

Twelve tools (toolset `construct`), a `/construct` command, and the `construct:construct` skill that teaches Hermes
the craft: the fast and masterpiece modes, research and provenance rules, review as an art director, an
independent critic run as a fresh subagent through Hermes's delegation, and sixteen tutorials.

| tool | what it does |
|---|---|
| `construct_start` | a project from a finished construct the plugin ships (sixteen, from a Land Cruiser to the Sainte-Chapelle), an archetype, a category starter or a scene you name; with no arguments, the menu |
| `construct_edit` | change a scene by part id (move, rotate, resize, set fields, add or remove parts, facts and sources, certainty): each step validated, written only when nothing breaks, with the diff |
| `construct_check` | validate, compile and audit: every problem with its JSON path and a fix hint; `fit` finds solids that poke through or hide |
| `construct_inspect` | what the construct's own record says is known: parts by certainty, dimensions, facts and sources, joints, the critic's verdict, and its size as a body and overall (with what stands out) |
| `construct_build` | the self-contained animated WebGL page, shown live in the chat |
| `construct_review` | review images in a headless browser: hero, contact sheets, views, the solid |
| `construct_export` | glTF/OBJ (named parts, working joints, physics bodies), STL/3MF (watertight, checked), FreeCAD and STEP; every file read back and summarised |
| `construct_film` | a film of the construct assembling, across a music track if you like, rendered in the background |
| `construct_job` | progress and results of background work; `wait_seconds` waits for it |
| `construct_netlogo_run` | a NetLogo model run headless (yours, or one from your installed Models Library), drawn as a construct; N seeded runs compared |
| `construct_netlogo_draw` | recorded NetLogo runs drawn or compared, with no NetLogo needed |
| `construct_command` | the rest of Construct's command line (critique, rounds, tracing, lofting, likeness, terrain, globe, model kits, NetLogo plates and films), guarded |

Long work never runs into Hermes's tool deadline: a film, a NetLogo run, or a build, review or export that takes
longer than a few minutes, continues as a background job; `construct_job` reports it and waits for it, and a status
message in the chat follows its progress.

`/construct` lists your projects; `/construct open <project>`, `/construct examples`, `/construct learn [n]`
(the tutorials, with the message that starts one) and `/construct jobs` work on every surface.

## Hermes Desktop

- **Live in the chat.** A built construct plays in the conversation, with a toolbar: Provenance (how each part is
  known), Solid, Replay, How to read it, Open in browser, and actions that ask Hermes for the next step in that
  chat: Export a glTF, More detail, Review it. A NetLogo run's construct grows in the card while the run goes.
- **Its own viewers.** A glTF export opens as a model to turn, with each part's name, certainty and role on hover
  and its joints' animations to play; a STEP or FreeCAD file shows what was read back from it (parts, solids, exact
  and faceted shapes, surfaces, size); a model kit opens with its steps in 3D (back, next, step n of m) and its
  booklet. Films play.
- **The Constructs page** (sidebar, and the palette: *Construct: Open the Constructs page*, *Start from an
  example*, *Learn*): your projects, told apart by name, id and date, each with its builds, kits, exports, films and
  runs, and a note when the scene changed after its last build; **Start from**, the shipped constructs, each opening
  a new chat; and **Learn**, the tutorials, each a guided chat.
- **Job progress** in the status bar while a film renders or a run goes.

A construct page is several megabytes, more than a frame's address can carry, so the chat shows a small loader
that receives the page from the plugin's own backend route and replaces itself with it, inside the sandboxed
frame. The glTF viewer is three.js r180 (MIT, © three.js authors), bundled into `desktop/plugin.js` with its
licence; nothing is fetched at run time.

## Install

```bash
hermes plugins install rtmandreyev/construct#hermes/construct
hermes plugins enable construct
```

What Hermes installs is `hermes/construct/` in the Construct repository, generated by
`python3 scripts/hermes_plugin.py`, which adds the bundled engine (`_vendor/`), the skill's references, the shipped
constructs (`examples/`) and three.js (`hosts/hermes/three/`, built into `desktop/plugin.js`) to the plugin's source
in `hosts/hermes/construct/`. A test keeps the two in step.

Then restart the gateway (for the Desktop backend routes) and turn the Desktop half on in **Capabilities →
Plugins**. Requires Hermes 0.22 or newer and Python 3.10+ (Hermes's own). Optional programs, used when present
and never installed: a Chromium-family browser (review images, gallery stills, films), ffmpeg (films), FreeCAD
(FCStd and STEP), Blender (NetLogo films), NetLogo 7 with its Java (NetLogo runs).

Settings (**Settings → Plugins → Construct**): the projects folder (default: the plugin's data folder), *Ask
before running programs*, which puts each call that runs a browser, ffmpeg, FreeCAD, Blender or NetLogo behind
Hermes's approval prompt (scheduled runs are then refused rather than left waiting), and the NetLogo folder (blank:
`CONSTRUCT_NETLOGO` and the usual install places).

## What it touches (disclosures)

- **Local programs:** it runs Construct in a child Python process (Hermes's own interpreter), and, when present,
  a headless Chrome/Chromium (captures only: a private temporary profile, driven over a local debugging port),
  ffmpeg, FreeCAD and Blender. Nothing already on the machine is changed. No approval prompt unless *Ask before
  running programs* is on.
- **No network.** Nothing is fetched or sent; the subcommands that call a model over the network (`author`,
  `trace-image`, `--base-url`, `rounds run`) are refused, and the critic runs as a Hermes subagent instead.
- **Files:** it writes only inside its data folder (`<HERMES_HOME>/plugin-data/construct/`) or the projects
  folder you set, plus short-lived temporary files (the browser's profile) in the system's temporary folder,
  removed when each run ends. It reads scenes, images and music files you name.
- **NetLogo (optional).** `construct_netlogo_run` runs NetLogo models headless on this machine with NetLogo's own
  Java (or `JAVA_HOME`, a Homebrew OpenJDK, or `java` on the PATH), as a background job. It reads models from your
  NetLogo install or a path you give, and writes only into the plugin's data or projects folder (an instrumented
  copy of the model, the recordings, the constructs). The plugin bundles no NetLogo model, run or construct of one.
  Models Library models are © their authors under CC BY-NC-SA 3.0: a construct made from one carries the model's
  credit and licence (in its record and a README.md in its project) and is for non-commercial use, shared alike.
- **Background processes:** films, NetLogo runs and long work continue as background jobs; they are stopped when
  the plugin unloads.
- **No telemetry**, no stored credentials.

## License

Apache-2.0, as Construct. See `LICENSE` and `NOTICE`.
