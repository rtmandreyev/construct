# Construct for Hermes

Build **constructs** with Hermes: animated holographic models of real or invented things (a camera, a
lighthouse, a bus, a jellyfish), built from facts, with every part saying how it is known. Hermes writes the
scene; Construct checks it, audits it, renders it and exports it. In Hermes Desktop each construct appears live
in the chat, and a **Constructs** page keeps them all.

This is the Hermes plugin of [Construct](https://github.com/rtmandreyev/construct) (Apache-2.0). It runs
Construct's own engine, bundled as Python source; nothing is downloaded.

## What it does

Nine tools (toolset `construct`), and the `construct:construct` skill that teaches Hermes the craft: the fast and
masterpiece modes, research and provenance rules, review as an art director, and an independent critic run as a
fresh subagent through Hermes's delegation.

| tool | what it does |
|---|---|
| `construct_start` | a project from an archetype (CD case, book, guitar, synth, car, bottle...), a starter scene, a bundled example or a scene you name; with no arguments, the menu |
| `construct_check` | validate, compile and audit: every problem with its JSON path and a fix hint; `fit` finds solids that poke through or hide, with the parts and a fix |
| `construct_inspect` | what the construct's own record says is known: parts by certainty, verified and inferred dimensions, facts and sources, joints, the critic's verdict |
| `construct_build` | the self-contained animated WebGL page, shown live in the chat |
| `construct_review` | review images in a headless browser: hero, contact sheets, views, the solid |
| `construct_export` | glTF/OBJ (named parts, working joints, physics bodies), STL/3MF (watertight, checked), FreeCAD and STEP |
| `construct_film` | a film of the construct assembling, across a music track if you like, rendered in the background |
| `construct_job` | progress and results of background work |
| `construct_command` | the rest of Construct's command line (critique, rounds, tracing, lofting, likeness, terrain, globe, model kits, NetLogo), guarded |

Long work never runs into Hermes's tool deadline: a film, or a build, review or export that takes longer than a
few minutes, continues as a background job; `construct_job` reports it, and a status message in the chat follows
its progress.

## Hermes Desktop

- **Live in the chat.** A built construct plays in the conversation, with a toolbar: Provenance (how each part is
  known), Solid, Replay, Open in browser, and actions that ask Hermes for the next step in that chat: Export a
  glTF, More detail, Review it.
- **Constructs page.** A gallery of everything built (title, parts, date, a still), each one opening live.
- **Job progress** in the status bar while a film renders.

The page is several megabytes, more than a frame's address can carry, so the chat shows a small loader that
receives the page from the plugin's own backend route and replaces itself with it, inside the sandboxed frame.

## Install

```bash
hermes plugins install rtmandreyev/construct-hermes
hermes plugins enable construct
```

This package is generated from the Construct repository (`python3 scripts/hermes_plugin.py`), which adds the
bundled engine (`_vendor/`), the skill's references and the example scenes to the plugin's source in
`hosts/hermes/construct/`.

Then restart the gateway (for the Desktop backend routes) and turn the Desktop half on in **Capabilities →
Plugins**. Requires Hermes 0.22 or newer and Python 3.10+ (Hermes's own). Optional programs, used when present
and never installed: a Chromium-family browser (review images, gallery stills, films), ffmpeg (films), FreeCAD
(FCStd and STEP), Blender (NetLogo films).

Settings (**Settings → Plugins → Construct**): the projects folder (default: the plugin's data folder) and *Ask
before running programs*, which puts each call that runs a browser, ffmpeg, FreeCAD or Blender behind Hermes's
approval prompt (scheduled runs are then refused rather than left waiting).

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
- **Background processes:** films and long runs continue as background jobs; they are stopped when the plugin
  unloads.
- **No telemetry**, no stored credentials.

## License

Apache-2.0, as Construct. See `LICENSE` and `NOTICE`.
