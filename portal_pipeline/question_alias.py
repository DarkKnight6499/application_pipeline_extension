"""Author: Yazad Madan. Explicitly reviewed question aliases with conservative wording checks."""
import argparse
import hashlib
import json
import re
from pathlib import Path

import answer_memory
import intent_layer
import miss_log
from shared_storage import atomic_json, file_lock

# Config
FILENAME = "question_aliases.json"
SCHEMA_VERSION = 1
AUTHOR = "Yazad Madan"
MIN_SIMILARITY = 0.85
MIN_CONTENT_TOKENS = 2
MAX_LABEL = 300
LABEL_COLUMN, ANSWER_COLUMN = "label", "answer"
HOST_COLUMN, URL_COLUMN, COMPANY_COLUMN = "host", "url", "company_hint"
OPTIONS_COLUMN, PREVIOUS_COLUMN = "options", "previous_answer"
PORTALS_COLUMN, QUESTIONS_COLUMN, TEXT_COLUMN, KEY_COLUMN = "portals", "questions", "text", "key"
KB_COMPANY_COLUMN = "company"
QUESTION_LABEL_COLUMN = "question_label"
ALIASES_COLUMN, ANSWERS_COLUMN = "aliases", "answers"
TARGET_COLUMN, DIGEST_COLUMN = "target", "answer_digest"
KIND_COLUMN = "target_kind"
SIMILAR_COLUMN, SCOPE_COLUMN, OPT_IN_COLUMN = "similar_to", "similar_scope", "use_alias"
COMPANY_DIRECTORY = "company_kb"
SCOPE_PATTERN = re.compile(r"[a-f0-9]{64}")
POLITE_PREFIXES = {"please", "kindly", "briefly"}
QUESTION_PREFIXES = tuple(phrase.split() for phrase in (
    "tell us about your", "tell us about the", "tell us about", "what is your", "what are your",
    "what is the", "what are the", "describe your", "describe the", "describe a", "describe an",
    "provide your", "provide the", "share your", "describe", "provide", "share"))
EXTRA_BLOCKED = re.compile(r"\b(?:religio\w*|marital status|reserves|active duty|service member|uniformed services)\b", re.I)


def blocked(field):
    context = [field.get(LABEL_COLUMN, ""), *field.get(OPTIONS_COLUMN, [])]
    return answer_memory.is_protected(field) or any(
        miss_log.BLOCKED.search(miss_log.normalized(text)) or EXTRA_BLOCKED.search(text) for text in context)


def similarity(left, right):
    """Only presentation words may differ; content words must retain their order."""
    if blocked({LABEL_COLUMN: left}) or blocked({LABEL_COLUMN: right}):
        return 0
    tokens = [miss_log.normalized(text).split() for text in (left, right)]
    if tokens[0] == tokens[1] and tokens[0]:
        return 1
    content = []
    for words in tokens:
        while words and words[0] in POLITE_PREFIXES:
            words = words[1:]
        prefix = next((prefix for prefix in QUESTION_PREFIXES if words[:len(prefix)] == prefix), [])
        content.append(words[len(prefix):])
    if min(map(len, content)) < MIN_CONTENT_TOKENS or content[0] != content[1]:
        return 0
    return len(set(content[0]) & set(content[1])) / len(set(content[0]) | set(content[1]))


def previous_answer(service, body, memory, scoped=True):
    label = body[LABEL_COLUMN]
    if scoped:
        previous = answer_memory.lookup(memory, label) or service.company_answer(body, include_local=False)
        global_memory = answer_memory.load_memory(service.data)
    else:
        previous = None
        global_memory = memory
    return (previous or intent_layer.lookup(global_memory, label) or answer_memory.lookup(global_memory, label)
            or lookup(service, body))


def accept_reviewed(service, body, memory, scoped):
    label, answer = body[LABEL_COLUMN], body[ANSWER_COLUMN].strip()
    previous = previous_answer(service, body, memory, scoped)
    if previous is not None and previous != answer and body.get(PREVIOUS_COLUMN) != previous:
        raise ValueError("Stored answer changed. Review it before replacing it.")
    saved = service.save_reviewed(memory, label, answer, scoped)
    if saved and not scoped and len(label) <= MAX_LABEL:
        intent = intent_layer.classify(label)
        if intent:
            key = answer_memory.normalize_label(intent_layer.key_for(intent))
            memory[ANSWERS_COLUMN][key][QUESTION_LABEL_COLUMN] = label
    return saved


def validate_pair(pair):
    if OPT_IN_COLUMN in pair and not isinstance(pair[OPT_IN_COLUMN], bool):
        raise ValueError("Alias selection must be a boolean.")
    if SIMILAR_COLUMN in pair and (not isinstance(pair[SIMILAR_COLUMN], str) or
                                   not pair[SIMILAR_COLUMN].strip() or len(pair[SIMILAR_COLUMN]) > MAX_LABEL):
        raise ValueError("Similar question must be a bounded nonempty string.")
    if SCOPE_COLUMN in pair and pair[SCOPE_COLUMN] not in ("company", "global"):
        raise ValueError("Invalid similar question scope.")


def load(directory):
    path = Path(directory) / FILENAME
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "author": AUTHOR, ALIASES_COLUMN: {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != SCHEMA_VERSION or not isinstance(data.get(ALIASES_COLUMN), dict):
        raise ValueError("Unsupported question alias store.")
    data["author"] = AUTHOR
    return data


def fingerprint(answer):
    return hashlib.sha256(answer.strip().encode("utf-8")).hexdigest()


def reference_answers(service, body):
    """Read the same company JSON contract as the helper without invoking a writer."""
    directory = service.reference / COMPANY_DIRECTORY
    company = body.get(COMPANY_COLUMN, "").strip()
    slug = re.sub(r"[^a-z0-9]+", "_", company.lower()).strip("_")
    if (not company or not (directory / (slug + ".json")).is_file()) and body.get(HOST_COLUMN):
        companies = set()
        for path in directory.glob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            if any(portal.get(HOST_COLUMN, "").lower() == body[HOST_COLUMN].lower() for portal in data.get(PORTALS_COLUMN, [])):
                companies.add(data.get(KB_COMPANY_COLUMN, ""))
        if len(companies) == 1:
            company = companies.pop()
    slug = re.sub(r"[^a-z0-9]+", "_", company.lower()).strip("_")
    path = directory / (slug + ".json")
    if not company or not path.is_file():
        return {}
    answers = {}
    for row in json.loads(path.read_text(encoding="utf-8")).get(QUESTIONS_COLUMN, []):
        label, answer = row.get(TEXT_COLUMN, row.get(KEY_COLUMN, "")), row.get(ANSWER_COLUMN)
        if not isinstance(label, str) or not isinstance(answer, str) or not label.strip() or not answer.strip():
            continue
        key = answer_memory.normalize_label(label)
        if key in answers:
            return {}
        answers[key] = {LABEL_COLUMN: label, ANSWER_COLUMN: answer}
    return answers


def _resolve(service, directory, memory, body):
    label = body[LABEL_COLUMN]
    key = answer_memory.normalize_label(label)
    row = load(directory)[ALIASES_COLUMN].get(key)
    if not isinstance(row, dict) or key in memory[ANSWERS_COLUMN]:
        return None
    target = memory[ANSWERS_COLUMN].get(row.get(TARGET_COLUMN), {})
    if not target and row.get(KIND_COLUMN) == "reference":
        target = reference_answers(service, body).get(row.get(TARGET_COLUMN), {})
    question = target.get(QUESTION_LABEL_COLUMN, target.get(LABEL_COLUMN, ""))
    answer = target.get(ANSWER_COLUMN, "")
    if (not answer or similarity(label, question) < MIN_SIMILARITY or
            row.get(DIGEST_COLUMN) != fingerprint(answer)):
        return None
    return answer


def lookup(service, body):
    if blocked(body):
        return None
    directories = []
    if body.get(HOST_COLUMN) and body.get(URL_COLUMN):
        directories.append(service.company_scope(body)[0])
    directories.append(service.data)
    for directory in directories:
        memory = answer_memory.load_memory(directory)
        # Exact scoped answers retain precedence over global aliases.
        if answer_memory.lookup(memory, body[LABEL_COLUMN]):
            return None
        value = _resolve(service, directory, memory, body)
        if value:
            return value
    return None


def candidate(service, directory, memory, pair, body):
    if blocked(pair):
        return None
    key = answer_memory.normalize_label(pair[LABEL_COLUMN])
    matches = []
    reference = {key: row for key, row in reference_answers(service, body).items() if key not in memory[ANSWERS_COLUMN]}
    for scope, kind, store, rows in (("company", "memory", directory, memory[ANSWERS_COLUMN]),
                                    ("company", "reference", directory, reference),
                                    ("global", "memory", service.data, answer_memory.load_memory(service.data)[ANSWERS_COLUMN])):
        for target, entry in rows.items():
            label = entry.get(QUESTION_LABEL_COLUMN, entry.get(LABEL_COLUMN, ""))
            answer = entry.get(ANSWER_COLUMN, "")
            if (target == key or answer_memory.normalize_label(label) == key or not answer or
                    len(label) > MAX_LABEL or similarity(pair[LABEL_COLUMN], label) < MIN_SIMILARITY):
                continue
            matches.append({SIMILAR_COLUMN: label, SCOPE_COLUMN: scope, TARGET_COLUMN: target,
                            "directory": store, ANSWER_COLUMN: answer, KIND_COLUMN: kind})
    if len(matches) != 1 or matches[0][ANSWER_COLUMN] != pair[ANSWER_COLUMN].strip():
        return None
    # A direct answer in either scope must not conflict with the proposed link.
    for rows in (memory, answer_memory.load_memory(service.data)):
        direct = answer_memory.lookup(rows, pair[LABEL_COLUMN])
        if direct is not None:
            return None
    return matches[0]


def review(service, body, memory, pair, dry_run, store, previous):
    """Return review metadata and whether this row is handled as an alias."""
    directory = service.company_scope(body)[0]
    match = candidate(service, directory, memory, pair, body) if previous in (None, pair[ANSWER_COLUMN].strip()) else None
    metadata = {key: match[key] for key in (SIMILAR_COLUMN, SCOPE_COLUMN)} if match else {}
    if not pair.get(OPT_IN_COLUMN) or dry_run:
        return metadata, False
    metadata.update(stored=False, alias_status="refused")
    if (not store or not match or pair.get(SIMILAR_COLUMN) != match[SIMILAR_COLUMN] or
            pair.get(SCOPE_COLUMN) != match[SCOPE_COLUMN]):
        return metadata, True
    path = match["directory"] / FILENAME
    key = answer_memory.normalize_label(pair[LABEL_COLUMN])
    row = {LABEL_COLUMN: pair[LABEL_COLUMN], TARGET_COLUMN: match[TARGET_COLUMN],
           SIMILAR_COLUMN: match[SIMILAR_COLUMN], DIGEST_COLUMN: fingerprint(match[ANSWER_COLUMN]), KIND_COLUMN: match[KIND_COLUMN]}
    with file_lock(path):
        aliases = load(match["directory"])
        previous = aliases[ALIASES_COLUMN].get(key)
        if previous is not None and previous != row:
            return metadata, True
        aliases[ALIASES_COLUMN][key] = row
        atomic_json(path, aliases)
    metadata.update(stored=True, alias_status="stored")
    return metadata, True


def scope_directory(data, scope):
    if scope == "global":
        return data
    if not SCOPE_PATTERN.fullmatch(scope):
        raise ValueError("Scope must be global or a company directory hash from list.")
    directory = (data / COMPANY_DIRECTORY / scope).resolve()
    if not directory.is_relative_to(data.resolve()):
        raise ValueError("Alias scope escapes the data directory.")
    return directory


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=answer_memory.DATA_DIR, help="Assist data directory")
    parser.add_argument("--scope", help="global or a company directory hash from list")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List alias wording and targets, without answer values")
    remove = commands.add_parser("remove", help="Remove one alias; the stored target answer remains")
    remove.add_argument("question")
    args = parser.parse_args(argv)
    data = args.data.resolve()
    try:
        if args.command == "list":
            scopes = [args.scope] if args.scope else ["global", *sorted(
                path.parent.name for path in (data / COMPANY_DIRECTORY).glob(f"*/{FILENAME}"))]
            rows = []
            for scope in scopes:
                directory = scope_directory(data, scope)
                rows.extend({"scope": scope, LABEL_COLUMN: row[LABEL_COLUMN], SIMILAR_COLUMN: row[SIMILAR_COLUMN]}
                            for row in load(directory)[ALIASES_COLUMN].values())
            print(json.dumps(rows, indent=2, ensure_ascii=True))
        else:
            if not args.scope:
                raise ValueError("Removal requires --scope from list.")
            directory = scope_directory(data, args.scope)
            with file_lock(directory / FILENAME):
                aliases = load(directory)
                removed = aliases[ALIASES_COLUMN].pop(answer_memory.normalize_label(args.question), None)
                if removed is not None:
                    atomic_json(directory / FILENAME, aliases)
            print("Removed alias." if removed is not None else "Alias not found.")
            return 0 if removed is not None else 1
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
