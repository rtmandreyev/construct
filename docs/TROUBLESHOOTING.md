# Troubleshooting

Most problems with Construct come down to a few things: no browser for the review pictures, a
host's limits cutting a masterpiece run short, or a construct that needs another pass. Each
section below starts with what you see, then what is going on and what to do.

## "No Chromium-family browser found"

You asked for review stills or a video, and Construct couldn't find a browser to take them with.
Construct takes its pictures with a Chromium-family browser already on your machine (Chrome,
Chromium, Edge or Brave) and never installs one itself.

Install one of those browsers, or, if you already have one in an unusual place, point to it:
`export HOLOGRAM_CHROME=/path/to/browser`. Everything else works without a browser: `check` and
`build` don't need one, and the finished `construct.html` opens in any browser with WebGL2.

## The construct page is blank or shows "WebGL2 is not available"

`construct.html` draws with WebGL2, which every current desktop browser supports. If the page
stays blank, check that hardware acceleration is turned on in your browser's settings, or try
another browser. Very old browsers and some locked-down environments don't offer WebGL2.

## `check` reports errors

That is the check doing its job. Each error says where the problem is in the scene and how to fix
it, for example a part that floats in the air, or a fact marked *verified* without a source. When
an agent is working, it reads these and repairs the scene itself; it keeps going until the check
passes. If you are editing by hand, `check --json` gives the same report in a form you can read
part by part. Warnings don't stop a construct from building; they point at things a viewer might
notice.

## A masterpiece run in Hermes stops judging after two rounds

Hermes limits how many helper agents a one-shot run may start, and the default is two. The
masterpiece critic is a helper agent started every round, so after two rounds the critic is gone
and later rounds are only self-reviewed. Raise `oneshot_max_children` under `delegation:` in
Hermes's `config.yaml` (14 is enough for a masterpiece run; `0` means no limit), run Hermes
interactively, or let the critic be a second model with `rounds run --base-url ...`. Details are in
[USING.md](USING.md#in-hermes).

## A Hermes run stops with an error after the review pictures

Hermes sends at most 8 MB in one message, and several full-size review stills at once can pass
that. Ask for smaller stills (`review --size 1280x800`) and only the sheets you need
(`--sheets assembly,views`). The skill saves a valid scene after every round, so nothing finished
is lost.

## A masterpiece run is taking a long time

That is expected: masterpiece mode can run for up to two hours of the agent's own working time,
plus the critic's time each round. It stops on its own when it stops improving (two rounds in a row
without a better version), after 12 rounds, or at the two-hour limit. You can stop it at any point
and keep the best version so far, which is always saved. If you wanted something quicker, ask for
**fast** mode instead: one careful pass in about ten minutes.

If a run was interrupted, by a usage limit for example, `rounds status` in the run's folder says
where it stopped, and the agent can pick up from there.

## The construct looks sparse, flat or like cardboard

A construct should read as one clear object from a distance and still have something true to find
up close. If yours looks thin, ask the agent for another pass with more detail where the thing's
identity lives (a watch's dial, a car's lamps, a cathedral's windows), or run it in
**masterpiece** mode. If the check warns `bare-surface`, a main surface was drawn as a flat dark
shape with no outline: keeping a faint outline over it fixes the cardboard look. The drawing
guide in `construct_hologram/skill/references/craft.md` explains what makes a construct read well.

## The likeness is off

Proportions are hard to get from text alone. For a named subject, use **masterpiece** mode with a
recommended model (GPT-6.1 Sol or Claude Opus) and make sure the agent can find reference photos;
the critic compares every version with them. For shapes like a guitar body or a car's side,
tracing an outline from a photo helps most ([USING.md](USING.md#getting-the-likeness-right)).

## A small model doesn't finish

Small or free models (MiniMax, Inkling, Nemotron, for example) often fail to save a scene at all or
get the scale wrong. For common things, ask for the archetype path (`author ... --params`), which
small models handle well; for anything else, use DeepSeek or one of the recommended models.

## The labels are missing

Press **L** to show them. A construct only labels facts its scene records, so a thing you didn't
say, like a book's author, has no label by design.

## Something else

Open an issue on GitHub with what you ran, what you expected and what `check` says. Please leave
out API keys and private files; see [SECURITY.md](../SECURITY.md).
