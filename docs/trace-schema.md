# Trace schema v0

Agent Scorecard accepts newline-delimited JSON.

## Event fields

Common fields:

- `type`: one of `user`, `assistant`, `tool_call`, `tool_result`, `artifact`, `error`
- `text`: natural language content
- `tool`: tool name for `tool_call`
- `path`: file path or artifact path
- `command`: shell command, when applicable
- `ok`: boolean result flag

## Minimal example

```jsonl
{"type":"user","text":"Check the repo and fix the bug."}
{"type":"assistant","text":"I will inspect the repo, patch the bug, and run tests."}
{"type":"tool_call","tool":"read_file","path":"src/app.py"}
{"type":"tool_call","tool":"write_file","path":"src/app.py"}
{"type":"tool_call","tool":"terminal","command":"pytest tests/test_app.py -q"}
{"type":"tool_result","ok":true,"text":"3 passed"}
{"type":"assistant","text":"Fixed and verified: tests pass."}
```
