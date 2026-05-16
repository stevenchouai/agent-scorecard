"""Tests for the scoring anatomy module."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

GOOD_TRACE = Path(__file__).resolve().parents[1] / "examples" / "traces" / "good_obsidian_task.jsonl"
BAD_TRACE = Path(__file__).resolve().parents[1] / "examples" / "traces" / "bad_busywork_task.jsonl"


def _load_jsonl(path: Path) -> list[dict]:
    import json as _json
    return [_json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class AnatomyGoodTraceTests(unittest.TestCase):
    """Verify the anatomy report for the good trace (expected 100/100)."""

    @classmethod
    def setUpClass(cls) -> None:
        from agent_scorecard.anatomy import score_anatomy

        cls.anatomy = score_anatomy(_load_jsonl(GOOD_TRACE))

    def test_score_matches_core(self) -> None:
        from agent_scorecard.core import score_events

        core_report = score_events(_load_jsonl(GOOD_TRACE))
        self.assertEqual(self.anatomy.score, core_report.score)

    def test_score_is_100(self) -> None:
        self.assertEqual(self.anatomy.score, 100)

    def test_verdict_is_invest_more(self) -> None:
        self.assertEqual(self.anatomy.verdict, "Invest more")

    def test_all_nine_checks_present(self) -> None:
        expected = {
            "promised_action_executed",
            "uses_tools_for_retrieval",
            "verification_present",
            "durable_artifact",
            "no_busywork",
            "concise_final",
            "steven_preference_fit",
            "side_effect_safety",
            "clear_verdict",
        }
        self.assertEqual(set(self.anatomy.checks.keys()), expected)

    def test_all_checks_pass(self) -> None:
        for name, check in self.anatomy.checks.items():
            self.assertTrue(check.passed, f"Check {name!r} should pass but failed: {check.reason}")

    def test_promised_action_found_i_will(self) -> None:
        check = self.anatomy.checks["promised_action_executed"]
        self.assertIn("i will", check.patterns_found)
        self.assertTrue(check.passed)

    def test_retrieval_found_research_and_browser(self) -> None:
        check = self.anatomy.checks["uses_tools_for_retrieval"]
        found = check.patterns_found
        self.assertIn("research", found)
        self.assertIn("browser", found)
        self.assertTrue(check.passed)

    def test_verification_found_read_file(self) -> None:
        check = self.anatomy.checks["verification_present"]
        self.assertIn("read_file", check.patterns_found)
        self.assertTrue(check.passed)

    def test_durable_artifact_found_paths(self) -> None:
        check = self.anatomy.checks["durable_artifact"]
        self.assertTrue(any("/vault/" in p for p in check.patterns_found))
        self.assertTrue(check.passed)

    def test_no_busywork_clean(self) -> None:
        check = self.anatomy.checks["no_busywork"]
        self.assertTrue(check.passed)
        self.assertIn("No obvious", check.reason)

    def test_concise_final_char_count(self) -> None:
        check = self.anatomy.checks["concise_final"]
        self.assertTrue(check.passed)
        self.assertTrue(any("chars" in p for p in check.patterns_found))

    def test_preference_fit_found_steven(self) -> None:
        check = self.anatomy.checks["steven_preference_fit"]
        self.assertIn("steven", check.patterns_found)
        self.assertTrue(check.passed)

    def test_side_effect_safety_no_unsafe(self) -> None:
        check = self.anatomy.checks["side_effect_safety"]
        self.assertTrue(check.passed)
        self.assertEqual(check.patterns_found, [])

    def test_clear_verdict_found_verdict(self) -> None:
        check = self.anatomy.checks["clear_verdict"]
        self.assertIn("verdict", check.patterns_found)
        self.assertTrue(check.passed)


class AnatomyBadTraceTests(unittest.TestCase):
    """Verify the anatomy report for the bad trace (expected 45/100)."""

    @classmethod
    def setUpClass(cls) -> None:
        from agent_scorecard.anatomy import score_anatomy

        cls.anatomy = score_anatomy(_load_jsonl(BAD_TRACE))

    def test_score_matches_core(self) -> None:
        from agent_scorecard.core import score_events

        core_report = score_events(_load_jsonl(BAD_TRACE))
        self.assertEqual(self.anatomy.score, core_report.score)

    def test_score_is_45(self) -> None:
        self.assertEqual(self.anatomy.score, 45)

    def test_verdict_is_do_not_delegate(self) -> None:
        self.assertEqual(self.anatomy.verdict, "Do not delegate")

    def test_promised_action_fails_no_tools(self) -> None:
        check = self.anatomy.checks["promised_action_executed"]
        self.assertFalse(check.passed)
        self.assertIn("i will", check.patterns_found)
        self.assertIn("no tool call", check.reason.lower())

    def test_retrieval_fails_no_tools(self) -> None:
        check = self.anatomy.checks["uses_tools_for_retrieval"]
        self.assertFalse(check.passed)
        self.assertIn("market", check.patterns_found)

    def test_verification_passes_no_side_effects(self) -> None:
        check = self.anatomy.checks["verification_present"]
        self.assertTrue(check.passed)
        self.assertIn("No side effect", check.reason)

    def test_durable_artifact_fails(self) -> None:
        check = self.anatomy.checks["durable_artifact"]
        self.assertFalse(check.passed)
        self.assertEqual(check.patterns_found, [])

    def test_no_busywork_passes(self) -> None:
        check = self.anatomy.checks["no_busywork"]
        self.assertTrue(check.passed)

    def test_concise_final_passes(self) -> None:
        check = self.anatomy.checks["concise_final"]
        self.assertTrue(check.passed)

    def test_preference_fit_passes_via_user_text(self) -> None:
        check = self.anatomy.checks["steven_preference_fit"]
        self.assertTrue(check.passed)
        self.assertIn("worth", check.patterns_found)

    def test_side_effect_safety_passes(self) -> None:
        check = self.anatomy.checks["side_effect_safety"]
        self.assertTrue(check.passed)

    def test_clear_verdict_fails(self) -> None:
        check = self.anatomy.checks["clear_verdict"]
        self.assertFalse(check.passed)
        self.assertEqual(check.patterns_found, [])


class AnatomyMarkdownTests(unittest.TestCase):
    """Verify the Markdown output of the anatomy report."""

    @classmethod
    def setUpClass(cls) -> None:
        from agent_scorecard.anatomy import score_anatomy

        cls.good_md = score_anatomy(_load_jsonl(GOOD_TRACE)).to_markdown()
        cls.bad_md = score_anatomy(_load_jsonl(BAD_TRACE)).to_markdown()

    def test_good_markdown_has_title(self) -> None:
        self.assertIn("# Scoring Anatomy Report", self.good_md)

    def test_good_markdown_has_score(self) -> None:
        self.assertIn("**Score:** 100/100", self.good_md)

    def test_good_markdown_has_all_checks(self) -> None:
        for name in (
            "promised_action_executed",
            "uses_tools_for_retrieval",
            "verification_present",
            "durable_artifact",
            "no_busywork",
            "concise_final",
            "steven_preference_fit",
            "side_effect_safety",
            "clear_verdict",
        ):
            self.assertIn(f"`{name}`", self.good_md, f"Missing check {name} in markdown")

    def test_good_markdown_has_pass_indicators(self) -> None:
        self.assertIn("PASS", self.good_md)

    def test_bad_markdown_has_score(self) -> None:
        self.assertIn("**Score:** 45/100", self.bad_md)

    def test_bad_markdown_has_fail_indicators(self) -> None:
        self.assertIn("FAIL", self.bad_md)

    def test_bad_markdown_has_failure_modes(self) -> None:
        self.assertIn("Top failure modes", self.bad_md)

    def test_markdown_has_patterns_searched(self) -> None:
        self.assertIn("Patterns searched", self.good_md)

    def test_markdown_has_patterns_found(self) -> None:
        self.assertIn("Patterns found", self.good_md)

    def test_markdown_has_recommendation(self) -> None:
        self.assertIn("## Recommendation", self.good_md)

    def test_bad_markdown_shows_no_tool_call_reason(self) -> None:
        self.assertIn("no tool call", self.bad_md.lower())


class AnatomyCLITests(unittest.TestCase):
    """Verify the --anatomy CLI flag works end-to-end."""

    def test_cli_anatomy_flag_outputs_report(self) -> None:
        from agent_scorecard.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "anatomy.md"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    main([str(GOOD_TRACE), "--anatomy", "--output", str(output)]),
                    0,
                )
            content = output.read_text(encoding="utf-8")
            self.assertIn("# Scoring Anatomy Report", content)
            self.assertIn("**Score:** 100/100", content)

    def test_cli_anatomy_stdout(self) -> None:
        from agent_scorecard.cli import main

        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            main([str(BAD_TRACE), "--anatomy"])

        output = stdout.getvalue()
        self.assertIn("# Scoring Anatomy Report", output)
        self.assertIn("**Score:** 45/100", output)


class AnatomyScoreConsistencyTests(unittest.TestCase):
    """Ensure anatomy scores always match core.py scores for all traces."""

    def test_good_trace_consistency(self) -> None:
        from agent_scorecard.anatomy import score_anatomy
        from agent_scorecard.core import score_events

        events = _load_jsonl(GOOD_TRACE)
        self.assertEqual(score_anatomy(events).score, score_events(events).score)

    def test_bad_trace_consistency(self) -> None:
        from agent_scorecard.anatomy import score_anatomy
        from agent_scorecard.core import score_events

        events = _load_jsonl(BAD_TRACE)
        self.assertEqual(score_anatomy(events).score, score_events(events).score)

    def test_synthetic_trace_consistency(self) -> None:
        from agent_scorecard.anatomy import score_anatomy
        from agent_scorecard.core import score_events

        events = [
            {"type": "assistant", "text": "I will fix the old repo quickly."},
            {"type": "tool_call", "tool": "terminal", "command": "echo cosmetic update"},
            {"type": "assistant", "text": "Done."},
        ]
        self.assertEqual(score_anatomy(events).score, score_events(events).score)

    def test_all_check_points_match(self) -> None:
        from agent_scorecard.anatomy import score_anatomy
        from agent_scorecard.core import score_events

        for trace_path in (GOOD_TRACE, BAD_TRACE):
            events = _load_jsonl(trace_path)
            anatomy = score_anatomy(events)
            core = score_events(events)
            for name in core.checks:
                self.assertEqual(
                    anatomy.checks[name].points,
                    core.checks[name].points,
                    f"Points mismatch for {name} on {trace_path.name}",
                )
                self.assertEqual(
                    anatomy.checks[name].passed,
                    core.checks[name].passed,
                    f"Passed mismatch for {name} on {trace_path.name}",
                )


if __name__ == "__main__":
    unittest.main()
