"""Author: Yazad Madan. Reviewed dropdown wording shared only within an ATS vendor."""
import json
import re
from pathlib import Path

import answer_memory
import intent_layer
import miss_log
from shared_storage import atomic_json, file_lock

# Config
FILENAME = "dropdown_mappings.json"
SCHEMA_VERSION = 1
MAX_STORE_BYTES = 1024 * 1024
MAX_LABEL = 300
MAX_TEXT = 2000
LABEL, ANSWER, OPTION = "label", "answer", "option"
ROWS, VENDOR = "mappings", "vendor"
SELECT_TYPES = {"select", "select-one", "combobox", "radio"}
VENDOR_DOMAINS = {
    "workday": ("myworkdayjobs.com", "myworkdaysite.com"),
    "greenhouse": ("greenhouse.io",), "ashby": ("ashbyhq.com",),
    "icims": ("icims.com",), "successfactors": ("successfactors.com", "successfactors.eu"),
    "oraclecloud": ("oraclecloud.com",), "lever": ("lever.co",),
    "smartrecruiters": ("smartrecruiters.com",), "taleo": ("taleo.net",),
    "jobvite": ("jobvite.com",), "paylocity": ("paylocity.com",),
    "paycom": ("paycomonline.net",), "dayforce": ("dayforcehcm.com",),
    "ultipro": ("ultipro.com",), "adp": ("adp.com",),
}
HOST_PATTERN = re.compile(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}")
SELF_ID_CONTEXT = re.compile(r"\b(?:reserves|active duty|service member|uniformed services|religio\w*|marital status)\b", re.I)


def vendor_from_host(host):
    """Accept a hostname, never a URL or a suffix lookalike."""
    if not isinstance(host, str):
        return None
    host = host.lower().removesuffix(".")
    if len(host) > 253 or not HOST_PATTERN.fullmatch(host):
        return None
    for vendor, domains in VENDOR_DOMAINS.items():
        if any(host == domain or host.endswith("." + domain) for domain in domains):
            return vendor
    return None


def blocked(body):
    values = [body.get(LABEL, ""), *body.get("options", [])]
    return answer_memory.is_protected(body) or any(
        miss_log.BLOCKED.search(value) or SELF_ID_CONTEXT.search(value)
        for value in map(miss_log.normalized, values))


def stored_answer(service, body):
    value = service.company_answer(body)
    if value:
        return value, "company_kb"
    memory = answer_memory.load_memory(service.data)
    value = intent_layer.lookup(memory, body[LABEL])
    if value:
        return value, "intent"
    return answer_memory.lookup(memory, body[LABEL]), "answer_memory"


def _key(vendor, label, answer):
    return vendor, answer_memory.normalize_label(label), answer


def _valid(row):
    return (isinstance(row, dict) and isinstance(row.get(VENDOR), str) and row[VENDOR] in VENDOR_DOMAINS
            and all(isinstance(row.get(key), str) and row[key].strip() and len(row[key]) <= limit
                    for key, limit in ((LABEL, MAX_LABEL), (ANSWER, MAX_TEXT), (OPTION, MAX_TEXT)))
            and bool(answer_memory.normalize_label(row[LABEL]))
            and not blocked({LABEL: row[LABEL], "options": [row[ANSWER], row[OPTION]]}))


def load(data):
    path = Path(data) / FILENAME
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "author": "Yazad Madan", ROWS: []}
    with path.open("rb") as handle:
        raw = handle.read(MAX_STORE_BYTES + 1)
    if len(raw) > MAX_STORE_BYTES:
        raise ValueError("Dropdown mapping store is too large.")
    store = json.loads(raw)
    if (not isinstance(store, dict) or store.get("schema_version") != SCHEMA_VERSION
            or not isinstance(store.get(ROWS), list) or not all(_valid(row) for row in store[ROWS])):
        raise ValueError("Invalid dropdown mapping store.")
    keys = [_key(row[VENDOR], row[LABEL], row[ANSWER]) for row in store[ROWS]]
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate dropdown mapping keys.")
    return store


def lookup(store, vendor, label, answer):
    key = _key(vendor, label, answer)
    return next((row[OPTION] for row in store[ROWS]
                 if _key(row[VENDOR], row[LABEL], row[ANSWER]) == key), None)


def update(data, vendor, label, answer, option, previous=None):
    """Compare the reviewed option before replacing or removing a mapping."""
    row = {VENDOR: vendor, LABEL: label, ANSWER: answer, OPTION: "unused" if option is None else option}
    if not _valid(row):
        raise ValueError("Invalid or protected dropdown mapping.")
    path = Path(data) / FILENAME
    with file_lock(path):
        store = load(data)
        if lookup(store, vendor, label, answer) != previous:
            return False
        key = _key(vendor, label, answer)
        store[ROWS] = [row for row in store[ROWS] if _key(row[VENDOR], row[LABEL], row[ANSWER]) != key]
        if option is not None:
            row[OPTION] = option
            store[ROWS].append(row)
        store["author"] = "Yazad Madan"
        if len(json.dumps(store, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8")) > MAX_STORE_BYTES:
            raise ValueError("Dropdown mapping store is too large.")
        atomic_json(path, store)
        return True


def response(service, body, result):
    candidates = result.get("candidates", [])
    mapped = [None] * len(candidates)
    vendor = vendor_from_host(body.get("host"))
    if result.get("status") == "stored" and vendor and not blocked(body):
        store = load(service.data)
        mapped = [lookup(store, vendor, body[LABEL], candidate) for candidate in candidates]
        if mapped:
            mapped[0] = lookup(store, vendor, body[LABEL], result[ANSWER]) or mapped[0]
    return {**result, "mapped_options": mapped}


def review(service, body, pair, dry_run):
    """Return a mapping review instead of replacing the underlying stored answer."""
    if pair.get("type") not in SELECT_TYPES:
        return None
    context = {**body, LABEL: pair[LABEL]}
    value, _ = stored_answer(service, context)
    option = pair[ANSWER].strip()
    if not value or value == option:
        return None
    vendor = vendor_from_host(body.get("host"))
    if (not vendor or pair.get("manual") is not True or blocked(pair)
            or not _valid({VENDOR: vendor, LABEL: pair[LABEL], ANSWER: value, OPTION: option})
            or (pair.get("type") != "combobox" and option not in pair.get("options", []))):
        return {LABEL: pair[LABEL], "status": "skipped", "stored": False}
    previous = lookup(load(service.data), vendor, pair[LABEL], value)
    stored = (not dry_run and pair.get("mapping_answer") == value
              and "previous_option" in pair and pair["previous_option"] == previous
              and update(service.data, vendor, pair[LABEL], value, option, previous))
    return {LABEL: pair[LABEL], ANSWER: option, "status": "dropdown", "stored": stored,
            "mapping_answer": value, "previous_option": previous, VENDOR: vendor}
