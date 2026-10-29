"""Author: Yazad Madan. Bounded diagnostics without answer values."""
import hashlib
import re
import subprocess
from subprocess import run as run_git
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

# Config
TEXT_LIMIT = 240
FIELD_LIMIT = 200
ERROR_LIMIT = 10
DIALOG_LIMIT = 120
NUMBER_LIMIT = 1000000
FIELD_RECORDS_KEY = "field_results"
NEXT_KEY = "next_outcome"
REVISION_KEY = "source_revision"
FILL_STOP_KEY = "fill_stop_reason"
RETRY_KEY = "rerender_retries"
RETRY_EVENTS_KEY = "retry_events"
TRANSIENT_FAILURES = frozenset({"identity_changed", "node_replaced"})
DOM_STATE_KEY = "dom_state"
ROW_BINDING_KEY = "row_binding"
VALUE_KIND_KEY = "attempted_value_kind"
VALUE_LENGTH_KEY = "attempted_value_length"
FIELD_TEXT_KEYS = ("label", "key", "type", "adapter")
RESULT_TEXT_KEYS = ("status", "reason", "reason_code", "failure_kind", "validation_error")
ANSWER_KEYS = ("current", "proposal")
DOM_KEYS = ("visible", "aria_invalid", "validity", "popup_expanded", "popup_owned", "option_count", "selected_token_count")
VALIDITY_KEYS = ("valid", "valueMissing", "typeMismatch", "patternMismatch", "tooLong", "tooShort", "rangeUnderflow", "rangeOverflow", "stepMismatch", "badInput", "customError")
STRUCTURE_KEYS = ("dom_id", "name", "automation_id")
ROW_KEYS = ("id", "group", "index")
FAILURE_ACTIONS = {
    "structure_changed": "retry", "node_replaced": "retry", "fill_aborted": "retry",
    "unsupported_control": "human", "human_gate": "human", "refused": "human",
    "validation_error": "hard", "reverted": "hard", "identity_changed": "retry",
    "row_identity_changed": "hard", "collateral_change": "hard", "error": "hard",
    "missing_result": "hard", "result_mismatch": "hard",
    "attachment_mismatch": "hard",
}
SECRET_PATTERN = re.compile(r"""(?i)\b(password|passwd|api[_ -]?key|access[_ -]?token|token|secret|authorization|cookie|verification code)["']?\s*[:=]\s*(?:"[^"]*"|'[^']*'|[^\s,;}]+)""")
BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]+=*")
EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
TOKEN_PATTERN = re.compile(r"\b(?=[A-Za-z0-9_-]{32,}\b)(?=[A-Za-z0-9_-]*[0-9])(?=[A-Za-z0-9_-]*[A-Za-z])[A-Za-z0-9_-]+\b")
INLINE_SUCCESS = re.compile(r"successfully\s+(?:uploaded|attached|saved)|(?:upload|attachment)\s+(?:was\s+)?(?:successful|complete(?:d)?)\b", re.I)
INLINE_FAILURE = re.compile(r"\b(?:error|failed|failure|invalid|rejected|unable|required|must)\b", re.I)


def clean_text(value, secrets=(), limit=TEXT_LIMIT):
    text = str("" if value is None else value)
    for secret in sorted({str(item) for item in secrets if item is not None and str(item)}, key=len, reverse=True):
        pattern = re.escape(secret) if len(secret) >= 4 else r"(?<!\w)" + re.escape(secret) + r"(?!\w)"
        text = re.sub(pattern, "[redacted]", text, flags=re.I)
    text = BEARER_PATTERN.sub("[credential redacted]", text)
    text = SECRET_PATTERN.sub("[credential redacted]", text)
    text = EMAIL_PATTERN.sub("[email redacted]", text)
    text = TOKEN_PATTERN.sub("[token redacted]", text)
    return " ".join(text.split())[:limit]


def safe_url(value, secrets=()):
    try:
        parts = urlsplit(str(value))
        host = parts.hostname or ""
        host = f"[{host}]" if ":" in host else host
        authority = f"{host}:{parts.port}" if parts.port is not None else host
        return clean_text(urlunsplit((parts.scheme, authority, parts.path, "", "")), secrets)
    except ValueError:
        return "[invalid URL]"


def answer_strings(value):
    if isinstance(value, dict):
        return {text for key, item in value.items() if key not in {"source", "label", "key", "id", "type"}
                for text in answer_strings(item)}
    if isinstance(value, (list, tuple)):
        return {text for item in value for text in answer_strings(item)}
    return {str(value)} if value is not None and str(value) else set()


def source_revision(directory):
    root = Path(directory)
    hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in ("workday_run.py", "apply.py")}
    revision = {"files": hashes}
    try:
        result = run_git(["git", "-c", f"safe.directory={root.parent.as_posix()}", "rev-parse", "--short", "HEAD"],
                         cwd=root, capture_output=True, text=True, timeout=2, check=False)
        if result.returncode == 0 and re.fullmatch(r"[a-f0-9]{7,40}", result.stdout.strip()):
            revision["git"] = result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return revision


def failure_action(result):
    kind = result.get("failure_kind") or result.get("reason_code") or result.get("status")
    return FAILURE_ACTIONS.get(kind, "hard")


def record_retry(event, results, attempt, secrets=()):
    event[RETRY_KEY] = attempt
    records = event.setdefault(RETRY_EVENTS_KEY, [])
    for result in results:
        if len(records) >= FIELD_LIMIT:
            event["retry_events_truncated"] = True
            break
        records.append({"attempt": attempt, "field_id": clean_text(result.get("id"), secrets),
                        "failure_kind": clean_text(result.get("failure_kind") or result.get("reason_code"), secrets),
                        "reason": clean_text(result.get("reason") or result.get("message"), secrets)})


def is_inline_error(message):
    text = str(message or "").strip()
    return bool(text) and (not INLINE_SUCCESS.search(text) or bool(INLINE_FAILURE.search(text)))


def bounded_dom(state):
    state = state if isinstance(state, dict) else {}
    result = {}
    for key in DOM_KEYS:
        value = state.get(key)
        if key == "validity" and isinstance(value, dict):
            result[key] = {name: value[name] for name in VALIDITY_KEYS if isinstance(value.get(name), bool)}
        elif isinstance(value, bool):
            result[key] = value
        elif key.endswith("count") and isinstance(value, int):
            result[key] = max(0, min(value, NUMBER_LIMIT))
    return result


def field_record(field, selection, result, secrets=()):
    value = selection.get("value")
    kind = "null" if value is None else "boolean" if isinstance(value, bool) else "string" if isinstance(value, str) else "array" if isinstance(value, list) else "number" if isinstance(value, (int, float)) else "object"
    length = len(value) if isinstance(value, (str, list, dict)) else len(str(value)) if value is not None else 0
    record = {key: clean_text(field.get(key), secrets) for key in FIELD_TEXT_KEYS}
    record["adapter"] = clean_text(field.get("adapter") or result.get("adapter") or "native", secrets)
    record.update({key: clean_text((field.get("structure") or {}).get(key), secrets) for key in STRUCTURE_KEYS})
    row = field.get("record") or {}
    record[ROW_BINDING_KEY] = {key: clean_text(row.get(key), secrets) for key in ROW_KEYS}
    record[ROW_BINDING_KEY]["index"] = row.get("index") if type(row.get("index")) is int else None
    record.update(required=bool(field.get("required")), disabled=bool(field.get("disabled")),
                  overwrite=selection.get("overwrite") is True)
    record[VALUE_KIND_KEY] = kind
    record[VALUE_LENGTH_KEY] = min(length, NUMBER_LIMIT)
    record.update({key: clean_text(result.get(key), secrets) for key in RESULT_TEXT_KEYS})
    record["reason"] = clean_text(result.get("reason") or result.get("message"), secrets)
    record[DOM_STATE_KEY] = bounded_dom(result.get(DOM_STATE_KEY, field.get(DOM_STATE_KEY)))
    return record


def append_results(event, fields, selections, results, secrets=()):
    records = event.setdefault(FIELD_RECORDS_KEY, [])
    indexed = {result.get("id"): result for result in results}
    for field, selection in zip(fields, selections):
        result = indexed.get(field.get("id"), {"status": "failed", "failure_kind": "missing_result", "reason": "Engine returned no result."})
        if len(records) >= FIELD_LIMIT:
            event["field_results_truncated"] = True
            if result.get("status") not in {"filled", "preserved", "skipped_existing"}:
                records[-1] = field_record(field, selection, result, secrets)
        else:
            records.append(field_record(field, selection, result, secrets))


def row_identity_stable(before, after):
    def identity(field):
        row = field.get("record") or {}
        structure = field.get("structure") or {}
        return (field.get("key"), field.get("label"), field.get("type"),
                tuple(row.get(key) for key in ROW_KEYS), tuple(structure.get(key) for key in STRUCTURE_KEYS))
    indexed = {field.get("id"): identity(field) for field in after}
    return all(field.get("id") in indexed and indexed[field.get("id")] == identity(field) for field in before)


def upload_reason(state):
    if state.get("rejected"):
        return "upload_rejected"
    if state.get("stale_filename"):
        return "upload_stale_filename"
    if state.get("size_mismatch"):
        return "upload_size_mismatch"
    if state.get("confirmed"):
        return "upload_confirmed"
    if state.get("container_replaced"):
        return "upload_container_replaced"
    return "upload_timeout"


def next_reason(before, after, timed_out=False):
    if after.get("dialog"):
        return "dialog_opened"
    errors = [text for text in after.get("inline_errors", []) if is_inline_error(text)]
    previous = [text for text in before.get("inline_errors", []) if is_inline_error(text)]
    if errors and errors != previous:
        return "inline_validation_error"
    if after.get("title") and after.get("title") != before.get("title"):
        return "step_changed"
    return "timeout" if timed_out else None
