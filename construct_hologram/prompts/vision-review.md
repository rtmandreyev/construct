# Art-direction review of your construct (for models that can see images)

Here are the renders of your construct: `hero.png` (the finished object), `sheet-views.png`
(hero, front, side, back, top, three-quarter), `sheet-assembly.png` (how it builds) and, when
it opens, `view-open.png`. Judge the pictures against the request and your references, not
the JSON. The question is not "is it recognisable?" but "is it genuinely good: accurate and
beautiful, something you would put in a launch video?"

Score each criterion 0-3 (0 missing, 1 weak, 2 good, 3 striking):

- `silhouette`: it reads instantly as this thing, from the hero and in every view;
- `proportions`: right against the facts and references (heights, widths, spacing);
- `identity`: the two or three identity features are rendered with care, in proportion;
- `depth`: masses, structure, detail and ornament layer clearly; nothing equally loud;
- `composition`: strong hero framing, nothing cut off, good use of the frame;
- `assembly`: the build order tells the object's story (foundations first, the reveal last);
- `motion`: articulations and idle life bring it alive without noise (judge from the
  assembly sheet and what moves);
- `density`: rich detail that never clutters; no hairlines, nothing hovering or poking through;
- `honesty`: labels come only from facts; inferred and decorative parts look it.

Answer with one JSON object:

```json
{"verdict": "good", "scores": {"silhouette": 3, "proportions": 2, "identity": 2, "depth": 2,
 "composition": 3, "assembly": 2, "motion": 2, "density": 2, "honesty": 3},
 "weakest": "the criterion to improve first",
 "fix": "the concrete change to the scene that improves it most",
 "next": ["further improvements, most valuable first"]}
```

`verdict` is "good" only when every score is 2 or more and you would show it as it is;
otherwise "improve". Be a demanding art director: a construct that is merely correct is not
yet good. You will then be asked to apply the fix and send the whole corrected scene.
