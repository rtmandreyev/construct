# Look at your hologram (optional, for models that can see images)

You wrote a scene; here are its renders: `hero.png` (the finished object) and, when it
opens, `view-open.png`. Compare them with the request, not with the JSON.

Answer with one JSON object:

```json
{"recognisable": true, "reads_as": "what a stranger would call it in three words",
 "defects": [{"part": "part id", "problem": "what is wrong in the picture", "fix": "the change to the scene"}]}
```

Look for, in this order:
1. Does the silhouette read as the requested thing at a glance? If not, which mass is wrong?
2. Does anything hover, poke through, or end short of what it should touch?
3. Is any arm, leg, cable or frame so thin it barely shows?
4. Are the two or three features that make it itself visible and in proportion?
5. Is any text on the object wrong, upside down, or not from a fact?

List only defects you can see. An empty list is a good answer. Then apply your fixes to the
scene and send the whole corrected JSON for checking.
