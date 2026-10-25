"""One command from a job link and an application folder to a filled application that stops before Submit."""
import argparse
import contextlib
import hashlib
import io
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

import edge_launch
import login_fill
import workday_run

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


def open_job(job):
    """Open the job link in the attached browser and click through to the form; returns notes for the report."""
    notes = []
    url = job["url"].rstrip("/") + APPLY_PATH_SUFFIX.get(job["portal"], "")
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(workday_run.CDP_URL)
        page = browser.contexts[0].new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(PAGE_WAIT_MS)
        if job["portal"] == "icims":
            notes.append(click_icims_apply(page))
        for selector in APPLY_CLICK.get(job["portal"], []):
            target = page.locator(selector)
            if target.count() < 1:
                notes.append(f"Apply control not found ({selector}); click Apply yourself.")
                break
            target.first.click()
            page.wait_for_timeout(CLICK_WAIT_MS)
            notes.append(f"clicked {selector}")
        browser.close()
    return notes


def password_box_visible(page):
    return any(page.locator(login_fill.PASSWORD_SELECTOR).nth(i).is_visible() for i in range(page.locator(login_fill.PASSWORD_SELECTOR).count()))


def login_step(job, wait=time.sleep, clock=time.monotonic):
    """Type the stored login, or wait for a manual login; returns a result code, never a secret."""
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(workday_run.CDP_URL)
        try:
            tabs = [page for context in browser.contexts for page in context.pages if login_fill.same_host(page.url, job["url"])]
            if len(tabs) != 1:
                return f"login skipped: {len(tabs)} tab(s) on the job host"
            tab = tabs[0]
            result = login_fill.login(tab, job["url"], submit=True)["result"]
            deadline = clock() + LOGIN_WAIT_SECONDS
            while password_box_visible(tab):
                if clock() >= deadline:
                    raise workday_run.DriverStopped(f"Login not completed ({result}). Sign in by hand, then run again.")
                wait(LOGIN_POLL_SECONDS)
            return result
        finally:
            browser.close()


def run(url=None, folder=None, open_page=True, launch=False, dry=False):
    """Returns the exit code: 0 Review reached, 2 human gate, 3 failure; writes data/runs/<id>.json."""
    job = resolve(url, folder)
    notes = []
    try:
        if launch:
            notes.append("edge: " + ("started" if edge_launch.ensure_edge()["started"] else "already running"))
        if open_page:
            notes += open_job(job)
        if launch:
            notes.append("login: " + login_step(job))
        args = workday_run.parse_args(driver_args(job) + (["--dry"] if dry else []))
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            report = workday_run.execute(args)
        print(buffer.getvalue())
    except (edge_launch.EdgeRefused, edge_launch.EdgeNotReady, workday_run.DriverStopped) as stop:
        report = workday_run.RunReport(job["portal"], dry).finish_report(str(stop), getattr(stop, "code", workday_run.EXIT_FAILURE))
    data = {**report.data, "url": job["url"], "notes": notes,
            "resume": {"file": job["resume"].name, "sha256": sha256_of(job["resume"])} if job["resume"] else None,
            "cover": {"file": job["cover"].name, "sha256": sha256_of(job["cover"])} if job["cover"] else None}
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = RUNS_DIR / f"{time.strftime('%Y%m%d_%H%M%S')}_{job['portal']}.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(report.summary())
    print(f"Report: {path}")
    return report.data["exit_code"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", nargs="?", help="Job link; optional when the folder has apply.json.")
    parser.add_argument("--folder", type=Path, help="Application folder holding the resume and cover letter.")
    parser.add_argument("--no-open", action="store_true", help="Use the tab that is already open instead of opening the link.")
    parser.add_argument("--launch", action="store_true", help="Start the dedicated Edge if needed, type the stored login, then drive the form.")
    parser.add_argument("--dry", action="store_true", help="Scan and print proposals only; nothing is written to the portal.")
    args = parser.parse_args(argv)
    return run(args.url, args.folder, open_page=not args.no_open, launch=args.launch, dry=args.dry)


if __name__ == "__main__":
    sys.exit(main())
