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
            "trace-walkthrough.html",
            "good_obsidian_task.md",
            "bad_busywork_task.md",
            "hermes_session_sanitized.md",
        ):
            self.assertIn(f'href="{report_name}"', html)

    def test_trace_walkthrough_explains_input_checks_score_and_decision(self) -> None:
        from agent_scorecard.core import WEIGHTS

        html = (REPORTS_DIR / "trace-walkthrough.html").read_text(encoding="utf-8")

        self.assertIn("<!doctype html>", html.lower())
        self.assertIn("From a tiny trace to a trust decision.", html)
        self.assertIn("1. Tiny Sanitized Trace", html)
        self.assertIn("2. Checks Applied", html)
        self.assertIn("3. Why The Decision Changes When Evidence Is Missing", html)
        self.assertIn("artifacts/agent-eval-market.md", html)
        self.assertIn("100/100", html)
        self.assertIn("Verdict: Invest more", html)
        self.assertIn("45/100, Do not delegate", html)
        self.assertIn("Stop delegation until fixed", html)

        for check_name in WEIGHTS:
            self.assertIn(f"<code>{check_name}</code>", html)

        for report_name in (
            "portfolio-viewer.html",
            "good_obsidian_task.md",
            "bad_busywork_task.md",
            "index.json",
        ):
            self.assertIn(f'href="{report_name}"', html)

        lower_html = html.lower()
        self.assertNotIn("<script", lower_html)
        self.assertNotIn("javascript:", lower_html)
        self.assertNotIn("@import", lower_html)
        self.assertNotIn("https://", lower_html)
        self.assertNotIn("http://", lower_html)
        local_roots = ("Use" + "rs", "ho" + "me", "private" + "/tmp", "t" + "mp", "var" + "/folders")
        self.assertNotRegex(html, r"/(?:" + "|".join(local_roots) + r")/")
        self.assertNotRegex(html, r"[A-Za-z]:\\" + "Use" + "rs" + r"\\")
        secret_terms = (
            "api" + r"[_-]?" + "key",
            "access" + r"[_-]?" + "tok" + "en",
            "refresh" + r"[_-]?" + "tok" + "en",
        )
        self.assertNotRegex(html, r"(?i)\b(?:" + "|".join(secret_terms) + r")\b")

    def test_trace_walkthrough_is_linked_from_public_entry_points(self) -> None:
        root_readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        reports_readme = (REPORTS_DIR / "README.md").read_text(encoding="utf-8")
        portfolio_html = (REPORTS_DIR / "portfolio-viewer.html").read_text(encoding="utf-8")

        self.assertIn("examples/reports/trace-walkthrough.html", root_readme)
        self.assertIn("trace-walkthrough.html", reports_readme)
        self.assertIn('href="trace-walkthrough.html"', portfolio_html)

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
