# Flocking, recorded

[![Flocking](hero.jpg)](https://rtmandreyev.github.io/construct/examples/netlogo-flocking/)

**[Open the construct →](https://rtmandreyev.github.io/construct/examples/netlogo-flocking/)**

One run of NetLogo's **Flocking** model, recorded with Construct's NetLogo bridge and drawn as a construct
(the space-time view). Each bird's track rises with time: the floor is the world, height is ticks. Near the floor the birds fly at random; higher up they have found each other, and the tracks run in parallel streams: flocks.

**Credit:** *Flocking* © 1998 Uri Wilensky, NetLogo Models Library: Wilensky, U. (1998). NetLogo Flocking model. http://ccl.northwestern.edu/netlogo/models/Flocking. Center for Connected Learning and Computer-Based Modeling, Northwestern University, Evanston, IL. Licensed under
[CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/); so is this folder (see
[LICENSE](LICENSE)).

## How it was made

The data is computed from the recorded run, never drawn by a model. An AI art-direction pass (Claude Opus 5.5) then added the labels and milestones on top, and a data lock keeps it off the data.

1. **Instrumented** with `construct netlogo-instrument "Flocking.nlogox" --title "Flocking" --out . --turtles heading --seed 7 --ticks 300`,
   which adds `__includes ["construct.nls"]`, the recording after setup's `reset-ticks` and after
   go's `tick`, and a headless experiment. The model's own rules are unchanged.
2. **Run** in NetLogo 7.0.4, headless, with random-seed 7 and the model's defaults (300 birds):
   `NetLogo_Console --headless --model "Flocking-construct.nlogox" --setup-file construct-experiment.xml --experiment construct --threads 1`.
   Construct's recorder wrote every bird each tick (who, position, colour, heading) to `run.jsonl` (not kept here: the run reproduces it).
3. **Drawn** with `construct netlogo run.jsonl --view space-time --title "Flocking (NetLogo)" --art art.json --out scene.json`: 150 of the 300 birds, chosen evenly by who. Every data part
   is verified against the recording, and the build rises from the floor, so the construct's
   assembly replays the run.

4. **Art-directed** by Claude Opus 5.5 in [`art.json`](art.json): rings where half the birds' headings agree (tick 49) and nine in ten (tick 81), the tick numbers and three views. Alignment is the length of the birds' mean heading: 0.04 at tick 0, 0.98 at tick 300. Each milestone was computed from `run.jsonl` by a short script and is marked `inferred`, with how in its note. The scene's `data_lock` fact makes `construct check` refuse any change to the data under it.

See [the NetLogo bridge](../../docs/NETLOGO.md).
