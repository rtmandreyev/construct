# Hard limits in Claude Code

The skill tells the agent its tier's limits; this hook enforces them from outside the model.
Without it an agent can overrun (seen in a live run: seven review rounds against a cap of four).

1. Copy `construct_budget.py` into your project's `.claude/hooks/`.
2. Add to the project's `.claude/settings.json` (your user settings are not touched):

```json
{
  "hooks": {
    "SessionStart": [{"hooks": [{"type": "command", "command": "python3 \"${CLAUDE_PROJECT_DIR}/.claude/hooks/construct_budget.py\" session-start", "timeout": 10}]}],
    "PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "python3 \"${CLAUDE_PROJECT_DIR}/.claude/hooks/construct_budget.py\" pre", "timeout": 10}]}],
    "PostToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "python3 \"${CLAUDE_PROJECT_DIR}/.claude/hooks/construct_budget.py\" post", "timeout": 10}]}]
  }
}
```

3. Pick the tier in the environment that starts Claude Code: `CONSTRUCT_TIER=showcase`
   (default `standard`), or set single limits: `CONSTRUCT_MAX_SECONDS=900`,
   `CONSTRUCT_MAX_REVIEWS=3`.

What it does, per session:

| when | effect |
|---|---|
| session start | records the start time; tells the agent its budget |
| each `construct review` | counts a review round; past the tier's rounds, review is refused with the reason |
| 80% of the wall clock | tells the agent once: the wrap-up point |
| past the wall clock | every tool is refused except reading and `check`/`build`, so the saved scene can still be made valid and delivered |

State is a small JSON file per session in `.construct-budget/` in the project; delete it to
reset. Add `.construct-budget/` to the project's `.gitignore`.

## Hermes

Hermes has the wall clock built in, per run, without touching `config.yaml`:

```bash
hermes chat --run-budget 600 --max-turns 120 -q "..."
```

`--run-budget` (seconds; `agent.run_budget_seconds` in config) gives the agent a one-time
wrap-up notice at 80% and caps provider waits to what remains; `--max-turns` caps the
tool-calling steps. Use 120 / 600 / 1800 seconds for quick / standard / showcase. Review
rounds are counted by the agent (`authoring.review_rounds`; `check` warns `tier-rounds`
past the cap).

## Any other host

Give the run a wall-clock timeout and a cost ceiling of your own, read a tier's limits from
the MCP tool `construct_limits` (or `construct_hologram.tiers.limits`), and treat the
`tier-rounds` warning from `check` as the signal to stop reviewing. `construct author`
enforces every limit itself.
