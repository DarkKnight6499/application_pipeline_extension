"""Author: Yazad Madan. Scan a bounded queue of existing tabs before any live fill."""
import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import apply as application
import batch_apply
import failure_telemetry as telemetry
import learning_queue as learning
import workday_run
from browser_target import normalize_url

# Config
DEFAULT_MAX_JOBS = 10
SCAN_WORKERS = 1
RUNS_DIR = batch_apply.RUNS_DIR
REPORT_PREFIX = "dry_scan"
UNSUPPORTED_PORTAL = "unsupported"
LINK_KEY = "link"
CURRENT_KEY = "current"
SCAN_ONLY_KEY = batch_apply.SCAN_ONLY_KEY
BASE_REPORT = workday_run.RunReport


class ScanReport(BASE_REPORT):
    def record_unanswered(self, fields, url):
        entries = []
        for field in fields:
            if field.get(CURRENT_KEY) not in ("", False, None) or not learning.eligible(field, include_optional=True):
                continue
            options = [option.get(learning.LABEL_KEY, "") if isinstance(option, dict) else option
                       for option in field.get(learning.OPTIONS_KEY, [])]
            entries.append({learning.LABEL_KEY: telemetry.clean_text(field[learning.LABEL_KEY], workday_run.report_secrets(), workday_run.QUEUE_LABEL_LIMIT),
                            learning.TYPE_KEY: field.get(learning.TYPE_KEY, learning.TYPE_TEXT),
                            learning.OPTIONS_KEY: [telemetry.clean_text(str(option), workday_run.report_secrets(), workday_run.QUEUE_LABEL_LIMIT)
                                                   for option in options],
                            learning.HOST_KEY: urlsplit(url).hostname or "",
                            learning.REQUIRED_KEY: field.get(learning.REQUIRED_KEY, False)})
        self.data[learning.UNANSWERED_KEY] = entries
        self.data[learning.PAGES_SCANNED_KEY] = len(self.data[learning.PAGES_KEY])

    def write(self, directory=None, path=None):
        self.data.update({SCAN_ONLY_KEY: True, learning.DRY_KEY: True, learning.AUTHOR_KEY: learning.AUTHOR,
                          learning.PAGES_NOT_REACHED_KEY: None, learning.COVERAGE_REASON_KEY: learning.CURRENT_PAGE_LIMIT})
        self.data.setdefault(learning.PAGES_SCANNED_KEY, 0)
        return super().write(directory, path)


def scan_job(url, report_path):
    # The child process changes report collection only, keeping the existing dry driver.
    original = workday_run.RunReport
    workday_run.RunReport = ScanReport
    try:
        if urlsplit(url).scheme != "https":
            raise ValueError("Scanning requires an HTTPS application URL.")
        return application.run(url=url, open_page=False, dry=True, batch=True, report_path=report_path)
    except (SystemExit, ValueError) as error:
        report = ScanReport(UNSUPPORTED_PORTAL, dry=True)
        report.data[learning.URL_KEY] = url
        report.finish_report(f"Cannot scan job: {error}", batch_apply.EXIT_FAILURE).write(path=report_path)
        return batch_apply.EXIT_FAILURE
    finally:
        workday_run.RunReport = original


def read_queue(path):
    rows = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(rows, list):
        raise ValueError("Expected a queue containing a list of job objects.")
    urls = [row[LINK_KEY].strip() for row in rows
            if isinstance(row, dict) and isinstance(row.get(LINK_KEY), str) and row[LINK_KEY].strip()]
    missing = len(rows) - len(urls)
    if missing:
        print(f"Skipped {missing} queue row(s) with missing or invalid links.")
    return urls


def build_jobs(urls, max_jobs=DEFAULT_MAX_JOBS):
    if max_jobs < 1:
        raise ValueError("max must be positive")
    jobs, seen, batch_id = [], set(), uuid4().hex
    for url in urls:
        try:
            identity, portal = normalize_url(url), application.portal_for(url)
        except ValueError:
            identity, portal = url, None
        if identity in seen:
            continue
        jobs.append({batch_apply.URL_KEY: url, batch_apply.PORTAL_KEY: portal or UNSUPPORTED_PORTAL, SCAN_ONLY_KEY: True,
                     batch_apply.REPORT_PATH_KEY: str(RUNS_DIR / f"{REPORT_PREFIX}_{batch_id}_{len(jobs)}.json")})
        seen.add(identity)
        if len(jobs) >= max_jobs:
            break
    if not jobs:
        raise ValueError("No job links to scan.")
    return jobs


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--urls", nargs="+")
    source.add_argument("--queue-file", type=Path)
    source.add_argument("--scan-job", help=argparse.SUPPRESS)
    parser.add_argument("--max", dest="max_jobs", type=int, default=DEFAULT_MAX_JOBS)
    parser.add_argument("--report-path", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.max_jobs < 1:
        parser.error("max must be positive")
    if bool(args.scan_job) != bool(args.report_path):
        parser.error("scan-job requires report-path; report-path is internal only")
    return args


def main(argv=None):
    args = parse_args(argv)
    try:
        if args.scan_job:
            return scan_job(args.scan_job, args.report_path)
        urls = args.urls if args.urls is not None else read_queue(args.queue_file)
        jobs = build_jobs(urls, args.max_jobs)
        print(f"Scanning {len(jobs)} job(s), current page only. Later pages remain unreached.")
        return batch_apply.execute_jobs(jobs, workers=SCAN_WORKERS, dry=True)
    except (OSError, ValueError, KeyError, TypeError, SystemExit) as error:
        print(f"Dry scan stopped: {error}")
        return batch_apply.EXIT_FAILURE


if __name__ == "__main__":
    sys.exit(main())
