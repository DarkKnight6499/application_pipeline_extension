"""One command from a job link and an application folder to a filled application that stops before Submit."""
import argparse
import contextlib
import hashlib
import io
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from browser_target import select_tab, sync_playwright, target_id_of
from shared_storage import file_lock

import edge_launch
import login_fill
import workday_run
import reuse_mode as reuse

# Config
HERE = Path(__file__).resolve().parent
RUNS_DIR = HERE / "data" / "runs"
APPLY_JSON = "apply.json"
SESSION_SUBFOLDER = "_inputs"  # prepare_apply.py writes the session here so the folder stays deliverables-only
RESUME_NAMES = ("Yazad_Madan.docx", "Yazad_Madan.pdf")
COVER_PREFIX = "CoverLetter_"
COVER_SUFFIXES = (".docx", ".pdf")
HOST_PORTALS = (("myworkdayjobs.com", "workday"), ("oraclecloud.com", "oracle"), ("icims.com", "icims"), ("lever.co", "lever"),
                ("ashbyhq.com", "ashby"), ("smartrecruiters.com", "smartrecruiters"), ("eightfold.ai", "eightfold"),
                ("taleo.net", "taleo"), ("greenhouse.io", "greenhouse"))
APPLY_PATH_SUFFIX = {"lever": "/apply", "ashby": "/application"}
APPLY_CLICK = {
    "workday": ['[data-automation-id="adventureButton"]', '[data-automation-id="applyManually"]'],
    "oracle": ['a:has-text("Apply Now"), button:has-text("Apply Now")'],
}
ICIMS_APPLY_TEXT = "apply for this job"
PAGE_WAIT_MS = 6000
CLICK_WAIT_MS = 3000
LOGIN_WAIT_SECONDS = 600
LOGIN_POLL_SECONDS = 3
TARGET_KEY, URL_KEY, NOTES_KEY = "target_id", "url", "notes"
LOGIN_LOCK_PREFIX = "portal-login:"
VERIFICATION_LABEL = re.compile(r"verification code|security code|one.?time|\botp\b", re.I)
LAST_APPLICATION_PATTERN = re.compile(os.environ.get("WORKDAY_LAST_APPLICATION_PATTERN", r"last application|previous application|use my last"), re.I)
LAST_APPLICATION_SELECTOR = 'button,[role="button"],input[type="button"],a'
UNSAFE_APPLY_LABEL = re.compile(r"submit|finish|\bsign\b|signature|attest|certif|\blog.?in\b|captcha|verif", re.I)
WORKDAY_APPLY_LABEL = re.compile(r"\bapply\b", re.I)


def portal_for(url):
    host = urlsplit(url).hostname or ""
    for mark, portal in HOST_PORTALS:
        if host == mark or host.endswith("." + mark):
            return portal
    return None


def find_files(folder):
    """The reviewed resume and cover letter inside an application folder; None for any that is missing."""
    folder = Path(folder)
    resume = next((folder / name for name in RESUME_NAMES if (folder / name).is_file()), None)
    covers = sorted(path for path in folder.glob(COVER_PREFIX + "*") if path.suffix.lower() in COVER_SUFFIXES)
    return resume, (covers[0] if covers else None)


def read_apply_json(folder):
    for path in (Path(folder) / SESSION_SUBFOLDER / APPLY_JSON, Path(folder) / APPLY_JSON):
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    return {}


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def resolve(url, folder):
    """Job link, portal, resume and cover letter from the arguments and an optional apply.json."""
    settings = read_apply_json(folder) if folder else {}
    url = url or settings.get("url")
    if not url:
        raise SystemExit("No job link. Pass it or put it in apply.json.")
    portal = portal_for(url)
    if not portal:
        raise SystemExit(f"No adapter for {urlsplit(url).hostname}.")
    resume, cover = find_files(folder) if folder else (None, None)
    if settings.get("session"):
        # A prepared session names its files exactly; nothing is auto-picked from the folder.
        resume = Path(settings["resume"]) if settings.get("resume") else None
        cover = Path(settings["cover"]) if settings.get("cover") else None
    else:
        resume = Path(settings["resume"]) if settings.get("resume") else resume
        cover = Path(settings["cover"]) if settings.get("cover") else cover
    expected = settings.get("resume_sha256")
    if expected:
        if not resume or not resume.is_file():
            raise SystemExit("Session resume file is missing.")
        if sha256_of(resume) != expected:
            raise SystemExit("Resume changed since the audit (SHA-256 mismatch). Rebuild and audit it again.")
    return {"url": url, "portal": portal, "resume": resume, "cover": cover}


def driver_args(job):
    args = ["--portal", job["portal"]]
    if job["resume"]:
        args += ["--resume", str(job["resume"])]
    if job["cover"]:
        args += ["--cover", str(job["cover"])]
    return args


def click_icims_apply(page):
    """The iCIMS Apply link sits in the job iframe and needs a logged-in candidate."""
    for frame in page.frames:
        link = frame.locator("a", has_text=ICIMS_APPLY_TEXT)
        if link.count() == 1:
            link.click()
            page.wait_for_timeout(CLICK_WAIT_MS)
            return "clicked iCIMS Apply for this job"
    return "iCIMS Apply link not found (log in first); click Apply yourself."


def last_application_match(labels, pattern=None):
    pattern = pattern or LAST_APPLICATION_PATTERN
    matches = [index for index, label in enumerate(labels) if pattern.search(str(label))]
    if any(UNSAFE_APPLY_LABEL.search(str(labels[index])) for index in matches):
        return None, "unsafe"
    return (matches[0], "matched") if len(matches) == 1 else (None, "ambiguous" if matches else "none")


def choose_last_application(page):
    controls = [control for control in page.locator(LAST_APPLICATION_SELECTOR).all()
                if control.is_visible() and control.is_enabled()]
    labels = [control.inner_text() or control.get_attribute("aria-label") or control.get_attribute("value") or ""
              for control in controls]
    index, reason = last_application_match(labels)
    if index is None:
        return False, f"Last application fallback: {reason}; using the existing Apply Manually path."
    target = controls[index]
    if target.get_attribute("type") in {"submit", "image"} or target.evaluate("node => Boolean(node.form && node.type === 'submit')") is True:
        return False, "Last application fallback: unsafe control type; using the existing Apply Manually path."
    target.click()
    page.wait_for_timeout(CLICK_WAIT_MS)
    return True, "Clicked the uniquely matched last application control."


def open_job(job):
    """Open one tab and return its stable target id after the posting navigation."""
    notes = []
    last_used = reuse.UNKNOWN
    url = job["url"].rstrip("/") + APPLY_PATH_SUFFIX.get(job["portal"], "")
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(workday_run.CDP_URL)
        try:
            page = browser.contexts[0].new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(PAGE_WAIT_MS)
            if job["portal"] == "icims":
                notes.append(click_icims_apply(page))
            for selector in APPLY_CLICK.get(job["portal"], []):
                if job["portal"] == "workday" and selector == APPLY_CLICK["workday"][1]:
                    if job.get(reuse.MODE_KEY) != reuse.FRESH:
                        last_used, note = choose_last_application(page)
                        notes.append(note)
                        if last_used:
                            break
                    else:
                        last_used = False
                        notes.append("Last application fallback: fresh mode requested; using Apply Manually.")
                target = page.locator(selector)
                if target.count() < 1:
                    notes.append(f"Apply control not found ({selector}); click Apply yourself.")
                    break
                if job["portal"] == "workday":
                    label = target.first.inner_text() or target.first.get_attribute("aria-label") or target.first.get_attribute("value") or ""
                    if (not WORKDAY_APPLY_LABEL.search(str(label)) or UNSAFE_APPLY_LABEL.search(str(label))
                            or target.first.get_attribute("type") in {"submit", "image"}
                            or target.first.evaluate("node => Boolean(node.form && node.type === 'submit')") is True):
                        notes.append("Apply control label or type could not be matched safely; click Apply yourself.")
                        break
                target.first.click()
                page.wait_for_timeout(CLICK_WAIT_MS)
                notes.append(f"clicked {selector}")
            return {NOTES_KEY: notes, URL_KEY: page.url, TARGET_KEY: target_id_of(page), reuse.LAST_USED_KEY: last_used}
        finally:
            browser.close()


def password_box_visible(page):
    return any(page.locator(login_fill.PASSWORD_SELECTOR).nth(i).is_visible() for i in range(page.locator(login_fill.PASSWORD_SELECTOR).count()))


def verification_visible(page):
    return any(VERIFICATION_LABEL.search(str(field.evaluate(login_fill.LABEL_JS) or ""))
               for field in login_fill.visible(page, login_fill.CODE_INPUT_SELECTOR))


def login_step(job, wait=time.sleep, clock=time.monotonic):
    """Wait for human login on the bound tab without typing credentials or codes."""
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(workday_run.CDP_URL)
        try:
            tab = select_tab(browser, job[URL_KEY], job.get(TARGET_KEY))
            deadline = clock() + LOGIN_WAIT_SECONDS
            while password_box_visible(tab) or login_fill.gate_on(tab) or verification_visible(tab):
                if clock() >= deadline:
                    raise workday_run.DriverStopped("Manual login or verification is still pending. Sign in by hand, then run again.")
                wait(LOGIN_POLL_SECONDS)
            return "manual login complete or no login form"
        finally:
            browser.close()


def run(url=None, folder=None, open_page=True, launch=False, dry=False, batch=False, target_id=None, report_path=None, fresh=False):
    """Returns the exit code: 0 Review reached, 2 human gate, 3 failure; writes data/runs/<id>.json."""
    job = resolve(url, folder)
    job[reuse.MODE_KEY] = reuse.REUSE if job["portal"] == "workday" and not fresh else reuse.FRESH
    last_used = reuse.UNKNOWN
    if target_id:
        job[TARGET_KEY] = target_id
    notes = []
    try:
        if launch and not dry:
            notes.append("edge: " + ("started" if edge_launch.ensure_edge()["started"] else "already running"))
        lock = file_lock(LOGIN_LOCK_PREFIX + (urlsplit(job[URL_KEY]).hostname or "").lower()) if batch and not dry else contextlib.nullcontext()
        with lock:
            if open_page and not dry:
                opened = open_job(job)
                if isinstance(opened, dict):
                    notes += opened[NOTES_KEY]
                    job.update({URL_KEY: opened[URL_KEY], TARGET_KEY: opened[TARGET_KEY]})
                    last_used = opened.get(reuse.LAST_USED_KEY, reuse.UNKNOWN)
                else:
                    notes += opened
            if (launch or batch) and not dry:
                notes.append("login: " + login_step(job))
        extra = ["--job-url", job[URL_KEY]]
        if fresh:
            extra += ["--fresh"]
        if job.get(TARGET_KEY):
            extra += ["--target-id", job[TARGET_KEY]]
        args = workday_run.parse_args(driver_args(job) + extra + (["--dry"] if dry else []) + (["--batch"] if batch else []))
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            report = workday_run.execute(args)
        print(buffer.getvalue())
    except (edge_launch.EdgeRefused, edge_launch.EdgeNotReady, workday_run.DriverStopped) as stop:
        report = workday_run.RunReport(job["portal"], dry).finish_report(str(stop), getattr(stop, "code", workday_run.EXIT_FAILURE))
    except (Exception, SystemExit) as error:
        report = workday_run.RunReport(job["portal"], dry).finish_report(
            f"{type(error).__name__}: {str(error)[:160]}", workday_run.EXIT_FAILURE)
    data = {**report.data, URL_KEY: job[URL_KEY], TARGET_KEY: job.get(TARGET_KEY), "folder": str(Path(folder).resolve()) if folder else None, "notes": notes,
            "resume": {"file": job["resume"].name, "sha256": sha256_of(job["resume"])} if job["resume"] else None,
            "cover": {"file": job["cover"].name, "sha256": sha256_of(job["cover"])} if job["cover"] else None}
    report.data = data
    report.data.update({reuse.MODE_KEY: job[reuse.MODE_KEY], reuse.LAST_USED_KEY: last_used})
    path = report.write(RUNS_DIR, path=report_path)
    print(report.summary())
    print(f"Report: {path}")
    return report.data["exit_code"]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", nargs="?", help="Job link; optional when the folder has apply.json.")
    parser.add_argument("--folder", type=Path, help="Application folder holding the resume and cover letter.")
    parser.add_argument("--no-open", action="store_true", help="Use the tab that is already open instead of opening the link.")
    parser.add_argument("--launch", action="store_true", help="Start the dedicated Edge if needed, wait for manual login, then drive the form.")
    parser.add_argument("--dry", action="store_true", help="Scan and print proposals only; nothing is written to the portal.")
    parser.add_argument("--fresh", action="store_true", help="Use the empty-form path instead of reusing a previous Workday application.")
    parser.add_argument("--batch", action="store_true", help="Serialize manual login per host and queue missing answers.")
    parser.add_argument("--target-id", help="Use this existing tab, including after navigation.")
    parser.add_argument("--report-path", type=Path, help="Exact unique report path assigned by the batch runner.")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    return run(args.url, args.folder, open_page=not args.no_open, launch=args.launch, dry=args.dry,
               batch=args.batch, target_id=args.target_id, report_path=args.report_path, fresh=args.fresh)


if __name__ == "__main__":
    sys.exit(main())
