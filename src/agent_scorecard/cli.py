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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score an agent workflow trace.")
    parser.add_argument("trace", type=Path, help="Path to JSONL trace")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args(argv)

    report = score_events(load_jsonl(args.trace))
    if args.format == "json":
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
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(to_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
