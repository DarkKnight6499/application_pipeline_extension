"""One command from a job link and an application folder to a filled application that stops before Submit."""
import argparse
import contextlib
import io
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

import workday_run

# Config
HERE = Path(__file__).resolve().parent
RUNS_DIR = HERE / "data" / "runs"
APPLY_JSON = "apply.json"
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
PAGE_WAIT_MS = 6000
CLICK_WAIT_MS = 3000


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
    path = Path(folder) / APPLY_JSON
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


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
    resume = Path(settings["resume"]) if settings.get("resume") else resume
    cover = Path(settings["cover"]) if settings.get("cover") else cover
    return {"url": url, "portal": portal, "resume": resume, "cover": cover}


def driver_args(job):
    args = ["--portal", job["portal"]]
    if job["resume"]:
        args += ["--resume", str(job["resume"])]
    if job["cover"]:
        args += ["--cover", str(job["cover"])]
    return args


def open_job(job):
    """Open the job link in the attached browser and click through to the form; returns notes for the report."""
    notes = []
    url = job["url"].rstrip("/") + APPLY_PATH_SUFFIX.get(job["portal"], "")
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(workday_run.CDP_URL)
        page = browser.contexts[0].new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(PAGE_WAIT_MS)
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


def run(url=None, folder=None, open_page=True):
    job = resolve(url, folder)
    report = {"started": datetime.now().isoformat(timespec="seconds"), "url": job["url"], "portal": job["portal"],
              "resume": str(job["resume"]) if job["resume"] else None, "cover": str(job["cover"]) if job["cover"] else None, "notes": []}
    if open_page:
        report["notes"] += open_job(job)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        workday_run.main(driver_args(job))
    output = buffer.getvalue()
    print(output)
    report["driver_output"] = output.splitlines()
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    (RUNS_DIR / f"{time.strftime('%Y%m%d_%H%M%S')}_{job['portal']}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", nargs="?", help="Job link; optional when the folder has apply.json.")
    parser.add_argument("--folder", type=Path, help="Application folder holding the resume and cover letter.")
    parser.add_argument("--no-open", action="store_true", help="Use the tab that is already open instead of opening the link.")
    args = parser.parse_args(argv)
    run(args.url, args.folder, open_page=not args.no_open)


if __name__ == "__main__":
    sys.exit(main())
