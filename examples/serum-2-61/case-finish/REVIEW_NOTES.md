# Case and finish follow-up: final review

This is a self-reviewed follow-up to the public audited example. It does not reuse the original critic's score. The original project folder and the example's archived run documents were not written. No commit or push was made.

## What was inspected

The eight files in `renders/` were rendered from the actual exported `serum.glb` through this checkout's `hosts/blender/` add-on, in Cycles, 32 samples with denoising. The product's geometry and mapped materials were not edited in Blender. Only studio floor, neutral lights and cameras were added. The rear/service inspection fill is enabled for those views; the normal front views avoid a reflected softbox obscuring the display graphics.

| View, personally inspected | Result |
| --- | --- |
| `hero.jpg` | Full instrument retains the same architecture and proportions. The fixed slip closes the former open channel; charcoal and blue-grey finishes, lime oscillator graphics and cyan modulation/selection are legible. |
| `front-junction.jpg` | Low front close-up: a continuous return behind the key tails masks the harness and electronics. The key openings remain; there is no open line into the bay. |
| `end-right.jpg` | Deck/end reveal, right key cheek and lower return form closed surfaces. The apron/tray/end junction has no exposed interior. |
| `end-left.jpg` | The stepped performance/key-slip corner is now closed by its end return. The performance well is backed by a solid wall; octave/hold buttons remain accessible. |
| `rear.jpg` | Straight, lit rear view: the raised I/O carrier closes against the deck; the service-hinge barrel/recess, connectors and outer reveals remain distinct. The recess behind the I/O wall has a job: hinge motion, and is not an exposed electronics opening. |
| `front-low.jpg` | Very low full-width angle: no exposed harness/cavity beneath the slip or at the key/performance transitions. |
| `service.jpg` | Original 80-degree service opening operates; the fixed slip, baffle, cheeks and corner return stay with the base and clear the moving deck. New optical surfaces follow the deck. This is nominal animation/clearance evidence, not a hinge load, fatigue or cable-flex simulation. |
| `editor.jpg` | Opaque charcoal optical face below thin clear cover glass; actual cyan graph surfaces are visible in the GLB, rather than relying on unexported labels or native hologram colours. |

Three solid-mode captures (not kept here) were also inspected from the built Construct in S/solid mode, with `open=0`: hero, low front and end. Its house palette is retained.

## Iteration caught by the views

A first roof-only closure still allowed the low front view to see the harness between white keys; the rear dust baffle closed that sightline. A plain-material left-end render then exposed an open stepped corner that was hard to judge in charcoal. The added `performance-key-slip-step-return` closes it. `renders/corner-check-end-left.jpg` is the accepted plain-material check of the same final geometry; earlier working images are not kept here.

## Checks and boundaries

`check scene.json --fit`: zero errors, the same three tiny-detail warnings, and exactly the four baseline buried findings (DAC, ADC, line drivers, fan hubs). No new fit findings and no suppressed rules.

`hinge-clearance.json` records the 0.02-degree cross-section sweep and bound between samples: at least 1.46 mm nominal deck/slip separation throughout 0–80 degrees; closed reveal 1.5 mm. Side reveals are 1 mm; wall/deck rear reveal is 0.94–1.50 mm. The rear hinge recess and the key openings are deliberate functional openings. Internal mounting contacts/overlaps are assembly joints, not exposed case seams. Production tolerances, loads, seals and actual keybed procurement remain mechanical-engineering work.

The material map records the printed/PDF manual pages 16, 37 and 188, screenshot regions and RGB readings. They are readings of the UI screenshots, not calibrated finish measurements. Anodizing, rough metal, polymer, glass and emitted brightness are physical design choices. All new geometry is inferred/designed and requirement-linked. No actual UI screenshots, logos or Xfer names were placed on the hardware.
