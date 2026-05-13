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

Open `failure-replay.html` to see the public-safe contrast between a good delegated run and a bad busywork run, including the artifact, verification, privacy, handoff, and autonomy-decision differences.
