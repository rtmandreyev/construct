# One improvement round: one critic, three parts, in this order

You are the round's one independent critic. Work through the parts in order and write each
part's answer before you open the next: part 1 is your blind judgement, and it must not be
shaped by the history in parts 2 and 3.

**Part 1, this version alone.** Open `step-1/packet.md` and judge as it asks: scores, the
identity checklist and the ranked defects (a construct-critique). Every score below 3 cites a
defect of its criterion. Write it down now and do not change it later.

**Part 2, against the best so far** (when the packet has `step-2/`). The same views of two
versions, A and B, unlabelled and in a random order, beside the same references. Which is
better overall and more recognisable as the real thing? For each criterion: A, B or same. Then
the concrete differences: each one with the version that is better (`better`: A or B), its
criterion, the parts, and the evidence you see. Judge the pictures, not a guess about which is
newer.

**Part 3, the ledger.** Open `step-3/ledger.json`: the defects found in earlier rounds. For each
item say `fixed`, `open` or `regressed` in this version (part 1's renders), with one line of
evidence, or `inexpressible` when the construct's tools cannot draw what it asks. Then list the
ranks of your part-1 defects that are genuinely new (not a ledger item again), and which of them
ask for the medium's limits (`limits`: {rank: "L1" | "L2" | "L3"}: hidden lines showing through,
tinted glass, an opening in a still).

Answer with one JSON object, no prose:

```json
{"format": "construct-round", "version": 1, "scene_sha256": "copy it from the packet",
 "critique": {"format": "construct-critique", "...": "part 1, as step-1/packet.md asks"},
 "pairwise": {"winner": "A", "criteria": {"silhouette": "A", "proportions": "same", "identity": "B", "depth": "A",
               "composition": "same", "assembly": "same", "motion": "same", "density": "A", "honesty": "same"},
              "differences": [{"better": "A", "criterion": "identity", "parts": ["headlamp-left"],
                                "evidence": "what you see in which view"}]},
 "reconcile": {"items": [{"id": "D3", "status": "fixed", "evidence": "one line from the renders"}], "new": [1, 4],
               "limits": {}}}
```

Leave `pairwise` out when the packet has no part 2 (the first version).
