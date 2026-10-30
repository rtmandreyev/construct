# FreeCAD

<p align="center"><img src="media/freecad-piano-leica.jpg" width="100%" alt="The Yamaha CFX and the Leica M3 constructs as FreeCAD solids, with the piano's lid and prop and the Leica's extending lens opened by their joints and shown in magenta"></p>
<p align="center"><sub>The Yamaha CFX and the Leica M3 from the gallery, built in FreeCAD by <code>construct freecad</code>: named solids, the parts that move (magenta) in their joints' groups, opened by setting each group's Placement to its <code>Open</code> value. Drawn from FreeCAD's own tessellation.</sub></p>

`construct freecad` builds a construct in FreeCAD as named solids with its joints, and writes a
FreeCAD document and STEP, for engineering work and CAD tools.

```
your scene  ──►  construct freecad scene.json --out model.FCStd --step model.step  ──►  FreeCAD, and any CAD tool through STEP
```

It runs FreeCAD's own command line, so FreeCAD 1.0 or newer must be installed (freecad.org). It is
found as `$CONSTRUCT_FREECAD`, `freecadcmd` on the PATH, or the usual installs; `--freecad PATH`
names one.

## Build a construct in FreeCAD

```sh
construct freecad scene.json --out model.FCStd
construct freecad scene.json --out model.FCStd --step model.step
construct freecad scene.json --out model.step
```

```
wrote piano.FCStd, piano.step: 26 named parts, 2 joints
  true shapes (exact solids, splines, NURBS): 26 of 26 parts
  drawn only in lines, left out: case-rim, plate, strings-treble, strings-bass, bridge
```

## True shapes

A construct's parts are made from parameters (a box's size, a lathe's profile, a loft's sections), so
FreeCAD builds most of them as real CAD shapes, not facets:

| Shape | In FreeCAD |
| --- | --- |
| box, cylinder, cone, sphere, torus | the exact solid (a cylinder is a cylindrical surface; an ellipsoid a NURBS sphere stretched) |
| lathe | its profile as a spline, revolved: a smooth bottle, dome or bezel |
| extrude | its profile as splines between the sharp corners, extruded |
| loft (car bodies, hulls) | a smooth NURBS surface through its sections, each section a closed spline |
| tube | a circle swept along a spline (or the polyline, rounded at its turns) |

Each copy (a repeat, a mirror) is placed by the same transform the construct uses: a rotation keeps the
surfaces exact; a mirror or a stretch makes them NURBS. Every shape is then checked against the
construct's own surfaces: if its box differs by more than 4% of the part, it is tried again straight
(polygon profiles, a loft ruled between its sections), and if that fails too, the part is faceted as the
construct draws it, and the command lists it. Curves, paths, points, terrain, the architecture kit and
tapered tubes are always faceted. `--facets` facets every part, as before. Measured on the gallery: every
part of the CFX (26 of 26), the DB5 (38), the FJ62 (89 of 93; the rest are kinds that stay faceted), the
F40 and all but two of the Leica's are true shapes.

## What is in the document

| In the construct | In FreeCAD |
| --- | --- |
| a part | a `Part::Feature` labelled with its id (its label as `Label2`): a true shape (below) where it can be, else its closed pieces sewn into solids and refined, so coplanar facets become one face; its open surfaces as shells |
| its role, certainty, source, basis, stage | properties in the group "Construct" |
| assembly stages | a group per stage, `stage-0`, `stage-1`, … for the parts that do not move |
| an articulation (hinge, turn, slide, lift) | a group `joint-<id>` holding its parts, nested as the joints ride on one another, with its type, axis, pivot and amount, and an `Open` placement: set the group's Placement to it and the joint opens; its axis drawn as a line |
| metres, Y up | millimetres, Z up |

STEP keeps the tree and the names. The construct's annotations and its parts drawn only in lines
are left out, and the command lists them.

## What it is not

The shapes are the construct's own: true shapes where its parameters allow, smooth where the construct
draws a polygon (a loft's NURBS surface follows its sections more smoothly than the construct's straight
strips between them, by design). They are good for layout, clearance, packaging, rendering and a start to
model over; a construct's dimensions are as certain as it says, so they are not for machining. Joints are
groups with their axis and range, not FreeCAD Assembly joints; dimensions come from the construct,
so a part's size is as certain as the construct says.

The tests build the Yamaha CFX in FreeCAD when `CONSTRUCT_FREECAD` names its `freecadcmd`, reopen
the document, check every shape is valid, open the lid by its joint and read the STEP back.
