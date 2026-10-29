# In a classroom, and in a museum

Construct's NetLogo tools are made to be taught with: a run of a model becomes something a student can
turn around, replay tick by tick, compare and print. This page puts them in the order a lesson or an
exhibit uses them. Everything runs on the teacher's computer, offline, with NetLogo 7 and Python 3.10
or newer; films need Blender.

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

## An exhibit

1. **A run to explore.** A construct's page, `construct.html`, is a single file that needs no network:
   copy it to the exhibit's computer and open it in its browser.
2. **A film for the screen in the lobby.** `construct netlogo-film run.jsonl --out film.mp4` renders a
   run as every agent in moving light, in Blender.

Pages made for a museum screen, which loop by themselves and open to a touch, come in a later release.

## Credit

NetLogo's models are © Uri Wilensky and their authors, most under CC BY-NC-SA 3.0: credit the model as
its Info tab asks, on the worksheet and the exhibit's label (**Cite this run** gives the line).
