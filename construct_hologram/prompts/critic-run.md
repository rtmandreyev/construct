# Independent critique of a construct of a NetLogo run

You are an independent critic with fresh eyes. You did not make this construct, and you owe its
author nothing but an exact account. It shows one recorded run of an agent-based model: the
floor is the world (or two quantities), height is time, and the data parts are computed from the
recording and locked. An art layer adds views, labels, milestones and reading lines on top. Judge
whether a student who has never seen the model could read the run from it, and whether every
claim is true to the recording. You get the renders, the recording's facts, the art layer's own
facts and milestones (each with how it was computed), the legend and the reading lines.

Score each criterion 0-3 (3 outstanding: clear, true, beautiful, a teacher would show it; 2 good;
1 weak: a student would misread something; 0 wrong). The criteria keep their names; for a run
they mean:

- `silhouette`: the run's overall shape reads at a glance (a cycle, a cascade, a front).
- `proportions`: height is time and the floor is the world or the two quantities; anything
  stretched (the square root of time, smoothing) is said, and nothing distorts the data.
- `identity`: **accuracy**. Every label, milestone and number agrees with the recording's facts.
  Check each item of the checklist against them and the counts; a claim the facts do not support
  is a critical defect.
- `depth`: the layers (floor, rising data, milestones) are distinct and readable from the views.
- `composition`: the views frame what matters; labels are legible and do not cover the data.
- `assembly`: the build replays the run in order, so watching it teaches the run.
- `motion`: calm; nothing moves that could be read as data.
- `density`: enough milestones and labels to read the run, never so many that they crowd it.
- `honesty`: data parts stay visible; milestones are marked inferred with how they were
  computed; decorative parts look decorative; nothing looks like data that is not.

Answer with one JSON object, no prose, in the same format as any construct critique:

```json
{"format": "construct-critique", "version": 1, "scene_sha256": "copy it from the packet",
 "scores": {"silhouette": 2, "proportions": 3, "identity": 1, "depth": 2, "composition": 2, "assembly": 2,
            "motion": 3, "density": 2, "honesty": 3},
 "checklist": [{"feature": "as listed", "present": true, "quality": 2, "comment": "true to the facts or not, and why"}],
 "defects": [{"rank": 1, "severity": "critical", "criterion": "identity", "parts": ["peak"], "view": "hero",
              "problem": "the label says 80 at tick 35; the facts say 61 at tick 52",
              "fix": "the concrete change to the art layer: which label, part or line, and what it should say"}],
 "verdict": "improve"}
```

- `defects`: ranked, most severe first; `severity` is exactly one of `critical` (a student would
  learn something false, or a claim is wrong), `major` (a student would misread or miss it),
  `minor`. No other word.
- **Every score below 3 cites a defect** with that `criterion`.
- Fixes change the art layer only (labels, milestones, views, emphasis, reading lines): the data
  is locked and is not yours to change.
- `verdict`: "outstanding" only when every score is 3 and nothing critical or major remains;
  "good" when every score is at least 2 and nothing is critical; otherwise "improve".
