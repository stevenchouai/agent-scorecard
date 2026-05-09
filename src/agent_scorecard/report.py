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

    payload = to_batch_summary_payload(results)
    ranked = _ranked_results(results)
    decision = payload["autonomy_decision"]
    average = payload["average_score"]
    verdict_counts = payload["verdict_mix"]
    leader_name, leader_report = ranked[0]
    attention = payload["needs_attention"]
    lines = [
        "# Agent Scorecard Portfolio Summary",
        "",
        f"**Traces scored:** {len(results)}",
        f"**Average score:** {average:.1f}/100",
        f"**Top candidate:** {_escape_markdown_cell(leader_name)} ({leader_report.score}/100, {leader_report.verdict})",
        (
            f"**Needs attention:** {_escape_markdown_cell(attention['trace'])} "
            f"({attention['score']}/100, {attention['verdict']})"
        ),
        "",
        "## Autonomy decision",
        "",
        f"**Decision:** {decision['label']}",
        f"**Reason:** {_escape_markdown_cell(decision['reason'])}",
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
    average_score = _average_score(results)

    return {
        "traces_scored": len(results),
        "average_score": average_score,
        "top_candidate": ranked_traces[0] if ranked_traces else None,
        "needs_attention": needs_attention,
        "autonomy_decision": _autonomy_decision(average_score, needs_attention),
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


def _autonomy_decision(average_score: float, worst_trace: dict[str, Any] | None) -> dict[str, Any]:
    if worst_trace is None:
        return {
            "decision": "insufficient_data",
            "label": "Insufficient data",
            "reason": "No traces were scored, so no autonomy decision is available.",
            "average_score": average_score,
            "worst_trace": None,
        }

    worst_score = worst_trace["score"]
    worst_name = worst_trace["trace"]
    worst_verdict = worst_trace["verdict"]

    if average_score >= 85 and worst_score >= 85:
        decision = "increase_autonomy"
        label = "Increase autonomy"
        reason = (
            f"Average score is {average_score:.1f}/100 and the weakest trace, {worst_name}, "
            f"scored {worst_score}/100 ({worst_verdict})."
        )
    elif average_score >= 70 and worst_score >= 50:
        decision = "keep_supervised"
        label = "Keep supervised"
        reason = (
            f"Average score is {average_score:.1f}/100, but the weakest trace, {worst_name}, "
            f"scored {worst_score}/100 ({worst_verdict}). Keep human review until the weakest trace reaches 85."
        )
    elif worst_score < 50:
        decision = "stop_delegation_until_fixed"
        label = "Stop delegation until fixed"
        reason = (
            f"The weakest trace, {worst_name}, scored {worst_score}/100 ({worst_verdict}), "
            "below the 50/100 delegation floor."
        )
    else:
        decision = "stop_delegation_until_fixed"
        label = "Stop delegation until fixed"
        reason = (
            f"Average score is {average_score:.1f}/100, below the 70/100 supervised-use floor; "
            f"the weakest trace is {worst_name} at {worst_score}/100 ({worst_verdict})."
        )

    return {
        "decision": decision,
        "label": label,
        "reason": reason,
        "average_score": average_score,
        "worst_trace": worst_trace,
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
