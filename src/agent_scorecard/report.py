from __future__ import annotations

import json
from typing import Any

from .core import ScoreReport

VERDICT_ORDER = (
    "Invest more",
    "Use with supervision",
    "Narrow delegation only",
    "Do not delegate",
)


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

    ranked = _ranked_results(results)
    lowest = min(results, key=lambda item: (item[1].score, item[0]))
    average = _average_score(results)
    verdict_counts = _verdict_mix(results)
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


def to_batch_summary_json(results: list[tuple[str, ScoreReport]]) -> str:
    return json.dumps(to_batch_summary_payload(results), ensure_ascii=False, indent=2) + "\n"


def to_batch_summary_payload(results: list[tuple[str, ScoreReport]]) -> dict[str, Any]:
    ranked = _ranked_results(results)
    ranked_traces = [_trace_summary(name, report) for name, report in ranked]
    needs_attention = min(ranked_traces, key=lambda item: (item["score"], item["trace"])) if ranked_traces else None

    return {
        "traces_scored": len(results),
        "average_score": _average_score(results),
        "top_candidate": ranked_traces[0] if ranked_traces else None,
        "needs_attention": needs_attention,
        "verdict_mix": _verdict_mix(results),
        "ranked_traces": ranked_traces,
    }


def _trace_summary(name: str, report: ScoreReport) -> dict[str, Any]:
    return {
        "trace": name,
        "score": report.score,
        "verdict": report.verdict,
        "top_signal": _top_signal(report),
    }


def _ranked_results(results: list[tuple[str, ScoreReport]]) -> list[tuple[str, ScoreReport]]:
    return sorted(results, key=lambda item: (-item[1].score, item[0]))


def _average_score(results: list[tuple[str, ScoreReport]]) -> float:
    return round(sum(report.score for _, report in results) / len(results), 1) if results else 0.0


def _verdict_mix(results: list[tuple[str, ScoreReport]]) -> dict[str, int]:
    verdict_mix = dict.fromkeys(VERDICT_ORDER, 0)
    for _, report in results:
        verdict_mix[report.verdict] = verdict_mix.get(report.verdict, 0) + 1
    return verdict_mix


def _top_signal(report: ScoreReport) -> str:
    if report.failure_modes:
        return report.failure_modes[0]
    return report.recommendation


def _escape_markdown_cell(value: str) -> str:
    return value.replace("\n", " ").replace("|", "\\|")
