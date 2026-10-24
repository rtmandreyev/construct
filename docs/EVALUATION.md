# Evaluation

## Cross-model, synthetic

Five synthetic tasks, every name invented ([tasks](../construct_hologram/evaluation/TASKS.md)):
a jewel-case CD; a paperback whose author and year the user does not know; a 440 ml can whose
brewery the user does not know; a desk lamp; a fictional three-legged moss snail carrying a
lantern. Models get only the prompts and the checker. `score.py` re-checks every answer:
one point each for **valid**, **factual** (the user's facts kept, nothing unknown invented,
`verified` only with a source) and **plausible** (archetype, category, size).

| model | how | score | notes |
|---|---|---|---|
| Claude Haiku | prompts + CLI, round 1 | 13/15 | ABV as text, a 330 ml can for 440 ml |
| Claude Haiku | after the prompt fixes | 15/15 | |
| Claude Sonnet | prompts + CLI | 15/15 | |
| Claude Opus | prompts + CLI | 15/15 | |
| DeepSeek (`deepseek-flash`) | live, through Hermes | 15/15 | $0.038 for all five, 258 s |
| GPT-6.1 Sol | live, through Hermes (ChatGPT plan) | 15/15 | 357 s |

No model invented an author, year, label or brewery the user did not know. Parameter entries
look identical across models; free scenes vary in likeness with the model, which is why the
review step and the `detached`/`thin` checks exist. Details of the Claude runs:
[RESULTS.md](../construct_hologram/evaluation/RESULTS.md).

## Score your own model

Put one answer file per task in a folder (names in `construct_hologram/evaluation/tasks.json`),
for example with `construct author ... --out t1-cd.json`, then:

```sh
python3 -m construct_hologram.evaluation.score path/to/answers [more/folders] [--json]
```

The scorer calls no model and needs no key.

The test suite is described in [DEVELOPMENT.md](DEVELOPMENT.md#tests).
