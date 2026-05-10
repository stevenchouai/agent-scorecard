from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
REPORTS_DIR = REPO_ROOT / "examples" / "reports"


class StaticViewerTests(unittest.TestCase):
    def test_portfolio_viewer_matches_public_summary_payload(self) -> None:
        payload = json.loads((REPORTS_DIR / "index.json").read_text(encoding="utf-8"))
        html = (REPORTS_DIR / "portfolio-viewer.html").read_text(encoding="utf-8")
        decision = payload["autonomy_decision"]
        worst_trace = decision["worst_trace"]

        self.assertIn("<!doctype html>", html.lower())
        self.assertIn(f"{payload['average_score']}/100", html)
        self.assertIn(decision["label"], html)
        self.assertIn(decision["reason"], html)
        self.assertIn(worst_trace["trace"], html)
        self.assertIn(worst_trace["top_signal"], html)

        for entry in payload["ranked_traces"]:
            self.assertIn(entry["trace"], html)
            self.assertIn(f"{entry['score']}/100", html)
            self.assertIn(entry["verdict"], html)
            self.assertIn(entry["top_signal"], html)

        for report_name in (
            "index.md",
            "index.json",
            "good_obsidian_task.md",
            "bad_busywork_task.md",
            "hermes_session_sanitized.md",
        ):
            self.assertIn(f'href="{report_name}"', html)

    def test_portfolio_badge_matches_public_summary_payload(self) -> None:
        from agent_scorecard.report import to_portfolio_badge_svg

        payload = json.loads((REPORTS_DIR / "index.json").read_text(encoding="utf-8"))
        svg = (REPORTS_DIR / "portfolio-badge.svg").read_text(encoding="utf-8")
        decision = payload["autonomy_decision"]

        self.assertEqual(svg, to_portfolio_badge_svg(payload))
        self.assertIn(f"{payload['average_score']:.1f}/100", svg)
        self.assertIn(decision["label"], svg)

        lower_svg = svg.lower()
        self.assertNotIn("<script", lower_svg)
        self.assertNotIn("javascript:", lower_svg)
        self.assertNotIn("href=", lower_svg)
        self.assertNotIn("src=", lower_svg)
        self.assertNotIn("url(", lower_svg)
        self.assertNotIn("@import", lower_svg)


if __name__ == "__main__":
    unittest.main()
