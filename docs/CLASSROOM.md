# In a classroom, and in a museum

Construct's NetLogo tools are made to be taught with: a run of a model becomes something a student can
turn around, replay tick by tick, compare, hear and print. This page puts them in the order a lesson
or an exhibit uses them. Everything runs on the teacher's computer, offline, with NetLogo 7 and
Python 3.10 or newer; music needs ffmpeg, films need Blender.

## A lesson: what a parameter does (45 minutes)

1. **Pick a model whose shape tells a story.** Virus on a Network (a spread), Wolf Sheep Predation (a
   cycle), Fire (a front), Flocking (agents moving together). Add `extensions [construct]` to the top
   of its Code tab ([install the extension](../hosts/netlogo/README.md)).
2. **One run, drawn.** Type `construct:run` in the Command Center. The construct opens in the browser:
   time is height, the legend names each part, and **How to read it** (H) explains the shape. Drag the
   replay bar to see the run form, with its counts at each tick.
3. **A question.** "What happens if the virus spreads a little more easily?" Record a run at each value:
   ```
   random-seed 7  set virus-spread-chance 2.5  construct:run
   random-seed 7  set virus-spread-chance 6    construct:run
   ```
   (rename the first `…-run.jsonl` before the second run, or record each from its own copy of the model).
4. **Side by side.** `construct netlogo-compare low.jsonl high.jsonl --labels "2.5%,6%" --out compare/scene.json`
   then `construct build compare/scene.json --out compare`. Both runs are drawn the same way on one time
   scale: with seed 7, 2.5% dies out after 11 ticks while 6% runs for 973, and the difference is one
   glance.
5. **The worksheet.** Scrub the replay to the moment you want, then print the page (Cmd/Ctrl+P, or Save
   as PDF): one page with the construct, how to read it, the counts at that tick, the citation and three
   questions with room to answer.
6. **The data, and where it came from.** **Data (CSV)** in the panel gives the counts for a spreadsheet;
   **Cite this run** gives the model, NetLogo's version, the seed, the ticks and the data lock, so a
   report can say exactly which run it shows.

Every part of the construct is computed from the recording; the data lock makes the audit refuse a
construct whose data was changed after it was drawn, so what students read is what the model did.

## A lesson with music: rules that listen

A model can follow a track, which makes rules visible: students hear the cause and see the effect.

1. Open Flocking, and add a few lines to `go` that listen (see the [extension's README](../hosts/netlogo/README.md)):
   `set max-separate-turn 1.5 + 12 * construct:kick` makes every kick push the birds apart.
2. `construct:music "track.mp3"`, `setup`, `construct:play`, then **go**: with `construct:sync` after
   `tick`, the flock moves in time with the music in NetLogo's own view.
3. Ask what the music changes and what it does not: the birds still only follow their three rules;
   the music only sets how strongly.
4. The same with Fireflies: given the beat as one more flash to see, the fireflies fall into step with
   it (entrainment). How fast they lock, and whether, depends on the beat's tempo against their cycle:
   a good question to test.

## An exhibit

1. **Build the pieces.** Any construct: an object, a NetLogo run, a song (`construct song track.mp3`),
   a score (`construct song piece.mid`).
2. **A show.** `construct kiosk a.json b.json c.json --out show --each 90` makes `show/index.html`: full
   screen after its first touch ("Touch to start"), each construct playing through once and then
   staying 90 seconds, a visitor's touch holding the one they explore. Copy the folder to the exhibit's
   computer and open `index.html` in its browser; it needs no network.
3. **Listening.** `--live` makes every page react to the room's sound after the first touch: the light
   follows the loudness and kicks pulse the glow. The sound is analysed in the page and never recorded
   or sent.
4. **A film for the screen in the lobby.** `construct netlogo-film run.jsonl --out film.mp4` renders a
   run as every agent in moving light, with its music, in Blender.

## Credit

NetLogo's models are © Uri Wilensky and their authors, most under CC BY-NC-SA 3.0: credit the model as
its Info tab asks, on the worksheet and the exhibit's label (**Cite this run** gives the line).
