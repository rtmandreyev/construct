# Fire, recorded

[![Fire](hero.jpg)](https://rtmandreyev.github.io/construct/examples/netlogo-fire/)

**[Open the construct →](https://rtmandreyev.github.io/construct/examples/netlogo-fire/)**

One run of NetLogo's **Fire** model, recorded with Construct's NetLogo bridge and drawn as a construct
(the field view). The fire's front, every 26 ticks, raised to its tick: it starts at the left edge and climbs as it crosses the forest. Where a pocket burned long after its surroundings, the fronts stack into a ladder; where nothing burned, nothing is drawn.

**Credit:** *Fire* © 1997 Uri Wilensky, NetLogo Models Library: Wilensky, U. (1997). NetLogo Fire model. http://ccl.northwestern.edu/netlogo/models/Fire. Center for Connected Learning and Computer-Based Modeling, Northwestern University, Evanston, IL. Licensed under
[CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/); so is this folder (see
[LICENSE](LICENSE)).

## How it was made

No model and no agent drew this: the construct is computed from the recorded run.

1. **Instrumented** with `construct netlogo-instrument "Fire.nlogox" --title "Fire" --out . --patches pcolor:4 --no-turtles --seed 3 --ticks 1000`,
   which adds `__includes ["construct.nls"]`, the recording after setup's `reset-ticks` and after
   go's `tick`, and a headless experiment. The model's own rules are unchanged.
2. **Run** in NetLogo 7.0.4, headless, with random-seed 3 and density 61%:
   `NetLogo_Console --headless --model "Fire-construct.nlogox" --setup-file construct-experiment.xml --experiment construct --threads 1`.
   Construct's recorder wrote every patch's colour every 4 ticks to `run.jsonl` (not kept here: the run reproduces it).
3. **Drawn** with `construct netlogo run.jsonl --view field --levels 24 --out scene.json`: blocks of 4 x 4 patches, each the earliest burn among its trees. Every data part
   is verified against the recording, and the build rises from the floor, so the construct's
   assembly replays the run.

See [the NetLogo bridge](../../docs/NETLOGO.md).
