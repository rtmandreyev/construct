# Villa Savoye — desktop FDM model kit

## Start here

Open `booklet.html` for illustrated plate maps and assembly instructions. Keep its `img/` folder alongside it. `assembly.html` is the interactive 3D instruction viewer. Import `plate-1.3mf` through `plate-5.3mf` into your slicer as separate plates; `pieces/` contains individual replacement STLs.

The assembled model is approximately **182.6 × 200 × 83.9 mm**, at **1:115**. This is a **glue-fit kit**, not a snap-fit system. The ground chassis combines the base, pilotis and ground-floor enclosure. Floors, facade panels, circulation assemblies, roof plates and solarium remain separate. All glazing is deliberately opaque and paintable; FDM printing will not reproduce optically clear glass.

## Printer assumption and slicing

The plate layout assumes the desktop class: **250 × 210 × 220 mm** build volume (Prusa MK4-class), not a confirmed printer belonging to you. If your bed is smaller, import the individual STLs and rearrange them without scaling individual parts. The base itself needs a roughly 183 × 200 mm usable footprint plus any brim. Uniformly shrinking the kit can make reinforced details too thin.

Suggested starting settings, **not tested printer profiles**:

- PLA, 0.4 mm nozzle, 0.16–0.20 mm layers.
- 3 perimeters; 4–5 top/bottom layers; about 15% infill.
- Preserve supplied flat-face orientations; inspect every part in the slicer before printing.
- Enable supports where the preview shows unsupported soffits, stair/ramp overhangs, planter/table details or curved screens. Do not assume these plates are support-free. Use build-plate-only supports where sufficient; otherwise use removable supports with accessible contact points.
- Add a brim for thin upright or curved parts when the slicer/your printer needs it. Repack if the brim exceeds the bed.
- Check first-layer contact, bridges, narrow walls and support removal access. No G-code is supplied because printer, filament and temperatures are not specified.

Print one small circulation/detail part first to check your settings. Before printing all five plates, inspect the slicer's toolpaths rather than relying only on the solid preview.

## Assembly

Remove supports carefully, deburr mating faces and dry-fit all subassemblies before gluing. The kit is intended for adhesive assembly; flush digital interfaces have no calibrated printer-specific clearance. Light sanding may be required. Use adhesive suitable for your filament and follow its ventilation and handling instructions.

Follow the illustrated assembly groups: lower circulation, first-floor plates, interior partitions, facade panels, upper circulation and details, then roof plates and solarium screens. **Fit interior partitions, including the bathroom shower divider, before closing them under roofs.** Keep the roof dry-fitted until all internal work is complete. Paint glazing and other hard-to-reach interior surfaces before final enclosure.

## Designed adaptations and verification limits

The researched reconstruction is approximate; the print kit is not a measured restoration model. Its original `scene.json` was preserved. The separate `scene-print-kit.json` reinforces the foundation downward, thickens stair treads/parapets and selected small supports, extends planter bottoms to supporting plates, and closes a wall-corner joint. `kit-plan-desktop.json` records grouping and assembly order. These changes are manufacturing design decisions, not newly verified historical facts.

See `kit.json` for the actual manufacturing check and final part/plate/step counts. Its automatic checks cover bed fit, fragile/sliver pieces, floating pieces, disconnected merges and digital glue contacts. They do **not** prove support removal, real adhesive strength or physical fit. **No physical printing or assembly test has been performed, and no slicer was installed or run.**

The separately supplied 15-second MP4 is an architectural-stage assembly visualization of the researched source, not a frame-by-frame depiction of these exact printable modules. Use `assembly.html` and the booklet for the kit's physical assembly sequence.
