"""Local memory of reviewed answers, matched on exact normalized question text only (no fuzzy matching)."""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import re

from question_corpus import normalize_label

# Config
DATA_DIR = Path(__file__).resolve().parent / "data"
MEMORY_FILENAME = "answer_memory.json"
SCHEMA_VERSION = 1
LABEL_COLUMN = "label"
TYPE_COLUMN = "type"
FIELDS_COLUMN = "fields"
MAX_ANSWER = 2000
DEFAULT_SALARY = 50000  # per year, used when a posting shows no band (user rule 2026-10-25)
# Demographic self-ID answers are allowed (user decision 2026-10-25); credentials, attestations and signatures never are.
NEVER_STORE = re.compile(r"\b(password|passcode|captcha|one.?time|otp|ssn|social security|credit card|bank account|routing number|signature|attest|certify|certification of|consent|agree|accept terms|privacy policy|declaration)\b", re.I)


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
        return {"schema_version": SCHEMA_VERSION, "answers": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != SCHEMA_VERSION or not isinstance(data.get("answers"), dict):
        raise ValueError("Answer memory has an unsupported schema.")
    return data


def save_memory(data, data_dir=DATA_DIR):
    path = memory_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


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


def has_consent(data, host, label):
    return consent_key(host, label) in data.get("consents", {})


def salary_expectation(band_low=None):
    """Salary answer: the posting's lower band when known, else the default."""
    try:
        low = int(band_low)
    except (TypeError, ValueError):
        return DEFAULT_SALARY
    return low if low > 0 else DEFAULT_SALARY


def lookup(data, label):
    entry = data["answers"].get(normalize_label(label))
    return entry["answer"] if entry else None


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
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="Store one reviewed answer.")
    add.add_argument("question")
    add.add_argument("answer")
    report = sub.add_parser("gaps", help="List questions in an Inspect export with no stored answer.")
    report.add_argument("export")
    args = parser.parse_args(argv)
    data = load_memory()
    if args.command == "add":
        if not remember(data, args.question, args.answer):
            print("Not stored: empty, oversized or protected question.", file=sys.stderr)
            return 1
        save_memory(data)
        print(f"Stored. {len(data['answers'])} answer(s).")
        return 0
    fields = json.loads(Path(args.export).read_text(encoding="utf-8")).get(FIELDS_COLUMN, [])
    for label in gaps(data, fields):
        print(label)
    return 0


if __name__ == "__main__":
    sys.exit(main())
