"""Walk a Workday application in a debuggable Edge window: fill what is known, learn the rest, stop at Review. Never clicks Submit."""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

import answer_memory
from portal_profile import resolve_profile

# Config
HERE = Path(__file__).resolve().parent
EXTENSION = HERE / "extension"
CDP_URL = "http://127.0.0.1:9223"
SOURCE = Path(os.environ.get("PORTAL_SOURCE", r"D:\Code\Resume"))
HOST_MARK = "myworkdayjobs.com"
SCRIPTS = ["adapters/registry.js", "adapters/generic.js", "adapters/workday.js", "adapters/aria-listbox.js", "workday-menu.js",
           "classifier.js", "picker-search.js", "engine.js"]
NEXT_SELECTOR = '[data-automation-id="pageFooterNextButton"]'
STEP_SELECTOR = '[data-automation-id="progressBarActiveStep"]'
FINAL_STEP_PATTERN = re.compile(r"\breview\b", re.I)
GLOBALS = ["PortalEngine", "PortalAdapters", "PortalClassifier", "PortalWorkdayMenu", "PortalPickerSearch"]
MAX_PAGES = 10
PAGE_SETTLE_SECONDS = 4
GAP_POLL_SECONDS = 3
GAP_WAIT_SECONDS = 600
STEP_PATTERN = re.compile(r"step (\d+) of (\d+)")


def page_of(browser):
    for context in browser.contexts:
        for page in context.pages:
            if HOST_MARK in page.url:
                return page
    raise SystemExit("No Workday tab found in the debuggable Edge window.")


def inject(page):
    page.evaluate("names => names.forEach(name => { delete globalThis[name]; })", GLOBALS)
    for name in SCRIPTS:
        page.add_script_tag(path=str(EXTENSION / name))


def step_title(page):
    return page.evaluate("(sel) => (document.querySelector(sel)?.textContent || '').replace(/\\s+/g, ' ').trim()", STEP_SELECTOR)


def build_profile():
    profile = resolve_profile(SOURCE)
    profile["answers"] = answer_memory.profile_answers(answer_memory.load_memory())
    return profile


def scan(page, profile):
    return page.evaluate("profile => PortalEngine.scan(profile)", profile)


def prepared(fields):
    return [f for f in fields if f["status"] == "prepared" and f["proposal"] != "" and not f["blocked"] and f["type"] != "file" and not f["disabled"]]


def unanswered(fields):
    """Required, empty, unblocked fields that have no proposal: the ones a person must answer once."""
    return [f for f in fields if f["required"] and not f["blocked"] and f["current"] in ("", False) and f["proposal"] == "" and f["type"] != "file"]


def learn(page, profile, fields):
    """Store what the person entered for fields that had no answer, under the exact question text."""
    memory = answer_memory.load_memory()
    learned = 0
    for field in scan(page, profile):
        if field["blocked"] or field["current"] in ("", False) or field["proposal"] != "":
            continue
        if field["type"] == "checkbox":
            continue
        if answer_memory.remember(memory, field["label"], str(field["current"]), source="manual"):
            learned += 1
    if learned:
        answer_memory.save_memory(memory)
    return learned


def run_page(page, profile, dry):
    fields = scan(page, profile)
    todo = prepared(fields)
    print(f"  fields {len(fields)} | proposals {len(todo)} | blocked {sum(f['blocked'] for f in fields)}")
    if dry:
        for f in fields:
            print(f"    [{f['status']}] {f['type']:9} {f['label'][:60]!r} -> {str(f['proposal'])[:30]!r} (now {str(f['current'])[:20]!r})")
        return fields
    if todo:
        results = page.evaluate("async selections => PortalEngine.fill(selections)", [{"id": f["id"], "value": f["proposal"]} for f in todo])
        counts = {}
        for r in results:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        print("  fill:", counts)
        for r in results:
            if r["status"] in ("failed", "refused"):
                print("   !", r.get("message", "")[:120])
    return fields


def wait_for_person(page, profile):
    """Block until required gaps are answered by the person, then learn them."""
    deadline = time.time() + GAP_WAIT_SECONDS
    while time.time() < deadline:
        gaps = unanswered(scan(page, profile))
        if not gaps:
            return True
        time.sleep(GAP_POLL_SECONDS)
    return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry", action="store_true", help="Scan and print proposals only; write and click nothing.")
    args = parser.parse_args(argv)
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        page = page_of(browser)
        for _ in range(MAX_PAGES):
            inject(page)
            title = step_title(page)
            print(title)
            profile = build_profile()
            fields = run_page(page, profile, args.dry)
            if args.dry or FINAL_STEP_PATTERN.search(title):
                break
            if not wait_for_person(page, profile):
                print("  Required answers are still missing. Stopping here for you.")
                break
            learned = learn(page, profile, fields)
            if learned:
                print(f"  learned {learned} answer(s)")
            button = page.locator(NEXT_SELECTOR)
            if button.count() != 1 or not re.search(r"save and continue|next", button.inner_text(), re.I):
                print("  No single Save and Continue button. Stopping.")
                break
            button.click()
            time.sleep(PAGE_SETTLE_SECONDS)
        print("Stopped. Submit stays manual.")
        browser.close()


if __name__ == "__main__":
    sys.exit(main())
