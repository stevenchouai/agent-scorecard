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

FIXTURES_DIR = Path(__file__).parent / "fixtures"
HERMES_FIXTURE = FIXTURES_DIR / "hermes_session_sanitized.json"


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _synthetic_leaked_trace_jsonl() -> tuple[str, dict[str, str]]:
    posix_path = "/" + "Users/example/PrivateVault/private-note.md"
    windows_path = "C:" + "\\Users\\example\\Vault\\private-note.md"
    secret_key = "api" + "_key"
    secret_value = "SYNTHETIC_" + "SECRET_VALUE"
    bearer_value = "SYNTHETIC_" + "BEARER_VALUE_12345"
    feishu_id = "ou_" + "syntheticidentifier123"
    text = (
        f"{secret_key}={secret_value}; Authorization: {'Bearer'} {bearer_value}; "
        f"open_id={feishu_id}; wrote {posix_path}; copied {windows_path}"
    )
    return json.dumps({"type": "tool_result", "tool": "terminal", "text": text}) + "\n", {
        "posix_path": posix_path,
        "windows_path": windows_path,
        "secret_value": secret_value,
        "bearer_value": bearer_value,
        "feishu_id": feishu_id,
    }


class ScorecardTests(unittest.TestCase):
    def test_good_trace_scores_invest_more(self) -> None:
        from agent_scorecard.core import score_events

        events = [
            {"type": "user", "text": "Research this and write a short Obsidian note."},
            {"type": "assistant", "text": "I will check sources, write the note, and verify it."},
            {"type": "tool_call", "tool": "browser_navigate"},
            {"type": "tool_call", "tool": "write_file", "path": "/vault/wiki/outputs/agent-eval.md"},
            {"type": "tool_call", "tool": "read_file", "path": "/vault/wiki/outputs/agent-eval.md"},
            {
                "type": "assistant",
                "text": (
                    "Verdict: done. Wrote /vault/wiki/outputs/agent-eval.md and verified the file. "
                    "This is worth investing because it creates a durable artifact and avoids busywork."
                ),
            },
        ]

        report = score_events(events)

        self.assertGreaterEqual(report.score, 85)
        self.assertEqual(report.verdict, "Invest more")
        self.assertTrue(report.checks["durable_artifact"].passed)
        self.assertTrue(report.checks["verification_present"].passed)

    def test_bad_trace_penalizes_promises_without_action(self) -> None:
        from agent_scorecard.core import score_events

        events = [
            {"type": "user", "text": "Look at the market and tell me if this is worth doing."},
            {"type": "assistant", "text": "I will research the market and create a plan."},
            {"type": "assistant", "text": "This is obviously a good idea. We should do it."},
        ]

        report = score_events(events)

        self.assertLess(report.score, 50)
        self.assertEqual(report.verdict, "Do not delegate")
        self.assertFalse(report.checks["promised_action_executed"].passed)
        self.assertFalse(report.checks["uses_tools_for_retrieval"].passed)

    def test_markdown_report_contains_failures(self) -> None:
        from agent_scorecard.core import score_events
        from agent_scorecard.report import to_markdown

        report = score_events(
            [
                {"type": "assistant", "text": "I will fix the old repo quickly."},
                {"type": "tool_call", "tool": "terminal", "command": "echo cosmetic update"},
                {"type": "assistant", "text": "Done."},
            ]
        )

        markdown = to_markdown(report)

        self.assertIn("# Agent Scorecard Report", markdown)
        self.assertIn("promised_action_executed", markdown)
        self.assertIn("Top failure modes", markdown)

    def test_cli_writes_single_report(self) -> None:
        from agent_scorecard.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            trace = tmp_path / "trace.jsonl"
            output = tmp_path / "report.md"
            trace.write_text(
                "\n".join(
                    json.dumps(event)
                    for event in [
                        {"type": "assistant", "text": "I will write a durable artifact."},
                        {"type": "tool_call", "tool": "write_file", "path": "/tmp/artifact.md"},
                        {"type": "tool_call", "tool": "read_file", "path": "/tmp/artifact.md"},
                        {"type": "assistant", "text": "Done: wrote and verified /tmp/artifact.md for Steven."},
                    ]
                ),
                encoding="utf-8",
            )

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([str(trace), "--output", str(output)]), 0)

            self.assertTrue(output.exists())
            self.assertIn("# Agent Scorecard Report", output.read_text(encoding="utf-8"))

    def test_cli_batch_generates_reports(self) -> None:
        from agent_scorecard.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            traces = tmp_path / "traces"
            reports = tmp_path / "reports"
            traces.mkdir()
            for name in ("good", "bad"):
                (traces / f"{name}.jsonl").write_text(
                    json.dumps({"type": "assistant", "text": "Done: clear verdict for Steven."}),
                    encoding="utf-8",
                )

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--batch-dir", str(traces), "--reports-dir", str(reports)]), 0)

            self.assertTrue((reports / "good.md").exists())
            self.assertTrue((reports / "bad.md").exists())

    def test_cli_batch_summary_generates_portfolio_index(self) -> None:
        from agent_scorecard.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            traces = tmp_path / "traces"
            reports = tmp_path / "reports"
            traces.mkdir()
            (traces / "good.jsonl").write_text(
                "\n".join(
                    json.dumps(event)
                    for event in [
                        {"type": "user", "text": "Research this and write a note for Steven's investment decision."},
                        {"type": "assistant", "text": "I will check sources, write the note, and verify it."},
                        {"type": "tool_call", "tool": "browser_navigate"},
                        {"type": "tool_call", "tool": "write_file", "path": "artifact.md"},
                        {"type": "tool_call", "tool": "read_file", "path": "artifact.md"},
                        {
                            "type": "assistant",
                            "text": (
                                "Verdict: done. Wrote artifact.md and verified it. "
                                "This is worth investing in because it creates a durable artifact."
                            ),
                        },
                    ]
                ),
                encoding="utf-8",
            )
            (traces / "bad.jsonl").write_text(
                "\n".join(
                    json.dumps(event)
                    for event in [
                        {"type": "user", "text": "Look at the market and tell me if this is worth doing."},
                        {"type": "assistant", "text": "I will research the market and create a plan."},
                        {"type": "assistant", "text": "This is obviously a good idea. We should do it."},
                    ]
                ),
                encoding="utf-8",
            )

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(main(["--batch-dir", str(traces), "--reports-dir", str(reports), "--summary"]), 0)

            summary = reports / "index.md"
            markdown = summary.read_text(encoding="utf-8")

            self.assertEqual(stdout.getvalue().strip(), str(summary))
            self.assertIn("# Agent Scorecard Portfolio Summary", markdown)
            self.assertIn("**Traces scored:** 2", markdown)
            self.assertIn("| good.jsonl | 100/100 | Invest more |", markdown)
            self.assertIn("| bad.jsonl | 45/100 | Do not delegate |", markdown)
            self.assertLess(
                markdown.index("| good.jsonl | 100/100 | Invest more |"),
                markdown.index("| bad.jsonl | 45/100 | Do not delegate |"),
            )
            self.assertIn("promised_action_executed: Assistant promised action but no tool call followed.", markdown)

    def test_cli_batch_summary_json_generates_machine_readable_index(self) -> None:
        from agent_scorecard.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            traces = tmp_path / "traces"
            output = tmp_path / "index.json"
            traces.mkdir()
            (traces / "good.jsonl").write_text(
                "\n".join(
                    json.dumps(event)
                    for event in [
                        {"type": "user", "text": "Research this and write a note for Steven's investment decision."},
                        {"type": "assistant", "text": "I will check sources, write the note, and verify it."},
                        {"type": "tool_call", "tool": "browser_navigate"},
                        {"type": "tool_call", "tool": "write_file", "path": "artifact.md"},
                        {"type": "tool_call", "tool": "read_file", "path": "artifact.md"},
                        {
                            "type": "assistant",
                            "text": (
                                "Verdict: done. Wrote artifact.md and verified it. "
                                "This is worth investing in because it creates a durable artifact."
                            ),
                        },
                    ]
                ),
                encoding="utf-8",
            )
            (traces / "bad.jsonl").write_text(
                "\n".join(
                    json.dumps(event)
                    for event in [
                        {"type": "user", "text": "Look at the market and tell me if this is worth doing."},
                        {"type": "assistant", "text": "I will research the market and create a plan."},
                        {"type": "assistant", "text": "This is obviously a good idea. We should do it."},
                    ]
                ),
                encoding="utf-8",
            )

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(
                    main(["--batch-dir", str(traces), "--summary", "--format", "json", "--output", str(output)]),
                    0,
                )

            payload = json.loads(output.read_text(encoding="utf-8"))

            self.assertEqual(stdout.getvalue().strip(), str(output))
            self.assertEqual(
                set(payload),
                {
                    "traces_scored",
                    "average_score",
                    "top_candidate",
                    "needs_attention",
                    "verdict_mix",
                    "ranked_traces",
                },
            )
            self.assertEqual(payload["traces_scored"], 2)
            self.assertEqual(payload["average_score"], 72.5)
            self.assertEqual(payload["top_candidate"]["trace"], "good.jsonl")
            self.assertEqual(payload["top_candidate"]["score"], 100)
            self.assertEqual(payload["top_candidate"]["verdict"], "Invest more")
            self.assertEqual(payload["needs_attention"]["trace"], "bad.jsonl")
            self.assertEqual(
                payload["verdict_mix"],
                {
                    "Invest more": 1,
                    "Use with supervision": 0,
                    "Narrow delegation only": 0,
                    "Do not delegate": 1,
                },
            )
            self.assertEqual([entry["trace"] for entry in payload["ranked_traces"]], ["good.jsonl", "bad.jsonl"])
            for entry in payload["ranked_traces"]:
                self.assertEqual(set(entry), {"trace", "score", "verdict", "top_signal"})
            self.assertIn(
                "promised_action_executed: Assistant promised action but no tool call followed.",
                payload["ranked_traces"][1]["top_signal"],
            )

    def test_cli_summary_requires_batch_dir(self) -> None:
        from agent_scorecard.cli import main

        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(["examples/traces/good_obsidian_task.jsonl", "--summary"])

    def test_cli_audit_privacy_passes_clean_trace(self) -> None:
        from agent_scorecard.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            trace = Path(tmp) / "clean.jsonl"
            trace.write_text(
                json.dumps(
                    {
                        "type": "assistant",
                        "text": "Done: wrote <LOCAL_PATH>/scorecard-note.md and verified it.",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(main(["--audit-privacy", str(trace)]), 0)

        self.assertIn("Privacy audit passed", stdout.getvalue())

    def test_cli_audit_privacy_fails_synthetic_leaked_trace(self) -> None:
        from agent_scorecard.cli import main

        leaked_jsonl, leaked_values = _synthetic_leaked_trace_jsonl()

        with tempfile.TemporaryDirectory() as tmp:
            trace = Path(tmp) / "leaked.jsonl"
            trace.write_text(leaked_jsonl, encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(main(["--audit-privacy", str(trace)]), 1)

        output = stdout.getvalue()
        self.assertIn("Privacy audit failed", output)
        self.assertIn("local_path", output)
        self.assertIn("secret", output)
        self.assertIn("feishu_id", output)
        for leaked_value in leaked_values.values():
            self.assertNotIn(leaked_value, output)

    def test_cli_audit_privacy_json_output_is_structured(self) -> None:
        from agent_scorecard.cli import main

        leaked_jsonl, leaked_values = _synthetic_leaked_trace_jsonl()

        with tempfile.TemporaryDirectory() as tmp:
            trace = Path(tmp) / "leaked.jsonl"
            trace.write_text(leaked_jsonl, encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(main(["--audit-privacy", str(trace), "--format", "json"]), 1)

        payload = json.loads(stdout.getvalue())
        self.assertFalse(payload["passed"])
        self.assertIn("findings", payload)
        self.assertIn("local_path", {finding["rule"] for finding in payload["findings"]})
        self.assertTrue(all("location" in finding for finding in payload["findings"]))
        rendered = json.dumps(payload)
        for leaked_value in leaked_values.values():
            self.assertNotIn(leaked_value, rendered)


class HermesImportTests(unittest.TestCase):
    def test_fixture_contains_no_private_values(self) -> None:
        raw = HERMES_FIXTURE.read_text(encoding="utf-8")

        self.assertNotRegex(raw, r"/(?:Users|home|private/tmp|tmp|var/folders)/")
        self.assertNotRegex(raw, r"[A-Za-z]:\\Users\\")
        self.assertNotRegex(raw, r"\b(?:ou|on|oc|om|cli|msg|chat|tenant)_[A-Za-z0-9]{8,}\b")
        self.assertNotRegex(raw, r"(?i)\bBearer\s+")
        self.assertNotRegex(raw, r"(?i)\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token)\b")

    def test_hermes_import_converts_messages_tools_results_and_artifacts(self) -> None:
        from agent_scorecard.core import score_events
        from agent_scorecard.hermes_import import import_hermes_session

        events = import_hermes_session(HERMES_FIXTURE)

        self.assertEqual(
            [event["type"] for event in events],
            [
                "user",
                "assistant",
                "tool_call",
                "tool_call",
                "tool_result",
                "tool_call",
                "artifact",
                "assistant",
            ],
        )
        self.assertTrue(events[0]["text"].startswith("Research scorecard inputs"))
        self.assertEqual(events[2]["tool"], "read_file")
        self.assertIs(events[4]["ok"], True)
        self.assertEqual(events[6]["path"], "<LOCAL_PATH>/scorecard-note.md")
        self.assertGreaterEqual(score_events(events).score, 85)

    def test_hermes_import_handles_content_block_tools_and_failed_results(self) -> None:
        from agent_scorecard.hermes_import import normalize_hermes_session

        payload = {
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "I will inspect the repo."},
                        {
                            "type": "tool_use",
                            "name": "read_file",
                            "input": {"path": "README.md"},
                        },
                    ],
                },
                {
                    "type": "tool_result",
                    "tool": "read_file",
                    "status": "failed",
                    "content": [{"type": "text", "text": "file missing"}],
                },
            ]
        }

        events = normalize_hermes_session(payload)

        self.assertEqual([event["type"] for event in events], ["assistant", "tool_call", "tool_result"])
        self.assertEqual(events[0]["text"], "I will inspect the repo.")
        self.assertEqual(events[1], {"type": "tool_call", "tool": "read_file", "path": "README.md"})
        self.assertEqual(events[2]["tool"], "read_file")
        self.assertIs(events[2]["ok"], False)
        self.assertEqual(events[2]["text"], "file missing")

    def test_hermes_import_redacts_secrets_feishu_ids_and_private_paths(self) -> None:
        from agent_scorecard.hermes_import import import_hermes_session

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            posix_path = "/" + "Users/example/PrivateVault/secret-note.md"
            tmp_private_path = "/" + "private/tmp/hermes/private-output.md"
            windows_path = "C:" + "\\Users\\example\\Vault\\private-note.md"
            secret_value = "SYNTHETIC_" + "SECRET_VALUE"
            token_value = "SYNTHETIC_" + "TOKEN_VALUE"
            bearer_value = "SYNTHETIC_" + "BEARER_VALUE_12345"
            feishu_id = "ou_" + "syntheticidentifier123"
            session_path = tmp_path / "session.json"
            _write_json(
                session_path,
                {
                    "events": [
                        {
                            "role": "user",
                            "content": f"Use api_key={secret_value} and token '{token_value}' for this synthetic request.",
                        },
                        {
                            "role": "assistant",
                            "content": f"I will write {posix_path}, {tmp_private_path}, and {windows_path}.",
                        },
                        {
                            "type": "tool_call",
                            "tool": "terminal",
                            "command": (
                                f"agent --token {token_value} --api-key={secret_value} "
                                f"&& cat '{posix_path}'"
                            ),
                        },
                        {
                            "type": "tool_result",
                            "tool": "terminal",
                            "content": (
                                f"Authorization: Bearer {bearer_value}; open_id={feishu_id}; "
                                f"path {tmp_private_path}"
                            ),
                        },
                    ]
                },
            )

            rendered = json.dumps(import_hermes_session(session_path), ensure_ascii=False)

        self.assertNotIn(secret_value, rendered)
        self.assertNotIn(token_value, rendered)
        self.assertNotIn(bearer_value, rendered)
        self.assertNotIn(feishu_id, rendered)
        self.assertNotRegex(rendered, r"/(?:Users|home|private/tmp|tmp|var/folders)/")
        self.assertNotRegex(rendered, r"[A-Za-z]:\\Users\\")
        self.assertIn("[REDACTED]", rendered)
        self.assertIn("Bearer [REDACTED]", rendered)
        self.assertIn("<LOCAL_PATH>/secret-note.md", rendered)
        self.assertIn("<LOCAL_PATH>/private-output.md", rendered)
        self.assertIn("<LOCAL_PATH>/private-note.md", rendered)

    def test_hermes_import_redacts_json_style_secret_values(self) -> None:
        from agent_scorecard.hermes_import import redact_text

        key_value = "sk-" + "SYNTHETICVALUE1234567890"
        access_value = "SYNTHETIC_" + "ACCESS_VALUE"
        text = json.dumps({"api_key": key_value, "access_token": access_value})

        redacted = redact_text(text)

        self.assertNotIn(key_value, redacted)
        self.assertNotIn(access_value, redacted)
        self.assertIn('"api_key": "[REDACTED]"', redacted)
        self.assertIn('"access_token": "[REDACTED]"', redacted)

    def test_privacy_audit_passes_sanitized_jsonl(self) -> None:
        from agent_scorecard.hermes_import import audit_privacy_jsonl

        trace = (REPO_ROOT / "examples/traces/hermes_session_sanitized.jsonl").read_text(encoding="utf-8")
        report = audit_privacy_jsonl(trace)

        self.assertTrue(report.passed)
        self.assertEqual(report.findings, ())

    def test_privacy_audit_finds_synthetic_leaks(self) -> None:
        from agent_scorecard.hermes_import import audit_privacy_jsonl

        leaked_jsonl, leaked_values = _synthetic_leaked_trace_jsonl()
        report = audit_privacy_jsonl(leaked_jsonl)

        self.assertFalse(report.passed)
        self.assertIn("local_path", {finding.rule for finding in report.findings})
        self.assertIn("secret", {finding.rule for finding in report.findings})
        self.assertIn("feishu_id", {finding.rule for finding in report.findings})
        samples = " ".join(finding.sample for finding in report.findings)
        for leaked_value in leaked_values.values():
            self.assertNotIn(leaked_value, samples)
        self.assertIn("[REDACTED]", samples)
        self.assertIn("<LOCAL_PATH>", samples)

    def test_hermes_import_handles_minimal_and_malformed_sessions(self) -> None:
        from agent_scorecard.hermes_import import HermesImportError, import_hermes_session

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            minimal = tmp_path / "minimal.json"
            minimal.write_text('{"session":{"id":"empty"}}', encoding="utf-8")
            self.assertEqual(import_hermes_session(minimal), [])

            malformed = tmp_path / "malformed.json"
            malformed.write_text('{"session":', encoding="utf-8")
            with self.assertRaises(HermesImportError):
                import_hermes_session(malformed)

    def test_cli_converts_hermes_session_to_jsonl_file(self) -> None:
        from agent_scorecard.cli import load_jsonl, main
        from agent_scorecard.core import score_events

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "trace.jsonl"

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(main(["--from-hermes-session", str(HERMES_FIXTURE), "--output", str(output)]), 0)
            events = load_jsonl(output)

            self.assertEqual(stdout.getvalue().strip(), str(output))
            self.assertTrue(output.exists())
            self.assertEqual(len(events), 8)
            self.assertTrue(all(json.loads(line)["type"] for line in output.read_text(encoding="utf-8").splitlines()))
            self.assertGreaterEqual(score_events(events).score, 85)

    def test_cli_converts_hermes_session_to_stdout_jsonl(self) -> None:
        from agent_scorecard.cli import main

        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(main(["--from-hermes-session", str(HERMES_FIXTURE)]), 0)

        lines = stdout.getvalue().splitlines()
        events = [json.loads(line) for line in lines]
        self.assertEqual(len(events), 8)
        self.assertEqual(events[0]["type"], "user")
        self.assertEqual(events[-1]["type"], "assistant")


if __name__ == "__main__":
    unittest.main()
