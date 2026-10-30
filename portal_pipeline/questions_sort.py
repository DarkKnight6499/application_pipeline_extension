"""Author: Yazad Madan. Sort local page captures and promote only nonconflicting answers."""
import argparse
import contextlib
import hashlib
import json
import sys
import unicodedata
from pathlib import Path

import answer_memory
import assist_jobs
import intent_layer
import page_questions
import question_alias
from assist_api import AssistService
from shared_storage import atomic_json, file_lock

# Config
DATA_DIR = answer_memory.DATA_DIR
STATE_FILENAME = "questions_processed.json"
CONFLICTS_FILENAME = "conflicts.json"
SCHEMA_VERSION = 1
AUTHOR = "Yazad Madan"
SECTIONS = ("AGREE", "CONFLICT", "SINGLE", "SENSITIVE")
LABEL, ANSWER, COMPANY, HOST = "label", "answer", "company", "host"
LABELS, ANSWERS, ROWS = "labels", "answers", "_rows"
KEY, STATUS, RESOLVED = "key", "status", "resolved"
FIRST, LAST = "first_seen", "last_seen"
PROCESSED, RESOLUTIONS = "processed", "resolutions"
QUESTION_LABEL = "question_label"
SCOPE = "scope"
SCOPES, CONFLICTS = "scopes", "conflicts"
TS, SENSITIVE, TRUNCATED = "ts", "sensitive", "truncated"
STORED, COMPANIES = "stored_answers", "companies"
COMPANY_COUNT, SIGHTING_COUNT = "company_count", "sighting_count"
CAPTURE_COUNT = "capture_count"
NORMALIZED_ANSWER = "normalized_answer"


def normalized_text(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def normalized_answer(value):
    text = normalized_text(value)
    if text in {word.casefold() for word in intent_layer.YES_WORDS}:
        return intent_layer.YES.casefold()
    if text in {word.casefold() for word in intent_layer.NO_WORDS}:
        return intent_layer.NO.casefold()
    return text


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=True, sort_keys=True).encode("utf-8")).hexdigest()


def related(left, right):
    return (answer_memory.normalize_label(left) == answer_memory.normalize_label(right)
            or question_alias.similarity(left, right) >= question_alias.MIN_SIMILARITY)


def context(row, label=None):
    return {LABEL: label or row[LABEL], HOST: row[HOST], "url": "https://" + row[HOST] + "/",
            "company_hint": row[COMPANY]}


def company_key(row):
    return normalized_text(row[COMPANY] or row[HOST])


def load_state(data):
    path = Path(data) / STATE_FILENAME
    if not path.exists():
        return {"author": AUTHOR, "schema_version": SCHEMA_VERSION, PROCESSED: {}, RESOLUTIONS: {}}
    state = json.loads(path.read_text(encoding="utf-8"))
    if (state.get("schema_version") != SCHEMA_VERSION or not isinstance(state.get(PROCESSED), dict)
            or not isinstance(state.get(RESOLUTIONS), dict)):
        raise ValueError("Unsupported questions processed state.")
    return state


@contextlib.contextmanager
def locked(service, rows):
    directories = {service.company_scope(context(row))[0] for row in rows}
    directories.update(path.parent for path in (service.data / "company_kb").glob("*/answer_memory.json"))
    with file_lock(service.data / STATE_FILENAME), contextlib.ExitStack() as stack:
        for directory in sorted(directories):
            stack.enter_context(answer_memory.memory_lock(directory))
        stack.enter_context(answer_memory.memory_lock(service.data))
        yield


def sightings_digest(group):
    return digest(group[ROWS])


def matching_entries(memory, labels):
    intents = {answer_memory.normalize_label(intent_layer.key_for(intent))
               for label in labels if (intent := intent_layer.classify(label))}
    return [entry for key, entry in memory[ANSWERS].items()
            if key in intents or any(related(label, entry.get(QUESTION_LABEL, entry.get(LABEL, ""))) for label in labels)]


def stored_entries(service, group):
    entries = [{SCOPE: "global", **entry} for entry in matching_entries(answer_memory.load_memory(service.data), group[LABELS])]
    directories = {service.company_scope(context(row))[0] for row in group[ROWS]}
    directories.update(path.parent for path in (service.data / "company_kb").glob("*/answer_memory.json"))
    for directory in sorted(directories):
        entries.extend({SCOPE: directory.name, **entry}
                       for entry in matching_entries(answer_memory.load_memory(directory), group[LABELS]))
    seen = set()
    for row in group[ROWS]:
        identity = row[HOST], row[COMPANY]
        if identity in seen:
            continue
        seen.add(identity)
        reference = question_alias.reference_answers(service, context(row))
        entries.extend({SCOPE: "reference:" + (row[COMPANY] or row[HOST]), **entry}
                       for entry in reference.values() if any(related(label, entry[LABEL]) for label in group[LABELS]))
    return sorted(entries, key=lambda entry: (entry[SCOPE], entry.get(LABEL, ""), entry[ANSWER]))


def build_report(service, rows, state):
    groups = []
    for row in sorted(rows, key=lambda row: (answer_memory.normalize_label(row[LABEL]), row[TS], row[COMPANY], row[ANSWER])):
        # Complete linkage prevents a wording bridge from joining different meanings.
        group = next((group for group in groups if all(related(row[LABEL], label) for label in group[LABELS])), None)
        if group is None:
            group = {LABELS: [], ROWS: []}
            groups.append(group)
        if row[LABEL] not in group[LABELS]:
            group[LABELS].append(row[LABEL])
        group[ROWS].append(row)
    for group in groups:
        group[LABELS].sort()
        group[KEY] = answer_memory.normalize_label(group[LABELS][0])
        group[LABEL] = group[LABELS][0]
        answers = {}
        companies = {normalized_text(row[COMPANY]) for row in group[ROWS] if row[COMPANY].strip()}
        for row in group[ROWS]:
            key = normalized_answer(row[ANSWER])
            answer = answers.setdefault(key, {ANSWER: row[ANSWER], NORMALIZED_ANSWER: key, COMPANIES: {}})
            identity = company_key(row)
            names = answer[COMPANIES].setdefault(identity, set())
            names.add(row[COMPANY] or row[HOST])
        group[ANSWERS] = [{**answer, COMPANIES: sorted({name for names in answer[COMPANIES].values() for name in names}),
                           COMPANY_COUNT: len(answer[COMPANIES])} for _, answer in sorted(answers.items())]
        group[COMPANY_COUNT] = len(companies)
        group[SIGHTING_COUNT] = len({company_key(row) for row in group[ROWS]})
        group[CAPTURE_COUNT] = len(group[ROWS])
        group[FIRST] = min(row[TS] for row in group[ROWS])
        group[LAST] = max(row[TS] for row in group[ROWS])
        group[TRUNCATED] = any(row.get(TRUNCATED, False) for row in group[ROWS])
        group[STORED] = [{SCOPE: entry[SCOPE], LABEL: entry.get(QUESTION_LABEL, entry.get(LABEL, "")),
                                    ANSWER: entry[ANSWER]} for entry in stored_entries(service, group)]
        group[SENSITIVE] = any(row.get(SENSITIVE, False) or page_questions.sensitive(row) for row in group[ROWS])
        stored = {normalized_answer(entry[ANSWER]) for entry in group[STORED]}
        conflicts = len(answers) > 1 or bool(stored - set(answers))
        group[STATUS] = "SENSITIVE" if group[SENSITIVE] else "CONFLICT" if conflicts else "AGREE" if len(companies) >= 2 else "SINGLE"
        resolution = state[RESOLUTIONS].get(group[KEY], {})
        global_answers = [normalized_answer(entry[ANSWER]) for entry in group[STORED] if entry[SCOPE] == "global"]
        group[RESOLVED] = bool(not group[SENSITIVE] and resolution.get("sightings") == sightings_digest(group)
                               and global_answers and all(digest(value) == resolution.get("answer_digest") for value in global_answers))
    # Distinct questions can share an intent key in the reviewed-answer store.
    for group in groups:
        intents = {intent_layer.classify(label) for label in group[LABELS]} - {None}
        values = {normalized_answer(answer[ANSWER]) for answer in group[ANSWERS]}
        if not group[SENSITIVE] and any(
                intents & ({intent_layer.classify(label) for label in other[LABELS]} - {None})
                and values != {normalized_answer(answer[ANSWER]) for answer in other[ANSWERS]}
                for other in groups if other is not group and not other[SENSITIVE]):
            group[STATUS] = "CONFLICT"
    return sorted(groups, key=lambda group: group[KEY])


def report(service):
    with assist_jobs.JOB_SLOTS:
        return _report(service)


def _report(service):
    with checked_report(service) as (groups, state):
        write_conflicts(service, groups)
    return {section: [{key: value for key, value in group.items() if key != ROWS}
                      for group in groups if group[STATUS] == section] for section in SECTIONS}


@contextlib.contextmanager
def checked_report(service):
    while True:
        rows = page_questions.read(service.data)
        state = load_state(service.data)
        groups = build_report(service, rows, state)
        with locked(service, rows), file_lock(service.data / page_questions.FILENAME):
            # Retry outside the write locks if captures, resolutions, or stores changed during sorting.
            if (page_questions._read(service.data / page_questions.FILENAME) != rows
                    or load_state(service.data) != state
                    or any(group[STORED] != stored_values(service, group) for group in groups)):
                continue
            yield groups, state
            return


def stored_values(service, group):
    return [{SCOPE: entry[SCOPE], LABEL: entry.get(QUESTION_LABEL, entry.get(LABEL, "")), ANSWER: entry[ANSWER]}
            for entry in stored_entries(service, group)]


def write_conflicts(service, groups):
    conflicts = []
    for group in groups:
        if group[STATUS] != "CONFLICT":
            continue
        answers = {}
        intents = {intent_layer.classify(label) for label in group[LABELS]} - {None}
        related_groups = [other for other in groups if other is group or (not other[SENSITIVE]
                          and intents & ({intent_layer.classify(label) for label in other[LABELS]} - {None}))]
        for other in related_groups:
            for value in other[ANSWERS]:
                entry = answers.setdefault(normalized_answer(value[ANSWER]),
                                           {ANSWER: value[ANSWER], COMPANIES: set(), SCOPES: set()})
                entry[COMPANIES].update(value[COMPANIES])
            for value in other[STORED]:
                entry = answers.setdefault(normalized_answer(value[ANSWER]),
                                           {ANSWER: value[ANSWER], COMPANIES: set(), SCOPES: set()})
                entry[SCOPES].add(value[SCOPE])
                if value[SCOPE].startswith("reference:"):
                    entry[COMPANIES].add(value[SCOPE].removeprefix("reference:"))
                else:
                    entry[COMPANIES].update(row[COMPANY] or row[HOST] for row in other[ROWS]
                                            if service.company_scope(context(row))[0].name == value[SCOPE])
        conflicts.append({LABEL: group[LABEL], LABELS: group[LABELS], RESOLVED: group[RESOLVED],
                          ANSWERS: [{ANSWER: entry[ANSWER], COMPANIES: sorted(entry[COMPANIES]),
                                     SCOPES: sorted(entry[SCOPES])} for _, entry in sorted(answers.items())]})
    atomic_json(service.data / CONFLICTS_FILENAME,
                {"author": AUTHOR, "schema_version": SCHEMA_VERSION, CONFLICTS: conflicts})


def save(service, directory, labels, answer, scoped, source, replace=False):
    def update(memory):
        wrote = False
        for label in labels:
            exact = answer_memory.lookup(memory, label)
            if (replace and not scoped and intent_layer.classify(label) and exact is not None
                    and normalized_answer(exact) != normalized_answer(answer)):
                wrote = bool(service.save_reviewed(memory, label, answer, True, source=source)) or wrote
            current = answer_memory.lookup(memory, label) if scoped else intent_layer.lookup(memory, label) or answer_memory.lookup(memory, label)
            if current is not None and normalized_answer(current) == normalized_answer(answer):
                continue
            if current is not None and not replace:
                raise ValueError("Stored answer changed. Report again before promoting.")
            saved = service.save_reviewed(memory, label, answer, scoped, source=source)
            if not saved:
                raise ValueError("Question cannot be stored in answer memory.")
            wrote = True
        return wrote
    service.update_reviewed(update, directory, scoped)


def promotion_digest(group):
    return digest({"sightings": sightings_digest(group), "stored": group[STORED]})


def promote(service):
    with assist_jobs.JOB_SLOTS:
        return _promote(service)


def _promote(service):
    rows = page_questions.read(service.data)
    candidates = build_report(service, rows, load_state(service.data))
    summary = {"shared": 0, "company": 0, "conflict": 0, "sensitive": 0, "unchanged": 0}
    completed = set()
    for candidate in candidates:
        with checked_report(service) as (groups, state):
            group = next((group for group in groups if candidate[LABEL] in group[LABELS]), None)
            if group is None or group[KEY] in completed:
                continue
            completed.add(group[KEY])
            status = group[STATUS]
            if group[RESOLVED]:
                summary["unchanged"] += 1
                continue
            if status in ("CONFLICT", "SENSITIVE"):
                summary[status.lower()] += 1
                continue
            if state[PROCESSED].get(group[KEY]) == promotion_digest(group):
                summary["unchanged"] += 1
                continue
            answer = group[ANSWERS][0][ANSWER]
            if status == "AGREE":
                save(service, service.data, group[LABELS], answer, False, "questions-promoted")
                summary["shared"] += 1
            else:
                for directory in sorted({service.company_scope(context(row))[0] for row in group[ROWS]}):
                    save(service, directory, group[LABELS], answer, True, "questions-single")
                summary["company"] += 1
            group[STORED] = stored_values(service, group)
            state[PROCESSED][group[KEY]] = promotion_digest(group)
            state["author"] = AUTHOR
            atomic_json(service.data / STATE_FILENAME, state)
    with checked_report(service) as (groups, state):
        write_conflicts(service, groups)
    return summary


def resolve(service, label, answer):
    with assist_jobs.JOB_SLOTS:
        return _resolve(service, label, answer)


def _resolve(service, label, answer):
    if (not isinstance(answer, str) or not answer.strip() or len(answer) > page_questions.MAX_ANSWER
            or not isinstance(label, str) or not label.strip() or len(label) > page_questions.MAX_LABEL):
        raise ValueError("Resolve requires bounded question and answer strings.")
    with checked_report(service) as (all_groups, state):
        groups = [group for group in all_groups if all(related(label, variant) for variant in group[LABELS])]
        if len(groups) != 1 or groups[0][SENSITIVE] or page_questions.sensitive({LABEL: label}):
            raise ValueError("Resolve requires one nonsensitive captured group. Sensitive groups remain manual.")
        group = groups[0]
        scoped = {}
        for row in group[ROWS]:
            directory = service.company_scope(context(row))[0]
            scoped.setdefault(directory, {})[normalized_answer(row[ANSWER])] = row[ANSWER]
        if any(len(values) > 1 for values in scoped.values()):
            raise ValueError("Multiple answers within one company require manual company review.")
        # Validate every company write before changing any store.
        for directory, values in scoped.items():
            value = next(iter(values.values()))
            for entry in matching_entries(answer_memory.load_memory(directory), group[LABELS]):
                if normalized_answer(entry[ANSWER]) != normalized_answer(value):
                    raise ValueError("Company answer changed. Review that company manually.")
        for directory, values in scoped.items():
            value = next(iter(values.values()))
            if normalized_answer(value) != normalized_answer(answer):
                save(service, directory, group[LABELS], value, True, "questions-single")
        labels = sorted(set(group[LABELS] + [entry[LABEL] for entry in group[STORED]
                                          if entry[SCOPE] == "global" and entry[LABEL] and not entry[LABEL].startswith("intent:")]))
        save(service, service.data, labels, answer.strip(), False, "questions-promoted", replace=True)
        state[RESOLUTIONS][group[KEY]] = {"sightings": sightings_digest(group),
                                        "answer_digest": digest(normalized_answer(answer))}
        state["author"] = AUTHOR
        atomic_json(service.data / STATE_FILENAME, state)
    _report(service)
    return {"resolved": 1}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA_DIR)
    commands = parser.add_subparsers(dest="command", required=True)
    reporting = commands.add_parser("report")
    reporting.add_argument("--json", action="store_true")
    commands.add_parser("promote")
    resolving = commands.add_parser("resolve")
    resolving.add_argument("--label", required=True)
    resolving.add_argument("--answer", required=True)
    args = parser.parse_args(argv)
    try:
        service = AssistService(args.data, token="questions-sort-local")
        if args.command == "report":
            result = report(service)
            if args.json:
                print(json.dumps(result, ensure_ascii=True, sort_keys=True))
            else:
                for section, groups in result.items():
                    print("SENSITIVE (captured, never auto-filled)" if section == "SENSITIVE" else section)
                    for group in groups:
                        print(json.dumps(group, ensure_ascii=True, sort_keys=True))
        else:
            result = promote(service) if args.command == "promote" else resolve(service, args.label, args.answer)
            print(json.dumps(result, sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError, TimeoutError):
        print("Cannot sort questions. Check local capture and answer stores; no values are printed in errors.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
