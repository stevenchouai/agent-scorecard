# Hermes session import

The Hermes importer converts one sanitized Hermes session JSON file into Agent Scorecard JSONL. It is a public-safe bridge for demos and PR review; it is not a crawler for local session stores.

## What it accepts

Pass a single JSON file with a transcript-like array. The importer looks for common containers such as `events`, `messages`, `items`, `turns`, `transcript`, or `conversation`, including under `session` or `data`.

Within each item, it normalizes:

- user and assistant messages from role/speaker-style fields
- tool calls from tool/action/function-style fields
- tool results and observations
- artifact records with paths, URLs, or filenames
- error records from failed status or error fields

The output schema is the normal scorecard JSONL event format documented in `docs/trace-schema.md`.

## Convert a sanitized session

Use a sanitized file you have already reviewed:

```bash
PYTHONPATH=src python3 -m agent_scorecard.cli \
  --from-hermes-session tests/fixtures/hermes_session_sanitized.json \
  --output examples/traces/hermes_session_sanitized.jsonl
```

The generated demo trace is committed at `examples/traces/hermes_session_sanitized.jsonl`.

## Audit the converted trace

Before scoring or publishing a converted trace, run the privacy audit gate:

```bash
PYTHONPATH=src python3 -m agent_scorecard.cli \
  --audit-privacy examples/traces/hermes_session_sanitized.jsonl
```

The command exits non-zero if it finds obvious secret values, Feishu/OpenPlatform IDs, or local private paths. Use `--format json` when another script needs structured pass/fail output.

## Score the converted trace

Render a Markdown report from the converted JSONL:

```bash
PYTHONPATH=src python3 -m agent_scorecard.cli \
  examples/traces/hermes_session_sanitized.jsonl \
  --format markdown \
  --output examples/reports/hermes_session_sanitized.md
```

The committed demo report is `examples/reports/hermes_session_sanitized.md`.

## Privacy rules

- Import one intentionally sanitized JSON file at a time.
- Do not point commands at private local session, Codex, Hermes, Obsidian, or log directories.
- Do not commit real workspace paths, personal note content, employer-sensitive text, access tokens, API keys, cookies, or Feishu/OpenPlatform IDs.
- Keep public fixtures synthetic. Use placeholders such as `<LOCAL_PATH>/scorecard-note.md` for artifact paths.
- Re-run `--audit-privacy` before committing generated traces, reports, or docs.
