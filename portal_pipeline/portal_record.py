"""Per-application portal record plus the printed tracker command; this module never touches the tracker."""
import datetime
import json
import os
import re
import tempfile
from pathlib import Path

import question_corpus

# Config
SCHEMA_VERSION = 1
RECORD_DIR = "records"
ADAPTER_VERSION = "1"
RESUME_FILE_NAME = "Yazad_Madan.docx"
SUBMITTED_STATE = "candidate_reported_submitted"
PAGE_STATES = ("scanned", "prepared", "partially_filled", "awaiting_review", "complete_for_review")
SPONSORSHIP_MODES = ("truthful", "screening_no")
DEFAULT_SPONSORSHIP_MODE = "truthful"
MARK_SCRIPT = r"D:\Code\Resume\_Reference\mark_application_status.py"
EMPLOYER_REF_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._/#-]{0,63}")
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
MAX_FIELDS = 500
MAX_TEXT = 2000
MAX_EVENTS = 500
MAX_LIST = 200
FIELD_TEXT_KEYS = ("field_id", "label", "key", "proposal", "final_value", "source", "result", "readback")


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _default_write(path, data):
    path = Path(path)
    handle, temp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(handle, "w", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2)
    os.replace(temp, path)


def _path(data, application_id):
    if isinstance(application_id, bool) or not isinstance(application_id, int) or application_id < 0:
        raise ValueError("The application id must be a whole number.")
    base = (Path(data) / RECORD_DIR).resolve()
    target = (base / f"{application_id}.json").resolve()
    if target.parent != base:
        raise ValueError("Record path escapes the records directory.")
    return base, target


def _blank(application_id):
    return {"schema_version": SCHEMA_VERSION, "application_id": application_id, "employer_reference_id": None,
            "company": "", "role": "", "posting_url": "", "portal": "generic", "adapter_version": ADAPTER_VERSION,
            "sponsorship_answer_mode": DEFAULT_SPONSORSHIP_MODE,
            "resume": {"filename": RESUME_FILE_NAME, "sha256": ""}, "portal_state": "scanned", "pages": [],
            "unanswered_required": [], "manual_interventions": [], "events": []}


def _seed(record, session):
    for key, source in (("company", "company"), ("role", "role"), ("posting_url", "url"), ("portal", "portal")):
        if session.get(source):
            record[key] = str(session[source])[:MAX_TEXT]
    record["resume"]["sha256"] = str(session.get("resume_sha256") or record["resume"]["sha256"])
    mode = session.get("sponsorship_answer_mode")
    record["sponsorship_answer_mode"] = mode if mode in SPONSORSHIP_MODES else DEFAULT_SPONSORSHIP_MODE


def load_record(data, application_id, session=None, write=None):
    """Returns the stored record; a missing one is created from the session when given, else returned blank and unsaved."""
    base, target = _path(data, application_id)
    if target.is_file():
        record = json.loads(target.read_text(encoding="utf-8"))
        record.setdefault("sponsorship_answer_mode", DEFAULT_SPONSORSHIP_MODE)
        return record
    record = _blank(application_id)
    if session is not None:
        _seed(record, session)
        _save(data, application_id, record, write)
    return record


def _save(data, application_id, record, write=None):
    base, target = _path(data, application_id)
    base.mkdir(parents=True, exist_ok=True)
    (write or _default_write)(target, record)


def _text(value, limit=MAX_TEXT):
    return "" if value is None else str(value)[:limit]


def append_event(data, application_id, kind, detail, write=None, now=None):
    record = load_record(data, application_id)
    record["events"].append({"at": now or _now(), "kind": _text(kind, 60), "detail": _text(detail, 500)})
    del record["events"][:-MAX_EVENTS]
    _save(data, application_id, record, write)
    return record


def _clean_field(entry):
    probe = {"label": entry.get("label", ""), "type": entry.get("type", ""), "protected": entry.get("protected")}
    if question_corpus.is_protected(probe):
        return None
    clean = {key: _text(entry.get(key)) for key in FIELD_TEXT_KEYS}
    clean["selected"] = entry.get("selected") is True
    clean["overwrite"] = entry.get("overwrite") is True
    return clean


def _list(values):
    return [_text(item, 300) for item in values[:MAX_LIST]] if isinstance(values, list) else []


def record_page(data, application_id, page, write=None, now=None):
    if not isinstance(page, dict) or not isinstance(page.get("fields", []), list) or len(page.get("fields", [])) > MAX_FIELDS:
        raise ValueError("A page needs a fields list of at most 500 entries.")
    state = page.get("portal_state")
    if state is not None and state not in PAGE_STATES:
        raise ValueError("Portal state must be one of " + ", ".join(PAGE_STATES) + ".")
    record = load_record(data, application_id)
    fields = [clean for entry in page.get("fields", []) if isinstance(entry, dict) and (clean := _clean_field(entry))]
    entry = {"page_key": _text(page.get("page_key"), 300), "scanned_at": _text(page.get("scanned_at")) or now or _now(), "fields": fields}
    record["pages"] = [p for p in record["pages"] if p["page_key"] != entry["page_key"]] + [entry]
    if state and record["portal_state"] != SUBMITTED_STATE:
        record["portal_state"] = state
    for key in ("unanswered_required", "manual_interventions"):
        if key in page:
            record[key] = sorted(set(record[key]) | set(_list(page[key])))
    _save(data, application_id, record, write)
    return record


def _checked_reference(application_id, reference):
    if reference is None or not str(reference).strip():
        return None
    reference = str(reference).strip()
    if not EMPLOYER_REF_PATTERN.fullmatch(reference) or "--" in reference:
        raise ValueError("The employer reference may use letters, digits, spaces and . _ / # - only.")
    if reference == str(application_id):
        raise ValueError("The employer reference must differ from the tracker Application ID.")
    return reference


def mark_reported_submitted(data, application_id, employer_reference_id, write=None, now=None):
    reference = _checked_reference(application_id, employer_reference_id)
    record = load_record(data, application_id)
    record["portal_state"] = SUBMITTED_STATE
    record["employer_reference_id"] = reference
    record["events"].append({"at": now or _now(), "kind": "reported_submitted", "detail": "Candidate reported submitting the application."})
    _save(data, application_id, record, write)
    return record


def _quote(text):
    return re.sub(r'(["`$])', r"`\1", str(text))


def tracker_command(record, today):
    if not DATE_PATTERN.fullmatch(str(today)):
        raise ValueError("The date must be YYYY-MM-DD.")
    application_id = record.get("application_id")
    if isinstance(application_id, bool) or not isinstance(application_id, int):
        raise ValueError("The record has no tracker Application ID.")
    command = f'py -3 {MARK_SCRIPT} "{_quote(record.get("company", ""))}" "{_quote(record.get("role", ""))}" Applied {today} --id {application_id}'
    reference = _checked_reference(application_id, record.get("employer_reference_id"))
    return command + (f' --employer-ref "{_quote(reference)}"' if reference else "")
