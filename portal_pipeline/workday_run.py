"""Walk a Workday application in a debuggable Edge window: fill what is known, learn the rest, stop at Review. Never clicks Submit."""
import argparse
import base64
import hashlib
import mimetypes
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

import answer_memory
import picker_aliases
from portal_profile import resolve_profile

# Config
HERE = Path(__file__).resolve().parent
EXTENSION = HERE / "extension"
CDP_URL = "http://127.0.0.1:9223"
SOURCE = Path(os.environ.get("PORTAL_SOURCE", r"D:\Code\Resume"))
HOST_MARK = "myworkdayjobs.com"
NEXT_LABELS = {"save and continue", "next"}
SCRIPTS = ["adapters/registry.js", "adapters/generic.js", "adapters/workday.js", "adapters/aria-listbox.js", "workday-menu.js",
           "classifier.js", "picker-search.js", "workday-upload.js", "workday-date.js", "workday-picker.js", "engine.js"]
NEXT_SELECTOR = '[data-automation-id="pageFooterNextButton"]'
STEP_SELECTOR = '[data-automation-id="progressBarActiveStep"]'
FINAL_STEP_PATTERN = re.compile(r"\breview\b", re.I)
GLOBALS = ["PortalEngine", "PortalAdapters", "PortalClassifier", "PortalWorkdayMenu", "PortalPickerSearch", "PortalWorkdayUpload", "PortalWorkdayDate", "PortalWorkdayPicker"]
FAILED = {}
MAX_PAGES = 10
FILL_ROUNDS = 3
PAGE_SETTLE_SECONDS = 4
GAP_POLL_SECONDS = 3
GAP_WAIT_SECONDS = 600
STEP_PATTERN = re.compile(r"step (\d+) of (\d+)")


def is_workday_url(url):
    host = urlsplit(url).hostname or ""
    return host == HOST_MARK or host.endswith("." + HOST_MARK)


def is_next_label(text):
    return " ".join(str(text).lower().split()) in NEXT_LABELS


def page_of(browser):
    tabs = [page for context in browser.contexts for page in context.pages if is_workday_url(page.url)]
    if len(tabs) != 1:
        raise SystemExit(f"Expected exactly one Workday tab, found {len(tabs)}. Close the extras.")
    return tabs[0]


def inject(page):
    page.evaluate("names => names.forEach(name => { delete globalThis[name]; })", GLOBALS)
    for name in SCRIPTS:
        page.add_script_tag(path=str(EXTENSION / name))


def step_title(page):
    return page.evaluate("(sel) => (document.querySelector(sel)?.textContent || '').replace(/\\s+/g, ' ').trim()", STEP_SELECTOR)


def build_profile():
    profile = resolve_profile(SOURCE)
    memory = answer_memory.load_memory()
    profile.update(answers=answer_memory.profile_answers(memory), consents=answer_memory.profile_consents(memory),
                   aliases=answer_memory.profile_aliases(memory), pickers=picker_aliases.profile_pickers(picker_aliases.load_aliases()))
    return profile


def attachment_for(path):
    """The {name, mime, base64, sha256} record the upload module verifies before writing."""
    path = Path(path)
    data = path.read_bytes()
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return {"name": path.name, "mime": mime, "base64": base64.b64encode(data).decode("ascii"), "sha256": hashlib.sha256(data).hexdigest()}


def upload_resume(page, resume):
    """Attach the reviewed resume when the page has exactly one Workday upload input; returns a status line."""
    found = page.evaluate("!!PortalWorkdayUpload.find()")
    if not found:
        return None
    if not resume:
        return "Upload input found but no --resume given; attach it yourself."
    try:
        return page.evaluate("async attachment => PortalWorkdayUpload.upload(PortalWorkdayUpload.find(), attachment)", attachment_for(resume))
    except Exception as error:  # noqa: BLE001 - report and let the person attach it
        return f"Upload failed: {str(error)[:120]}"


def scan(page, profile, bindings=None):
    return page.evaluate("([profile, bindings]) => PortalEngine.scan(profile, {bindings})", [profile, bindings or {}])


CLICK_ADD_JS = """heading => {
  const buttons = [...document.querySelectorAll('button[data-automation-id="add-button"]')];
  const owns = (button) => { for (let node = button.parentElement, depth = 0; node && depth < 8; node = node.parentElement, depth += 1) {
    if ([...node.children].some(child => /^H[1-6]$/.test(child.tagName) && child.textContent.trim() === heading)) return true; } return false; };
  const found = buttons.filter(owns);
  if (found.length !== 1) return false;
  found[0].click();
  return true;
}"""
HISTORY_SECTIONS = {"employment": "Work Experience", "education": "Education"}
ROW_SETTLE_SECONDS = 1.5


def click_add(page, heading):
    """Click the one Add button under a section heading; False when there is not exactly one."""
    return page.evaluate(CLICK_ADD_JS, heading)


def row_ids(fields, group):
    """Distinct history record ids of a group in page order."""
    seen = []
    for f in fields:
        record = f["record"]
        if record and record["group"] == group and record["id"] not in seen:
            seen.append(record["id"])
    return seen


def ensure_rows(page, profile):
    """Add history rows until each group has as many as the profile has records; returns False if an Add button is missing."""
    for group, heading in HISTORY_SECTIONS.items():
        needed = len(profile.get(group, []))
        for _ in range(needed + 1):
            if len(row_ids(scan(page, profile), group)) >= needed:
                break
            if not click_add(page, heading):
                return False
            time.sleep(ROW_SETTLE_SECONDS)
    return True


def bind_rows(page, profile):
    """Bind the page's rows to profile records in order; returns the bindings for scan."""
    fields = scan(page, profile)
    bindings = {}
    for group in HISTORY_SECTIONS:
        for index, record_id in enumerate(row_ids(fields, group)):
            if index < len(profile.get(group, [])):
                bindings[record_id] = index
    return bindings


def prepared(fields):
    return [f for f in fields if f["status"] == "prepared" and f["proposal"] != "" and not f["blocked"] and f["type"] != "file" and not f["disabled"]]


def unanswered(fields):
    """Required, still-empty, unblocked fields after filling: the ones a person must answer."""
    return [f for f in fields if f["required"] and not f["blocked"] and f["current"] in ("", False) and f["type"] != "file"]


def learnable(fields):
    """Fields whose typed value may be remembered by exact question; history row fields differ per row, so never."""
    return [f for f in fields if not f["blocked"] and f["current"] not in ("", False) and f["proposal"] == "" and f["type"] != "checkbox" and not f["record"]]


def learn(page, profile, fields):
    """Store what the person entered for fields that had no answer, under the exact question text."""
    memory = answer_memory.load_memory()
    learned = 0
    for field in learnable(scan(page, profile, bind_rows(page, profile))):
        if answer_memory.remember(memory, field["label"], str(field["current"]), source="manual"):
            learned += 1
    if learned:
        answer_memory.save_memory(memory)
    return learned


def run_page(page, profile, dry):
    if not dry and not ensure_rows(page, profile):
        print("  Could not add every history row. Add them yourself; stopping fill for this page.")
    bindings = bind_rows(page, profile)
    fields = scan(page, profile, bindings)
    todo = prepared(fields)
    print(f"  fields {len(fields)} | proposals {len(todo)} | blocked {sum(f['blocked'] for f in fields)}")
    if dry:
        for f in fields:
            print(f"    [{f['status']}] {f['type']:9} {f['label'][:60]!r} -> {str(f['proposal'])[:30]!r} (now {str(f['current'])[:20]!r})")
        return fields
    for round_number in range(FILL_ROUNDS):
        if not todo:
            break
        results = page.evaluate("async selections => PortalEngine.fill(selections)", [{"id": f["id"], "value": f["proposal"]} for f in todo])
        counts = {}
        for r in results:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        print(f"  fill round {round_number + 1}:", counts)
        for r in results:
            if r["status"] in ("failed", "refused"):
                FAILED["count"] = FAILED.get("count", 0) + 1
                print("   !", r.get("message", "")[:120])
        if not counts.get("filled"):
            break
        time.sleep(ROW_SETTLE_SECONDS)
        fields = scan(page, profile, bindings)
        todo = [f for f in prepared(fields) if f["current"] in ("", False)]
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
    parser.add_argument("--resume", type=Path, help="Reviewed resume file to attach on the upload step.")
    parser.add_argument("--dry", action="store_true", help="Scan and print proposals only; write and click nothing.")
    args = parser.parse_args(argv)
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        page = page_of(browser)
        for _ in range(MAX_PAGES):
            if page.locator("[role=dialog], [role=alertdialog]").count():
                print("A dialog is open. Stopping so nothing is discarded or submitted.")
                break
            inject(page)
            title = step_title(page)
            print(title)
            if FINAL_STEP_PATTERN.search(title) and not args.dry:
                print("  Review page reached. Nothing is filled here. Check it and submit yourself.")
                break
            profile = build_profile()
            fields = run_page(page, profile, args.dry)
            if FAILED.get("count"):
                print("  A fill failed. Stopping so you can check the page.")
                break
            if not args.dry:
                note = upload_resume(page, args.resume)
                if note:
                    print("  upload:", note)
            if args.dry or FINAL_STEP_PATTERN.search(title):
                break
            if not wait_for_person(page, profile):
                print("  Required answers are still missing. Stopping here for you.")
                break
            learned = learn(page, profile, fields)
            if learned:
                print(f"  learned {learned} answer(s)")
            button = page.locator(NEXT_SELECTOR)
            if button.count() != 1 or not is_next_label(button.inner_text()):
                print("  No single Save and Continue button. Stopping.")
                break
            button.click()
            time.sleep(PAGE_SETTLE_SECONDS)
            if step_title(page) == title:
                print("  The page did not advance (Workday probably flagged a field). Stopping for you.")
                break
        print("Stopped. Submit stays manual.")
        browser.close()


if __name__ == "__main__":
    sys.exit(main())
