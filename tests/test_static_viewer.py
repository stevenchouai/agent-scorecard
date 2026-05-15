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

    def test_failure_replay_page_is_static_public_and_actionable(self) -> None:
        html_path = REPORTS_DIR / "failure-replay.html"
        self.assertTrue(html_path.exists())

        html = html_path.read_text(encoding="utf-8")
        root_readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        reports_readme = (REPORTS_DIR / "README.md").read_text(encoding="utf-8")
        self.assertIn("<!doctype html>", html.lower())
        self.assertIn("Agent Scorecard failure replay", html)
        self.assertIn("A bad trace changes the next autonomy decision.", html)

        for label in (
            "Good delegated run",
            "Bad busywork run",
            "good_obsidian_task.jsonl, 100/100, Invest more",
            "bad_busywork_task.jsonl, 45/100, Do not delegate",
            "artifacts/agent-eval-market.md",
            "promised_action_executed: Assistant promised action but no tool call followed.",
            "uses_tools_for_retrieval: Research/file/system claims had no retrieval tool evidence.",
            "durable_artifact: No durable artifact detected.",
            "Stop delegation until fixed",
            "Do not increase permissions for this task pattern.",
        ):
            self.assertIn(label, html)

        for dimension in (
            "Artifacts",
            "Verification",
            "Privacy",
            "Handoff quality",
            "Autonomy decision",
        ):
            self.assertIn(dimension, html)

        for report_name in (
            "trace-walkthrough.html",
            "delegation-policy.html",
            "portfolio-viewer.html",
            "index.json",
        ):
            self.assertIn(f'href="{report_name}"', html)

        self.assertIn("examples/reports/failure-replay.html", root_readme)
        self.assertIn("failure-replay.html", reports_readme)

        lower_html = html.lower()
        self.assertNotIn("<script", lower_html)
        self.assertNotIn("javascript:", lower_html)
        self.assertNotIn("@import", lower_html)
        self.assertNotIn("url(", lower_html)

        for forbidden in (
            "http://",
            "https://",
            "file://",
            "/Users/",
            "/private/",
            "/vault/",
            "Steven",
            "stevenchou",
            "api_key",
            "access_token",
            "refresh_token",
            "Authorization:",
            "<script src",
            "<link rel=\"stylesheet\"",
        ):
            self.assertNotIn(forbidden, html)

        self.assertNotRegex(html, r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")

    def test_trust_contract_page_is_static_public_and_linked(self) -> None:
        html_path = REPORTS_DIR / "trust-contract.html"
        self.assertTrue(html_path.exists())

        html = html_path.read_text(encoding="utf-8")
        root_readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        reports_readme = (REPORTS_DIR / "README.md").read_text(encoding="utf-8")

        self.assertIn("<!doctype html>", html.lower())
        self.assertIn("Agent Scorecard trust contract", html)
        self.assertIn("Steven's personal AI OS", html)
        self.assertIn("trace evidence earns a score", html)
        self.assertIn("public proof", html)
        self.assertIn("agent evaluation", html)
        self.assertIn("How to use this in a real agent run", html)

        for anchor in (
            'id="trace-evidence"',
            'id="score"',
            'id="permission-tiers"',
            'id="stop-conditions"',
            'id="real-agent-run"',
        ):
            self.assertIn(anchor, html)

        for tier in (
            "Observe only",
            "Supervised draft",
            "Bounded write",
            "Broader delegation",
        ):
            self.assertIn(tier, html)

        for phrase in (
            "Required evidence",
            "Stop condition",
            "0-49: do not delegate",
            "50-69: limited trust",
            "70-84: supervised autonomy",
            "85-100: invest more",
            "trace evidence -> deterministic checks -> score -> verdict -> next permission",
        ):
            self.assertIn(phrase, html)

        for report_name in (
            "trace-walkthrough.html",
            "portfolio-viewer.html",
            "delegation-policy.html",
            "failure-replay.html",
        ):
            self.assertIn(f'href="{report_name}"', html)

        self.assertIn("examples/reports/trust-contract.html", root_readme)
        self.assertIn("trust-contract.html", reports_readme)

        lower_html = html.lower()
        self.assertNotIn("<script", lower_html)
        self.assertNotIn("javascript:", lower_html)
        self.assertNotIn("@import", lower_html)
        self.assertNotIn("url(", lower_html)

        for forbidden in (
            "http://",
            "https://",
            "file://",
            "/Users/",
            "/private/",
            "/vault/",
            "stevenchou",
            "api_key",
            "access_token",
            "refresh_token",
            "Authorization:",
            "<script src",
            "<link rel=\"stylesheet\"",
        ):
            self.assertNotIn(forbidden, html)

        self.assertNotRegex(html, r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")

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

    def test_delegation_policy_page_is_static_public_and_actionable(self) -> None:
        html_path = REPORTS_DIR / "delegation-policy.html"
        markdown_path = REPORTS_DIR / "delegation-policy.md"
        html = html_path.read_text(encoding="utf-8")
        markdown = markdown_path.read_text(encoding="utf-8")
        combined = f"{html}\n{markdown}"

        self.assertTrue(html_path.exists())
        self.assertTrue(markdown_path.exists())
        self.assertIn("<!doctype html>", html.lower())

        for label in (
            "Delegation Policy Simulator",
            "Give more permissions",
            "Keep supervised",
            "Stop delegation until fixed",
            "bad_busywork_task.jsonl",
            "promised_action_executed: Assistant promised action but no tool call followed.",
        ):
            self.assertIn(label, combined)

        for forbidden in (
            "http://",
            "https://",
            "file://",
            "/Users/",
            "/private/",
            "stevenchou",
            "api_key",
            "access_token",
            "refresh_token",
            "Authorization:",
            "<script src",
            "<link rel=\"stylesheet\"",
        ):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
