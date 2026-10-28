"""Local memory of reviewed answers, matched on exact normalized question text only (no fuzzy matching)."""
import argparse
import copy
import contextlib
import json
import sys
from datetime import date
from contextvars import ContextVar
from pathlib import Path

import re

from question_corpus import normalize_label
from shared_storage import atomic_json, file_lock

# Config
DATA_DIR = Path(__file__).resolve().parent / "data"
MEMORY_FILENAME = "answer_memory.json"
SCHEMA_VERSION = 1
LABEL_COLUMN = "label"
TYPE_COLUMN = "type"
FIELDS_COLUMN = "fields"
ANSWERS_KEY = "answers"
SOURCE_BATCH_REVIEW = "batch-review"
MERGE_SECTIONS = (ANSWERS_KEY, "consents", "aliases")
HELD_MEMORY_LOCKS = ContextVar("held_memory_locks", default=())
MAX_ANSWER = 2000
START_MONTH_DAY = (12, 15)  # every application starts 15 December (user rule 2026-10-25)
DEFAULT_SALARY = 50000  # per year, used when a posting shows no band (user rule 2026-10-25)
# Demographic self-ID answers are allowed (user decision 2026-10-25); credentials, attestations and signatures never are.
NEVER_STORE = re.compile(r"\b(password|passcode|captcha|one.?time|otp|verification code|security code|authenticator|ssn|social security|credit card|bank account|routing number|signature|signed|initials|attest|attestation|certify|certification of|consent|agree|accept terms|privacy policy|declaration|username|user name|login|log in)\b", re.I)


def is_protected(field):
    return bool(field.get("protected")) or str(field.get(TYPE_COLUMN, "")).lower() in {"password", "file", "signature"} or bool(NEVER_STORE.search(str(field.get(LABEL_COLUMN, ""))))


# Consent and attestation boxes are auto-tickable only after one manual tick on that host (user decision 2026-10-25); signatures never are.
CONSENT_TERMS = re.compile(r"\b(agree|consent|accept|terms|privacy|certify|attest|attestation|acknowledge|declare|true and (correct|accurate)|truthful)\b", re.I)
SIGNATURE_TERMS = re.compile(r"\b(signature|sign|signed|initials)\b", re.I)


def memory_path(data_dir=DATA_DIR):
    return Path(data_dir).resolve() / MEMORY_FILENAME


def load_memory(data_dir=DATA_DIR):
    path = memory_path(data_dir)
    if not path.is_file():
        return MemoryData({"schema_version": SCHEMA_VERSION, ANSWERS_KEY: {}})
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != SCHEMA_VERSION or not isinstance(data.get("answers"), dict):
        raise ValueError("Answer memory has an unsupported schema.")
    return MemoryData(data)


class MemoryData(dict):
    def __init__(self, data):
        super().__init__(data)
        self.baseline = copy.deepcopy(data)


@contextlib.contextmanager
def memory_lock(data_dir=DATA_DIR):
    path = memory_path(data_dir)
    if path in HELD_MEMORY_LOCKS.get():
        yield
        return
    with file_lock(path):
        token = HELD_MEMORY_LOCKS.set((*HELD_MEMORY_LOCKS.get(), path))
        try:
            yield
        finally:
            HELD_MEMORY_LOCKS.reset(token)


def save_memory(data, data_dir=DATA_DIR):
    path = memory_path(data_dir)
    baseline = getattr(data, "baseline", {})
    with memory_lock(data_dir):
        current = load_memory(data_dir)
        for section in MERGE_SECTIONS:
            changes = {key: value for key, value in data.get(section, {}).items()
                       if baseline.get(section, {}).get(key) != value}
            if changes:
                current.setdefault(section, {}).update(changes)
        atomic_json(path, current)
    if isinstance(data, MemoryData):
        data.baseline = copy.deepcopy(dict(data))


def update_memory(update, data_dir=DATA_DIR):
    """Reload and update under one lock so concurrent reviewed answers merge."""
    with memory_lock(data_dir):
        data = load_memory(data_dir)
        result = update(data)
        if result:
            if data_dir == DATA_DIR:
                save_memory(data)
            else:
                save_memory(data, data_dir)
        return result


def remember(data, label, answer, source="manual", now=None):
    """Stores one reviewed answer; returns False for protected, empty or oversized input."""
    key = normalize_label(label)
    text = str(answer or "").strip()
    if not key or not text or len(text) > MAX_ANSWER or is_protected({LABEL_COLUMN: label}):
        return False
    today = now or date.today().isoformat()
    entry = data["answers"].setdefault(key, {LABEL_COLUMN: str(label).strip()[:300], "first_seen": today, "uses": 0})
    entry.update(answer=text, source=source, last_seen=today)
    return True


def consent_key(host, label):
    return f"{str(host).strip().lower()}|{normalize_label(label)}"


def record_consent(data, host, label, now=None):
    """Remembers a consent box the user ticked manually; returns False for signatures and non-consent labels."""
    text = str(label or "")
    if not str(host).strip() or not normalize_label(text) or SIGNATURE_TERMS.search(text) or not CONSENT_TERMS.search(text):
        return False
    data.setdefault("consents", {})[consent_key(host, text)] = {"label": text.strip()[:300], "accepted": now or date.today().isoformat()}
    return True


def alias_key(host, value):
    return f"{str(host).strip().lower()}|{normalize_label(value)}"


def remember_alias(data, host, value, portal_label):
    """Remembers the wording a portal used for a profile value (a degree, say) on one host; exact value only."""
    key, label = alias_key(host, value), str(portal_label or "").strip()
    if not str(host).strip() or not normalize_label(value) or not label or len(label) > MAX_ANSWER:
        return False
    data.setdefault("aliases", {})[key] = label
    return True


def profile_aliases(data):
    return dict(data.get("aliases", {}))


def profile_consents(data):
    """Recorded host|question consent keys, the shape the extension reads from profile.consents."""
    return list(data.get("consents", {}))


def has_consent(data, host, label):
    return consent_key(host, label) in data.get("consents", {})


def salary_expectation(band_low=None):
    """Salary answer: the posting's lower band when known, else the default."""
    try:
        low = int(band_low)
    except (TypeError, ValueError):
        return DEFAULT_SALARY
    return low if low > 0 else DEFAULT_SALARY


def start_date(today=None):
    """Next 15 December on or after today (user rule 2026-10-25), as an ISO date."""
    today = today or date.today()
    year = today.year if (today.month, today.day) <= START_MONTH_DAY else today.year + 1
    return date(year, *START_MONTH_DAY).isoformat()


def lookup(data, label):
    entry = data["answers"].get(normalize_label(label))
    return entry["answer"] if entry else None


def profile_answers(data):
    """Normalized question to answer, the shape the extension reads from profile.answers."""
    return {key: entry["answer"] for key, entry in data["answers"].items()}


def gaps(data, fields):
    """Distinct unprotected question labels with no stored answer, in first-seen order."""
    seen, result = set(), []
    for field in fields:
        label = str(field.get(LABEL_COLUMN) or "").strip()
        key = normalize_label(label)
        if not key or key in seen or key in data["answers"] or is_protected(field):
            continue
        seen.add(key)
        result.append(label)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--import-answers", type=Path, help="Import reviewed batch answers and resume queued tabs.")
    parser.add_argument("--store-only", action="store_true", help="Store imported answers without resuming browser tabs.")
    sub = parser.add_subparsers(dest="command")
    add = sub.add_parser("add", help="Store one reviewed answer.")
    add.add_argument("question")
    add.add_argument("answer")
    report = sub.add_parser("gaps", help="List questions in an Inspect export with no stored answer.")
    report.add_argument("export")
    args = parser.parse_args(argv)
    if args.import_answers:
        if args.command:
            parser.error("import-answers cannot be combined with another command")
        from learning_queue import import_answers
        try:
            stored, jobs = import_answers(args.import_answers)
        except (OSError, ValueError, TypeError, KeyError) as error:
            print(f"Not imported: {error}", file=sys.stderr)
            return 1
        print(f"Stored {stored} batch-review answer(s).")
        if stored and not args.store_only:
            from batch_apply import resume_jobs
            return resume_jobs(jobs)
        return 0
    if not args.command or args.store_only:
        parser.error("choose add, gaps, or import-answers; store-only requires import-answers")
    if args.command == "add":
        if not update_memory(lambda memory: remember(memory, args.question, args.answer)):
            print("Not stored: empty, oversized or protected question.", file=sys.stderr)
            return 1
        print(f"Stored. {len(load_memory()['answers'])} answer(s).")
        return 0
    fields = json.loads(Path(args.export).read_text(encoding="utf-8")).get(FIELDS_COLUMN, [])
    for label in gaps(load_memory(), fields):
        print(label)
    return 0


if __name__ == "__main__":
    sys.exit(main())
