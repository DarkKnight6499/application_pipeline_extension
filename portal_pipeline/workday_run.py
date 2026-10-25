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

import oracle_attach
import oracle_history
import single_upload
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
ORACLE_HOST_MARK = "oraclecloud.com"
ORACLE_EXTRA_SCRIPTS = ["oracle-grid.js", "adapters/oracle.js", "oracle-live.js"]
ORACLE_GLOBALS = ["PortalOracleGrid", "PortalOracleAdapter"]
GREENHOUSE_HOST_MARK = "greenhouse.io"
GREENHOUSE_EXTRA_SCRIPTS = ["adapters/greenhouse.js", "adapters/greenhouse-select.js"]
GREENHOUSE_GLOBALS = ["PortalGreenhouse", "PortalGreenhouseSelect"]
GREENHOUSE_UPLOAD_SELECTORS = {"resume": "form#application-form input#resume", "cover": "form#application-form input#cover_letter"}
SINGLE_PAGE_HOSTS = {"greenhouse": "greenhouse.io", "lever": "lever.co", "ashby": "ashbyhq.com", "smartrecruiters": "smartrecruiters.com", "eightfold": "eightfold.ai", "icims": "icims.com", "taleo": "taleo.net"}
LEVER_EXTRA_SCRIPTS = ["adapters/lever.js", "lever-live.js"]
LEVER_GLOBALS = ["PortalLeverAdapter"]
FRAME_PORTALS = {"icims"}
FORM_FRAME_JS = "() => [...document.querySelectorAll('input,select,textarea')].filter(i => i.type !== 'hidden' && i.getClientRects().length).length"
PORTAL = {"frame": False, "oracle": False, "greenhouse": False, "lever": False, "single": False, "host": ""}
NEXT_LABELS = {"save and continue", "next", "update profile"}
ICIMS_NEXT_SELECTOR = "input#cp_form_submit_i, input.iCIMS_PrimaryButton[value='Next']"
ICIMS_TITLE_JS = "() => [...document.querySelectorAll('h1,h2,h3')].filter(n => n.getClientRects().length).slice(0, 4).map(n => n.textContent.trim()).join(' / ')"
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
RUNS_DIR = HERE / "data" / "runs"
EXIT_REVIEW, EXIT_GATE, EXIT_FAILURE = 0, 2, 3  # Review reached, human gate, failure
REPORT_LABEL_LIMIT = 60
FILL_OK_STATUSES = {"filled", "preserved", "skipped_existing"}
FILL_GATE_STATUSES = {"blocked_by_human_gate", "refused"}
DIALOG_TEST_JS = "[...document.querySelectorAll('[role=dialog],[role=alertdialog],dialog[open]')].some(node => node.getClientRects().length > 0 && node.innerText.trim() !== '' && !/cookie/i.test(node.innerText))"
WORKDAY_STEP_CHECK_JS = r"""const title = (document.querySelector('[data-automation-id="progressBarActiveStep"]')?.textContent || '').trim();
  if (!title || /\breview\b/i.test(title)) throw new Error('Review reached or the step is unknown. Continue manually.');"""
DIALOG_CHECK_JS = "if (" + DIALOG_TEST_JS + ") throw new Error('A dialog appeared. Continue manually.');"
PAGE_BOUNDARY_JS = "() => {\n  " + DIALOG_CHECK_JS + "\n  " + WORKDAY_STEP_CHECK_JS + "\n}"  # runs before every field write
DIALOG_BOUNDARY_JS = "() => {\n  " + DIALOG_CHECK_JS + "\n}"
FILL_JS = "async selections => PortalEngine.fill(selections, {checkBoundary: " + PAGE_BOUNDARY_JS + "})"
FILL_JS_DIALOG_ONLY = "async selections => PortalEngine.fill(selections, {checkBoundary: " + DIALOG_BOUNDARY_JS + "})"
UPLOAD_JS = "async attachment => PortalWorkdayUpload.upload(PortalWorkdayUpload.find(), attachment, " + PAGE_BOUNDARY_JS + ")"
REVIEW_ATTACHMENTS_JS = r"""() => {
  const names = new Set();
  const pattern = /[^\s"'()<>:\\\/]+\.(?:pdf|docx?|rtf|txt|odt)(?![A-Za-z0-9])/gi;
  for (const node of document.querySelectorAll('[data-automation-id]')) {
    if (node.children.length > 3) continue;
    for (const match of (node.textContent || '').matchAll(pattern)) names.add(match[0]);
  }
  return [...names].sort();
}"""


class DriverStopped(RuntimeError):
    """A live boundary requires the person to continue manually (exit code 2 unless stated)."""

    def __init__(self, message, code=EXIT_GATE):
        super().__init__(message)
        self.code = code


class DriverFailed(DriverStopped):
    def __init__(self, message):
        super().__init__(message, EXIT_FAILURE)


class ReviewReached(DriverStopped):
    def __init__(self, message="Review page reached."):
        super().__init__(message, EXIT_REVIEW)


class RunReport:
    """Per-page events and the stop reason; holds labels and hashes only, never field values."""

    def __init__(self, portal="workday", dry=False):
        self.data = {"started": time.strftime("%Y-%m-%dT%H:%M:%S"), "portal": portal, "dry": dry, "pages": [],
                     "stop_reason": None, "exit_code": None, "review_attachments": None}

    def new_page(self, title):
        event = {"title": title, "fields": 0, "filled": 0, "pending_required": [], "blocked_gates": [], "uploads": [], "learned": 0}
        self.data["pages"].append(event)
        return event

    def finish_report(self, reason, code):
        self.data.update(stop_reason=reason, exit_code=code)
        return self

    def write(self, directory=None):
        directory = Path(directory or RUNS_DIR)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{time.strftime('%Y%m%d_%H%M%S')}_{self.data['portal']}.json"
        path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        return path

    def summary(self):
        pages = self.data["pages"]
        filled = sum(page["filled"] for page in pages)
        pending = sum(len(page["pending_required"]) for page in pages)
        return f"{len(pages)} page(s), {filled} field(s) filled, {pending} required still open. Stop: {self.data['stop_reason']} (exit {self.data['exit_code']})."


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def plain_workday():
    return not (PORTAL["oracle"] or PORTAL["single"] or PORTAL["frame"])


def is_workday_url(url):
    parts = urlsplit(url)
    host = parts.hostname or ""
    if parts.scheme != "https":
        return False
    mark = PORTAL["host"] or (ORACLE_HOST_MARK if PORTAL["oracle"] else HOST_MARK)
    return host == mark or host.endswith("." + mark)


def dialog_open(page):
    return page.evaluate(DIALOG_TEST_JS)


def is_next_label(text):
    return " ".join(str(text).lower().split()) in NEXT_LABELS


def page_of(browser):
    tabs = [page for context in browser.contexts for page in context.pages if is_workday_url(page.url)]
    if len(tabs) != 1:
        raise SystemExit(f"Expected exactly one Workday tab, found {len(tabs)}. Close the extras.")
    if PORTAL["frame"]:
        best = max(tabs[0].frames, key=lambda frame: frame.evaluate(FORM_FRAME_JS))  # the form lives in one iframe
        return best
    return tabs[0]


def inject(page):
    page.evaluate("names => names.forEach(name => { delete globalThis[name]; })", GLOBALS + ORACLE_GLOBALS + GREENHOUSE_GLOBALS + LEVER_GLOBALS)
    in_frame = hasattr(page, "page")  # iframes share their parent CDP session, so they take the plain evaluate path
    session = None if in_frame else page.context.new_cdp_session(page)
    for name in SCRIPTS + (ORACLE_EXTRA_SCRIPTS if PORTAL["oracle"] else []) + (GREENHOUSE_EXTRA_SCRIPTS if PORTAL["greenhouse"] else []) + (LEVER_EXTRA_SCRIPTS if PORTAL["lever"] else []):
        source = (EXTENSION / name).read_text(encoding="utf-8")
        if in_frame:
            page.evaluate("() => {" + source + chr(10) + "}")
        else:
            session.send("Runtime.evaluate", {"expression": source})  # CDP evaluate is not bound by page CSP


ORACLE_NEXT_SELECTOR = 'button[data-qa="applyFlowPaginationNextButton"]'
ORACLE_TITLE_JS = "() => { const heading = [...document.querySelectorAll('h1,h2')].find(n => n.getClientRects().length); return (location.pathname.split('/apply/')[1] || '') + ' ' + (heading ? heading.textContent : ''); }"


def next_selector():
    if PORTAL["frame"]:
        return ICIMS_NEXT_SELECTOR
    return ORACLE_NEXT_SELECTOR if PORTAL["oracle"] else NEXT_SELECTOR


ICIMS_OVERRIDE = "input[name=override][type=checkbox]"


def accept_address_override(page):
    """iCIMS asks 'Use this address anyway?' when it cannot verify city, zip and state; the person chose to accept it."""
    box = page.locator(ICIMS_OVERRIDE)
    if box.count() != 1 or not box.is_visible():
        return False
    box.check()
    return True


def step_title(page):
    if PORTAL["frame"]:
        return " ".join(page.evaluate(ICIMS_TITLE_JS).split())
    if PORTAL["single"]:
        return "single page application form"
    if PORTAL["oracle"]:
        return " ".join(page.evaluate(ORACLE_TITLE_JS).split())
    return page.evaluate("(sel) => (document.querySelector(sel)?.textContent || '').replace(/\\s+/g, ' ').trim()", STEP_SELECTOR)


OPT_WORD = r"\bopt\b(?![- ]?(?:in|out)\b)"  # "opt in" and "opt out" are marketing wording, not work authorization
OPT_CONTEXT = r"(?:\bead\b|\bstem\b|\bf-?1\b|practical training|sponsorship|\bvisa\b|work authori[sz]ation|extension|24-?month)"
OPT_IMMIGRATION = OPT_WORD + r".{0,80}" + OPT_CONTEXT + "|" + OPT_CONTEXT + r".{0,80}" + OPT_WORD
IMMIGRATION_LABEL = re.compile(r"sponsorship|\bsponsor\b.{0,80}(?:visa|work|employment|immigration|h-?1b)|\bvisa\b|h-?1b|immigration|work permit|\bead\b|employment authori[sz]ation|practical training|\bstem[- ]opt\b|" + OPT_IMMIGRATION, re.I)  # stale prefilled immigration answers must not become stored truth
UNLEARNABLE_LABELS = {"login", "type", "number", "username", "user name"}  # account fields and bare option ids are not reusable answers
SPONSORSHIP_KEYS = ("sponsorship_now", "sponsorship_future", "sponsorship_now_or_future")
SPONSORSHIP_SOURCE = "User rule 2026-10-25: H-1B sponsorship questions (now or future) are answered No"
H1B_LABEL = re.compile(r"h-?1b", re.I)
EAD_OPT_LABEL = re.compile(r"\bead\b|employment authori[sz]ation|practical training|\bstem[- ]opt\b|" + OPT_IMMIGRATION, re.I)


def sponsorship_answer(label):
    """User rule 2026-10-25: a question naming H-1B is No; one naming only EAD or OPT is Yes; any other sponsorship question is No."""
    text = str(label or "")
    if H1B_LABEL.search(text):
        return "No"
    return "Yes" if EAD_OPT_LABEL.search(text) else "No"


def build_profile():
    profile = resolve_profile(SOURCE)
    for key in SPONSORSHIP_KEYS:
        profile["values"][key] = {"value": "No", "source": SPONSORSHIP_SOURCE}
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


def greenhouse_upload(page, slot, path):
    """Attach a file to the one Greenhouse input for the slot when it is empty; returns a status line or None."""
    if not path:
        return None
    locator = page.locator(GREENHOUSE_UPLOAD_SELECTORS[slot])
    if locator.count() != 1:
        return f"{slot}: upload input not found exactly once; attach it yourself."
    if page.evaluate("el => el.files.length", locator.element_handle()):
        return f"{slot}: a file is already attached; left alone."
    locator.set_input_files(str(path))
    return f"{slot}: attached {Path(path).name}"


def require_writable_step(page):
    """Raise unless the page is a known, non-Review step with no dialog open; returns the step title."""
    if not PORTAL["frame"] and not is_workday_url(page.url):
        raise DriverStopped("The page left the expected HTTPS host. Continue manually.")
    if dialog_open(page):
        raise DriverStopped("A dialog is open. Continue manually.")
    title = step_title(page)
    if FINAL_STEP_PATTERN.search(title):
        raise ReviewReached("Review page reached.")
    if not title and plain_workday():
        raise DriverStopped("The current step is unknown. Continue manually.")
    return title


def upload_resume(page, resume):
    """Attach the reviewed resume when the page has exactly one Workday upload input; returns an upload record or None."""
    found = page.evaluate("!!PortalWorkdayUpload.find()")
    if not found:
        return None
    if not resume:
        raise DriverStopped("Upload input found but no reviewed resume given. Attach it manually.")
    record = {"file": Path(resume).name, "sha256": sha256_file(resume), "status": "unconfirmed"}
    try:
        require_writable_step(page)
        outcome = page.evaluate(UPLOAD_JS, attachment_for(resume))
    except DriverStopped:
        raise
    except Exception as error:  # noqa: BLE001 - an unconfirmed upload is reported, any other error stops the run
        if "not confirmed" in str(error):
            return record
        raise DriverFailed(f"Upload failed: {str(error)[:120]}") from error
    record["status"] = "already attached" if outcome == "already attached" else "confirmed"
    return record


def compare_attachments(found, expected):
    """Names on the Review page against the files apply.json named; read-only."""
    found, expected = sorted(set(found)), sorted(set(expected))
    missing = [name for name in expected if name not in found]
    unexpected = [name for name in found if name not in expected]
    return {"expected": expected, "found": found, "missing": missing, "unexpected": unexpected, "ok": not missing and not unexpected}


def review_attachment_check(page, expected):
    """Lists attachment names on the Review page and compares them to the reviewed files; writes nothing."""
    return compare_attachments(page.evaluate(REVIEW_ATTACHMENTS_JS), expected)


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


def has_heading(page, heading):
    return page.evaluate("text => [...document.querySelectorAll('h1,h2,h3,h4')].some(node => node.textContent.trim() === text)", heading)


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
    """Add history rows until each group has as many as the profile has records; returns False if an Add button is missing or rows are still short after the bounded attempts."""
    if PORTAL["oracle"]:
        return True  # Oracle history sections have no Workday Add buttons
    for group, heading in HISTORY_SECTIONS.items():
        needed = len(profile.get(group, []))
        if not has_heading(page, heading):
            continue
        for _ in range(needed + 1):
            if len(row_ids(scan(page, profile), group)) >= needed:
                break
            require_writable_step(page)
            if not click_add(page, heading):
                return False
            time.sleep(ROW_SETTLE_SECONDS)
        if len(row_ids(scan(page, profile), group)) < needed:
            return False  # Add was clicked but no row appeared; never bind into too few rows
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


def is_sponsorship(field):
    return "sponsorship" in str(field.get("key") or "") or bool(IMMIGRATION_LABEL.search(str(field.get("label") or "")))


def selection_for(field):
    """Sponsorship answers overwrite what the portal prefilled, because the rule is always No."""
    selection = {"id": field["id"], "value": field["proposal"]}
    if is_sponsorship(field):
        selection["overwrite"] = True
        selection["value"] = sponsorship_answer(field.get("label"))
    return selection


def prepared(fields):
    return [f for f in fields if f["status"] == "prepared" and f["proposal"] != "" and not f["blocked"] and f["type"] != "file" and not f["disabled"]]


def unanswered(fields):
    """Required, still-empty, unblocked fields after filling: the ones a person must answer."""
    return [f for f in fields if f["required"] and not f["blocked"] and f["current"] in ("", False) and f["type"] != "file"]


def learnable(fields):
    """Fields whose typed value may be remembered by exact question; history row fields differ per row, so never."""
    counts = {}
    for f in fields:
        counts[f["label"]] = counts.get(f["label"], 0) + 1
    return [f for f in fields if not f["blocked"] and f["current"] not in ("", False) and f["proposal"] == "" and f["type"] != "checkbox" and not f["record"] and counts[f["label"]] == 1 and not (f["type"] == "select-one" and str(f["current"]).isdigit()) and f["type"] != "password" and f["label"].strip().lower() not in UNLEARNABLE_LABELS and not IMMIGRATION_LABEL.search(f["label"])]


def learn(page, profile, fields):
    """Store what the person entered for fields that were empty and unanswered before; history rows and file fields never."""
    eligible = {f["id"] for f in fields if not f.get("record") and not f["blocked"] and f["current"] in ("", False) and f["proposal"] == "" and f["type"] != "file"}
    memory = answer_memory.load_memory()
    learned = 0
    for field in learnable(scan(page, profile, bind_rows(page, profile))):
        if field["id"] in eligible and answer_memory.remember(memory, field["label"], str(field["current"]), source="manual"):
            learned += 1
    if learned:
        answer_memory.save_memory(memory)
    return learned


def run_page(page, profile, dry, event=None):
    event = event if event is not None else {}
    if not dry and not ensure_rows(page, profile):
        raise DriverStopped("Could not add every history row. Add them manually before continuing.")
    bindings = bind_rows(page, profile)
    fields = scan(page, profile, bindings)
    todo = prepared(fields)
    event.update(fields=len(fields), blocked_gates=[f["label"][:REPORT_LABEL_LIMIT] for f in fields if f["blocked"]][:REPORT_LABEL_LIMIT])
    print(f"  fields {len(fields)} | proposals {len(todo)} | blocked {sum(f['blocked'] for f in fields)}")
    if dry:
        for f in fields:
            print(f"    [{f['status']}] {f['type']:9} {f['label'][:60]!r} -> {str(f['proposal'])[:30]!r} (now {str(f['current'])[:20]!r})")
        return fields
    fill_script = FILL_JS if plain_workday() else FILL_JS_DIALOG_ONLY
    for round_number in range(FILL_ROUNDS):
        if not todo:
            break
        require_writable_step(page)
        results = page.evaluate(fill_script, [selection_for(f) for f in todo])
        counts = {}
        for r in results:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        print(f"  fill round {round_number + 1}:", counts)
        event["filled"] = event.get("filled", 0) + counts.get("filled", 0)
        for r in results:
            if r["status"] in ("failed", "refused"):
                print("   !", r.get("message", "")[:120])
        if len(results) != len(todo) or any(r["status"] not in FILL_OK_STATUSES for r in results):
            gate = any(r["status"] in FILL_GATE_STATUSES for r in results) and not any(r["status"] == "failed" for r in results)
            raise (DriverStopped if gate else DriverFailed)("A field was not filled successfully. Review it manually before continuing.")
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
        require_writable_step(page)
        gaps = unanswered(scan(page, profile))
        if not gaps:
            return True
        time.sleep(GAP_POLL_SECONDS)
    return False


def check_review(page, args, report):
    """Read-only: compare attachment names on the Review page with the files this run was given."""
    expected = [Path(path).name for path in (args.resume, args.cover) if path]
    if not expected or not plain_workday():
        return
    result = review_attachment_check(page, expected)
    report.data["review_attachments"] = result
    print("  Review attachments:", "match" if result["ok"] else f"MISMATCH missing {result['missing']} unexpected {result['unexpected']}")


def record_upload(event, file_name, path, status):
    event["uploads"].append({"file": file_name, "sha256": sha256_file(path) if path else None, "status": status})


def drive(page, args, report):
    """Walk pages until Review or a stop; every stop is a DriverStopped the caller turns into a report."""
    for _ in range(MAX_PAGES):
        if dialog_open(page):
            raise DriverStopped("A dialog is open. Stopping so nothing is discarded or submitted.")
        title = step_title(page)
        print(title)
        event = report.new_page(title)
        if FINAL_STEP_PATTERN.search(title) and not args.dry:
            print("  Review page reached. Nothing is filled here. Check it and submit yourself.")
            check_review(page, args, report)
            raise ReviewReached()
        if not title and plain_workday() and not args.dry:
            raise DriverStopped("The current step is unknown. Continue manually.")
        inject(page)
        profile = build_profile()
        if PORTAL["oracle"] and not args.dry and "section/3" in title:
            for line in oracle_history.apply(page, profile):
                print("  history:", line)
        fields = run_page(page, profile, args.dry, event)
        if not args.dry:
            if PORTAL["oracle"]:
                for line in oracle_attach.apply(page, args.resume, args.cover, args.no_cover):
                    print("  attach:", line)
            if PORTAL["single"]:
                for slot, path in (("resume", args.resume), ("cover", args.cover)):
                    line = single_upload.upload(page, slot, path)
                    if line:
                        print("  upload:", line)
                        record_upload(event, Path(path).name, path, line)
            if not PORTAL["oracle"] and not PORTAL["single"]:
                record = upload_resume(page, args.resume)
                if record:
                    event["uploads"].append(record)
                    print(f"  upload: {record['file']} {record['status']}")
                    if record["status"] == "unconfirmed":
                        raise DriverStopped("The upload was not confirmed by exact filename. Check it manually.")
        if args.dry:
            raise ReviewReached("Dry run finished; nothing was written.")
        if not wait_for_person(page, profile):
            event["pending_required"] = [f["label"][:REPORT_LABEL_LIMIT] for f in unanswered(scan(page, profile))][:REPORT_LABEL_LIMIT]
            raise DriverStopped("Required answers are still missing. Stopping here for you.")
        event["learned"] = learn(page, profile, fields)
        if event["learned"]:
            print(f"  learned {event['learned']} answer(s)")
        if PORTAL["single"]:
            raise ReviewReached("Single-page form filled; submit stays manual.")
        if dialog_open(page):
            raise DriverStopped("A dialog appeared while filling. Stopping before Next.")
        button = page.locator(next_selector())
        label = button.get_attribute("value") if PORTAL["frame"] and button.count() == 1 else button.inner_text() if button.count() == 1 else ""
        if button.count() != 1 or not is_next_label(label):
            raise DriverFailed("No single Save and Continue button. Stopping.")
        button.click()
        time.sleep(PAGE_SETTLE_SECONDS)
        if PORTAL["frame"] and step_title(page) == title and accept_address_override(page):
            page.locator(next_selector()).click()
            time.sleep(PAGE_SETTLE_SECONDS)
        if step_title(page) == title:
            raise DriverStopped("The page did not advance (Workday probably flagged a field). Stopping for you.")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume", type=Path, help="Reviewed resume file to attach on the upload step.")
    parser.add_argument("--cover", type=Path, help="Oracle: cover letter to attach, replacing a different one.")
    parser.add_argument("--no-cover", action="store_true", help="Oracle: remove any attached cover letter.")
    parser.add_argument("--portal", choices=["workday", "oracle", *SINGLE_PAGE_HOSTS], default="workday")
    parser.add_argument("--dry", action="store_true", help="Scan and print proposals only; write and click nothing.")
    parser.add_argument("--report-dir", type=Path, default=None, help="Where to write the run report (default data/runs).")
    return parser.parse_args(argv)


def execute(args):
    """Run the driver once and return its RunReport (exit code and stop reason set); writes nothing to disk."""
    getattr(sys.stdout, "reconfigure", lambda **_: None)(errors="replace")  # page labels can hold symbols the console codepage lacks
    PORTAL["oracle"] = args.portal == "oracle"
    PORTAL["greenhouse"] = args.portal == "greenhouse"
    PORTAL["lever"] = args.portal == "lever"
    PORTAL["frame"] = args.portal in FRAME_PORTALS
    PORTAL["single"] = args.portal in SINGLE_PAGE_HOSTS and args.portal not in FRAME_PORTALS
    PORTAL["host"] = SINGLE_PAGE_HOSTS.get(args.portal, "")
    report = RunReport(args.portal, args.dry)
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(CDP_URL)
            try:
                drive(page_of(browser), args, report)
            finally:
                browser.close()
        raise DriverStopped("Page limit reached.")
    except DriverStopped as stop:
        code, reason = stop.code, str(stop)
    except SystemExit as stop:
        code, reason = EXIT_FAILURE, str(stop.code)
    except Exception as error:  # noqa: BLE001 - any crash still produces a report and a failure code
        code, reason = EXIT_FAILURE, f"{type(error).__name__}: {str(error)[:160]}"
    return report.finish_report(reason, code)


def main(argv=None):
    args = parse_args(argv)
    report = execute(args)
    print(report.data["stop_reason"])
    print("Stopped. Submit stays manual.")
    path = report.write(args.report_dir)
    print(report.summary())
    print(f"Report: {path}")
    return report.data["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
