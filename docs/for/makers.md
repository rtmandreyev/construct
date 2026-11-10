# Construct for makers

A construct knows its real sizes and its named parts, so it can come out of the computer three ways: as one checked
print at the largest size your printer takes, as a model kit that comes apart where a kit designer would cut it, and
as true CAD shapes in FreeCAD and STEP. This page follows one construct through all three, then lists the five kits
you can open today.

<p align="center"><a href="https://rtmandreyev.github.io/construct/examples/yamaha-cfx/kit/assembly.html"><img src="../media/kit-cfx.jpg" alt="The Yamaha CFX as a 1:12 kit: step 3 in 3D, the keybed built on its own at the bench with numbered lines to each piece, and the same step in the paper booklet as an exploded drawing"></a></p>
<p align="center"><sub>The Yamaha CFX as a 1:12 kit: step 3 in 3D (left) and in the paper booklet (right). The keybed is built at the bench, on its own, before it goes on the piano: each new piece numbered, in its own colour and its paint. Open it: <a href="https://rtmandreyev.github.io/construct/examples/yamaha-cfx/kit/assembly.html">the kit in 3D</a>, <a href="https://rtmandreyev.github.io/construct/examples/yamaha-cfx/kit/booklet.html">its booklet</a>.</sub></p>

## One construct, three ways out: Tompion's clock

[Tompion's year-going longcase clock](https://rtmandreyev.github.io/construct/examples/tompion-year-going-clock/)
was built by DeepSeek V4.1 Flash in masterpiece mode from the Royal Collection's record and two photographs: 207
named parts, 2.23 m tall. The steps below are from its [end-to-end run](../END-TO-END.md); the scene, its finish
map and its kit plan are in [examples/tompion-year-going-clock](../../examples/tompion-year-going-clock/).

**How big, on which printer.** `construct print scene.json --printers` writes nothing; it says what each printer class
can do with this construct:

```
desktop  1:11    43.1 x 24.4 x 211.2 mm, voxel 0.4 mm; real features under ~4.2 mm lost; parts 68 / 61 / 2
large    1:6.6   68.6 x 38.8 x 336 mm, voxel 0.4 mm; real features under ~2.7 mm lost; parts 102 / 29 / 0
resin    1:11    43.1 x 24.4 x 211.2 mm, voxel 0.235 mm (the grid's limit); real features under ~2.5 mm lost; parts 112 / 19 / 0
```

(three of the five classes; parts kept as themselves / thickened to the wall / lost).

**The print.** `construct print scene.json --out clock.3mf --printer desktop --fit --exact` writes one watertight
print, 21 cm tall, from the construct's own solids, with only too-thin surfaces given a real wall. PrusaSlicer reads it
as manifold and slices it: about 10½ hours and 100 g of PLA, with supports over the face where the hood overhangs the
trunk.

<p align="center"><img src="../media/tompion-prusaslicer.jpg" width="90%" alt="PrusaSlicer's G-code viewer: the clock sliced, supports in green over its face, about 10.5 hours"></p>

**The CAD file.** `construct freecad scene.json --out clock.FCStd --step clock.step` builds it in FreeCAD as named
solids: 131 parts, 125 of them true shapes (exact cylinders and boxes, lathes revolved from splines, NURBS lofts), the
other 6 faceted and listed; the two doors as joint groups you can open by their `Open` placement; every part's role,
certainty and source as properties. STEP keeps the same tree and names for any CAD program. What the construct draws
only in lines (a moulding's edge, the hour numerals) is left out of the CAD file, and the command says so.

<p align="center"><img src="../media/tompion-freecad.jpg" width="90%" alt="The clock in FreeCAD's window: the model tree of stages and named parts, and the clock as CAD solids"></p>

**The kit.** The first `construct kit` at 1:12 made 114 pieces in 60 steps and listed 17 problems: pillars too thin
to handle, a hood back glued before anything held it, a pane a hair from its frame. That is normal: a construct is
drawn to look right, not to be moulded. A plan of what a factory would cast in one piece
([kit-plan.json](../../examples/tompion-year-going-clock/kit-plan.json): the movement with its dial plate, the trunk as
one box, the pendulum with its bob, an order of sub-assemblies) brought it to **34 pieces on 2 plates in 15 steps**,
38 × 22 × 186 mm. [Open its booklet](https://rtmandreyev.github.io/construct/examples/tompion-year-going-clock/kit/booklet.html)
and [its steps in 3D](https://rtmandreyev.github.io/construct/examples/tompion-year-going-clock/kit/assembly.html).

## The kits to open today

Five kits, each with its steps in 3D, its booklet and a zip of its plates for your slicer (the plates, the booklet
and the 3D guide):

| Kit | Pieces | Steps in 3D | Booklet | Plates to print |
| --- | --- | --- | --- | --- |
| Yamaha CFX piano, 1:12 | 54 | [open](https://rtmandreyev.github.io/construct/examples/yamaha-cfx/kit/assembly.html) | [open](https://rtmandreyev.github.io/construct/examples/yamaha-cfx/kit/booklet.html) | [.zip](https://github.com/rtmandreyev/construct/releases/latest/download/construct-kit-yamaha-cfx.zip) |
| Tompion's year-going clock, 1:12 | 34 | [open](https://rtmandreyev.github.io/construct/examples/tompion-year-going-clock/kit/assembly.html) | [open](https://rtmandreyev.github.io/construct/examples/tompion-year-going-clock/kit/booklet.html) | [.zip](https://github.com/rtmandreyev/construct/releases/latest/download/construct-kit-tompion-year-going-clock.zip) |
| VW T1 Samba bus, 1:16 | 98 | [open](https://rtmandreyev.github.io/construct/examples/volkswagen-t1-samba/kit/assembly.html) | [open](https://rtmandreyev.github.io/construct/examples/volkswagen-t1-samba/kit/booklet.html) | [.zip](https://github.com/rtmandreyev/construct/releases/latest/download/construct-kit-volkswagen-t1-samba.zip) |
| Vespa GS 150, an owner's scooter, 1:12 | 28 | [open](https://rtmandreyev.github.io/construct/examples/vespa-gs150/kit/assembly.html) | [open](https://rtmandreyev.github.io/construct/examples/vespa-gs150/kit/booklet.html) | [.zip](https://github.com/rtmandreyev/construct/releases/latest/download/construct-kit-vespa-gs150.zip) |
| Villa Savoye, made in Hermes, 1:115 | 30 | [open](https://rtmandreyev.github.io/construct/examples/villa-savoye/kit/assembly.html) | [open](https://rtmandreyev.github.io/construct/examples/villa-savoye/kit/booklet.html) | [.zip](https://github.com/rtmandreyev/construct/releases/latest/download/construct-kit-villa-savoye.zip) |

What a kit does, in each of them: pieces true to the construct's shapes, trimmed where they meet; clear parts on
plates of their own; sub-assemblies built at the bench before they are fitted (a keybed, a wheel, glass into its
frame), repeated ones in one step, the shell after the interior, doors hung last, fragile pieces under 2 mm in a last
Details step; panel lines engraved; a booklet drawn like a kit sheet, with the paints and a card per step; the same
steps in 3D, to turn and rewatch. The Villa Savoye's kit was asked for in one sentence in Hermes
([the walkthrough](hermes-walkthrough.md)); the Vespa's is the owner's own scooter ([a kit of your own](a-kit-of-your-own.md)).

<p align="center"><img src="../media/print-exact-fj62.jpg" alt="The FJ62 printed as voxels on the left, with a stepped arch and tyre, and as an exact print on the right, with a clean arch and a round tyre"></p>
<p align="center"><sub>The same FJ62 print, voxels (left) and <code>--exact</code> (right): the construct's own solids keep a round tyre and a clean arch.</sub></p>

## Something you'll build: a shed into CAD

A construct of what you plan to make goes into CAD the same way. The [garden shed with its planned log store and
deck](https://rtmandreyev.github.io/construct/examples/garden-shed-planned/) was made from one photo of the shed,
then extended with what its owner meant to add, every new part marked as designed. Asked for "a STEP file of the
planned version", it opens in FreeCAD as named solids by stage, ready to dimension and change:

<p align="center"><img src="../media/everyday-shed-freecad.jpg" width="90%" alt="The planned shed in FreeCAD: the model tree of named parts by stage, and the shed with its log store, logs and deck as CAD solids"></p>

The steps, from the photo to the file: [your home or garden](home-and-garden.md).

## A piece of a world, on your desk

Every construct in a world is still a construct, so any of them prints on its own. Stortorget's red No. 20, one of
the eight houses of [a world made from one photograph](../../examples/worlds/stortorget/), as a desktop print:

```sh
construct print examples/worlds/stortorget/constructs/schantzska-huset-no-20/scene.json --out no20.3mf --fit --exact
# wrote no20.3mf: 71.5 x 84.7 x 211.7 mm at 1:137, 64996 triangles
```

The same goes for a house you placed in a world of your own, a car from a game level, or a shelf of things from
your room, each at the scale your printer takes; `construct kit` turns a construct into a model kit the same way.

## A part that fits

The same tools make a single part. The [Braun SK 4's replacement knob](https://rtmandreyev.github.io/construct/examples/braun-sk4-knob/)
was drawn as its own construct at real size beside the radio it belongs to: a 35 mm skirt, a fluted body, the
indicator bar and the bore for the shaft with its flat, the bore marked as designed to fit, to be measured before
printing. PrusaSlicer reads it as one part: about 34 minutes and 9 g of PLA. [Make the part →](replace-a-part.md)

## Your first kit, step by step

Say you want to build the Eiffel Tower on a basic home printer.

1. **Ask your agent for the construct:** *"make a construct of the Eiffel Tower"* (masterpiece mode if you want it
   detailed). You get `scene.json` and a page to look at it.
2. **Check that it holds together:** `construct check scene.json --fit`. It names every part that pokes through
   another, crosses a pane, hangs in the air, or leans with its weight off what it stands on. Ask your agent to fix
   each one; a kit cannot glue what does not touch.
3. **Make the kit at a size your printer takes:** `construct kit scene.json --size 200 --printer desktop --out kit/`.
   The check at the end names pieces that are too thin or too many; fix them in the construct (step 2) or with a plan.
4. **Read `kit/booklet.html` first,** then open `kit/assembly.html` to see the steps in 3D.
5. **Print one piece before the rest:** each piece is on its own in `kit/pieces/`. Open it in your slicer (PrusaSlicer,
   Cura, Bambu Studio) and print it. If it fits where it goes, print the plates (`plate-N.3mf`).
6. **If a piece comes out wrong,** print it again on its own: `construct kit ... --only 12` (or `--only 'door-glass*'`)
   writes `only.3mf` with just those pieces. A piece a little too tight or loose is a slicer setting (XY size
   compensation, or scale that one object); a piece the wrong shape is fixed in the construct, then the kit is made
   again with the same command.
7. **For a kit you would really build,** `construct kit --critic` prints a brief for a kit critic; its answer becomes a
   plan (`--plan kit-plan.json`: merges, parts to keep, clear parts, sub-assemblies in order), as the clock's did.
8. **Clean, glue and paint** step by step, following the booklet.

In Hermes Desktop the same happens from the chat: ask for a kit and it opens with its steps in 3D beside its booklet;
a construct's Export menu also offers STL or 3MF sized to a desktop printer.

## The commands

```sh
construct print scene.json --printers                                     # how large on each printer, what survives
construct print scene.json --out model.3mf --printer desktop --fit --exact
construct print scene.json --out model.3mf --scale 43 --lines engrave      # 1:43, line art cut in as panel lines
construct kit scene.json --scale 16 --printer large --out kit/            # kit/booklet.html, kit/assembly.html, plates
construct kit scene.json --scale 16 --printer large --out kit/ --only 12  # one piece again: kit/only.3mf
construct freecad scene.json --out model.FCStd --step model.step          # needs FreeCAD 1.0 or newer
```

`construct` is short for `python3 construct_hologram/cli.py` in a checkout of Construct. Open the 3MF in PrusaSlicer
(or any slicer that reads its part table), and the booklet in a browser.

## Good to know

- **No kit has yet been printed and built by a person.** They are made and checked by software and by AI critics. If
  you build one, please tell us what fitted and what did not: [issues](https://github.com/rtmandreyev/construct/issues).
- **A kit is only as buildable as its construct.** Parts that do not quite meet come out as slivers or loose pieces,
  and the check names them. Pieces are glued, without pins or hinge pins.
- **Sizes are as certain as the construct says.** Press **P** to see how each part is known. The CAD shapes are for
  layout, clearance, rendering and a start to model over, not for machining; measure before you make a part to fit.
- **What is too small is decided in millimetres.** `--printers` says which real features your printer loses before
  you print.

## Go deeper

- [3D printing and kits](../PRINTING.md): every option, how a print is made and checked
- [FreeCAD and STEP](../FREECAD.md): true shapes, joints, what the document holds
- [The clock, end to end](../END-TO-END.md): every command and what it found
- [Refining the solid](../../construct_hologram/skill/references/review.md#refining-the-solid)
