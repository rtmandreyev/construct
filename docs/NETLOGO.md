# The NetLogo bridge

<p align="center">
  <a href="https://rtmandreyev.github.io/construct/examples/netlogo-flocking/"><img src="../examples/netlogo-flocking/thumb.jpg" width="32%" alt="Flocking: each bird's track rising with time, random near the floor and in parallel streams higher up"></a>
  <a href="https://rtmandreyev.github.io/construct/examples/netlogo-wolf-sheep/"><img src="../examples/netlogo-wolf-sheep/thumb.jpg" width="32%" alt="Wolf Sheep Predation: the predator-prey cycle rising in time"></a>
  <a href="https://rtmandreyev.github.io/construct/examples/netlogo-fire/"><img src="../examples/netlogo-fire/thumb.jpg" width="32%" alt="Fire: the fire's front, every few ticks, raised to its tick"></a>
</p>
<p align="center"><sub>Three runs of NetLogo Models Library models (© Uri Wilensky, CC BY-NC-SA 3.0), recorded with the bridge and drawn as constructs from the data alone, then art-directed by Claude Opus 5.5 (labels and milestones; the data is locked): <a href="https://rtmandreyev.github.io/construct/examples/netlogo-flocking/">Flocking</a> · <a href="https://rtmandreyev.github.io/construct/examples/netlogo-wolf-sheep/">Wolf Sheep Predation</a> · <a href="https://rtmandreyev.github.io/construct/examples/netlogo-fire/">Fire</a>.</sub></p>

An agent-based model unfolds in time. The bridge records a NetLogo run and draws it as a construct
in which time is height: the floor is the world (or two of the model's quantities), and the run
rises from it. Because a construct assembles from the floor up, its assembly replays the run.

```
your model (.nlogox)  ──►  construct netlogo-instrument  ──►  the model, recording itself
NetLogo (setup, go)   ──►  run.jsonl
run.jsonl             ──►  construct netlogo --view …    ──►  scene.json  ──►  construct build
```

Or, inside NetLogo 7, with the [Construct extension](../hosts/netlogo/README.md): a few
`construct:` lines in the model record the run, and `construct:draw "phase"` in the Command Center
draws it and opens it in the browser. Both write the same recording.
An AI agent can do all of it over MCP: `construct_netlogo_instrument` returns the recording copy of
a model, and `construct_netlogo_draw` turns a recording into a construct (with an art layer, solids
and the run's colours on request), for `construct_compile` and `construct_export`.

No AI model is needed for any of it: the construct is computed from the recording, so the same run
always gives the same construct, and every data part is marked `verified` against the recording
(a dataset source that names the model, NetLogo's version and the random seed). An optional
[art-direction pass](#3-art-direction-optional) can then add views, emphasis, labels and
milestones on top, and the data lock makes sure it never changes the data.

## 1. Record a run

**The quickest way** (NetLogo 7, with the extension installed): add `extensions [construct]` at the
top of the model's Code tab and type `construct:run` in the Command Center. It runs the model as
its buttons do, records what is worth recording, waits for the model to stop (a model that never
stops is drawn after 1000 runs of go; `construct:run-for 3000` for longer), chooses the view and
opens the construct. `construct netlogo run.jsonl --view auto` makes the same choice from the
command line.

**With the extension, step by step** (NetLogo 7): install it (unzip `construct-<version>.zip` into a folder
called `construct` in NetLogo's `extensions` folder, or beside your model; build it with
`scripts/build_netlogo_extension.py`) and add to the model:

```
extensions [construct]

to setup
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

Run it, then type `(construct:draw "phase" "smooth" 25)` in the Command Center: the construct is
written beside the model and opens. Every primitive is in [its README](../hosts/netlogo/README.md).
Recording needs only NetLogo; drawing runs Construct, which the extension carries, with Python 3.10
or newer.

**Without changing the model by hand**, let Construct instrument a copy of it:

```sh
construct netlogo-instrument "Wolf Sheep Predation.nlogox" --title "Wolf Sheep Predation" --out run/ \
    --reporters "count sheep;count wolves" --no-turtles --seed 11 --ticks 1500
```

It writes, into `run/`, the model with three things added (and nothing else changed):
`__includes ["construct.nls"]`, the recording set up after setup's `reset-ticks`, and
`construct-record` after go's `tick` (in the procedure setup or go calls that has them, when they
are not in setup or go itself; at the end of setup and go in a model that never starts the tick
counter, whose records are then numbered as steps); it copies `construct.nls` beside it and writes a BehaviorSpace
experiment, `construct-experiment.xml`. Then either open the model in NetLogo and press setup and
go, or run it headless:

```sh
NetLogo_Console --headless --model "run/Wolf Sheep Predation-construct.nlogox" \
    --setup-file run/construct-experiment.xml --experiment construct --threads 1
```

(On a Mac the console is inside the NetLogo folder; `netlogo-headless.sh` there runs it, with
`JAVA_HOME` set to NetLogo's own `runtime/Contents/Home`.) The experiment sets the seed, runs up to
`--ticks` and calls `construct-finish`. To change the model's settings, add BehaviorSpace
`<constants>` to the experiment, as for any experiment. Setup and go are the model's `setup` and
`go`; when it has none (or they take inputs), they are the commands of its own buttons: the forever
button is go, and a setup button is setup. When a button's own code holds the `tick`, the button is
rewritten to record too. To choose, give the commands: `--setup "setup-random"`, `--setup "setup 4"`,
`--go "go-once"`.

| Option | What it records |
| --- | --- |
| (always) | each turtle's who, breed, position and colour, every record; the links whenever their number changes |
| `--turtles heading,energy` | turtle variables or reporters, per turtle |
| `--reporters "count sheep;count wolves"` | observer reporters, every record |
| `--patches pcolor:4` | a patch reporter, every 4 ticks |
| `--no-turtles` | no turtles (when only reporters or patches matter: much smaller files) |
| `--every 5` | a record every 5 ticks |
| `--seed 42` | sets and records the random seed |

**By hand**, for a model that instrumenting does not fit: put `construct.nls` beside the model, add
`__includes ["construct.nls"]`, and at the end of setup:

```
construct-start "My model" "run.jsonl"
construct-seed 42                                   ; the seed your run used, if you set one
construct-track-turtles ["energy"]
construct-track-reporters ["count sheep" "count wolves"]
construct-track-patches "pcolor" 4
construct-record
```

then `construct-record` at the end of go and `construct-finish` when the run ends. The recording is
JSON Lines: a header (the title, NetLogo's version, the seed, the world), then one line per
record. With BehaviorSpace, give each run its own file, since parallel runs would share one.

## 2. Draw it

```sh
construct netlogo run/run.jsonl --view phase --smooth 25 --out scene.json
construct build scene.json --out out/
```

| View | For | What it draws |
| --- | --- | --- |
| `space-time` | moving agents (flocks, ants, traffic) | each turtle's track, rising with time, in a cube as tall as the world is wide; up to 150 turtles (`--max-agents`), chosen evenly by who |
| `network-time` | spreading on a network (diffusion, epidemics, adoption) | the network on the floor; each turtle rises to the tick its `--state` variable first turned true, and each link between two risen turtles climbs from the earlier to the later |
| `phase` | two quantities in a cycle (predator and prey) | `--x` across the floor and `--z` front to back (the first two reporters by default), height is ticks; its shadow on the floor is the classic phase plot, and the walls carry each against time. `--smooth N` averages over N records, recorded as a fact |
| `field` | something spreading over patches (fire, contagion, settlement) | the front of change: where each patch's reporter first (`--change last`: last) changed, drawn every few ticks and raised to its tick; nothing where nothing changed. `--levels` fronts (32), over about `--resolution` blocks (64) |
| `pulse` | turtles that switch a state on and off again and again (fireflies, firing cells, blinking signals) | one ring per tick, its area the share of turtles in that state then (`--state`: a true/false variable, `hidden?` too): turtles on their own make a thin, ragged column, turtles in step wide plates with nothing between |

`--view auto` chooses: a network where a true-or-false variable turned (network-time), a network
that grew (network-time, each turtle at the tick it appeared), patches that changed (field), turtles
that switch a true/false state on and off at least four times each on average, at regular gaps
(pulse; a colour that changes shows a state, not a rhythm), two counts that move together (phase),
else the agents' paths (space-time; when the agents barely move it says so).

**Landmarks.** Every construct of a run marks the moments worth marking, computed from its first count
(the one the replay shows first): for a count that rises and holds, where it is half way and most of
the way (90%) from its start to its height; for one that rises and falls, its peak; for a pulse, the
first tick half the turtles, then all of them, were on at once. Each is a dashed frame in the accent at
its tick, labelled with its value ("Peak: 78 infected · tick 147"), marked inferred and kept under the
data lock. `--landmarks off` leaves them out; runs compared side by side have none.

**Colours.** A run is drawn in its own NetLogo colours: each breed's tracks in its turtles' colour, each
risen turtle of a network in the colour it ended in (with a bead of light at its top), a field in the
colour its patches changed to (Fire's embers, lifted to red), or from when they changed to no colour at all
(Ants' food, eaten to black). Each is made to read as
light on the dark ground: the hue kept, black lifted to grey, white held back, the saturation capped.
`--colors house` draws Construct's own tones instead. The 3D model carries the same colours: `--glb`
writes it with the lines as glowing tubes, the floor dark and the time axis grey (the look of the Blender
import), and `construct export` uses each part's colour. Colour is how a run is drawn, not what it says, so it sits outside the data lock.

**Where the order forms.** Moving turtles are measured by their alignment (how much they head one way:
0 every way, 1 all one way) and turtles that switch on and off by their synchrony (the order parameter
r, from each turtle's own events: 0 each on its own rhythm, 1 all in step). In a long run that order
usually forms early and then holds, and a construct of the whole run would squeeze that moment into a
few centimetres; so when it has formed by 60% of a run of 500 ticks or more, space-time and pulse are
drawn from tick 0 to just after it formed. The construct says so: its title ("ticks 0 to 1063 of 3978"), a `window` fact
with the measure at the start and by the window's end, and a line in How to read it. `--window whole`
draws the whole run, `--window 800` ends it at tick 800; the recording, the CSV and the film always
keep the whole run, and runs compared side by side are drawn whole. Both measures follow at most 200
turtles, chosen evenly by who.

`--time sqrt` stretches the early ticks, for a run whose changes come early (most of an adoption
cascade happens in its first tenth). Each construct records what was drawn as facts: the model, the
seed, the ticks, which agents, how the data was sampled.

A construct holds at most 24,000 line segments, so a long run with many moving agents is sampled
(the `sampling` fact says how much); the construct is the run's shape, and the replay its timing.

Every construct carries its legend: each part named where it is ("Each turtle, risen to the tick
infected? turned true"), shown as soon as the part it names is drawn (**L** hides it) and kept inside
the window. Nothing
decorative is added: no projector, no drifting motes, nothing that looks like data and isn't.

**Reading it.** The page has a **How to read it** panel (**H**): a few lines for the view, such as
"A link climbs from the earlier of its two turtles to the later: a steep climb joins two turtles
that turned far apart in time". And a replay bar: drag it, or press play, and the construct is
drawn up to that tick, with the tick and the run's counts beside it (the recorded reporters; else,
for a network, how many turtles have the state now, and for a field, how many patches have
changed). The counts and the clock are the run's data, under the data lock like the parts; an art
layer may reword the panel (`"reading": {"how": [...]}`) and nothing else of it.

**For a spreadsheet or a report.** A run's **How to read it** panel offers its counts as CSV (as the
replay shows them) and **Cite this run**: the model, NetLogo's version, the seed, the ticks,
Construct's version and the data lock, ready to paste. `construct netlogo … --csv
counts.csv` writes the counts at every record from the recording itself (the clock, each tracked
reporter, each breed's turtles).

**A worksheet.** Printed (Cmd/Ctrl+P, or Save as PDF), a construct's page is a one-page worksheet: the
construct as it is on screen (scrub the replay to the moment you want first), how to read it, the
counts at that tick, the citation, and three questions with room to answer.

**Two runs side by side.** `construct netlogo-compare a.jsonl b.jsonl --labels "vision 3,vision 6"
--out scene.json` draws two runs of a model the same way, on one time scale (the longer run's): A on
the left, B on the right, every label, fact and count marked with its run, and one data lock over
both recordings. For a lesson: the same model with a slider moved, or with another seed. In Virus on
a Network with seed 7, a spread chance of 2.5% dies out by tick 10 and 6% runs to tick 972: side
by side, one network stays on the floor and the other rises.

**More than two.** Give it up to eight recordings, and they stand left to right (in rows of four beyond
four), each labelled, on the longest run's time scale, under one lock: a slider stepped through its range
(`construct netlogo-compare r25.jsonl r4.jsonl r6.jsonl r8.jsonl --labels "2.5%,4%,6%,8%"`), or a handful
of seeds to see what varies and what holds. The replay shares its six counts between the runs.

## 3. Art direction (optional)

The bridge's construct is exact but plain: no names on the axes, no milestones, one view. An
art-direction pass, by an AI agent or by you, makes it read, as the
[Simple Viral Marketing](../examples/netlogo-viral-marketing/) example does with its adoption
rings and callouts. The pass is a separate layer, `art.json`, applied when the run is drawn:

```sh
construct netlogo run.jsonl --view field --levels 24 --art art.json --out scene.json
```

| Key | What it holds |
| --- | --- |
| `credit` | who directed it, required: a model (`"Claude Opus 5.5"`) or a person. It becomes the source `art`, "Art direction by …", shown with **P** |
| `title`, `summary` | the construct's title and its one-paragraph summary |
| `looks` | per data part, by id: its `label`, `look` (tone, weight, alpha, glow, line) or `note`, and nothing else |
| `parts`, `facts`, `annotations` | its own: milestone rings, tick marks, axis names, callouts. Source `art` (or none), `inferred` when computed from the run (the note says how) or `decorative` |
| `presentation` | views, framing and atmosphere, merged over the bridge's |
| `animation` | assembly, idle and camera, in place of the bridge's |
| `reading` | `{"how": [...]}`: the panel's lines, in the layer's own words (the clock and counts stay the run's) |
| `legend` | `false` drops the bridge's legend, when the layer's own annotations replace it; otherwise a part relabelled in `looks` has its legend relabelled too |

**The data lock.** Every scene the bridge draws carries a `data_lock` fact: the fingerprint of its
data (each part from the run, the run's facts, the view and the coordinates). `construct check` and
`build` refuse a scene whose data no longer matches it, so neither an art pass nor a hand edit can
move a point, drop a track or change a tick without it showing. Reformatting the file, or a data
part's label, look or note, leaves the fingerprint as it was. The layer itself can't claim the
recording either: a part or fact of its own with source `run` is refused.

What makes a good pass:
- **Milestones come from the recording,** computed by a short script over `run.jsonl`, never
  estimated by eye: "half the forest burned, tick 212" is what the run says.
- **Every data part stays visible.** Emphasis dims the context, never the data.
- **A few rounds, looked at.** `construct review scene.json --out out/` before and after each change;
  keep a change only when the construct reads better. The house style is in [STYLE.md](STYLE.md).
- The layer is kept beside the scene, so the pass is reviewable and redrawn with the run.

**Critic rounds (opt-in).** For a layer worth the time, run Construct's improvement rounds on the
scene (`construct rounds start scene.json --mode masterpiece`, redrawing with `--art` between
rounds): an independent model, which never saw the authoring, judges each version and only a
version it prefers is kept. For a run, the critic gets the recording's facts, the layer's own facts
and milestones with how each was computed, the legend, the reading lines and the counts over
time, and it scores the usual criteria with a run's meaning: above all accuracy (every label and
number must agree with the recording) and whether a student could read the run. Checked with
GPT-6.1 Sol through Hermes: given a layer with one planted error (a peak of 97 at tick 18, where
the recording says 79 at tick 260), it ranked that error first, as critical.

## 4. A 3D model (optional)

A run can also leave as a 3D model, for Blender, a game engine or a print:

```sh
construct netlogo run.jsonl --view network-time --state infected? --solid --glb run.glb --out scene.json
```

`--solid` adds solid parts to the construct: each turtle as a sphere where it rose (network-time;
up to 200, chosen evenly by who), the cycle as a tube (phase), and the spread as a surface, each
place at the height of the tick it changed (field; places that never changed sit at the top). The
tracks of space-time leave as tubes. `--glb` exports the model in the run's own NetLogo colours
(each turtle's last colour, each breed's most common one, the colour patches changed to), with
the build as `_PHASE`, so the Blender add-on's **Build** replays the run; `--materials-out` writes
that colour map for `construct export`. In NetLogo, `(construct:draw "network-time" "state"
"infected?" "model" true)` writes `run.glb` beside the page. The solids are drawn from the
recording like everything else, under the data lock; without `--solid`, nothing changes. Checked in
Blender 5.2 with the add-on: Virus on a Network, Wolf Sheep Predation, Rumor Mill and Flocking
import with each part a named object, and **Build** halfway shows the run halfway.

## 5. A run as a film (Blender)

A construct is the run's shape; a film is its motion. The Blender add-on imports a recording
itself (**File → Import → NetLogo Run (.jsonl)**, or headless with `scripts/run_film.py`): every
turtle at every tick as moving light with a trail, in its own colours, each link as a thin line of
light between its two turtles while the recording has it, the patches as a floor of cells in the
patch reporter's colours (NetLogo's colours for a colour, else dark to bright over the run's range;
at most 128 cells a side), the world's edge as a line of light, played at 30 ticks a second in a
steady light, without sound. Nothing is sampled: a
three-minute flock of 200 birds is 200 birds for three minutes. NetLogo 3D runs fly at their
recorded heights inside the world's box.
([hosts/blender](../hosts/blender/README.md#a-netlogo-run-as-a-film))

In NetLogo, `(construct:draw "auto" "film" true)` also writes `film.blend` beside the page: open it
in Blender with the Construct add-on and press play (or render it). From the command line:

```sh
construct netlogo-film flocking-run.jsonl --blend flocking.blend          # the scene, to play or render
construct netlogo-film flocking-run.jsonl --out flocking.mp4 --size 1920x1080   # the film
```

It finds Blender (`--blender`, `$CONSTRUCT_BLENDER`, `blender` on the PATH, or the usual installs)
and runs it in the background; `--from` and `--seconds` take a part of the run, `--samples` sets
EEVEE's quality, `--trail` the trails' length. Rendering a long film at full size takes a while
(about a second a frame on a laptop GPU); the `.blend` is ready in seconds.

## How it was checked

- **The bridge reproduces a run exactly.** The [Simple Viral Marketing](../examples/netlogo-viral-marketing/)
  example's model, instrumented and re-run with its seed and settings in NetLogo 7.0.4, gives the
  same run as its original export: it ends at tick 470, and all 500 people's adoption ticks are
  the same. The recorder uses no randomness, so it never changes a run.
- The three examples were recorded headless in NetLogo 7.0.4: Flocking (300 ticks, 4.5 seconds),
  Wolf Sheep Predation (1,500 ticks) and Fire (673 ticks over 63,001 patches, 8 seconds).
- **The whole Models Library.** Of NetLogo 7.0.4's 445 two-dimensional models (leaving out the 3D
  models and Code Examples), 388 record a run (at least two records) in a 50-step headless test
  with no change but the instrumenting, one model at a time; 41 of them are HubNet activities,
  which run but do little without participants. Of the other 57, 39 wait at setup for someone:
  games and mouse-driven models wait for a player, HubNet activities for a classroom, and a few
  finish at once; 6 need the `import-a` extension, which NetLogo doesn't bundle; 4 have no run to
  record (one-shot demonstrations, one needing an Arduino); 5 need typed input or participants, or
  build in phases before they run; and 3 were slower than the test allows. With the extension, a
  person running any of them in NetLogo is recorded like any other run.
- **The machine checks** (`scripts/library_check.py`, no AI): with `construct:run`, 373 of the 445
  models draw a construct; every data lock holds, every replay's clock and counts agree with the
  run, and no label leaves the window, overlaps another or hides under the panel or the replay bar.
  Most of the others wait for a player or a classroom; five change every patch at once, which none
  of the four views can draw yet.
- **The extension writes the same recording.** Virus on a Network (200 ticks) and the tests' model,
  recorded by the extension and by `construct.nls` with the same seed, give the same turtles,
  positions, colours, variables and links, tick by tick.
- The tests check instrumenting, reading a recording, every view, the legend, the data lock (a
  moved point, a dropped part, a changed tick or a part that claims the run fails; a restyled or
  reformatted scene passes) and the art layer on small recordings; when `CONSTRUCT_NETLOGO` names
  NetLogo's folder, a headless run end to end; and with `CONSTRUCT_JAVAC` (Java 17 or newer) too,
  the extension built, loaded by NetLogo, its errors and its recording against `construct.nls`'s.

## Limits

- Desktop NetLogo 6.x and 7 (`.nlogox` for instrumenting; the extension needs 7); NetLogo Web
  supports neither include files nor extensions. NetLogo 3D runs are recorded with each turtle's
  height (the extension; `construct.nls` records two dimensions), but the four views draw the floor
  only: the height is for the film (below).
- A construct holds 24,000 lines, so a long run of many agents is sampled; the facts say how.
- Construct does not colour by data (the renderer owns colour): a view shows a quantity by position,
  not by hue.
