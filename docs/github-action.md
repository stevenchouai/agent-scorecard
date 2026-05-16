# GitHub Action: Agent Scorecard

Score agent workflow traces directly in your CI pipeline. Get portfolio summaries, quality badges, and automatic PR comments — all from a single `uses:` step.

## Quick Start

```yaml
- uses: stevenchouai/agent-scorecard@main
  with:
    traces-dir: ./my-traces
```

## Full Example

```yaml
name: Score Agent Traces

on:
  pull_request:
    paths:
      - "traces/**"
  push:
    branches: [main]
    paths:
      - "traces/**"

permissions:
  pull-requests: write
  contents: read

jobs:
  scorecard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: stevenchouai/agent-scorecard@main
        id: scorecard
        with:
          traces-dir: ./traces
          format: markdown
          fail-under-average: 75
          fail-under-min: 50
          badge-output: scorecard-badge.svg
          post-comment: "true"

      - name: Upload badge artifact
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: scorecard-badge
          path: ${{ steps.scorecard.outputs.badge-path }}

      - name: Use results
        run: |
          echo "Score: ${{ steps.scorecard.outputs.average-score }}"
          echo "Verdict: ${{ steps.scorecard.outputs.verdict }}"
          echo "Report: ${{ steps.scorecard.outputs.report-path }}"
```

## Inputs

| Input | Description | Default |
|---|---|---|
| `traces-dir` | Directory containing `.jsonl` trace files | `examples/traces` |
| `format` | Report format: `markdown` or `json` | `markdown` |
| `fail-under-average` | Minimum average score (0–100) to pass. Set to `0` to disable. | `70` |
| `fail-under-min` | Minimum single-trace score (0–100) to pass. Set to `0` to disable. | `40` |
| `post-comment` | Post results as a PR comment | `true` |
| `badge-output` | Path to write the SVG portfolio badge | `scorecard-badge.svg` |

## Outputs

| Output | Description |
|---|---|
| `average-score` | Average score across all traces (e.g. `81.7`) |
| `verdict` | `pass` or `fail` |
| `badge-path` | Path to the generated SVG badge |
| `report-path` | Path to the generated summary report |

## PR Comment

When triggered on a pull request, the action posts a comment with:

- **Score summary** with a visual badge
- **Verdict** (pass/fail)
- **Portfolio badge** rendered inline (SVG)
- **Full report** in a collapsible section

The comment is posted using the `gh` CLI if available, otherwise via the GitHub API with `GITHUB_TOKEN`.

## Quality Gates

The action enforces two configurable thresholds:

- **Average gate** (`fail-under-average`): Fails if the average score across all traces is below the threshold.
- **Minimum gate** (`fail-under-min`): Fails if any single trace scores below the threshold.

To disable a gate, set its value to `0`:

```yaml
- uses: stevenchouai/agent-scorecard@main
  with:
    fail-under-average: 0     # Disable average gate
    fail-under-min: 50        # Only enforce minimum gate
```

## Permissions

To post PR comments, the workflow needs:

```yaml
permissions:
  pull-requests: write
  contents: read
```

If `post-comment` is `false`, only `contents: read` is needed.

## Edge Cases

| Scenario | Behavior |
|---|---|
| No traces found | Warning emitted, verdict set to `pass`, action succeeds |
| Single trace | Scored normally, average equals that trace's score |
| Empty trace directory | Treated as no traces found |
| Gate fails | Action fails, but PR comment is still posted |
| Not a PR event | Scoring runs normally, comment posting is skipped |

## Badge

The SVG badge shows the average score and autonomy decision:

- **Green** (≥85 avg, all ≥85): "Increase autonomy"
- **Yellow** (≥70 avg, worst ≥50): "Keep supervised"
- **Red** (worst <50 or avg <70): "Stop delegation until fixed"

Upload the badge as an artifact or commit it to your repo for display in READMEs.

## Standalone CLI

The action installs [`agent-scorecard`](https://github.com/stevenchouai/agent-scorecard) which you can also use directly:

```bash
# Score one trace
agent-scorecard trace.jsonl

# Score a batch with summary
agent-scorecard --batch-dir ./traces --summary

# JSON output with quality gate
agent-scorecard --batch-dir ./traces --summary --format json \
  --fail-under-average 70 --fail-under-min 40

# Generate badge SVG
agent-scorecard --batch-dir ./traces --summary --format badge --output badge.svg
```

## How It Works

1. Installs Python 3.11 and `agent-scorecard` via pip
2. Scans the traces directory for `.jsonl` files
3. Runs the scorecard CLI in batch + summary mode
4. Generates JSON summary, markdown/JSON report, and SVG badge
5. Extracts the average score and determines pass/fail
6. Posts a PR comment with results (if applicable)
7. Fails the step if quality gates are not met
