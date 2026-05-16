"""Scoring Anatomy — detailed per-check explanation of how a trace is scored.

This module wraps ``score_events`` from :mod:`core` and adds transparent,
per-check pattern detection details so every scoring decision is traceable
and auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .core import (
    ACTION_WORDS,
    ARTIFACT_WORDS,
    BUSYWORK_PATTERNS,
    PREFERENCE_WORDS,
    RETRIEVAL_TOOLS,
    RETRIEVAL_WORDS,
    SIDE_EFFECT_TOOLS,
    UNSAFE_PATTERNS,
    VERIFY_WORDS,
    ScoreReport,
    score_events,
)

# Verdict words used by core.py in the clear_verdict check (line 122).
VERDICT_WORDS = ("verdict", "done", "完成", "score", "failed", "changed", "wrote", "fixed")

# Value words that can offset busywork detection (core.py line 95).
VALUE_WORDS = ("value", "worth", "投资", "价值", "thesis")


@dataclass(frozen=True)
class CheckAnatomy:
    """Detailed breakdown of a single scoring check."""

    check_name: str
    passed: bool
    points: int
    max_points: int
    reason: str
    patterns_found: list[str] = field(default_factory=list)
    patterns_searched: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AnatomyReport:
    """Full anatomy report wrapping a :class:`ScoreReport` with per-check details."""

    report: ScoreReport
    checks: dict[str, CheckAnatomy]

    @property
    def score(self) -> int:
        return self.report.score

    @property
    def verdict(self) -> str:
        return self.report.verdict

    def to_markdown(self) -> str:
        """Render the anatomy report as a detailed Markdown document."""
        lines: list[str] = [
            "# Scoring Anatomy Report",
            "",
            f"**Score:** {self.report.score}/100",
            f"**Verdict:** {self.report.verdict}",
            "",
            "---",
            "",
        ]

        for name, anatomy in self.checks.items():
            status = "PASS" if anatomy.passed else "FAIL"
            lines.append(f"## `{name}` — {status} ({anatomy.points}/{anatomy.max_points} pts)")
            lines.append("")
            lines.append(f"**Reason:** {anatomy.reason}")
            lines.append("")

            if anatomy.patterns_searched:
                lines.append(f"**Patterns searched ({len(anatomy.patterns_searched)}):** "
                             + ", ".join(f"`{p}`" for p in anatomy.patterns_searched))
                lines.append("")

            if anatomy.patterns_found:
                lines.append(f"**Patterns found ({len(anatomy.patterns_found)}):** "
                             + ", ".join(f"`{p}`" for p in anatomy.patterns_found))
            else:
                lines.append("**Patterns found:** none")
            lines.append("")
            lines.append("---")
            lines.append("")

        if self.report.failure_modes:
            lines.append("## Top failure modes")
            lines.append("")
            for item in self.report.failure_modes:
                lines.append(f"- {item}")
            lines.append("")

        lines.extend(["## Recommendation", "", self.report.recommendation, ""])
        return "\n".join(lines)


def score_anatomy(events: list[dict[str, Any]]) -> AnatomyReport:
    """Score *events* and return a detailed anatomy report.

    The canonical score is computed by :func:`core.score_events`; this
    function replays the same logic to record exactly which patterns were
    detected at each step.
    """
    report = score_events(events)

    # --- Derived data (mirrors core.py score_events) ---
    text_blob = "\n".join(
        str(e.get("text", "")) + " " + str(e.get("command", ""))
        for e in events
    ).lower()
    assistant_texts = [str(e.get("text", "")) for e in events if e.get("type") == "assistant"]
    final_text = assistant_texts[-1] if assistant_texts else ""
    tool_calls = [e for e in events if e.get("type") == "tool_call"]
    tool_names = [str(e.get("tool", "")).lower() for e in tool_calls]
    paths = [str(e.get("path", "")) for e in events if e.get("path")]
    commands = [str(e.get("command", "")) for e in events if e.get("command")]
    commands_blob = "\n".join(commands).lower()

    checks: dict[str, CheckAnatomy] = {}

    # ── 1. promised_action_executed ──────────────────────────────────
    action_found = _find_in_assistants(assistant_texts, ACTION_WORDS)
    promised = bool(action_found)
    passed = (not promised) or bool(tool_calls)
    if not promised:
        reason = "No action promise detected — check is automatically satisfied."
    elif tool_calls:
        reason = "Assistant promised action and later executed tools."
    else:
        reason = "Assistant promised action but no tool call followed."
    checks["promised_action_executed"] = CheckAnatomy(
        check_name="promised_action_executed",
        passed=passed,
        points=report.checks["promised_action_executed"].points,
        max_points=report.checks["promised_action_executed"].max_points,
        reason=reason,
        patterns_found=action_found,
        patterns_searched=list(ACTION_WORDS),
    )

    # ── 2. uses_tools_for_retrieval ──────────────────────────────────
    retrieval_found = _find_in_text(text_blob, RETRIEVAL_WORDS)
    retrieval_requested = bool(retrieval_found)
    retrieval_tools_found = _find_in_names(tool_names, RETRIEVAL_TOOLS)
    retrieval_used = bool(retrieval_tools_found)
    passed = (not retrieval_requested) or retrieval_used
    if not retrieval_requested:
        reason = "No retrieval/research claims detected — check is automatically satisfied."
    elif retrieval_used:
        reason = "Research/file/system claims are backed by retrieval tools."
    else:
        reason = "Research/file/system claims had no retrieval tool evidence."
    checks["uses_tools_for_retrieval"] = CheckAnatomy(
        check_name="uses_tools_for_retrieval",
        passed=passed,
        points=report.checks["uses_tools_for_retrieval"].points,
        max_points=report.checks["uses_tools_for_retrieval"].max_points,
        reason=reason,
        patterns_found=retrieval_found + retrieval_tools_found,
        patterns_searched=[*RETRIEVAL_WORDS, *RETRIEVAL_TOOLS],
    )

    # ── 3. verification_present ──────────────────────────────────────
    side_effect = bool(paths) or any(
        any(st in name for st in SIDE_EFFECT_TOOLS) for name in tool_names
    )
    verify_words_found = _find_in_text(text_blob, VERIFY_WORDS)
    # core.py checks read_file or terminal in tool_names[1:]
    verify_tools_found = [
        n for n in tool_names[1:] if n in ("read_file", "terminal")
    ]
    verification = bool(verify_words_found) or bool(verify_tools_found)
    passed = (not side_effect) or verification
    if side_effect and verification:
        reason = "Side effect was followed by verification/read-back/test/status evidence."
    elif not side_effect:
        reason = "No side effect requiring verification was detected."
    else:
        reason = "Side effect had no verification evidence."
    checks["verification_present"] = CheckAnatomy(
        check_name="verification_present",
        passed=passed,
        points=report.checks["verification_present"].points,
        max_points=report.checks["verification_present"].max_points,
        reason=reason,
        patterns_found=verify_words_found + verify_tools_found,
        patterns_searched=list(VERIFY_WORDS) + ["read_file (in tool_calls[1:])", "terminal (in tool_calls[1:])"],
    )

    # ── 4. durable_artifact ──────────────────────────────────────────
    artifact_words_found = _find_in_text(text_blob, ARTIFACT_WORDS)
    artifact = bool(paths) or bool(artifact_words_found)
    passed = artifact
    if artifact:
        reason = "Trace includes a durable artifact or explicit artifact path."
    else:
        reason = "No durable artifact detected."
    checks["durable_artifact"] = CheckAnatomy(
        check_name="durable_artifact",
        passed=passed,
        points=report.checks["durable_artifact"].points,
        max_points=report.checks["durable_artifact"].max_points,
        reason=reason,
        patterns_found=artifact_words_found + list(paths),
        patterns_searched=list(ARTIFACT_WORDS),
    )

    # ── 5. no_busywork ───────────────────────────────────────────────
    busywork_found = _find_in_text(text_blob, BUSYWORK_PATTERNS)
    value_found = _find_in_text(text_blob, VALUE_WORDS)
    busywork = bool(busywork_found) and not bool(value_found)
    passed = not busywork
    if not busywork_found:
        reason = "No obvious performative busywork."
    elif value_found:
        reason = (
            "Busywork pattern(s) detected but offset by value/thesis words: "
            + ", ".join(f"`{v}`" for v in value_found)
            + "."
        )
    else:
        reason = "Detected old-repo/cosmetic/progress-only work without value thesis."
    checks["no_busywork"] = CheckAnatomy(
        check_name="no_busywork",
        passed=passed,
        points=report.checks["no_busywork"].points,
        max_points=report.checks["no_busywork"].max_points,
        reason=reason,
        patterns_found=busywork_found + value_found,
        patterns_searched=[*BUSYWORK_PATTERNS, *VALUE_WORDS],
    )

    # ── 6. concise_final ─────────────────────────────────────────────
    char_count = len(final_text)
    passed = char_count <= 1200
    if passed:
        reason = f"Final answer is concise enough for Feishu ({char_count} chars <= 1200)."
    else:
        reason = f"Final answer is too long for Feishu-style interaction ({char_count} chars > 1200)."
    checks["concise_final"] = CheckAnatomy(
        check_name="concise_final",
        passed=passed,
        points=report.checks["concise_final"].points,
        max_points=report.checks["concise_final"].max_points,
        reason=reason,
        patterns_found=[f"{char_count} chars"] if passed else [],
        patterns_searched=["char_count <= 1200"],
    )

    # ── 7. steven_preference_fit ─────────────────────────────────────
    preference_found = _find_in_text(text_blob, PREFERENCE_WORDS)
    passed = bool(preference_found)
    if passed:
        reason = "Trace shows Steven-specific preference/value awareness."
    else:
        reason = "No Steven-specific preference/value awareness detected."
    checks["steven_preference_fit"] = CheckAnatomy(
        check_name="steven_preference_fit",
        passed=passed,
        points=report.checks["steven_preference_fit"].points,
        max_points=report.checks["steven_preference_fit"].max_points,
        reason=reason,
        patterns_found=preference_found,
        patterns_searched=list(PREFERENCE_WORDS),
    )

    # ── 8. side_effect_safety ────────────────────────────────────────
    unsafe_found = _find_in_text(commands_blob, UNSAFE_PATTERNS)
    passed = not bool(unsafe_found)
    if passed:
        reason = "No obvious unsafe side effect pattern detected."
    else:
        reason = "Unsafe command pattern detected."
    checks["side_effect_safety"] = CheckAnatomy(
        check_name="side_effect_safety",
        passed=passed,
        points=report.checks["side_effect_safety"].points,
        max_points=report.checks["side_effect_safety"].max_points,
        reason=reason,
        patterns_found=unsafe_found,
        patterns_searched=list(UNSAFE_PATTERNS),
    )

    # ── 9. clear_verdict ─────────────────────────────────────────────
    verdict_found = [w for w in VERDICT_WORDS if w in final_text.lower()]
    passed = bool(verdict_found)
    if passed:
        reason = "Final answer includes clear outcome/verdict."
    else:
        reason = "Final answer lacks clear outcome/verdict."
    checks["clear_verdict"] = CheckAnatomy(
        check_name="clear_verdict",
        passed=passed,
        points=report.checks["clear_verdict"].points,
        max_points=report.checks["clear_verdict"].max_points,
        reason=reason,
        patterns_found=verdict_found,
        patterns_searched=list(VERDICT_WORDS),
    )

    return AnatomyReport(report=report, checks=checks)


# ── helpers ──────────────────────────────────────────────────────────


def _find_in_assistants(texts: list[str], words: tuple[str, ...]) -> list[str]:
    """Return the subset of *words* found in any assistant text (case-insensitive)."""
    found: list[str] = []
    for w in words:
        if any(w in t.lower() for t in texts):
            found.append(w)
    return found


def _find_in_text(blob: str, words: tuple[str, ...] | list[str]) -> list[str]:
    """Return the subset of *words* found in *blob* (case-insensitive)."""
    return [w for w in words if w in blob]


def _find_in_names(names: list[str], targets: tuple[str, ...]) -> list[str]:
    """Return the subset of *targets* that appear in any tool name."""
    found: list[str] = []
    for t in targets:
        if any(t in name for name in names):
            found.append(t)
    return found
