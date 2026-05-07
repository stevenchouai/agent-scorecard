def test_good_trace_scores_invest_more(tmp_path):
    from agent_scorecard.core import score_events

    events = [
        {"type": "user", "text": "Research this and write a short Obsidian note."},
        {"type": "assistant", "text": "I will check sources, write the note, and verify it."},
        {"type": "tool_call", "tool": "browser_navigate"},
        {"type": "tool_call", "tool": "write_file", "path": "/vault/wiki/outputs/agent-eval.md"},
        {"type": "tool_call", "tool": "read_file", "path": "/vault/wiki/outputs/agent-eval.md"},
        {"type": "assistant", "text": "Verdict: done. Wrote /vault/wiki/outputs/agent-eval.md and verified the file. This is worth investing because it creates a durable artifact and avoids busywork."},
    ]

    report = score_events(events)

    assert report.score >= 85
    assert report.verdict == "Invest more"
    assert report.checks["durable_artifact"].passed is True
    assert report.checks["verification_present"].passed is True


def test_bad_trace_penalizes_promises_without_action():
    from agent_scorecard.core import score_events

    events = [
        {"type": "user", "text": "Look at the market and tell me if this is worth doing."},
        {"type": "assistant", "text": "I will research the market and create a plan."},
        {"type": "assistant", "text": "This is obviously a good idea. We should do it."},
    ]

    report = score_events(events)

    assert report.score < 50
    assert report.verdict == "Do not delegate"
    assert report.checks["promised_action_executed"].passed is False
    assert report.checks["uses_tools_for_retrieval"].passed is False


def test_markdown_report_contains_failures():
    from agent_scorecard.core import score_events
    from agent_scorecard.report import to_markdown

    report = score_events([
        {"type": "assistant", "text": "I will fix the old repo quickly."},
        {"type": "tool_call", "tool": "terminal", "command": "echo cosmetic update"},
        {"type": "assistant", "text": "Done."},
    ])

    markdown = to_markdown(report)

    assert "# Agent Scorecard Report" in markdown
    assert "promised_action_executed" in markdown
    assert "Top failure modes" in markdown
