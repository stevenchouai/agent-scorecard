from __future__ import annotations

from .core import ScoreReport


def to_markdown(report: ScoreReport) -> str:
    lines = [
        "# Agent Scorecard Report",
        "",
        f"**Score:** {report.score}/100",
        f"**Verdict:** {report.verdict}",
        "",
        "## Checks",
        "",
        "| Check | Result | Points | Reason |",
        "|---|---:|---:|---|",
    ]
    for name, check in report.checks.items():
        result = "PASS" if check.passed else "FAIL"
        lines.append(f"| `{name}` | {result} | {check.points}/{check.max_points} | {check.reason} |")

    lines.extend(["", "## Top failure modes", ""])
    if report.failure_modes:
        for item in report.failure_modes:
            lines.append(f"- {item}")
    else:
        lines.append("- None detected.")

    lines.extend(["", "## Recommendation", "", report.recommendation, ""])
    return "\n".join(lines)


def to_batch_summary_markdown(results: list[tuple[str, ScoreReport]]) -> str:
    if not results:
        return "# Agent Scorecard Portfolio Summary\n\nNo traces scored.\n"

    ranked = sorted(results, key=lambda item: (-item[1].score, item[0]))
    lowest = min(results, key=lambda item: (item[1].score, item[0]))
    average = sum(report.score for _, report in results) / len(results)
    verdict_counts = {
        "Invest more": 0,
        "Use with supervision": 0,
        "Narrow delegation only": 0,
        "Do not delegate": 0,
    }
    for _, report in results:
        verdict_counts[report.verdict] = verdict_counts.get(report.verdict, 0) + 1

    leader_name, leader_report = ranked[0]
    attention_name, attention_report = lowest
    lines = [
        "# Agent Scorecard Portfolio Summary",
        "",
        f"**Traces scored:** {len(results)}",
        f"**Average score:** {average:.1f}/100",
        f"**Top candidate:** {_escape_markdown_cell(leader_name)} ({leader_report.score}/100, {leader_report.verdict})",
        (
            f"**Needs attention:** {_escape_markdown_cell(attention_name)} "
            f"({attention_report.score}/100, {attention_report.verdict})"
        ),
        "",
        "## Verdict mix",
        "",
        "| Verdict | Traces |",
        "|---|---:|",
    ]
    for verdict, count in verdict_counts.items():
        lines.append(f"| {verdict} | {count} |")

    lines.extend(
        [
            "",
            "## Ranked traces",
            "",
            "| Trace | Score | Verdict | Top signal |",
            "|---|---:|---|---|",
        ]
    )
    for name, report in ranked:
        lines.append(
            f"| {_escape_markdown_cell(name)} | {report.score}/100 | {report.verdict} | "
            f"{_escape_markdown_cell(_top_signal(report))} |"
        )

    lines.append("")
    return "\n".join(lines)


def _top_signal(report: ScoreReport) -> str:
    if report.failure_modes:
        return report.failure_modes[0]
    return report.recommendation


def _escape_markdown_cell(value: str) -> str:
    return value.replace("\n", " ").replace("|", "\\|")
