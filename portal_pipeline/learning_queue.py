"""Author: Yazad Madan. One reviewed answer sheet for a bounded application batch."""
import json
import re
from pathlib import Path

import answer_memory
from browser_target import normalize_url
from question_corpus import normalize_label
from shared_storage import atomic_json, atomic_text, file_lock

# Config
QUEUE_FILENAME = "learning_queue.json"
SHEET_FILENAME = "learning_queue.md"
SCHEMA_VERSION = 1
QUESTIONS_KEY, JOBS_KEY = "questions", "jobs"
LABEL_KEY, TYPE_KEY, OPTIONS_KEY = "label", "type", "options"
ANSWER_KEY, KEY_KEY, COUNT_KEY = "answer", "key", "job_count"
HOST_KEY, RECORD_KEY = "portal_host", "record"
UNANSWERED_KEY, REPORTS_KEY = "unanswered", "reports"
PORTAL_KEY, JOB_KEY = "portal", "job"
VARIANTS_KEY, REQUIRED_KEY = "variants", "required"
BLOCKED_KEY, SCHEMA_KEY = "blocked", "schema_version"
VISIBLE_KEY = "visible"
URL_KEY, TARGET_KEY, DRY_KEY = "url", "target_id", "dry"
REPORT_PATH_KEY, FOLDER_KEY = "report_path", "folder"
AUTHOR_KEY, AUTHOR = "author", "Yazad Madan"
TYPE_TEXT = "text"
NEVER_LEARN_TYPES = {"checkbox", "password", "file", "signature"}
IMMIGRATION_REVIEW_LABEL = re.compile(r"work authori[sz]ation|legally authori[sz]ed|right to work|citizenship|nationality", re.I)
IMMIGRATION_WORK_LABEL = re.compile(r"authori[sz](?:ed|ation).{0,60}\bwork\b|\beligib(?:le|ility).{0,40}\bwork\b", re.I)
JOB_URLS_KEY = "job_urls"
PAGES_KEY, PAGES_SCANNED_KEY = "pages", "pages_scanned"
PAGES_NOT_REACHED_KEY = "pages_not_reached"
JOBS_SCANNED_KEY, JOBS_TOTAL_KEY = "jobs_scanned", "jobs_total"
COVERAGE_REASON_KEY = "coverage_reason"
CURRENT_PAGE_LIMIT = "Dry scans cover only the current page. Later pages and conditional questions require manual advancement and another scan."


def eligible(field, include_optional=False):
    from workday_run import IMMIGRATION_LABEL, UNLEARNABLE_LABELS
    label = str(field.get(LABEL_KEY) or "")
    return (bool(normalize_label(label)) and (include_optional or field.get(REQUIRED_KEY, True) is True or field.get(VISIBLE_KEY) is True)
            and field.get(RECORD_KEY) is None and not field.get(BLOCKED_KEY)
            and str(field.get(TYPE_KEY, "")).lower() not in NEVER_LEARN_TYPES
            and not answer_memory.is_protected(field)
            and not answer_memory.CONSENT_TERMS.search(label)
            and not answer_memory.SIGNATURE_TERMS.search(label)
            and normalize_label(label) not in UNLEARNABLE_LABELS and not IMMIGRATION_LABEL.search(label)
            and not IMMIGRATION_REVIEW_LABEL.search(label) and not IMMIGRATION_WORK_LABEL.search(label))


def collect(reports, memory):
    questions, jobs, seen, scanned, identities = {}, [], set(), set(), set()
    for index, report in enumerate(reports):
        job = str(report.get(JOB_KEY) or report.get(FOLDER_KEY) or report.get(REPORT_PATH_KEY) or index)
        url = normalize_url(report[URL_KEY]) if report.get(URL_KEY) else ""
        identity = url or job
        identities.add(identity)
        pages_scanned = report.get(PAGES_SCANNED_KEY, len(report.get(PAGES_KEY, [])))
        if pages_scanned:
            scanned.add(identity)
        jobs.append({key: report[key] for key in (FOLDER_KEY, REPORT_PATH_KEY, PORTAL_KEY, URL_KEY, TARGET_KEY, DRY_KEY) if key in report})
        for field in report.get(UNANSWERED_KEY, []):
            key = normalize_label(field.get(LABEL_KEY))
            if not eligible(field, include_optional=report.get(DRY_KEY) is True) or key in memory[answer_memory.ANSWERS_KEY]:
                continue
            question = questions.setdefault(key, {KEY_KEY: key, LABEL_KEY: field[LABEL_KEY], ANSWER_KEY: "",
                                                  COUNT_KEY: 0, JOBS_KEY: [], VARIANTS_KEY: [], JOB_URLS_KEY: []})
            variant = {HOST_KEY: field.get(HOST_KEY, ""), TYPE_KEY: field.get(TYPE_KEY, TYPE_TEXT),
                       OPTIONS_KEY: field.get(OPTIONS_KEY, [])}
            if variant not in question[VARIANTS_KEY]:
                question[VARIANTS_KEY].append(variant)
            if (identity, key) not in seen:
                question[COUNT_KEY] += 1
                question[JOBS_KEY].append(job)
                seen.add((identity, key))
            if url and url not in question[JOB_URLS_KEY]:
                question[JOB_URLS_KEY].append(url)
    return {SCHEMA_KEY: SCHEMA_VERSION, AUTHOR_KEY: AUTHOR, JOBS_KEY: jobs,
            JOBS_SCANNED_KEY: len(scanned), JOBS_TOTAL_KEY: len(identities), PAGES_NOT_REACHED_KEY: None,
            QUESTIONS_KEY: sorted(questions.values(), key=lambda question: (-question[COUNT_KEY], question[KEY_KEY]))}


def write_queue(reports, data_dir=answer_memory.DATA_DIR):
    directory = Path(data_dir)
    with file_lock(directory.resolve() / QUEUE_FILENAME):
        queue = collect(reports, answer_memory.load_memory(data_dir))
        atomic_json(directory / QUEUE_FILENAME, queue)
        lines = ["# Batch learning review", "", f"Author: {AUTHOR}", "",
                 f"Jobs scanned: {queue[JOBS_SCANNED_KEY]} / {queue[JOBS_TOTAL_KEY]}",
                 "Pages not reached: unknown. " + CURRENT_PAGE_LIMIT, "",
                 "Fill answer values in learning_queue.json, then import that file. Blank answers remain pending.", ""]
        if queue[QUESTIONS_KEY]:
            lines.extend(["## Prefill differences", "", "Conflicts stay in per-job reports. Only new unanswered questions appear here.", ""])
        for question in queue[QUESTIONS_KEY]:
            lines.extend([f"{question[COUNT_KEY]} job(s): {question[LABEL_KEY]}", "Answer: ____________________"])
            lines.extend(f"  Job URL: {url}" for url in question[JOB_URLS_KEY])
            for variant in question[VARIANTS_KEY]:
                options = "; ".join(str(option) for option in variant[OPTIONS_KEY])
                lines.append(f"  {variant[HOST_KEY]} ({variant[TYPE_KEY]}): {options or 'Free text'}")
            lines.append("")
        atomic_text(directory / SHEET_FILENAME, "\n".join(lines))
    return queue


def import_answers(path, data_dir=answer_memory.DATA_DIR):
    """Accept reviewed answers only for currently queued, reusable questions."""
    directory = Path(data_dir)
    incoming = json.loads(Path(path).read_text(encoding="utf-8"))
    with file_lock(directory.resolve() / QUEUE_FILENAME):
        queue = json.loads((directory / QUEUE_FILENAME).read_text(encoding="utf-8"))
        if not isinstance(incoming, dict) or incoming.get(SCHEMA_KEY) != SCHEMA_VERSION or not isinstance(incoming.get(QUESTIONS_KEY), list):
            raise ValueError("Expected a learning queue with a questions list.")
        allowed = {question[KEY_KEY]: question for question in queue[QUESTIONS_KEY]}
        updates = []
        seen = set()
        for entry in incoming[QUESTIONS_KEY]:
            if not isinstance(entry, dict):
                raise ValueError("Each reviewed question must be an object.")
            label = str(entry.get(LABEL_KEY) or "")
            key = normalize_label(label)
            value = entry.get(ANSWER_KEY, "")
            if not value:
                continue
            if key in seen or key not in allowed or not isinstance(value, str) or not eligible({LABEL_KEY: label}):
                raise ValueError("Answer is duplicated, protected, or absent from the current learning queue.")
            question = allowed[key]
            if not eligible(question) or not value.strip() or len(value.strip()) > answer_memory.MAX_ANSWER:
                raise ValueError("Invalid reviewed answer.")
            for variant in question[VARIANTS_KEY]:
                if not eligible({LABEL_KEY: label, **variant}):
                    raise ValueError("Protected question variant cannot be imported.")
                options = variant[OPTIONS_KEY]
                if options and value.strip().casefold() not in {str(option).strip().casefold() for option in options}:
                    raise ValueError(f"Answer does not match every job's options for {label!r}.")
            updates.append((question[LABEL_KEY], value))
            seen.add(key)
        stored = answer_memory.update_memory(lambda data: sum(answer_memory.remember(
            data, label, value, source=answer_memory.SOURCE_BATCH_REVIEW) for label, value in updates), data_dir)
    return stored, queue[JOBS_KEY]
