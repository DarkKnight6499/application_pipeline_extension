"""Author: Yazad Madan. Local correction counts and draft suggestions, separate from answers."""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import answer_memory
import miss_log
from shared_storage import atomic_json, file_lock

# Config
DATA_DIR = Path(__file__).resolve().parent / "data"
FILENAME = "assist_corrections.json"
SCHEMA_VERSION = 1
AUTHOR = "Yazad Madan"
MIN_CORRECTIONS = 2
MAX_LABEL = 300
MAX_VALUE = 2000
MAX_COMPANY = 150
MAX_HOST = 253
MAX_TYPE = 40
LABEL, HOST, COMPANY, TYPE = "label", "host", "company_hint", "type"
WRONG, USER, COUNT, CHANGES = "wrong_value", "user_value", "count", "changes"
QUESTIONS = "questions"
SCHEMA, AUTHOR_KEY = "schema_version", "author"
FIRST_SEEN, LAST_SEEN, LATEST_USER = "first_seen", "last_seen", "latest_user_value"
HOST_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", re.I)
SELF_ID = re.compile(r"\b(?:reserves|active duty|service member|uniformed services|religio\w*|marital status)\b", re.I)


def blocked(body):
    context = [body.get(LABEL, ""), *body.get("options", [])]
    return answer_memory.is_protected(body) or any(
        miss_log.BLOCKED.search(miss_log.normalized(value)) or SELF_ID.search(miss_log.normalized(value))
        for value in context)


def _identity(body):
    identity = [body.get(HOST, "").strip().lower(), miss_log.normalized(body.get(COMPANY, "")),
                answer_memory.normalize_label(body[LABEL])]
    return hashlib.sha256(json.dumps(identity).encode("utf-8")).hexdigest()


def _load(path):
    if not path.is_file():
        return {SCHEMA: SCHEMA_VERSION, AUTHOR_KEY: AUTHOR, QUESTIONS: {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get(SCHEMA) != SCHEMA_VERSION or not isinstance(data.get(QUESTIONS), dict):
        raise ValueError("Unsupported correction store.")
    return data


def record(data, body):
    """Persist only permitted values, under one process-safe lock."""
    for key, limit in ((LABEL, MAX_LABEL), (HOST, MAX_HOST), (COMPANY, MAX_COMPANY),
                       (TYPE, MAX_TYPE), (WRONG, MAX_VALUE), (USER, MAX_VALUE)):
        value = body.get(key, "")
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError("Correction fields must be bounded strings.")
    if (not body[LABEL].strip() or not answer_memory.normalize_label(body[LABEL])
            or not HOST_PATTERN.fullmatch(body.get(HOST, "").strip())):
        raise ValueError("Correction requires a question and host.")
    if blocked(body):
        return False
    wrong, user = body.get(WRONG, "").strip(), body.get(USER, "").strip()
    if not wrong or not user or wrong == user:
        return False
    path = Path(data).resolve() / FILENAME
    with file_lock(path):
        store = _load(path)
        now = datetime.now(timezone.utc).isoformat()
        row = store[QUESTIONS].setdefault(_identity(body), {
            LABEL: body[LABEL].strip(), HOST: body[HOST].strip().lower(),
            COMPANY: body.get(COMPANY, "").strip(), TYPE: body.get(TYPE, "text"),
            COUNT: 0, CHANGES: [], FIRST_SEEN: now})
        change = next((item for item in row[CHANGES] if item[WRONG] == wrong and item[USER] == user), None)
        if change is None:
            change = {WRONG: wrong, USER: user, COUNT: 0}
            row[CHANGES].append(change)
        change[COUNT] += 1
        row.update({COUNT: row[COUNT] + 1, LAST_SEEN: now, LATEST_USER: user})
        store[AUTHOR_KEY] = AUTHOR
        atomic_json(path, store)
    return True


def suggestion(data, body):
    if blocked(body) or not body.get(HOST):
        return None
    path = Path(data).resolve() / FILENAME
    with file_lock(path):
        row = _load(path)[QUESTIONS].get(_identity(body))
    if not row:
        return None
    user = row[LATEST_USER]
    count = sum(change[COUNT] for change in row[CHANGES] if change[USER] == user)
    return user if count >= MIN_CORRECTIONS else None


def report(data):
    """Return counts and question metadata only; CLI output never includes values."""
    path = Path(data).resolve() / FILENAME
    with file_lock(path):
        rows = _load(path)[QUESTIONS].values()
    return sorted(({key: row[key] for key in (LABEL, HOST, COMPANY, COUNT)} for row in rows),
                  key=lambda row: (-row[COUNT], row[LABEL], row[HOST], row[COMPANY]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA_DIR)
    parser.add_argument("--json", action="store_true", help="Print question metadata and counts as JSON.")
    args = parser.parse_args(argv)
    try:
        rows = report(args.data)
    except (OSError, ValueError, KeyError, TypeError):
        print("Cannot read correction store.", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(rows, ensure_ascii=True))
    else:
        for row in rows:
            print(f"{row[COUNT]}\t{row[HOST]}\t{row[COMPANY]}\t{row[LABEL]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
