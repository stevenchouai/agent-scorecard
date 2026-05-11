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
