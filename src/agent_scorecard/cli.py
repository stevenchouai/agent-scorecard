from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import score_events
from .report import to_markdown


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
    report = score_events(load_jsonl(path))
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


def write_report(trace_path: Path, output_dir: Path, output_format: str) -> Path:
    suffix = ".json" if output_format == "json" else ".md"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{trace_path.stem}{suffix}"
    output_path.write_text(score_trace(trace_path, output_format), encoding="utf-8")
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score agent workflow traces.")
    parser.add_argument("trace", type=Path, nargs="?", help="Path to one JSONL trace")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--output", type=Path, help="Write the scored report to this file instead of stdout")
    parser.add_argument("--batch-dir", type=Path, help="Score every *.jsonl trace in this directory")
    parser.add_argument("--reports-dir", type=Path, default=Path("examples/reports"), help="Directory for --batch-dir reports")
    args = parser.parse_args(argv)

    if args.batch_dir:
        traces = sorted(args.batch_dir.glob("*.jsonl"))
        if not traces:
            raise SystemExit(f"No *.jsonl traces found in {args.batch_dir}")
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
