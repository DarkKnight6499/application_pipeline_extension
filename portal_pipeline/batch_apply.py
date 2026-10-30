"""Author: Yazad Madan. Run 1 to 8 application folders, defaulting to 6 workers and 2 jobs per host."""
import argparse
import glob
import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import apply as application
import answer_memory
import edge_launch
import learning_queue
import reuse_mode as reuse
from browser_target import normalize_url
from shared_storage import atomic_json, file_lock

# Config
HERE = Path(__file__).resolve().parent
DATA_DIR = answer_memory.DATA_DIR
RUNS_DIR = DATA_DIR / "runs"
LATEST_FILENAME = "latest_batch.json"
APPLY_SCRIPT = HERE / "apply.py"
DRY_SCAN_SCRIPT = HERE / "dry_scan.py"
STEP_PASS_SCRIPT = HERE / "step_pass.py"
DRIVER_APPLY, DRIVER_STEP_PASS = "apply", "step_pass"
DRIVER_KEY = "driver"
FOLDER_NAME_SEPARATOR = "_"
SCAN_ONLY_KEY = "scan_only"
DEFAULT_WORKERS = 6
MAX_WORKERS = 8
MIN_JOBS = 1
PER_HOST_LIMIT = 2
WINDOW_THRESHOLD = 3
NEW_WINDOW_KEY = "new_window"
STAGGER_SECONDS = 3
JOB_TIMEOUT_SECONDS = 3600
EXIT_OK, EXIT_GATE, EXIT_FAILURE = 0, 2, 3
FOLDER_KEY, PORTAL_KEY, URL_KEY = "folder", "portal", "url"
REPORT_PATH_KEY, TARGET_KEY = "report_path", "target_id"
EXIT_KEY, STOP_KEY, DRY_KEY = "exit_code", "stop_reason", "dry"
REPORTS_KEY = "reports"
SUMMARY_COLUMNS = (FOLDER_KEY, PORTAL_KEY, EXIT_KEY, STOP_KEY, REPORT_PATH_KEY)
SUMMARY_REASON_LIMIT = 100


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folders", nargs="+", type=Path)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--dry", action="store_true", help="Scan existing matching tabs without launching or navigating Edge.")
    parser.add_argument("--fresh", action="store_true", help="Use the empty-form path for Workday jobs.")
    parser.add_argument("--target-ids", nargs="+", help="Open tab ids, one per folder in order (step_pass driver).")
    parser.add_argument("--driver", choices=(DRIVER_APPLY, DRIVER_STEP_PASS), default=DRIVER_APPLY,
                        help="Per-job worker. step_pass drives an already open Workday tab and needs its target id.")
    parser.add_argument("--learn-only", action="store_true", help="Rebuild the review queue from the latest batch reports without a browser.")
    parser.add_argument("--from-reports", nargs="+", help="Report paths or quoted globs for learn-only.")
    args = parser.parse_args(argv)
    if args.workers < 1:
        parser.error("workers must be positive")
    args.workers = min(args.workers, MAX_WORKERS)
    if args.from_reports and not args.learn_only:
        parser.error("from-reports requires learn-only")
    if args.learn_only:
        if args.folders or args.dry:
            parser.error("learn-only takes no folders or dry flag")
    elif args.driver == DRIVER_STEP_PASS and args.dry:
        parser.error("the step_pass driver has no dry mode")
    elif args.driver == DRIVER_STEP_PASS and (not args.target_ids or len(args.target_ids) != len(args.folders or [])):
        parser.error("the step_pass driver needs one --target-ids value per folder")
    elif not args.folders or not MIN_JOBS <= len(args.folders) <= MAX_WORKERS:
        parser.error(f"provide {MIN_JOBS} to {MAX_WORKERS} application folders")
    elif len({str(folder.resolve()).casefold() for folder in args.folders}) != len(args.folders):
        parser.error("application folders must be distinct")
    return args


def worst_exit_code(codes):
    return max((code if code in (EXIT_OK, EXIT_GATE, EXIT_FAILURE) else EXIT_FAILURE for code in codes), default=EXIT_OK)


def extract_host(url):
    """Return a canonical hostname without a port, path, or query."""
    host = urlsplit(url).hostname
    if not host:
        raise ValueError("Job link must include a host.")
    return host.lower().rstrip(".")


def step_pass_command(job, path):
    """Command for the step_pass worker, or None when the job has no open tab to drive."""
    if not job.get(TARGET_KEY) or not job.get(FOLDER_KEY):
        return None
    folder = Path(job[FOLDER_KEY])
    parts = folder.name.split(FOLDER_NAME_SEPARATOR)
    company = parts[1] if len(parts) > 1 else folder.name
    resume = application.find_files(folder)[0]
    command = [sys.executable, "-B", str(STEP_PASS_SCRIPT), company, "--target-id", job[TARGET_KEY],
               "--report-path", str(path), "--folder", str(folder), "--url", job[URL_KEY]]
    return command + (["--resume", str(resume)] if resume else [])


def run_job(job, dry=False, resume=False):
    path = Path(job[REPORT_PATH_KEY])
    stepper = job.get(DRIVER_KEY) == DRIVER_STEP_PASS and not job.get(SCAN_ONLY_KEY)
    if stepper:
        command = step_pass_command(job, path)
    elif job.get(SCAN_ONLY_KEY):
        if not dry or resume:
            raise ValueError("Scan-only jobs cannot write or resume.")
        command = [sys.executable, "-B", str(DRY_SCAN_SCRIPT), "--scan-job", job[URL_KEY], "--report-path", str(path)]
    else:
        command = [sys.executable, "-B", str(APPLY_SCRIPT), job[URL_KEY], "--folder", str(job[FOLDER_KEY]),
                   "--batch", "--report-path", str(path)]
    if not stepper:
        if dry and not job.get(SCAN_ONLY_KEY):
            command += ["--dry", "--no-open"]
        elif resume:
            command += ["--no-open"]
        if job.get(TARGET_KEY):
            command += ["--target-id", job[TARGET_KEY]]
        if job.get(reuse.MODE_KEY) == reuse.FRESH and not job.get(SCAN_ONLY_KEY):
            command += ["--fresh"]
        if job.get(NEW_WINDOW_KEY) and not dry and not resume and not job.get(SCAN_ONLY_KEY):
            command += ["--new-window"]
    try:
        if command is None:
            raise ValueError("step_pass driver needs the folder and an open tab target id")
        process = subprocess.run(command, cwd=HERE, capture_output=True, text=True, timeout=JOB_TIMEOUT_SECONDS)
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get(EXIT_KEY) != process.returncode:
            raise ValueError("Child exit code disagrees with its report.")
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        data = {**job, EXIT_KEY: EXIT_FAILURE, STOP_KEY: f"Missing or invalid child report: {type(error).__name__}",
                DRY_KEY: dry, learning_queue.UNANSWERED_KEY: []}
        if job.get(SCAN_ONLY_KEY):
            data.update({learning_queue.AUTHOR_KEY: learning_queue.AUTHOR, learning_queue.PAGES_KEY: [],
                         learning_queue.PAGES_SCANNED_KEY: 0, learning_queue.PAGES_NOT_REACHED_KEY: None,
                         learning_queue.COVERAGE_REASON_KEY: learning_queue.CURRENT_PAGE_LIMIT})
        atomic_json(path, data)
    return {**data, REPORT_PATH_KEY: str(path)}


def print_summary(reports):
    print("job | portal | exit code | stop reason | report path")
    for report in reports:
        display = {**report, FOLDER_KEY: Path(str(report[FOLDER_KEY])).name if report.get(FOLDER_KEY) else report.get(URL_KEY, "unknown"),
                   STOP_KEY: str(report.get(STOP_KEY, ""))[:SUMMARY_REASON_LIMIT]}
        print(" | ".join(str(display.get(key, "")) for key in SUMMARY_COLUMNS))
    print("Prefill differences:")
    for report in reports:
        count = sum(page.get(reuse.DIFF_KEY, 0) for page in report.get("pages", []))
        name = Path(str(report[FOLDER_KEY])).name if report.get(FOLDER_KEY) else report.get(URL_KEY, "unknown")
        print(f"  {name}: {count}; see per-job report.")


def finish_batch(reports, data_dir=DATA_DIR):
    directory = Path(data_dir)
    with file_lock(directory.resolve() / LATEST_FILENAME):
        atomic_json(directory / LATEST_FILENAME, {REPORTS_KEY: [report[REPORT_PATH_KEY] for report in reports]})
        queue = learning_queue.write_queue(reports, directory)
    print_summary(reports)
    print(f"Learning review: {len(queue[learning_queue.QUESTIONS_KEY])} question(s), {directory / learning_queue.QUEUE_FILENAME}")
    return worst_exit_code(report[EXIT_KEY] for report in reports)


def execute_jobs(jobs, workers=DEFAULT_WORKERS, dry=False, resume=False):
    workers = min(workers, MAX_WORKERS)
    hosts = {extract_host(job[URL_KEY]) for job in jobs}
    limits = {host: threading.BoundedSemaphore(PER_HOST_LIMIT) for host in hosts}
    new_window = min(workers, len(jobs)) > WINDOW_THRESHOLD and not dry and not resume

    def limited_job(job):
        with limits[extract_host(job[URL_KEY])]:
            return run_job({**job, NEW_WINDOW_KEY: new_window}, dry=dry, resume=resume)

    futures = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for index, job in enumerate(jobs):
            if index:
                time.sleep(STAGGER_SECONDS)
            futures.append(pool.submit(limited_job, job))
        reports = [future.result() for future in futures]
    return finish_batch(reports, data_dir=DATA_DIR)


def resume_jobs(jobs):
    pending = []
    batch_id = uuid4().hex
    for job in jobs:
        if job.get(DRY_KEY):
            continue
        if not job.get(FOLDER_KEY) or not job.get(TARGET_KEY):
            print("Cannot resume a job without its folder and original target id. Run a new reviewed batch.")
            return EXIT_FAILURE
        pending.append({**job, REPORT_PATH_KEY: str(RUNS_DIR / f"{batch_id}_{len(pending)}.json")})
    if not pending:
        print("No writable jobs to resume. Dry scans require a separate reviewed batch.")
        return EXIT_OK
    return execute_jobs(pending, resume=True)


def load_reports(patterns):
    reports, seen = [], set()
    for pattern in patterns:
        paths = [Path(pattern)] if Path(pattern).is_file() else [Path(path) for path in sorted(glob.glob(str(pattern)))]
        if not paths:
            raise ValueError(f"No reports match {pattern!r}.")
        for path in paths:
            identity = str(path.resolve()).casefold()
            if identity in seen:
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get(EXIT_KEY) not in (EXIT_OK, EXIT_GATE, EXIT_FAILURE):
                raise ValueError(f"Invalid run report: {path}")
            reports.append({**data, REPORT_PATH_KEY: str(path.resolve())})
            seen.add(identity)
    if not reports:
        raise ValueError("No reports supplied.")
    return reports


def main(argv=None):
    args = parse_args(argv)
    try:
        if args.learn_only:
            paths = args.from_reports
            if not paths:
                manifest = json.loads((DATA_DIR / LATEST_FILENAME).read_text(encoding="utf-8"))
                paths = manifest[REPORTS_KEY]
            reports = load_reports(paths)
            return finish_batch(reports, data_dir=DATA_DIR)
        batch_id, jobs, seen = uuid4().hex, [], set()
        for folder in args.folders:
            job = application.resolve(None, folder)
            identity = normalize_url(job[URL_KEY])
            if identity in seen:
                raise ValueError("The same job URL cannot run twice in a batch.")
            seen.add(identity)
            jobs.append({FOLDER_KEY: str(folder.resolve()), PORTAL_KEY: job[PORTAL_KEY], URL_KEY: job[URL_KEY],
                         reuse.MODE_KEY: reuse.REUSE if job[PORTAL_KEY] == "workday" and not args.fresh else reuse.FRESH,
                         DRIVER_KEY: args.driver, **({TARGET_KEY: args.target_ids[len(jobs)]} if args.target_ids else {}),
                         REPORT_PATH_KEY: str(RUNS_DIR / f"{batch_id}_{len(jobs)}.json")})
        if not args.dry:
            try:
                edge_launch.ensure_edge()
            except (edge_launch.EdgeRefused, edge_launch.EdgeNotReady) as error:
                reports = []
                for job in jobs:
                    report = {**job, EXIT_KEY: EXIT_FAILURE, STOP_KEY: str(error), DRY_KEY: False,
                              learning_queue.UNANSWERED_KEY: []}
                    atomic_json(job[REPORT_PATH_KEY], report)
                    reports.append(report)
                return finish_batch(reports, data_dir=DATA_DIR)
        return execute_jobs(jobs, workers=args.workers, dry=args.dry)
    except (OSError, ValueError, KeyError, SystemExit, edge_launch.EdgeRefused, edge_launch.EdgeNotReady) as error:
        print(f"Batch stopped: {error}")
        return EXIT_FAILURE


if __name__ == "__main__":
    sys.exit(main())
