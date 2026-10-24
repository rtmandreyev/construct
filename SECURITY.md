# Security

## Reporting a vulnerability

Construct is a small single-author project with no security team. If you find a
security-relevant problem, please report it **privately** rather than in a public issue:

- Preferred: GitHub's private vulnerability reporting on this repository (*Security* →
  *Report a vulnerability*), which keeps the report and the fix out of public view until a fix
  exists.
- If that is unavailable, open a public issue that says only that you have a security-sensitive
  report and how to reach you, with no details.

There is no security email address. Please do not send credentials or private files to any
address you find in this repository.

## What Construct does that is security-relevant

- **A construct is a static page.** `construct.html` is one self-contained file: plain WebGL2,
  no external scripts, fonts or styles, and no network calls. It runs no code from the scene: a
  scene is data that the compiler validates, and text in it is escaped before it is embedded.
  The one exception to "no calls" is film mode: a construct built for film (`build --film`, or
  `video` with a film option) and opened with `?audio=features.json` reads that one file of
  numbers beside the page, and nothing else. A construct built without film mode makes no calls.
- **The toolkit is local.** It reads and writes files you point it at. It never downloads or
  installs anything, and it uses only Python's standard library.
- **Review captures** start a local Chromium-family browser you already have, headless, on the
  pages Construct built.
- **Model calls happen only when you ask for them**: `construct author`, `critique --base-url`
  and `rounds run` send the scene and its renders to the OpenAI-compatible endpoint you name.
  The API key is read from the environment variable you give (`--key-env`) and is never written
  to disk.
- **The MCP server** offers read-only tools: check, expand, compile and look up limits.

## Please do not include in a report or an issue

- API keys, tokens, passwords or private keys.
- Scenes, references or renders you are not allowed to share.
