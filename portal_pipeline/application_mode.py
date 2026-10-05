"""Persistent, monotonic fill restriction for an audited application."""
from __future__ import annotations

import json
import threading
from pathlib import Path

SCHEMA_VERSION = 1
RESTRICTED = "answer_sheet_only"
UNRESTRICTED = "fill"
REASON_CAPTCHA = "captcha"
_locks_guard = threading.Lock()
_locks = {}


def _identity(session):
    application_id = session.get("application_id") if isinstance(session, dict) else None
    if (not isinstance(session, dict) or session.get("mode") != "audited_import"
            or isinstance(application_id, bool) or not isinstance(application_id, int)
            or application_id <= 0):
        return None
    return application_id


def _result(application_id, mode, reason):
    return {"schema_version": SCHEMA_VERSION, "application_id": application_id,
            "mode": mode, "reason": reason}


def _path(data, application_id):
    root = Path(data).resolve()
    base = root / "application_modes"
    target = base / f"{application_id}.json"
    if base.is_symlink() or target.is_symlink():
        raise ValueError("Application mode path is a symlink.")
    if base.resolve() != base or target.resolve() != target:
        raise ValueError("Application mode path escapes the data directory.")
    if not target.parent.is_relative_to(root) or target.parent != base:
        raise ValueError("Application mode path escapes the data directory.")
    return base, target


def _lock(target):
    with _locks_guard:
        return _locks.setdefault(target, threading.RLock())


def _lock_key(data, application_id):
    return Path(data).resolve() / "application_modes" / f"{application_id}.json"


def _stored(target, application_id):
    if not target.exists():
        return None
    value = json.loads(target.read_text(encoding="utf-8"))
    if (not isinstance(value, dict) or set(value) != {"schema_version", "application_id", "mode", "reason"}
            or type(value.get("schema_version")) is not int or value["schema_version"] != SCHEMA_VERSION
            or type(value.get("application_id")) is not int or value["application_id"] != application_id
            or value.get("mode") != RESTRICTED or value.get("reason") != REASON_CAPTCHA):
        raise ValueError("Invalid stored application mode.")
    return value


def effective(data, session):
    application_id = _identity(session)
    if application_id is None:
        return _result(None, RESTRICTED, "unaudited_application")
    try:
        with _lock(_lock_key(data, application_id)):
            _, target = _path(data, application_id)
            stored = _stored(target, application_id)
        return stored or _result(application_id, UNRESTRICTED, "unrestricted")
    except (OSError, ValueError, TypeError):
        return _result(application_id, RESTRICTED, "storage_error")


def restrict(data, session, body, write):
    if not isinstance(body, dict) or body != {"mode": RESTRICTED, "reason": REASON_CAPTCHA}:
        raise ValueError("Only a CAPTCHA downgrade is accepted.")
    application_id = _identity(session)
    if application_id is None:
        raise ValueError("An audited positive Application ID is required.")
    with _lock(_lock_key(data, application_id)):
        base, target = _path(data, application_id)
        stored = _stored(target, application_id)
        if stored:
            return stored
        base.mkdir(parents=True, exist_ok=True)
        _, target = _path(data, application_id)
        result = _result(application_id, RESTRICTED, REASON_CAPTCHA)
        write(target, result)
        return result
