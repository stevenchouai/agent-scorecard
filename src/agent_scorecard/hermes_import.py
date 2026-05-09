from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any


class HermesImportError(ValueError):
    """Raised when a Hermes session file cannot be parsed."""


TRANSCRIPT_KEYS = ("events", "messages", "items", "turns", "transcript", "conversation")
NESTED_SESSION_KEYS = ("session", "data")
TEXT_KEYS = ("text", "content", "message", "body", "output", "result", "summary")
ROLE_KEYS = ("role", "speaker", "author", "sender", "from")
TYPE_KEYS = ("type", "kind", "event", "event_type")
TOOL_CALL_KEYS = ("tool_calls", "tool_call", "toolUses", "tool_uses", "actions")
TOOL_RESULT_KEYS = ("tool_results", "tool_result", "observations", "observation")
ARTIFACT_KEYS = ("artifacts", "artifact")
PATH_KEYS = ("path", "file_path", "filepath", "artifact_path", "filename", "url", "uri")
COMMAND_KEYS = ("command", "cmd", "shell_command")
ARGUMENT_KEYS = ("arguments", "args", "input", "parameters", "params")

USER_ROLES = ("user", "human", "steven", "client")
ASSISTANT_ROLES = ("assistant", "agent", "hermes", "model")
TOOL_ROLES = ("tool", "function")

SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b([A-Z0-9_.-]*(?:api[_-]?key|token|secret|password|passwd|credential|cookie|access[_-]?token|refresh[_-]?token|app[_-]?secret|client[_-]?secret)[A-Z0-9_.-]*)\b([\"']?\s*[:=]\s*[\"']?)[^\"'\s,;)}\]]+"
)
CLI_SECRET_OPTION_RE = re.compile(
    r"(?i)(?<!\w)(--?(?:api[_-]?key|token|secret|password|credential|access[_-]?token|refresh[_-]?token|app[_-]?secret|client[_-]?secret)\b(?:=|\s+)[\"']?)[^\"'\s,;)}\]]+"
)
SECRET_WORD_VALUE_RE = re.compile(
    r"(?i)\b((?:api[_ -]?key|access[_ -]?token|refresh[_ -]?token|token|secret|password|credential)\b\s+[\"']?)[^\"'\s,;)}\]]+"
)
BEARER_RE = re.compile(r"(?i)\bBearer\s+[^\"'\s,;)}\]]+")
TOKEN_RE = re.compile(
    r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{16,}\b|"
    r"\bgithub_pat_[A-Za-z0-9_]{16,}\b|"
    r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b|"
    r"\bAKIA[0-9A-Z]{16}\b|"
    r"\bAIza[0-9A-Za-z_-]{20,}\b|"
    r"\bsk-[A-Za-z0-9_-]{16,}\b"
)
FEISHU_ID_RE = re.compile(r"\b(?:ou|on|oc|om|cli|msg|chat|tenant)_[A-Za-z0-9]{8,}\b")
POSIX_LOCAL_PATH_PREFIX = r"/(?:Users|home|private/var/folders|private/tmp|tmp|var/tmp|Volumes)/"
QUOTED_POSIX_LOCAL_PATH_RE = re.compile(rf"(?P<quote>[\"'`])(?P<path>{POSIX_LOCAL_PATH_PREFIX}[^\"'`]+)(?P=quote)")
POSIX_LOCAL_PATH_RE = re.compile(rf"{POSIX_LOCAL_PATH_PREFIX}[^\s\"'`<>]+")
QUOTED_WINDOWS_LOCAL_PATH_RE = re.compile(r"(?P<quote>[\"'`])(?P<path>[A-Za-z]:\\Users\\[^\"'`]+)(?P=quote)")
WINDOWS_LOCAL_PATH_RE = re.compile(r"[A-Za-z]:\\Users\\[^\s\"'`<>]+")


def import_hermes_session(path: Path) -> list[dict[str, Any]]:
    return normalize_hermes_session(load_hermes_session(path))


def load_hermes_session(path: Path) -> Any:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise HermesImportError(f"Could not read Hermes session {path}: {exc}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HermesImportError(f"Invalid Hermes session JSON in {path}: {exc}") from exc


def normalize_hermes_session(payload: Any) -> list[dict[str, Any]]:
    items = _find_transcript(payload)
    if not items:
        return []

    events: list[dict[str, Any]] = []
    for item in items:
        events.extend(_normalize_item(item))
    return [_sanitize_event(event) for event in events if _has_payload(event)]


def events_to_jsonl(events: list[dict[str, Any]]) -> str:
    return "\n".join(json.dumps(event, ensure_ascii=False, separators=(",", ":")) for event in events) + ("\n" if events else "")


def write_jsonl(events: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(events_to_jsonl(events), encoding="utf-8")


def _find_transcript(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, Mapping):
        return []

    for key in TRANSCRIPT_KEYS:
        value = payload.get(key)
        if isinstance(value, list):
            return value

    for key in NESTED_SESSION_KEYS:
        value = payload.get(key)
        found = _find_transcript(value)
        if found:
            return found

    if _looks_like_event(payload):
        return [payload]
    return []


def _normalize_item(item: Any) -> list[dict[str, Any]]:
    if isinstance(item, str):
        return [{"type": "assistant", "text": item}]
    if not isinstance(item, Mapping):
        return []

    nested = _find_nested_transcript(item)
    if nested is not None:
        events: list[dict[str, Any]] = []
        for child in nested:
            events.extend(_normalize_item(child))
        return events

    events = _direct_events(item)
    events.extend(_content_block_events(item))

    for key in TOOL_CALL_KEYS:
        if key in item:
            for value in _as_list(item[key]):
                event = _tool_call_event(value)
                if event:
                    events.append(event)

    for key in TOOL_RESULT_KEYS:
        if key in item:
            for value in _as_list(item[key]):
                event = _tool_result_event(value)
                if event:
                    events.append(event)

    for key in ARTIFACT_KEYS:
        if key in item:
            for value in _as_list(item[key]):
                event = _artifact_event(value)
                if event:
                    events.append(event)

    return events


def _find_nested_transcript(item: Mapping[str, Any]) -> list[Any] | None:
    for key in TRANSCRIPT_KEYS:
        value = item.get(key)
        if isinstance(value, list):
            return value
    return None


def _direct_events(item: Mapping[str, Any]) -> list[dict[str, Any]]:
    role = _first_string(item, ROLE_KEYS).lower()
    kind = _first_string(item, TYPE_KEYS).lower()

    if _is_tool_result(item, role, kind):
        event = _tool_result_event(item)
        return [event] if event else []
    if _is_tool_call(item, kind):
        event = _tool_call_event(item)
        return [event] if event else []
    if "artifact" in kind:
        event = _artifact_event(item)
        return [event] if event else []
    if _is_error(item, kind):
        return [_error_event(item)]
    if role in USER_ROLES or role in ASSISTANT_ROLES:
        text = _extract_text(item)
        if not text:
            return []
        return [{"type": "user" if role in USER_ROLES else "assistant", "text": text}]
    return []


def _content_block_events(item: Mapping[str, Any]) -> list[dict[str, Any]]:
    content = item.get("content")
    if not isinstance(content, list):
        return []

    events: list[dict[str, Any]] = []
    for block in content:
        if not isinstance(block, Mapping):
            continue
        role = _first_string(block, ROLE_KEYS).lower()
        kind = _first_string(block, TYPE_KEYS).lower()
        if _is_tool_result(block, role, kind):
            event = _tool_result_event(block)
        elif _is_tool_call(block, kind):
            event = _tool_call_event(block)
        elif "artifact" in kind:
            event = _artifact_event(block)
        else:
            event = None
        if event:
            events.append(event)
    return events


def _is_error(item: Mapping[str, Any], kind: str) -> bool:
    status = str(item.get("status", "")).lower()
    return "error" in kind or "exception" in kind or status in {"error", "failed", "failure"} or ("error" in item and item.get("error"))


def _is_tool_result(item: Mapping[str, Any], role: str, kind: str) -> bool:
    if role in TOOL_ROLES:
        return True
    if _tool_name(item) and any(key in item for key in ("result", "output")) and not any(key in item for key in ARGUMENT_KEYS + COMMAND_KEYS):
        return True
    return any(marker in kind for marker in ("tool_result", "tool-result", "tool_response", "observation", "function_result"))


def _is_tool_call(item: Mapping[str, Any], kind: str) -> bool:
    if any(marker in kind for marker in ("tool_call", "tool-call", "tool_use", "tool-use", "function_call", "action")):
        return True
    return bool(_tool_name(item) or _extract_command(item))


def _tool_call_event(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, Mapping):
        text = _stringify_text(item)
        return {"type": "tool_call", "tool": "tool", "text": text} if text else None

    tool = _tool_name(item) or ("terminal" if _extract_command(item) else "tool")
    event: dict[str, Any] = {"type": "tool_call", "tool": tool}
    path = _extract_path(item)
    command = _extract_command(item)
    text = _extract_text(item)

    if path:
        event["path"] = path
    if command:
        event["command"] = command
    if text and text not in {path, command}:
        event["text"] = text
    return event


def _tool_result_event(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, Mapping):
        text = _stringify_text(item)
        return {"type": "tool_result", "ok": True, "text": text} if text else None

    event: dict[str, Any] = {"type": "tool_result"}
    tool = _tool_name(item)
    text = _extract_text(item)
    path = _extract_path(item)

    if tool:
        event["tool"] = tool
    if "ok" in item:
        event["ok"] = bool(item["ok"])
    elif "success" in item:
        event["ok"] = bool(item["success"])
    elif str(item.get("status", "")).lower() in {"error", "failed", "failure"}:
        event["ok"] = False
    elif text or path:
        event["ok"] = True
    if path:
        event["path"] = path
    if text:
        event["text"] = text
    return event if len(event) > 1 else None


def _artifact_event(item: Any) -> dict[str, Any] | None:
    if isinstance(item, str):
        return {"type": "artifact", "path": item}
    if not isinstance(item, Mapping):
        return None

    event: dict[str, Any] = {"type": "artifact"}
    path = _extract_path(item)
    text = _extract_text(item)
    if path:
        event["path"] = path
    if text and text != path:
        event["text"] = text
    return event if len(event) > 1 else None


def _error_event(item: Mapping[str, Any]) -> dict[str, Any]:
    text = _stringify_text(item.get("error")) or _extract_text(item) or str(item.get("status", "error"))
    return {"type": "error", "text": text}


def _extract_text(item: Mapping[str, Any]) -> str:
    for key in TEXT_KEYS:
        if key in item:
            if key == "content" and isinstance(item[key], list):
                text = _stringify_text_blocks(item[key])
            else:
                text = _stringify_text(item[key])
            if text:
                return text
    return ""


def _stringify_text_blocks(value: list[Any]) -> str:
    parts: list[str] = []
    for block in value:
        if isinstance(block, str):
            parts.append(block)
            continue
        if not isinstance(block, Mapping):
            text = _stringify_text(block)
            if text:
                parts.append(text)
            continue
        role = _first_string(block, ROLE_KEYS).lower()
        kind = _first_string(block, TYPE_KEYS).lower()
        if _is_tool_call(block, kind) or _is_tool_result(block, role, kind) or "artifact" in kind:
            continue
        text = _stringify_text(block)
        if text:
            parts.append(text)
    return "\n".join(parts)


def _stringify_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        parts = [_stringify_text(item) for item in value]
        return "\n".join(part for part in parts if part)
    if isinstance(value, Mapping):
        for key in TEXT_KEYS:
            if key in value:
                text = _stringify_text(value[key])
                if text:
                    return text
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _tool_name(item: Mapping[str, Any]) -> str:
    for key in ("tool", "name", "tool_name", "function_name"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value

    function = item.get("function")
    if isinstance(function, Mapping):
        value = function.get("name")
        if isinstance(value, str) and value:
            return value

    return ""


def _extract_path(item: Mapping[str, Any]) -> str:
    found = _find_first_nested(item, PATH_KEYS)
    return _stringify_text(found) if found is not None else ""


def _extract_command(item: Mapping[str, Any]) -> str:
    found = _find_first_nested(item, COMMAND_KEYS)
    return _stringify_text(found) if found is not None else ""


def _find_first_nested(value: Any, keys: tuple[str, ...]) -> Any:
    if isinstance(value, Mapping):
        for key in keys:
            if key in value and value[key]:
                return value[key]
        for key in ARGUMENT_KEYS:
            if key in value:
                nested = _decode_arguments(value[key])
                found = _find_first_nested(nested, keys)
                if found is not None:
                    return found
        function = value.get("function")
        if isinstance(function, Mapping):
            found = _find_first_nested(function, keys)
            if found is not None:
                return found
    return None


def _decode_arguments(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {"text": value}


def _first_string(item: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str):
            return value
    return ""


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return [value]


def _looks_like_event(payload: Mapping[str, Any]) -> bool:
    return bool(_first_string(payload, ROLE_KEYS) or _first_string(payload, TYPE_KEYS) or _tool_name(payload) or _extract_command(payload))


def _has_payload(event: dict[str, Any]) -> bool:
    return any(key in event for key in ("text", "tool", "path", "command", "ok"))


def _sanitize_event(event: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in event.items():
        if isinstance(value, str):
            sanitized[key] = redact_text(value)
        else:
            sanitized[key] = value
    return sanitized


def redact_text(text: str) -> str:
    redacted = QUOTED_POSIX_LOCAL_PATH_RE.sub(_redact_quoted_posix_local_path, text)
    redacted = POSIX_LOCAL_PATH_RE.sub(_redact_posix_local_path, redacted)
    redacted = QUOTED_WINDOWS_LOCAL_PATH_RE.sub(_redact_quoted_windows_local_path, redacted)
    redacted = WINDOWS_LOCAL_PATH_RE.sub(_redact_windows_local_path, redacted)
    redacted = BEARER_RE.sub("Bearer [REDACTED]", redacted)
    redacted = SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", redacted)
    redacted = CLI_SECRET_OPTION_RE.sub(lambda match: f"{match.group(1)}[REDACTED]", redacted)
    redacted = SECRET_WORD_VALUE_RE.sub(lambda match: f"{match.group(1)}[REDACTED]", redacted)
    redacted = TOKEN_RE.sub("[REDACTED]", redacted)
    redacted = FEISHU_ID_RE.sub("[REDACTED]", redacted)
    return redacted


def _redact_quoted_posix_local_path(match: re.Match[str]) -> str:
    return f"{match.group('quote')}{_redact_posix_path(match.group('path'))}{match.group('quote')}"


def _redact_posix_local_path(match: re.Match[str]) -> str:
    return _redact_posix_path(match.group(0))


def _redact_posix_path(raw_path: str) -> str:
    path, trailing = _split_trailing_punctuation(raw_path)
    basename = PurePosixPath(path).name
    return f"<LOCAL_PATH>/{basename}{trailing}" if basename else f"<LOCAL_PATH>{trailing}"


def _redact_quoted_windows_local_path(match: re.Match[str]) -> str:
    return f"{match.group('quote')}{_redact_windows_path(match.group('path'))}{match.group('quote')}"


def _redact_windows_local_path(match: re.Match[str]) -> str:
    return _redact_windows_path(match.group(0))


def _redact_windows_path(raw_path: str) -> str:
    path, trailing = _split_trailing_punctuation(raw_path)
    basename = re.split(r"[\\/]", path)[-1]
    return f"<LOCAL_PATH>/{basename}{trailing}" if basename else f"<LOCAL_PATH>{trailing}"


def _split_trailing_punctuation(path: str) -> tuple[str, str]:
    trailing = ""
    while path and path[-1] in ".,;:)]}":
        trailing = path[-1] + trailing
        path = path[:-1]
    return path, trailing
