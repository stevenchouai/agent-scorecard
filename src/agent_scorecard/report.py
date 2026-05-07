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
