# Publishing the repository and the examples gallery

This repository has two branches to publish:

- `main`: the source, tagged at each release (the latest is `v0.3.0`);
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

- Description: *Holographic constructs any AI agent can build: from a description, honestly.*
- Website: https://rtmandreyev.github.io/construct/
- Topics: `ai-agents`, `agent-skills`, `claude-code`, `mcp`, `webgl`, `hologram`,
  `procedural-generation`, `3d-visualization`, `llm`, `python`

## 2. Push `main` and the tag

```sh
cd ~/construct-public
git remote add origin https://github.com/rtmandreyev/construct.git
git push -u origin main
git push origin v0.3.0
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

Optionally, publish a release: **Releases → Draft a new release**, tag `v0.3.0`, and
[docs/releases/v0.3.0.md](docs/releases/v0.3.0.md) as the notes.

## 5. Update the gallery later

```sh
cd ~/construct-public
python3 scripts/build_site.py --out site --films DIR  # compiles every example with this checkout
python3 -m http.server 8000 --directory site          # preview at http://localhost:8000/
git worktree add ../construct-pages gh-pages
rsync -a --delete --exclude .git site/ ../construct-pages/
git -C ../construct-pages add -A
git -C ../construct-pages commit -m "Gallery: rebuild"
git -C ../construct-pages push origin gh-pages
git worktree remove ../construct-pages
```

To add an example: put its `scene.json`, `hero.jpg` (1440 × 900) and `thumb.jpg` (720 × 450)
in `examples/<slug>/`, add an entry to `examples/examples.json`, write its `README.md` like the
others, and rebuild.

The films are the exception to "everything is in the repository": their videos are published
with the gallery only, never in `main`. `--films DIR` names the folder that holds them (the file
names in `examples/films.json`); `--no-films` builds the gallery without them. To add a film: put
its scene in `examples/films/<slug>/scene.json`, add an entry to `examples/films.json` (the object,
mode, model, track and video file), keep the video at about 20 MB or less (re-encode it with
ffmpeg if needed), and rebuild with `--films`. The poster is drawn from the film's last frame.

## What the gallery needs

Nothing but static files: every link is relative, each construct is one self-contained
`construct.html` (plain WebGL2, no external scripts, fonts or styles), and `.nojekyll` tells
GitHub Pages to serve the files as they are. It is about 41 MB.
