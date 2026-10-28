# Construct for NetLogo

A NetLogo 7 extension that records a model's run and draws it as a construct: a hologram of the
run in which height is time. Recording needs nothing but NetLogo; drawing runs Construct, which
the extension carries, with Python 3.10 or newer.

**The quickest way:** add `extensions [construct]` at the top of the model's Code tab, then type
in the Command Center:

```
construct:run
```

It runs the model's own setup and go (as its buttons do), records what is worth recording (each
turtle, its true-or-false variables, each breed's count, the patches' colours), lets the run go
until the model stops by itself, picks the view the data suits and opens the construct. A model
that never stops is drawn after 1000 runs of go, and says so; `construct:run-for 3000` runs it as
long as you like.

**To choose what is recorded and how it is drawn,** use the commands one by one:

```
extensions [construct]

to setup
  clear-all
  ...
  reset-ticks
  construct:start "Wolf Sheep Predation"
  construct:track-reporter "sheep" [-> count sheep]
  construct:track-reporter "wolves" [-> count wolves]
  construct:record
end

to go
  ...
  tick
  construct:record
end
```

Run the model, then type `construct:draw "phase"` in the Command Center. The construct is written
beside the model (`wolf-sheep-predation-construct/construct.html`) and opens in the browser, with
its legend, a **How to read it** panel and a replay bar that draws the run up to any tick, with the
tracked counts at that tick.

**To make a model move to music,** name a track first. A tick becomes a moment of the track (30 a
second), and the model's own code can listen:

```
construct:music "track.mp3"
```

```
to go
  set max-separate-turn 1.5 + 12 * construct:kick   ;; each kick bursts the flock apart
  set max-align-turn 2 + 8 * construct:energy        ;; loud passages: the flock flies as one
  ask turtles [ flock ]
  ...
  tick
end
```

Then `construct:run` runs the model for the length of the track, and the construct plays it back
in time with the music: press play on its replay bar to hear the run with its track. The track is
analysed once (with ffmpeg) into a small features file beside the run; NetLogo never plays it.

## Primitives

| Primitive | What it does |
| --- | --- |
| `construct:start title` or `(construct:start title file)` | begins a recording (after `reset-ticks`); the file defaults to `<title>-run.jsonl` beside the model |
| `construct:seed n` | notes the random seed the run used, so it can be repeated |
| `construct:every n` | records every n ticks (default 1) |
| `construct:track-turtles ["var" ...]` | turtle (or breed) variables to record with each turtle's position and colour |
| `construct:track-reporter name [-> ...]` | a whole-model quantity, such as `"sheep" [-> count sheep]`; once for each |
| `construct:track-patches "var" n` | a patch variable, every n ticks |
| `construct:skip-turtles` | records no turtles or links (for models with very many) |
| `construct:record` | records this tick (after `tick`) |
| `construct:finish` | marks the end of the run and closes the file |
| `construct:file` | reports the recording's path |
| `construct:draw view` or `(construct:draw view option value ...)` | draws the recording so far and opens it, such as `(construct:draw "phase" "smooth" 25)` |
| `construct:run` | setup, a recording of everything worth recording, go until the model stops (or 1000 runs), then the view the data suits, opened |
| `construct:run-for n` | the same, for n runs of go |
| `construct:set-python path` | the Python to draw with (default `python3`, `python` on Windows) |
| `construct:music "track.mp3"` or `(construct:music "track.mp3" ticks-a-second)` | a track to run to: a tick is a moment of it (30 a second by default); `construct:run` then lasts the track; `construct:music ""` forgets it. Needs ffmpeg |
| `construct:kick`, `construct:energy`, `construct:high`, `construct:hit` | the music at this tick, 0 to 1: a kick or bass hit (a pulse), the loudness, the brightness, the strongest attacks (0 after the track) |
| `construct:music-time` | the seconds of the track at this tick |

Views: `"auto"` (the one the data suits: a network where a variable turned, patches that changed,
two counts that move together, else the agents' paths), `"space-time"` (every turtle's path rising through time), `"network-time"` (the network
on the floor, each turtle risen to when its state changed: `(construct:draw "network-time" "state"
"infected?")`), `"phase"` (two tracked reporters against each other, rising through time) and
`"field"` (a tracked patch variable as stacked layers). `"time" "sqrt"` stretches the early ticks.
`"model" true` also writes `run.glb` beside the page: a 3D model of the run for Blender or a game
engine, in the run's own colours (each turtle a sphere, a cycle as a tube, a spread as a surface).

The recording is the same JSON Lines file `construct netlogo-instrument` writes, so everything in
Construct's command line works on it too: `construct netlogo run.jsonl --view ...`, art
direction with `--art art.json`, and the data lock that keeps an art layer from changing the run's
data. See [docs/NETLOGO.md](../../docs/NETLOGO.md).

## Building

```
python3 scripts/build_netlogo_extension.py --netlogo "/Applications/NetLogo 7.0.4"
```

needs a Java 17 or newer `javac`, and writes `dist/construct-<version>.zip`. Unzip it into a
folder called `construct` in NetLogo's `extensions` folder, or beside your model.

Apache-2.0, like the rest of Construct (NetLogo itself is GPL-2.0-or-later, which allows it).
