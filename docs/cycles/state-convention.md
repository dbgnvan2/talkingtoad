# Cycle State Convention

Each active cycle lives in `docs/cycles/<cycle_label>/` with a `state.json` file
that tells any agent (or human) exactly where things stand at a glance.

## Directory Layout

```
docs/cycles/
  gg/                          # Cycle GG (Tree-walking validator)
    state.json                 # Current phase, status, history
    spec.md                    # Architect's structured spec (4-part)
    review.md                  # Snr Dev's review output
    implementation.md          # Claude Code prompt (Developer input)
    result.log                 # Test results / implementation report
    final-spec.md              # Final spec sent back to Architect
```

## state.json Fields

```json
{
  "cycle_label": "GG",
  "description": "Tree-walking validator for SEO issue detection",
  "phase": "spec_approval",
  "status": "pending",
  "history": [
    {"phase": "spec_drafting", "status": "completed", "timestamp": "2026-05-30T10:00:00Z"},
    {"phase": "spec_review", "status": "completed", "timestamp": "2026-05-30T10:15:00Z"}
  ],
  "artifacts": {
    "spec": "spec.md",
    "review": "review.md",
    "implementation": "implementation.md",
    "result": "result.log",
    "final_spec": "final-spec.md"
  }
}
```

## Phase Progression

| Phase | Who | Status | Next |
|---|---|---|---|
| `spec_drafting` | Architect (Gemini) | `pending` -> `completed` | spec_review |
| `spec_review` | Snr Dev (Gemini CLI) | `pending` -> `approved`| spec_implementation |
| `spec_review` | Snr Dev (Gemini CLI) | `pending` -> `rejected` | spec_drafting (revision) |
| `spec_implementation` | Developer (Claude Code) | `pending` -> `completed` | work_review |
| `work_review` | Snr Dev (Gemini CLI) | `pending` -> `approved` | final_spec |
| `work_review` | Snr Dev (Gemini CLI) | `pending` -> `rejected` | spec_implementation (revision) |
| `final_spec` | Architect (Gemini) | `pending` -> `completed` | **CYCLE DONE** |

## Status Values

- `pending` — waiting for the responsible agent to act
- `in_progress` — actively being worked on
- `completed` — phase finished successfully
- `approved` — review passed
- `rejected` — review failed, needs revision
- `cancelled` — cycle abandoned

## Integration with Existing Repo Convention

At cycle completion, the final spec output goes to `docs/pending/YYYY-MM-DD_cycle-<label>.md`
following the repo's existing micro-spec convention. This feeds into the Gemini Compiler
pipeline that updates `docs/functional-specification.md`.
