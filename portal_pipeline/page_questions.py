"""Author: Yazad Madan. Local, append-only capture of page questions and answers."""
import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import answer_memory
import corrections
import dropdown_mappings
import question_alias
from shared_storage import file_lock

# Config
FILENAME = "page_questions.jsonl"
AUTHOR = "Yazad Madan"
SCHEMA_VERSION = 1
MAX_PAIRS = 80
MAX_LABEL = 300
MAX_ANSWER = 2000
MAX_OPTIONS = 40
MAX_OPTION = 120
MAX_COMPANY = 150
MAX_HOST = 253
MAX_TYPE = 40
DEDUP_DAYS = 7
SOURCES = {"prefilled", "filled", "typed", "corrected"}
EXCLUDED_TYPES = {"password", "file"}
LABEL, ANSWER, COMPANY, HOST = "label", "answer", "company", "host"
TYPE, OPTIONS, SOURCE, TS = "type", "options", "source", "ts"
SENSITIVE, TRUNCATED, TRUNCATED_FIELDS = "sensitive", "truncated", "truncated_fields"
PAIR_DIGEST = "pair_digest"


def pair_digest(company, label, answer):
    return hashlib.sha256(json.dumps([company, label, answer], ensure_ascii=True).encode("utf-8")).hexdigest()


def sensitive(field):
    from assist_api import BLOCKED_DRAFT, NEVER_FILL
    context = " ".join([field.get(LABEL, ""), *field.get(OPTIONS, [])])
    return bool(answer_memory.is_protected(field) or question_alias.blocked(field)
                or corrections.blocked(field) or dropdown_mappings.blocked(field)
                or NEVER_FILL.search(context) or any(pattern.search(context) for pattern in BLOCKED_DRAFT))


def read(data):
    path = Path(data) / FILENAME
    with file_lock(path):
        return _read(path)


def _read(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle]
    if any(not isinstance(row, dict) or row.get("schema_version") != SCHEMA_VERSION for row in rows):
        raise ValueError("Unsupported page questions file.")
    return rows


def capture(service, body):
    if not isinstance(body, dict):
        raise ValueError("Dump requires a JSON object.")
    for key in (HOST, "url", "company_hint"):
        if not isinstance(body.get(key, ""), str):
            raise ValueError("Dump metadata must be strings.")
    service.company_scope(body)
    host = body[HOST].strip().lower()
    if len(host) > MAX_HOST or not dropdown_mappings.HOST_PATTERN.fullmatch(host):
        raise ValueError("Dump requires a valid page host.")
    pairs = body.get("pairs")
    if not isinstance(pairs, list) or len(pairs) > MAX_PAIRS:
        raise ValueError("Dump requires at most 80 pairs.")
    now = datetime.now(timezone.utc)
    page_id = secrets.token_hex(6)
    prepared, excluded = [], 0
    for pair in pairs:
        if not isinstance(pair, dict) or not isinstance(pair.get(TYPE, "text"), str):
            raise ValueError("Invalid dump pair.")
        kind = pair.get(TYPE, "text").strip().lower()
        if kind in EXCLUDED_TYPES:
            excluded += 1
            continue
        if (any(not isinstance(pair.get(key), str) or not pair[key].strip() for key in (LABEL, ANSWER))
                or pair.get(SOURCE) not in SOURCES):
            raise ValueError("Dump requires question, answer, and source strings.")
        options = pair.get(OPTIONS, [])
        if not isinstance(options, list) or any(not isinstance(value, str) for value in options):
            raise ValueError("Dump options must be strings.")
        if "protected" in pair and not isinstance(pair["protected"], bool):
            raise ValueError("Invalid protected flag.")
        fields = []
        def bounded(key, value, limit):
            if len(value) > limit:
                fields.append(key)
            return value[:limit]
        row = {"author": AUTHOR, "schema_version": SCHEMA_VERSION, TS: now.isoformat(),
               COMPANY: bounded(COMPANY, body.get("company_hint", "").strip(), MAX_COMPANY), HOST: host,
               "vendor": dropdown_mappings.vendor_from_host(host),
               LABEL: bounded(LABEL, pair[LABEL], MAX_LABEL), ANSWER: bounded(ANSWER, pair[ANSWER], MAX_ANSWER),
               SOURCE: pair[SOURCE], TYPE: bounded(TYPE, kind, MAX_TYPE),
               OPTIONS: [bounded(OPTIONS, option, MAX_OPTION) for option in options[:MAX_OPTIONS]],
               "page_id": page_id, SENSITIVE: sensitive(pair)}
        if len(options) > MAX_OPTIONS:
            fields.append(OPTIONS)
        row.update({TRUNCATED: bool(fields), TRUNCATED_FIELDS: sorted(set(fields))})
        if any(field in fields for field in (COMPANY, LABEL, ANSWER)):
            row[PAIR_DIGEST] = pair_digest(body.get("company_hint", "").strip(), pair[LABEL], pair[ANSWER])
        prepared.append(row)
    path = service.data / FILENAME
    result = {"saved": 0, "duplicate": 0, "excluded_by_type": excluded, "flagged_sensitive": 0}
    with file_lock(path):
        cutoff = now - timedelta(days=DEDUP_DAYS)
        recent = {row.get(PAIR_DIGEST) or pair_digest(row[COMPANY], row[LABEL], row[ANSWER]) for row in _read(path)
                  if datetime.fromisoformat(row[TS]) >= cutoff}
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            for row in prepared:
                key = row.get(PAIR_DIGEST) or pair_digest(row[COMPANY], row[LABEL], row[ANSWER])
                if key in recent:
                    result["duplicate"] += 1
                    continue
                handle.write(json.dumps(row, ensure_ascii=True) + "\n")
                handle.flush()
                recent.add(key)
                result["saved"] += 1
                result["flagged_sensitive"] += int(row[SENSITIVE])
    return result
