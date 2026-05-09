# Example evaluation report

Generated with:

```bash
PYTHONPATH=src python -m agent_scorecard.cli examples/traces/good_obsidian_task.jsonl
```

Expected result: score in `Invest more` band because the trace shows source lookup, artifact creation, verification, and Steven-specific investment framing.

The batch portfolio index is generated with:

```bash
PYTHONPATH=src python -m agent_scorecard.cli --batch-dir examples/traces --reports-dir examples/reports --summary
```
