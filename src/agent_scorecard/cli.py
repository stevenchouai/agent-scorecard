from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import ScoreReport, score_events
from .hermes_import import (
    HermesImportError,
    PrivacyAuditReport,
    audit_privacy_jsonl,
    events_to_jsonl,
    import_hermes_session,
    write_jsonl,
)
from .report import to_batch_summary_badge_svg, to_batch_summary_json, to_batch_summary_markdown, to_markdown


def load_jsonl(path: Path) -> list[dict]:
    events: list[dict] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSON on line {line_no}: {exc}") from exc
    return events


def score_trace(path: Path, output_format: str) -> str:
    report = score_trace_report(path)
    if output_format == "json":
        payload = {
            "score": report.score,
            "verdict": report.verdict,
            "checks": {
                name: {
                    "passed": check.passed,
                    "points": check.points,
                    "max_points": check.max_points,
                    "reason": check.reason,
                }
                for name, check in report.checks.items()
            },
            "failure_modes": report.failure_modes,
            "recommendation": report.recommendation,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    return to_markdown(report) + "\n"


def score_trace_report(path: Path) -> ScoreReport:
    return score_events(load_jsonl(path))


def write_report(trace_path: Path, output_dir: Path, output_format: str) -> Path:
    suffix = ".json" if output_format == "json" else ".md"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{trace_path.stem}{suffix}"
    output_path.write_text(score_trace(trace_path, output_format), encoding="utf-8")
    return output_path


def score_batch_reports(trace_paths: list[Path]) -> list[tuple[str, ScoreReport]]:
    results = [(trace_path.name, score_trace_report(trace_path)) for trace_path in trace_paths]
    return results


def write_batch_summary_results(results: list[tuple[str, ScoreReport]], output_path: Path, output_format: str) -> Path:
    rendered = _render_batch_summary_results(results, output_format)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    return output_path


def write_batch_summary(trace_paths: list[Path], output_path: Path, output_format: str) -> Path:
    return write_batch_summary_results(score_batch_reports(trace_paths), output_path, output_format)


def _render_batch_summary_results(results: list[tuple[str, ScoreReport]], output_format: str) -> str:
    if output_format == "json":
        return to_batch_summary_json(results)
    if output_format == "badge":
        return to_batch_summary_badge_svg(results)
    return to_batch_summary_markdown(results)


def _summary_suffix(output_format: str) -> str:
    if output_format == "json":
        return ".json"
    if output_format == "badge":
        return ".svg"
    return ".md"


def evaluate_summary_gates(
    results: list[tuple[str, ScoreReport]],
    fail_under_average: float | None,
    fail_under_min: float | None,
) -> list[str]:
    failures: list[str] = []
    if not results:
        return failures

    if fail_under_average is not None:
        average = round(sum(report.score for _, report in results) / len(results), 1)
        if average < fail_under_average:
            failures.append(
                f"--fail-under-average {_format_threshold(fail_under_average)} missed: "
                f"average score {average:.1f}/100"
            )

    if fail_under_min is not None:
        lowest_name, lowest_report = min(results, key=lambda item: (item[1].score, item[0]))
        if lowest_report.score < fail_under_min:
            failures.append(
                f"--fail-under-min {_format_threshold(fail_under_min)} missed: "
                f"lowest trace {lowest_name} scored {lowest_report.score}/100"
            )

    return failures


def _score_threshold(value: str) -> float:
    try:
        threshold = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number between 0 and 100") from exc
    if not 0 <= threshold <= 100:
        raise argparse.ArgumentTypeError("must be between 0 and 100")
    return threshold


def _format_threshold(value: float) -> str:
    return f"{value:g}"


def audit_privacy_trace(path: Path, output_format: str) -> tuple[str, bool]:
    try:
        report = audit_privacy_jsonl(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SystemExit(f"Could not read trace {path}: {exc}") from exc

    if output_format == "json":
        return json.dumps(_privacy_audit_payload(report), ensure_ascii=False, indent=2) + "\n", report.passed

    if report.passed:
        return (
            "Privacy audit passed: no obvious secrets, Feishu IDs, or local private paths found.\n",
            True,
        )

    lines = [f"Privacy audit failed: {len(report.findings)} finding(s)."]
    for finding in report.findings[:10]:
        lines.append(f"- {finding.location}: {finding.rule} ({finding.sample})")
    if len(report.findings) > 10:
        lines.append(f"- ... {len(report.findings) - 10} more finding(s)")
    return "\n".join(lines) + "\n", False


def _privacy_audit_payload(report: PrivacyAuditReport) -> dict:
    return {
        "passed": report.passed,
        "findings": [
            {
                "rule": finding.rule,
                "location": finding.location,
                "line": finding.line,
                "sample": finding.sample,
            }
            for finding in report.findings
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score agent workflow traces.")
    parser.add_argument("trace", type=Path, nargs="?", help="Path to one JSONL trace")
    parser.add_argument("--format", choices=["markdown", "json", "badge"], default="markdown")
    parser.add_argument(
        "--output",
        type=Path,
        help="Write the scored report, imported trace, batch summary, or privacy audit result to this file",
    )
    parser.add_argument("--batch-dir", type=Path, help="Score every *.jsonl trace in this directory")
    parser.add_argument("--reports-dir", type=Path, default=Path("examples/reports"), help="Directory for --batch-dir reports")
    parser.add_argument(
        "--summary",
        action="store_true",
        help="With --batch-dir, write a portfolio summary to --output or reports-dir/index.md/json",
    )
    parser.add_argument(
        "--fail-under-average",
        type=_score_threshold,
        metavar="N",
        help="With --batch-dir --summary, exit non-zero if the average score is below N",
    )
    parser.add_argument(
        "--fail-under-min",
        type=_score_threshold,
        metavar="N",
        help="With --batch-dir --summary, exit non-zero if any trace score is below N",
    )
    parser.add_argument("--from-hermes-session", type=Path, help="Convert one Hermes session JSON file to scorecard JSONL")
    parser.add_argument("--audit-privacy", type=Path, metavar="TRACE", help="Audit one JSONL trace for obvious sensitive values")
    args = parser.parse_args(argv)

    gate_requested = args.fail_under_average is not None or args.fail_under_min is not None
    if gate_requested and not (args.batch_dir and args.summary):
        parser.error("--fail-under-average and --fail-under-min require --batch-dir --summary")
    if args.format == "badge" and not (args.batch_dir and args.summary):
        parser.error("--format badge requires --batch-dir --summary")

    if args.audit_privacy:
        if args.trace or args.batch_dir or args.summary or args.from_hermes_session:
            parser.error("--audit-privacy cannot be combined with trace, --batch-dir, --summary, or --from-hermes-session")
        rendered, passed = audit_privacy_trace(args.audit_privacy, args.format)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
            print(args.output)
        else:
            print(rendered, end="")
        return 0 if passed else 1

    if args.from_hermes_session:
        if args.trace or args.batch_dir:
            parser.error("--from-hermes-session cannot be combined with trace or --batch-dir")
        try:
            events = import_hermes_session(args.from_hermes_session)
        except HermesImportError as exc:
            raise SystemExit(str(exc)) from exc
        if args.output:
            write_jsonl(events, args.output)
            print(args.output)
        else:
            print(events_to_jsonl(events), end="")
        return 0

    if args.summary and not args.batch_dir:
        parser.error("--summary requires --batch-dir")

    if args.batch_dir:
        traces = sorted(args.batch_dir.glob("*.jsonl"))
        if not traces:
            raise SystemExit(f"No *.jsonl traces found in {args.batch_dir}")
        if args.summary:
            suffix = _summary_suffix(args.format)
            summary_path = args.output or (args.reports_dir / f"index{suffix}")
            results = score_batch_reports(traces)
            print(write_batch_summary_results(results, summary_path, args.format))
            gate_failures = evaluate_summary_gates(results, args.fail_under_average, args.fail_under_min)
            if gate_failures:
                print(f"Portfolio gate failed: {'; '.join(gate_failures)}.", file=sys.stderr)
                return 1
            return 0
        written = [write_report(trace, args.reports_dir, args.format) for trace in traces]
        for path in written:
            print(path)
        return 0

    if not args.trace:
        parser.error("trace is required unless --batch-dir is used")

    rendered = score_trace(args.trace, args.format)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(args.output)
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
