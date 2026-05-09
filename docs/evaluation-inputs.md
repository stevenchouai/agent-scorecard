# Effective evaluation inputs

Agent Scorecard is useful only when it scores evidence, not vibes.

## Minimum useful input

A JSONL trace with:

1. `user` event — the task Steven actually asked for.
2. `assistant` events — promises, final answer, and any explicit reasoning shown to the user.
3. `tool_call` / `tool_result` events — searches, reads, writes, terminal commands, browser actions, Feishu/Obsidian/GitHub actions.
4. `artifact` events — file paths, commits, PRs, reports, notes, screenshots, or delivered messages.
5. `error` events — provider timeouts, failed deliveries, failed commands, blocked approvals.

Without tool calls and artifacts, the scorer can only detect obvious bad patterns such as promise-without-action. It cannot prove the agent was good.

## Hermes sessions

Use `docs/hermes-session-import.md` to convert one reviewed, sanitized Hermes session JSON into scorecard JSONL. A committed synthetic example is available at `examples/traces/hermes_session_sanitized.jsonl`, with its rendered report at `examples/reports/hermes_session_sanitized.md`.

## Best signal for Steven

Use real task traces, especially:

- market-research-to-recommendation tasks
- code change + test + commit tasks
- Obsidian note/log update tasks
- Feishu final-report tasks
- cron/autonomous task runs
- failures: timeout, not delivered, shallow research, old-repo busywork

## Labels needed later, not now

For v0, no manual labels are required.

For a stronger v1, collect 20-30 traces and label each with:

- `invest_more`
- `use_with_supervision`
- `narrow_delegation_only`
- `do_not_delegate`

Also tag the main failure mode:

- `no_tool_evidence`
- `no_verification`
- `no_artifact`
- `too_verbose`
- `busywork`
- `unsafe_side_effect`
- `weak_judgment`
- `delivery_failure`

## Good enough threshold

This is effective enough to publish as a proof-chain project when it can:

- give a high score to a verified artifact-producing trace
- give a low score to a promise-only trace
- explain the top failed checks without LLM judging
- run locally in CI with deterministic output

The current v0 meets that threshold. The next real improvement is trace collection, not more scoring complexity.
