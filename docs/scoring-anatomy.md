# Scoring Anatomy

The **Scoring Anatomy** module provides a detailed, per-check explanation of how a JSONL trace gets scored by the agent-scorecard evaluation engine. Every scoring decision is fully transparent and auditable.

## What it does

`score_anatomy` replays the same logic as `score_events` from `core.py`, but at each step records:

- **Which patterns were searched** — the full list of words, tool names, and patterns evaluated
- **Which patterns were found** — the specific items that matched
- **Why the check passed or failed** — a human-readable reason
- **Points awarded vs max points** — the per-check score

This makes it possible to understand exactly why an agent earned its score, and which specific signals drove each check.

## Usage

### Python API

```python
from agent_scorecard.anatomy import score_anatomy
from agent_scorecard.cli import load_jsonl
from pathlib import Path

events = load_jsonl(Path("examples/traces/good_obsidian_task.jsonl"))
report = score_anatomy(events)

print(report.score)       # 100
print(report.verdict)     # "Invest more"
print(report.to_markdown())  # Full detailed Markdown report
```

### CLI

Use the `--anatomy` flag with the standard CLI:

```bash
# Print anatomy report to stdout
python -m agent_scorecard.cli examples/traces/good_obsidian_task.jsonl --anatomy

# Save to file
python -m agent_scorecard.cli examples/traces/good_obsidian_task.jsonl --anatomy --output anatomy.md
```

## Anatomy Report Structure

The `AnatomyReport` dataclass contains:

| Field | Type | Description |
|---|---|---|
| `report` | `ScoreReport` | The canonical score report from `core.py` |
| `checks` | `dict[str, CheckAnatomy]` | Per-check anatomy details |

Each `CheckAnatomy` contains:

| Field | Type | Description |
|---|---|---|
| `check_name` | `str` | Name of the check (e.g., `promised_action_executed`) |
| `passed` | `bool` | Whether the check passed |
| `points` | `int` | Points awarded |
| `max_points` | `int` | Maximum possible points |
| `reason` | `str` | Human-readable explanation |
| `patterns_found` | `list[str]` | Specific patterns that matched |
| `patterns_searched` | `list[str]` | All patterns that were evaluated |

## Example: Good Trace (100/100)

```
# Scoring Anatomy Report

**Score:** 100/100
**Verdict:** Invest more

---

## `promised_action_executed` — PASS (10/10 pts)

**Reason:** Assistant promised action and later executed tools.

**Patterns searched (12):** `i will`, `我会`, `我来`, `先`, `will check`, ...

**Patterns found (1):** `i will`

---

## `uses_tools_for_retrieval` — PASS (10/10 pts)

**Reason:** Research/file/system claims are backed by retrieval tools.

**Patterns searched (18):** `research`, `market`, `查`, `调研`, ...

**Patterns found (2):** `research`, `browser`

---

## `verification_present` — PASS (15/15 pts)

**Reason:** Side effect was followed by verification/read-back/test/status evidence.

**Patterns found (1):** `read_file`

---

## `durable_artifact` — PASS (15/15 pts)

**Reason:** Trace includes a durable artifact or explicit artifact path.

**Patterns found (5):** `file`, `/vault/wiki/outputs/agent-eval-market.md`

---

## `no_busywork` — PASS (10/10 pts)

**Reason:** No obvious performative busywork.

**Patterns found:** none

---

## `concise_final` — PASS (10/10 pts)

**Reason:** Final answer is concise enough for Feishu (206 chars <= 1200).

**Patterns found (1):** `206 chars`

---

## `steven_preference_fit` — PASS (15/15 pts)

**Reason:** Trace shows Steven-specific preference/value awareness.

**Patterns found (3):** `steven`, `artifact`, `投资`

---

## `side_effect_safety` — PASS (10/10 pts)

**Reason:** No obvious unsafe side effect pattern detected.

**Patterns found:** none

---

## `clear_verdict` — PASS (5/5 pts)

**Reason:** Final answer includes clear outcome/verdict.

**Patterns found (2):** `verdict`, `done`

---

## Recommendation

Increase autonomy cautiously; keep lightweight regression checks.
```

### Key observations

- The agent promised action (`i will`) and delivered with 4 tool calls
- Retrieval claims were backed by `browser_navigate` calls
- Side effects (`write_file`) were verified by `read_file` read-back
- The trace produced a durable file artifact at an explicit path
- Steven-specific language (`steven`, `artifact`, `投资`) shows preference awareness
- The final answer is concise and includes a clear verdict

## Example: Bad Trace (45/100)

```
# Scoring Anatomy Report

**Score:** 45/100
**Verdict:** Do not delegate

---

## `promised_action_executed` — FAIL (0/10 pts)

**Reason:** Assistant promised action but no tool call followed.

**Patterns found (1):** `i will`

---

## `uses_tools_for_retrieval` — FAIL (0/10 pts)

**Reason:** Research/file/system claims had no retrieval tool evidence.

**Patterns found (1):** `market`

---

## `verification_present` — PASS (15/15 pts)

**Reason:** No side effect requiring verification was detected.

**Patterns found:** none

---

## `durable_artifact` — FAIL (0/15 pts)

**Reason:** No durable artifact detected.

**Patterns found:** none

---

## `no_busywork` — PASS (10/10 pts)

**Reason:** No obvious performative busywork.

**Patterns found:** none

---

## `concise_final` — PASS (10/10 pts)

**Reason:** Final answer is concise enough for Feishu (48 chars <= 1200).

**Patterns found (1):** `48 chars`

---

## `steven_preference_fit` — PASS (15/15 pts)

**Reason:** Trace shows Steven-specific preference/value awareness.

**Patterns found (1):** `worth`

---

## `side_effect_safety` — PASS (10/10 pts)

**Reason:** No obvious unsafe side effect pattern detected.

**Patterns found:** none

---

## `clear_verdict` — FAIL (0/5 pts)

**Reason:** Final answer lacks clear outcome/verdict.

**Patterns found:** none

---

## Top failure modes

- promised_action_executed: Assistant promised action but no tool call followed.
- uses_tools_for_retrieval: Research/file/system claims had no retrieval tool evidence.
- durable_artifact: No durable artifact detected.

## Recommendation

Fix the top failed check before expanding autonomy: promised_action_executed: Assistant promised action but no tool call followed.
```

### Key observations

- The agent promised research but **never called a single tool**
- The `market` keyword triggered the retrieval check, but no retrieval tools were used
- No file, path, or artifact was created
- No verdict word appeared in the final answer
- Hard gates capped the score at 45/100 because promises weren't backed by tool calls

## Relationship to core.py

The anatomy module **does not modify** the scoring logic. It:

1. Calls `score_events()` from `core.py` for the canonical score
2. Replays the same logic with pattern tracking to produce the anatomy
3. Ensures the anatomy score always matches the core score (verified in tests)

This guarantees that the anatomy report is always consistent with the actual scoring decisions.

## See also

- [Scorecard Standard](scorecard-standard.md) — the 9-check, 100-point evaluation standard
- `core.py` — the scoring engine (9 checks, hard gates, weights)
- `report.py` — standard report formatters
