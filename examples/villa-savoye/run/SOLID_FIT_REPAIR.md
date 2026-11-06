# Villa Savoye — scoped solid-fit repair

## Result

Repaired the reported architectural interferences and reviewed the full building and salon/rail details in **solid mode**. The finest available check now reports only two intentional guardrail/support junctions. This is **not a zero-finding raw fit result** and is not a watertightness, structural, headroom or printability certification.

The original judged scene is preserved as `before-solid-fit-repair.json`, and its sealed round-12 checkpoint was not edited. This follow-up is **self-reviewed**; the earlier independent critic's rating does not apply to the revised geometry.

## What changed

- Consolidated eight overlapping ribbon-rail/reveal pairs into single fitted profiles. They meet the masonry opening edges rather than straddling them.
- Trimmed three rear partition ends and the west bedroom partition to the inner glazing/reveal planes. Opposite ends and vertical datums were retained. The modified west partition was downgraded from traced to inferred.
- Seated sash top/bottom bars against their reveals instead of overlapping them by 5 mm.
- Raised the two lower salon tracks onto the threshold; seated the head tracks below the head reveal. Extended the supports to cover the complete opening and added the missing outer head track.
- Fitted the salon panes and four intermediate stiles between those tracks: lower edge **3.215 m**, upper edge **6.775 m**. These remain inferred construction dimensions.
- Consolidated the front end pier and jamb return into one extrusion preserving their former union footprint, and removed the redundant first frame-group mullion at that junction.
- Removed a stand-off buried in the bathroom jamb and terminated its rail at the wall. Shortened the seven remaining outer stand-offs so their cap centres meet the rail axes rather than continuing 20 mm above them.
- Seated the first curved-entry mullion against the service wall using the actual six-sided cylinder extent, not its nominal radius.

The final scene has **396 named entries / 553 instances**: 41 existing entries changed, 10 redundant entries removed, one outer head-track entry added.

## Fit checks — same resolution before and after

| Voxels along longest side | Before repair | After repair | Remaining classification |
|---|---:|---:|---|
| 200 | 23 findings | 4 findings | Thin parts sharing raster cells at mathematically touching faces |
| 400 | 27 findings | 6 findings | Five touching-face raster artifacts; one intentional rail/stand-off joint |
| 600 | 20 findings | 2 findings | Two intentional rail/support joints; no buried-part findings |

Final validation: **PASS, zero errors, eight `tiny` visibility warnings**. Those warnings concern the hob ring and seven small stand-offs at whole-building framing, not detached or penetrating architecture. They were not inflated to silence a visibility warning.

The final 600-cell findings are:

1. `return-stair-upper-tubular-handrail` / `rail-standoff-upper-left-front`.
2. `return-stair-upper-inner-rail` / `inner-rail-post-upper-b`.

Both are joined guardrail assemblies. The post cap centres coincide with the corresponding rail centreline stations, and the posts are narrower than their rails. They are not unrelated parts intruding through the building. The 400-cell report additionally flags the equivalent lower rail / lower-right-front stand-off connection. These intentional assembly overlaps are retained and disclosed, not filtered out of the audit.

## Coordinate checks independent of the voxel grid

`verify_solid_fit.py` passed **63 coordinate checks** on the compiled geometry, including repeated sash instances. It also confirms **107 protected entries unchanged**, including pilotis, floor/roof geometry, solarium, ramp assemblies, principal façade heads/spandrels and curved entrance panes. Published facts, cited sources and compiled overall bounds are unchanged.

Examples explaining the coarse-grid flags:

| Interface | First component Y span (m) | Second component Y span (m) | Actual relation |
|---|---|---|---|
| Front sill reveal / sash bottom | 4.360–4.390 | 4.390–4.440 | Touch at 4.390; no volumetric overlap |
| Sash top / head reveal | 5.390–5.440 | 5.440–5.470 | Touch at 5.440 |
| Salon threshold / lower tracks | 3.100–3.180 | 3.180–3.215 | Tracks sit on threshold |
| Salon outer head track / head reveal | 6.775–6.810 | 6.810–6.850 | Track sits below reveal |

The merged pier's volume matches the former pier-and-jamb union within the test tolerance. The terminal entry mullion's compiled rear surface meets the service-wall end. These tests check the named static interfaces; they are not an exhaustive triangle-pair collision proof for every part in the house.

`verify_promenade.py` also passes again: four ramp endpoint checks, 18 stair tread/parapet notch-footprint checks and landing elevations. Maximum ramp endpoint level discrepancy remains **0.001628 m**. This does not certify walkability or headroom.

## Revision and evidence

Final scene SHA-256:
`1c0ecb19ce64b271777fdd19a9cdc3d0433bae722330f95d1bea1bd9bc35326b`

- Coordinate evidence: `solid-fit-coordinate-verification.json`.
- Circulation evidence: `numerical-verification.json`.
- Final solid overview: `review/20261106-022252-0f83/review/solid.png`.
- Solid detail captures: `solid-fit-salon.png`, `solid-fit-rail-joint.png`.
- Tool run handles, baseline 200/400/600: `07ff1b15a37a`, `5c9070abdb8c`, `0c66d7a17bc0`.
- Tool run handles, final 200/400/600: `e64892de7c4d`, `5095fdb36e85`, `9b1488661537`.

The prior `FINAL_VERIFICATION.md` is retained as a historical record of the pre-repair version; use this report for the current geometry. No software was installed and no sealed judged checkpoint was rewritten.
