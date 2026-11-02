# Construct for makers

Anything you can describe can be printed, made into a model kit, or opened in CAD. The construct knows its real sizes
and its parts, so a print comes out at a true scale and a kit comes apart where a kit designer would cut it.

<p align="center"><a href="https://rtmandreyev.github.io/construct/examples/yamaha-cfx/kit/assembly.html"><img src="../media/kit-cfx.jpg" alt="The Yamaha CFX as a 1:12 kit: step 3 in 3D, the keybed built on its own at the bench with numbered lines to each piece, and the same step in the paper booklet as an exploded drawing"></a></p>
<p align="center"><sub>The Yamaha CFX as a 1:12 kit: step 3 in 3D (left) and in the paper booklet (right). The keybed is built at the bench, on its own, before it goes on the piano: each new piece numbered, in its own colour and its paint. Open it: <a href="https://rtmandreyev.github.io/construct/examples/yamaha-cfx/kit/assembly.html">the kit in 3D</a>, <a href="https://rtmandreyev.github.io/construct/examples/yamaha-cfx/kit/booklet.html">its booklet</a>; more in <a href="https://rtmandreyev.github.io/construct/#kits">the gallery's kits</a>.</sub></p>

## What you can do

- **Print it.** One checked, watertight print at the largest size your printer takes (`--printers` compares five
  printer classes), or `--exact`: the construct's own solids, with thin parts given true walls, for the finest detail.
- **Make it a kit.** Pieces true to the construct's shapes on numbered plates (clear plastic on its own plates),
  glued in the order a kit designer would: sub-assemblies built at the bench, repeated ones in one step (four
  wheels at once), the shell after the interior, doors hung last, fragile details at the end. A booklet on paper
  with pictures of the parts each step needs, and the same steps in 3D: turn it, rewatch any step.
- **Open it in CAD.** True CAD shapes in FreeCAD with its joints, and STEP for any CAD program.
- **Refine before you print.** `construct check --fit` names the parts that poke through others or hide inside them,
  so you, or your agent, can fix them part by part. Press **S** to see the result.

<p align="center"><img src="../media/print-exact-fj62.jpg" alt="The FJ62 printed as voxels on the left, with a stepped arch and tyre, and as an exact print on the right, with a clean arch and a round tyre"></p>
<p align="center"><sub>The same FJ62 print, voxels (left) and exact (right).</sub></p>

## Try it

```sh
construct print scene.json --printers                                   # how large on each printer, what survives
construct print scene.json --out model.3mf --printer desktop --fit --exact
construct kit scene.json --scale 16 --printer large --out kit/          # kit/booklet.html, kit/assembly.html, plates
construct kit scene.json --scale 16 --printer large --out kit/ --only 12  # one piece again: kit/only.3mf
construct freecad scene.json --out model.FCStd --step model.step
```

Open the 3MF in PrusaSlicer (or any slicer that reads its part table), and the booklet in a browser.

## The kits to try

Four kits, each with its steps in 3D, its booklet and its plates for your slicer (a zip with the plates, the
booklet and the 3D guide):

| Kit | Pieces | Steps in 3D | Booklet | Plates to print |
| --- | --- | --- | --- | --- |
| Yamaha CFX piano, 1:12 | 54 | [open](https://rtmandreyev.github.io/construct/examples/yamaha-cfx/kit/assembly.html) | [open](https://rtmandreyev.github.io/construct/examples/yamaha-cfx/kit/booklet.html) | [.zip](https://github.com/rtmandreyev/construct/releases/latest/download/construct-kit-yamaha-cfx.zip) |
| Tompion's year-going clock, 1:12 | 34 | [open](https://rtmandreyev.github.io/construct/examples/tompion-year-going-clock/kit/assembly.html) | [open](https://rtmandreyev.github.io/construct/examples/tompion-year-going-clock/kit/booklet.html) | [.zip](https://github.com/rtmandreyev/construct/releases/latest/download/construct-kit-tompion-year-going-clock.zip) |
| VW T1 Samba bus, 1:16 | 98 | [open](https://rtmandreyev.github.io/construct/examples/volkswagen-t1-samba/kit/assembly.html) | [open](https://rtmandreyev.github.io/construct/examples/volkswagen-t1-samba/kit/booklet.html) | [.zip](https://github.com/rtmandreyev/construct/releases/latest/download/construct-kit-volkswagen-t1-samba.zip) |
| Vespa GS 150, an owner's scooter, 1:12 | 32 | [open](https://rtmandreyev.github.io/construct/examples/vespa-gs150/kit/assembly.html) | [open](https://rtmandreyev.github.io/construct/examples/vespa-gs150/kit/booklet.html) | [.zip](https://github.com/rtmandreyev/construct/releases/latest/download/construct-kit-vespa-gs150.zip) |

## Your first kit, step by step

Say you want to build the Eiffel Tower on a basic home printer.

1. **Ask your agent for the construct:** *"make a construct of the Eiffel Tower"* (masterpiece mode if you want it
   detailed). You get `scene.json` and a page to look at it.
2. **Check that it holds together:** `construct check scene.json --fit`. Ask your agent to fix every part it names that
   pokes through another or floats; a kit cannot glue what does not touch.
3. **Make the kit at a size your printer takes:** `construct kit scene.json --size 200 --printer desktop --out kit/`.
   The check at the end names pieces that are too thin or too many; fix them in the construct (step 2) or with a plan.
4. **Read `kit/booklet.html` first,** then open `kit/assembly.html` to see the steps in 3D.
5. **Print one piece before the rest:** each piece is on its own in `kit/pieces/`. Open it in your slicer (PrusaSlicer,
   Cura, Bambu Studio) and print it. If it fits where it goes, print the plates (`plate-N.3mf`).
6. **If a piece comes out wrong,** print it again on its own: `construct kit ... --only 12` (or `--only 'door-glass*'`)
   writes `only.3mf` with just those pieces. A piece a little too tight or loose is a slicer setting (XY size
   compensation, or scale that one object); a piece the wrong shape is fixed in the construct, then the kit is made
   again with the same command.
7. **Clean, glue and paint** step by step, following the booklet.

## Honest about kits

**No kit has yet been printed and built by a person.** They are made and checked by software and by AI critics. If you
build one, please tell us how it went, what fitted and what did not:
[issues](https://github.com/rtmandreyev/construct/issues).

A kit is made from the construct's own geometry, so it is only as buildable as the construct: parts that do not quite
meet come out as slivers or loose pieces, and the check names them. Pieces are glued, without pins or hinge pins. A
first kit of a gallery construct is a good start; for a kit you would really build, run a kit critic and a plan
(`construct kit --critic`) and fix the fit the critic asks for.

## Go deeper

- [3D printing and kits](../PRINTING.md)
- [FreeCAD and STEP](../FREECAD.md)
- [Refining the solid](../../construct_hologram/skill/references/review.md#refining-the-solid)
