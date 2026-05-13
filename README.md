# Agent Scorecard

<p align="center">
  <img src="assets/repo-eval-loop.svg" alt="Agent Scorecard trace-first evaluation loop" width="100%">
</p>

A small, trace-first evaluation harness for answering one practical question:

> Is this agent worth Steven investing more tokens, permissions, and attention in?

This is not a generic LLM benchmark. It scores agent work against Steven-specific operating standards: useful artifacts, tool discipline, verification, concise communication, memory/logging, and avoidance of performative busywork.

## Part of StevenOS

`agent-scorecard` is the **evaluation layer** in Steven's Personal AI Operating System.

- **Upstream:** Hermes / OpenClaw / Codex-style traces from real agent work.
- **This layer:** deterministic checks for tool discipline, verification, artifact creation, and concise handoff quality.
- **Downstream:** autonomy decisions — which agents deserve more tokens, permissions, and attention.
- **Proof:** Markdown reports that explain what passed, what failed, and why the task should or should not be delegated again.

## MVP scope

- Define a transparent scoring standard in `docs/scorecard-standard.md`.
- Evaluate simple JSONL traces with rule-based checks.
- Produce Markdown reports that explain verdicts and failures.
- Compare Hermes/OpenClaw/Codex-style agents on the same work patterns.

## Quick start

Install the runnable package with test dependencies:

```bash
python -m pip install -e ".[dev]"
```

Run one trace and inspect the verdict:

```bash
agent-scorecard examples/traces/good_obsidian_task.jsonl
agent-scorecard examples/traces/bad_busywork_task.jsonl --format markdown
```

Expected signal from the good trace:

```text
Score: 100/100
Verdict: Invest more
```

Verify the repo locally:

```bash
pytest
```

No-install fallback:

```bash
PYTHONPATH=src python -m agent_scorecard.cli examples/traces/good_obsidian_task.jsonl
PYTHONPATH=src python -m unittest discover -v
```

Regenerate every public example report in one command:

```bash
PYTHONPATH=src python -m agent_scorecard.cli --batch-dir examples/traces --reports-dir examples/reports
```

Generate a portfolio summary across all public example traces:

```bash
PYTHONPATH=src python -m agent_scorecard.cli --batch-dir examples/traces --reports-dir examples/reports --summary
```

Generate the same portfolio summary as machine-readable JSON:

```bash
PYTHONPATH=src python -m agent_scorecard.cli --batch-dir examples/traces --summary --format json --output examples/reports/index.json
```

The Markdown summary includes an `Autonomy decision` section. The JSON summary exposes the same decision under
`autonomy_decision.decision`, with `reason` and `worst_trace` fields for CI logs and plain-English review output.

Open the static proof surface in a browser:

[![Agent Scorecard portfolio badge](examples/reports/portfolio-badge.svg)](examples/reports/portfolio-viewer.html)

[examples/reports/portfolio-viewer.html](examples/reports/portfolio-viewer.html)

For a 60-second no-install walkthrough of how one trace becomes checks, a score, and a trust decision, open:

[examples/reports/trace-walkthrough.html](examples/reports/trace-walkthrough.html)

Use the delegation policy simulator to translate those scores into a next-step autonomy decision:

[examples/reports/delegation-policy.html](examples/reports/delegation-policy.html)

Generate the compact SVG badge from the same public summary data:

```bash
PYTHONPATH=src python -m agent_scorecard.cli --batch-dir examples/traces --summary --format badge --output examples/reports/portfolio-badge.svg
```

Use a portfolio summary as an automation gate:

```bash
PYTHONPATH=src python -m agent_scorecard.cli --batch-dir examples/traces --summary --fail-under-average 70 --fail-under-min 40
```

## Public proof gate

This repo ships a GitHub Actions proof gate at `.github/workflows/scorecard.yml`. On every pull request and `main` push it:

1. runs the unit test suite;
2. audits every public example trace for obvious secrets, Feishu IDs, and local private paths;
3. regenerates the public Markdown/JSON/SVG proof reports;
4. enforces portfolio score floors with `--fail-under-average 70 --fail-under-min 40`; and
5. fails if regenerated public reports differ from the committed `examples/reports` artifacts.

That makes the public examples usable as a small CI-backed proof chain: if a future trace lowers quality, leaks private context, or leaves the published evidence stale, the workflow turns red before the evidence is published.

Convert a sanitized Hermes session JSON into scorecard JSONL:

```bash
PYTHONPATH=src python -m agent_scorecard.cli --from-hermes-session sanitized-hermes-session.json --output out/hermes-trace.jsonl
```

Audit the converted JSONL before using it as public proof:

```bash
PYTHONPATH=src python -m agent_scorecard.cli --audit-privacy out/hermes-trace.jsonl
```

See `docs/hermes-session-import.md` for the public-safe importer runbook and `examples/reports/hermes_session_sanitized.md` for a generated report from the synthetic fixture.

Or install locally first:

```bash
python -m pip install -e .
agent-scorecard examples/traces/good_obsidian_task.jsonl
agent-scorecard --batch-dir examples/traces --reports-dir examples/reports
agent-scorecard --batch-dir examples/traces --reports-dir examples/reports --summary
agent-scorecard --batch-dir examples/traces --summary --format json --output examples/reports/index.json
```

## Score bands

- `85-100`: invest more — reliable enough for higher autonomy.
- `70-84`: usable with supervision — good but needs targeted improvement.
- `50-69`: limited trust — useful for narrow tasks only.
- `<50`: do not delegate — too much review burden.

Portfolio autonomy decisions combine the aggregate score with the weakest trace: increase autonomy requires both average and weakest trace
to be `85+`; keep supervised requires average `70+` and weakest trace `50+`; otherwise stop delegation until fixed.

## Trace format

JSONL, one event per line:

```json
{"type":"user","text":"research this and write the result to Obsidian"}
{"type":"assistant","text":"I will check sources and write the note."}
{"type":"tool_call","tool":"browser_navigate"}
{"type":"tool_call","tool":"write_file","path":"/vault/wiki/outputs/report.md"}
{"type":"tool_call","tool":"read_file","path":"/vault/wiki/outputs/report.md"}
{"type":"assistant","text":"Done: wrote /vault/wiki/outputs/report.md and verified it."}
```

## What evidence is needed?

See `docs/evaluation-inputs.md`.

Short version: the scorer needs real traces with user ask, assistant messages, tool calls, artifacts, verification events, and failures. The next valuable improvement is trace collection from Hermes/OpenClaw runs, not adding more evaluator complexity.

## Repository status

This is a v0 local repo. The first goal is a useful internal standard, not a polished platform.
