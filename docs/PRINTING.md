# 3D printing

<p align="center"><img src="media/print-fj62-leica.jpg" width="100%" alt="Two 3D prints made by construct print, previewed from their STL files: the Toyota Land Cruiser FJ62 at 1:48 and the Leica M3 at 1:1.5, each one solid piece"></p>
<p align="center"><sub>The FJ62 (1:48) and the Leica M3 (1:1.5) from the gallery, as <code>construct print</code> writes them: one watertight piece each, 10 cm long, previewed from the STL. PrusaSlicer reads both as manifold, one part, and slices them.</sub></p>

A construct is drawn from many overlapping shapes, some of them open surfaces, which is right for a
hologram and for Blender but not for a printer: a slicer wants one closed surface. `construct print`
makes that surface and checks it.

```
your scene  ──►  construct print scene.json --out model.3mf  ──►  PrusaSlicer, Bambu Studio, Cura, OrcaSlicer
                 construct print scene.json --out model.stl  ──►  any slicer
```

You do not need a printer to check a print: open the file in a slicer and slice it. The slicer's
preview shows every layer, its supports, the time and the filament.

## Print a construct

```sh
construct print scene.json --out model.3mf
construct print scene.json --out fj62.stl --scale 43
```

| Option | What it does |
| --- | --- |
| `--out FILE.3mf` or `FILE.stl` | 3MF (millimetres, with the title and scale) or binary STL |
| `--size MM` | the longest side, in millimetres (default 100) |
| `--scale N` | instead, print at 1:N of the object's real size (1:43 and 1:24 are common model scales) |
| `--detail MM` | the voxel size (default 0.4, a common nozzle's width); smaller is finer and slower |
| `--wall MM` | open surfaces, and parts too thin to fill, are thickened to this wall (default 0.8) |
| `--join MM` | gaps between parts up to this wide are closed, so the print is one piece (default 1.6; 0 leaves them) |
| `--lines` | print the parts drawn only in lines (seams, engraving, grilles) as raised lines |
| `--bed WxDxH` | the printer's build volume in millimetres (default 250x210x220) |

It prints the size, the scale and what to know:

```
wrote fj62.3mf: 44.9 x 101.3 x 40.5 mm at 1:48, 280208 triangles
  overhangs need supports (4356 mm2 face down steeper than 45 degrees)
  thickened to the 0.8 mm wall: antenna, axle-front, axle-rear, badge-4wd-carrier, ...
  drawn only in lines, not printed (--lines prints them raised): a-pillar, belt-line, ...
  watertight
```

The exit status is 0 for a watertight print. Agents use the same print through the skill, and MCP
clients through the `construct_print` tool (the file comes back as base64, with the report).

## How the print is made

The print is made in voxels at its own scale, so what is too small to print is decided in
millimetres, not in the construct's metres.

1. Each part's closed surfaces are filled: a voxel is solid when its centre is inside (by the parity
   of rays, so the surfaces' winding does not matter).
2. Open surfaces (a panel, a shell, a fin), and closed parts too thin to fill, are thickened to the
   wall.
3. Everything is joined into one solid, and gaps between parts up to `--join` wide are closed. The
   construct's annotations (its floating parts) are left out, and so are parts drawn only in lines,
   unless `--lines`.
4. Sealed cavities are filled; the slicer makes its own infill.
5. The boundary of the solid becomes the surface, each edge shared by exactly two triangles (where
   two voxels meet only along an edge, one more is filled). It is smoothed, never by more than half
   a voxel, and each vertex within a voxel of the construct's own surface is moved onto it, so
   flat and sloping faces come out flat.
6. It stands on the bed: the lowest layer at z = 0, Z up.

## The checks

| Check | What it means |
| --- | --- |
| watertight | every edge shared by exactly two triangles, wound outward: a slicer reads it as a solid |
| pieces | separate solids after joining; a piece that would start in the air needs supports or a wider `--join` |
| fits the bed | the size against `--bed` |
| overhangs | faces pointing down more steeply than 45° from the vertical: the slicer will need supports |
| thickened | the parts made thicker than the construct draws them |
| left out | parts drawn only in lines, and annotations |

The tests check the first three against PrusaSlicer itself when it is installed
(`CONSTRUCT_PRUSASLICER=/path/to/PrusaSlicer`): `--info` reads each print as manifold and one part,
and a print slices with supports.

## What it is not

A print is the construct's form at a scale, solid, in one material. It does not hollow, split a
large object into pieces, add pegs, or orient the model for the fewest supports; a slicer does the
last well. Fine detail smaller than the voxel is lost or thickened, and the report says which
parts were thickened. Colour and multi-material printing are not made.
