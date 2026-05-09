from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import ScoreReport, score_events
from .hermes_import import HermesImportError, events_to_jsonl, import_hermes_session, write_jsonl
from .report import to_batch_summary_markdown, to_markdown


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


def write_batch_summary(trace_paths: list[Path], output_path: Path) -> Path:
    results = [(trace_path.name, score_trace_report(trace_path)) for trace_path in trace_paths]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(to_batch_summary_markdown(results), encoding="utf-8")
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score agent workflow traces.")
    parser.add_argument("trace", type=Path, nargs="?", help="Path to one JSONL trace")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--output", type=Path, help="Write the scored report, imported trace, or batch summary to this file")
    parser.add_argument("--batch-dir", type=Path, help="Score every *.jsonl trace in this directory")
    parser.add_argument("--reports-dir", type=Path, default=Path("examples/reports"), help="Directory for --batch-dir reports")
    parser.add_argument(
        "--summary",
        action="store_true",
        help="With --batch-dir, write a Markdown portfolio summary to --output or reports-dir/index.md",
    )
    parser.add_argument("--from-hermes-session", type=Path, help="Convert one Hermes session JSON file to scorecard JSONL")
    args = parser.parse_args(argv)

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
        if args.summary and args.format != "markdown":
            parser.error("--summary only supports markdown output")
        traces = sorted(args.batch_dir.glob("*.jsonl"))
        if not traces:
            raise SystemExit(f"No *.jsonl traces found in {args.batch_dir}")
        if args.summary:
            summary_path = args.output or (args.reports_dir / "index.md")
            print(write_batch_summary(traces, summary_path))
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
