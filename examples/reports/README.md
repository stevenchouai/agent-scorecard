# Example evaluation report

Generated with:

```bash
PYTHONPATH=src python -m agent_scorecard.cli examples/traces/good_obsidian_task.jsonl
```

Expected result: score in `Invest more` band because the trace shows source lookup, artifact creation, verification, and Steven-specific investment framing.

Open the visitor walkthrough directly in a browser:

[trace-walkthrough.html](trace-walkthrough.html)

It shows the public-safe flow from a tiny trace, to scoring checks, to the resulting score and autonomy decision without requiring Python.

The batch portfolio index is generated with:

```bash
PYTHONPATH=src python -m agent_scorecard.cli --batch-dir examples/traces --reports-dir examples/reports --summary
```

The machine-readable JSON portfolio index is generated with:

```bash
PYTHONPATH=src python -m agent_scorecard.cli --batch-dir examples/traces --summary --format json --output examples/reports/index.json
```

Open `portfolio-viewer.html` for the public score summary, then use `delegation-policy.html` to turn the same sample data into an autonomy decision: give more permissions, keep supervised, or stop delegation until fixed.

Open `trust-contract.html` for the public trust contract that explains how trace evidence becomes a score, a permission tier, and a stop condition for Steven's personal AI OS.

Open `failure-replay.html` to see the public-safe contrast between a good delegated run and a bad busywork run, including the artifact, verification, privacy, handoff, and autonomy-decision differences.

Open `evidence-intake.html` before sharing a trace for scoring. It lists what to capture, what to redact, what counts as proof, what blocks higher autonomy, and a small copy/paste checklist for preparing a public-safe agent trace.
Open `scoring-dimensions.html` to see how the 7 scoring dimensions work: interactive cards with pass/fail signals, a radar chart comparing good and bad agents, and sample profiles that show how scores translate into autonomy decisions.
