"""Author: Yazad Madan. Append-only, metadata-only unanswered question sightings."""
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from shared_storage import file_lock

# Config
LOG_FILENAME = "assist_misses.jsonl"
AUTHOR = "Yazad Madan"
SCHEMA_VERSION = 1
MAX_LABEL = 300
MAX_OPTIONS = 40
MAX_OPTION = 120
MAX_HOST = 253
MAX_COMPANY = 150
MAX_TYPE = 40
MAX_SAMPLES = 3
LABEL_COLUMN, HOST_COLUMN, TYPE_COLUMN = "label", "host", "type"
COMPANY_COLUMN, OPTIONS_COLUMN = "company_hint", "options"
KEY_COLUMN, COUNT_COLUMN = "key", "count"
FIRST_COLUMN, LAST_COLUMN = "first_seen", "last_seen"
COMPANIES_COLUMN, HOSTS_COLUMN, SAMPLES_COLUMN = "companies", "hosts", "option_samples"
EVENT_COLUMN, AUTHOR_COLUMN, SCHEMA_COLUMN = "event", "author", "schema_version"
RESOLVED_COLUMN = "resolved_at"
PROTECTED_COLUMN = "protected"
SELECT_TYPES = {"select", "select-one", "select-multiple", "combobox"}
BLOCKED_TYPES = {"password", "signature", "file"}
BLOCKED = re.compile(
    r"\b(?:password\w*|passcode\w*|captcha|s ?s ?n|social security|verification code|one time|otp|"
    r"signature\w*|sign|signed|signing|initials|attest\w*|certify|certifies|certified|certification of|consent|agree\w*|declaration|"
    r"i (?:confirm|affirm|declare)|truthful|accurate and complete|true and (?:correct|accurate)|"
    r"sponsor\w*|visa\w*|immigration|citizen\w*|nationality|work permit|opt|cpt|h 1b|"
    r"(?:work|employment) (?:authori[sz]\w*|eligib\w*)|"
    r"(?:authori[sz]\w*|eligib\w*|right|permit\w*|permission|allow\w*|legally).{0,60}(?:work|employment)|"
    r"veteran\w*|disab\w*|accommodation\w*|military|armed forces|national guard|reservist\w*|"
    r"gender\w*|sex|male|female|non ?binary|transgender|race|racial|ethnic\w*|hispanic|latino|"
    r"black|white|asian|indigenous|native american|pacific islander|sexual orientation|lgbtq\w*|"
    r"pronouns?|self ?(?:id\w*|identification|disclosure)|demographic\w*|eeo|national origin|"
    r"decline to (?:identify|answer|disclose))\b", re.I)


def normalized(value):
    value = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[\W_]+", " ", value).strip()


def _text(value, limit):
    return " ".join(value.split())[:limit]


def _metadata(body):
    if not isinstance(body, dict):
        raise ValueError("Miss must be a JSON object.")
    label = body.get(LABEL_COLUMN)
    if not isinstance(label, str) or not label.strip():
        raise ValueError("Miss label must be a nonempty string.")
    for key in (HOST_COLUMN, TYPE_COLUMN, COMPANY_COLUMN):
        if not isinstance(body.get(key, ""), str):
            raise ValueError("Miss metadata must be strings.")
    options = body.get(OPTIONS_COLUMN, [])
    if not isinstance(options, list) or any(not isinstance(option, str) for option in options):
        raise ValueError("Miss options must be a list of strings.")
    kind = _text(body.get(TYPE_COLUMN, "text"), MAX_TYPE).lower()
    # Check the full context before truncation so sensitive suffixes cannot bypass filtering.
    if (kind in BLOCKED_TYPES or body.get(PROTECTED_COLUMN) or
            any(BLOCKED.search(normalized(value)) for value in [label, *options])):
        return None
    label = _text(label, MAX_LABEL)
    if not normalized(label):
        raise ValueError("Miss label must contain question text.")
    return {LABEL_COLUMN: label, HOST_COLUMN: _text(body.get(HOST_COLUMN, ""), MAX_HOST).lower().rstrip("."),
            TYPE_COLUMN: kind, COMPANY_COLUMN: _text(body.get(COMPANY_COLUMN, ""), MAX_COMPANY),
            OPTIONS_COLUMN: [_text(option, MAX_OPTION) for option in options[:MAX_OPTIONS]] if kind in SELECT_TYPES else []}


def _state(path):
    rows, resolved = {}, set()
    if path.is_file():
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                event = json.loads(line)
                key = event[KEY_COLUMN]
                if event[EVENT_COLUMN] == "resolve":
                    resolved.add(key)
                else:
                    rows[key, event[HOST_COLUMN]] = event
                    resolved.discard(key)
    return rows, resolved


def _append(path, event):
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {AUTHOR_COLUMN: AUTHOR, SCHEMA_COLUMN: SCHEMA_VERSION, **event}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=True) + "\n")


def record(data, body):
    """Count one sighting; keep the latest bounded samples for each label and host."""
    metadata = _metadata(body)
    if metadata is None:
        return False
    path = Path(data).resolve() / LOG_FILENAME
    key = normalized(metadata[LABEL_COLUMN])
    with file_lock(path):
        rows, _ = _state(path)
        previous = rows.get((key, metadata[HOST_COLUMN]), {})
        now = datetime.now(timezone.utc).isoformat()
        companies = set(previous.get(COMPANIES_COLUMN, []))
        if metadata[COMPANY_COLUMN]:
            companies.add(metadata[COMPANY_COLUMN])
        samples = previous.get(SAMPLES_COLUMN, [])
        if metadata[OPTIONS_COLUMN] and metadata[OPTIONS_COLUMN] not in samples:
            samples = [*samples, metadata[OPTIONS_COLUMN]][-MAX_SAMPLES:]
        _append(path, {EVENT_COLUMN: "miss", KEY_COLUMN: key, **metadata,
                       COUNT_COLUMN: previous.get(COUNT_COLUMN, 0) + 1,
                       FIRST_COLUMN: previous.get(FIRST_COLUMN, now), LAST_COLUMN: now,
                       COMPANIES_COLUMN: sorted(companies), SAMPLES_COLUMN: samples})
    return True


def try_record(data, body):
    """Queue failures must not change an answer outcome."""
    try:
        return record(data, body)
    except (OSError, ValueError, KeyError, TypeError, TimeoutError):
        return False


def resolve(data, label):
    """Hide all hosts for a label until a new sighting reopens it."""
    key = normalized(_text(label, MAX_LABEL))
    if not key:
        raise ValueError("Resolve requires question text.")
    path = Path(data).resolve() / LOG_FILENAME
    with file_lock(path):
        _append(path, {EVENT_COLUMN: "resolve", KEY_COLUMN: key,
                       RESOLVED_COLUMN: datetime.now(timezone.utc).isoformat()})


def report(data):
    path = Path(data).resolve() / LOG_FILENAME
    with file_lock(path):
        rows, resolved = _state(path)
    groups = {}
    for (key, host), row in rows.items():
        if key in resolved:
            continue
        group = groups.setdefault(key, {KEY_COLUMN: key, LABEL_COLUMN: row[LABEL_COLUMN], COUNT_COLUMN: 0,
                                       HOSTS_COLUMN: [], COMPANIES_COLUMN: [], SAMPLES_COLUMN: [],
                                       FIRST_COLUMN: row[FIRST_COLUMN], LAST_COLUMN: row[LAST_COLUMN]})
        group[COUNT_COLUMN] += row[COUNT_COLUMN]
        group[HOSTS_COLUMN].append(host)
        group[COMPANIES_COLUMN] = sorted(set(group[COMPANIES_COLUMN]) | set(row[COMPANIES_COLUMN]))
        for sample in row[SAMPLES_COLUMN]:
            if sample not in group[SAMPLES_COLUMN]:
                group[SAMPLES_COLUMN].append(sample)
        group[FIRST_COLUMN] = min(group[FIRST_COLUMN], row[FIRST_COLUMN])
        group[LAST_COLUMN] = max(group[LAST_COLUMN], row[LAST_COLUMN])
    for group in groups.values():
        group[HOSTS_COLUMN].sort()
    return sorted(groups.values(), key=lambda row: (-row[COUNT_COLUMN], row[KEY_COLUMN]))
