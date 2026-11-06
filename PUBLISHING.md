# Publishing the repository and the examples gallery

This repository has two branches to publish:

- `main`: the source, tagged at each release (the latest is `v1.2.0`);
- `gh-pages`: the examples gallery, a static site served from the branch's root.

The public addresses below come from one place: `OWNER` and `REPO` at the top of
`scripts/build_site.py`. To publish under another name, run
`python3 scripts/build_site.py --set-url OWNER/REPO`, rebuild the gallery (step 5), and
commit; every link in the documents follows.

## 1. Create the repository

On GitHub, create an **empty public** repository named `construct` under `rtmandreyev`: no
README, no licence, no .gitignore (they are already here). With the GitHub CLI:

```sh
gh repo create rtmandreyev/construct --public --description "Holographic constructs any AI agent can build: from a description, honestly."
```

Commits here use the GitHub private address `269336670+rtmandreyev@users.noreply.github.com`.
If "Block command line pushes that expose my email" is on in your GitHub email settings,
pushes still go through.

**Reviewing it privately first?** Create it with `--private` instead. Everything in `main`
renders the same; GitHub Pages for a private repository needs a paid plan, so the gallery links
in the README work once the repository is public (or Pages is enabled on such a plan).
Making it public later: **Settings → General → Danger Zone → Change visibility**, then step 4.

**About and topics** (the repository page's gear icon next to "About"):

- Description: *Describe a thing, get a hologram, a 3D model and its parts: built by any AI agent, honestly.*
- Website: https://rtmandreyev.github.io/construct/
- Topics: `ai-agents`, `agent-skills`, `claude-code`, `mcp`, `webgl`, `hologram`,
  `procedural-generation`, `3d-visualization`, `gltf`, `blender-addon`, `game-assets`, `netlogo`,
  `agent-based-modeling`, `llm`, `python` (GitHub allows 20)

## 2. Push `main` and the tag

```sh
cd construct    # your checkout
git remote add origin https://github.com/rtmandreyev/construct.git
git push -u origin main
git push origin v1.2.0
```

## 3. Push the gallery

```sh
git push origin gh-pages
```

## 4. Turn on GitHub Pages

In the repository: **Settings → Pages → Build and deployment → Source: Deploy from a
branch**, branch **gh-pages**, folder **/ (root)**, then **Save**. Or with the CLI:

```sh
gh api -X POST repos/rtmandreyev/construct/pages -f "source[branch]=gh-pages" -f "source[path]=/"
```

After a minute or two the gallery is at https://rtmandreyev.github.io/construct/ (Settings →
Pages shows the address once it is live). Open it, open two or three examples, and check
that they assemble and that the README's animations link to them.

Optionally, publish a release: **Releases → Draft a new release**, tag `v1.2.0`, and
its notes: [docs/releases/v1.1.0.md](docs/releases/v1.1.0.md) for 1.1, its CHANGELOG entry for a fix release. Attach the two zips from `dist/`:
`construct-blender-1.2.0.zip` (`python3 scripts/build_blender_extension.py`) and `construct-1.2.0.zip`,
the NetLogo extension (`python3 scripts/build_netlogo_extension.py --netlogo "<NetLogo 7 folder>"`, with a
JDK 17 or newer: `--javac` names it). Attach the kits too, `construct-kit-<slug>.zip`, one per kit in
`examples/kits.json` (`python3 scripts/build_kit_zips.py`, about ten minutes): the gallery, the README and the docs
link to them as `releases/latest/download/construct-kit-<slug>.zip`, so every release carries them, under
those names.

## 5. Update the gallery later

```sh
cd construct    # your checkout
python3 scripts/build_site.py --out site --films DIR  # compiles every example and makes the kits (about ten minutes)
python3 -m http.server 8000 --directory site          # preview at http://localhost:8000/
git worktree add ../construct-pages gh-pages
rsync -a --delete --exclude .git site/ ../construct-pages/
git -C ../construct-pages add -A
git -C ../construct-pages commit -m "Gallery: rebuild"
git -C ../construct-pages push origin gh-pages
git worktree remove ../construct-pages
```

To add an example: put its `scene.json` in `examples/<slug>/`, add an entry to
`examples/examples.json`, write its `README.md` like the others, draw its pictures with
`python3 scripts/gallery_images.py <slug>` (`hero.jpg`, 1440 × 900, and `thumb.jpg`, 1200 × 750,
framed close to the construct), and rebuild.

The model kits (`examples/kits.json`) are made with `construct kit` from each example's scene (or a
kit-ready copy, `"scene"`), its plan and its paints, side by side; the gallery publishes each kit's 3D
guide and booklet, not its plates. `--no-kits` builds the gallery without them, in a minute or two.

The films are the exception to "everything is in the repository": their videos are published
with the gallery only, never in `main`. `--films DIR` names the folder that holds them (the file
names in `examples/films.json`); `--no-films` builds the gallery without them. To add a film: put
its scene in `examples/films/<slug>/scene.json`, add an entry to `examples/films.json` (the object,
mode, model and video file), keep the video at about 20 MB or less (re-encode it with ffmpeg if
needed), draw its poster with `python3 scripts/gallery_images.py <slug>`, and rebuild with
`--films`.

## 6. A new release: the version, everywhere

The version lives in a few places kept by hand; `test_package.py` checks them against `construct_hologram/product.py`,
so a release that misses one fails its tests. For version X.Y.Z:

1. `construct_hologram/product.py`: `VERSION = "X.Y.Z"`. The packages, the MCP server, the 3D exports' generator
   strings, the Blender and NetLogo manifests and the zips' names follow it.
2. `pyproject.toml`: `version = "X.Y.Z"`.
3. `scripts/hermes_submission/SKILL.md`: `version: X.Y.Z` and the `upstream:` line's `(vX.Y.Z)`.
4. `scripts/hermes_submission/PR.md`: the `Upstream:` line's `(Apache-2.0, vX.Y.Z)`; and `hosts/hermes/construct/plugin.yaml`:
   `version: "X.Y.Z"` (the Hermes plugin keeps Construct's version).
5. This file: the latest tag at the top, `git push origin vX.Y.Z` (step 2), the release's tag and the two zips'
   names (step 4).
6. `python3 scripts/hermes_submission.py --hub`, which regenerates `skills/construct/` (the Hermes skill, its
   frontmatter and its copy of `product.py`), and `python3 scripts/hermes_plugin.py`, which regenerates
   `hermes/construct/` (the Hermes plugin as Hermes installs it). After the release is pushed, the Hermes catalog
   entry (`plugin-catalog/construct.yaml` in NousResearch/hermes-agent, `subdir: hermes/construct`) gets the tagged
   commit's `sha` and the new `version` in a PR there.
7. `CHANGELOG.md`: the top heading becomes `## X.Y.Z — <date>`. A minor release (X.Y.0) also gets its notes,
   `docs/releases/vX.Y.Z.md`, listed in `README.md` and `docs/README.md`; a fix release uses its CHANGELOG entry.
8. Run the tests, commit, tag `vX.Y.Z`, then build the release's zips (step 4) and the gallery (step 5).

## What the gallery needs

Nothing but static files: every link is relative, each construct is one self-contained
`construct.html` (plain WebGL2, no external scripts, fonts or styles), and `.nojekyll` tells
GitHub Pages to serve the files as they are. The pages under Beyond objects (`examples/beyond.json`) are published as
they are and may load from other hosts: the NetLogo page loads three.js and its fonts from CDNs. It is about 90 MB, most of it the three films.
