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
from contextvars import ContextVar
from pathlib import Path
from uuid import uuid4

import oracle_attach
import oracle_history
import single_upload
from urllib.parse import urlsplit

from browser_target import select_tab, sync_playwright
from shared_storage import atomic_json

import answer_memory
import failure_telemetry as telemetry
import picker_aliases
import reuse_mode as reuse
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
PORTAL_CONTEXT = ContextVar("portal_settings", default=None)
UNANSWERED_KEY = "unanswered"
LABEL_KEY, TYPE_KEY, OPTIONS_KEY = "label", "type", "options"
HOST_KEY, RECORD_KEY = "portal_host", "record"
REQUIRED_KEY, PROTECTED_KEY, BLOCKED_KEY = "required", "protected", "blocked"
QUEUE_LABEL_LIMIT = 300
QUEUE_OPTIONS_LIMIT = 50
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
FILL_ROUNDS = 20  # a form that reflows after each write may take one field per round
PAGE_SETTLE_SECONDS = 4
NEXT_TIMEOUT_SECONDS = 15
NEXT_POLL_SECONDS = 0.1
UPLOAD_CONFIRM_SECONDS = 15
RERENDER_RETRY_CAP = 1
REPORT_SECRETS = ContextVar("report_secrets", default=None)
RUN_MODE = ContextVar("run_mode", default=None)
GAP_POLL_SECONDS = 3
GAP_WAIT_SECONDS = 600
STEP_PATTERN = re.compile(r"step (\d+) of (\d+)")
RUNS_DIR = HERE / "data" / "runs"
EXIT_REVIEW, EXIT_GATE, EXIT_FAILURE = 0, 2, 3  # Review reached, human gate, failure
REPORT_LABEL_LIMIT = 60
SUMMARY_DIFF_LIMIT = 10
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
UPLOAD_JS = "async ([attachment, timeout]) => PortalWorkdayUpload.upload(PortalWorkdayUpload.find(), attachment, " + PAGE_BOUNDARY_JS + ", {timeout, detailed: true})"
REPLACE_UPLOAD_JS = "async ([attachment, timeout, slot]) => PortalWorkdayUpload.replace(attachment, slot, " + PAGE_BOUNDARY_JS + ", {timeout})"
INSPECT_UPLOAD_JS = "slot => PortalWorkdayUpload.inspectSlot(slot)"
UPLOAD_SLOTS = ("resume", "cover")
PAGE_STATE_JS = r"""() => {
  const visible = node => node.getClientRects().length && !node.closest('[hidden],[aria-hidden=true]');
  const values = [...document.querySelectorAll('input,textarea,select')].flatMap(node =>
    [node.value, node.selectedOptions?.[0]?.textContent]).filter(Boolean).sort((a, b) => b.length - a.length);
  const scrub = text => { for (const value of values) text = text.split(value).join('[redacted]'); return text.slice(0, 240); };
  const dialog = [...document.querySelectorAll('[role=dialog],[role=alertdialog],dialog[open]')]
    .find(node => visible(node) && node.textContent.trim() && !/cookie/i.test(node.textContent));
  const title = dialog && (dialog.getAttribute('aria-label') ||
    document.getElementById(dialog.getAttribute('aria-labelledby'))?.textContent || dialog.querySelector('h1,h2,h3')?.textContent || '');
  return {dialog: dialog ? {title: scrub(title).slice(0, 120), text: scrub(dialog.innerText || dialog.textContent).slice(0, 120)} : null,
    inline_errors: [...document.querySelectorAll('[role=alert],[data-automation-id*=error],[id$="-error"]')]
      .filter(visible).slice(0, 10).map(node => scrub(node.innerText || node.textContent)).filter(Boolean)};
}"""
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
    """Per-page events, masked conflict previews, and bounded upload diagnostics."""

    def __init__(self, portal="workday", dry=False, mode=None):
        self._secrets = REPORT_SECRETS.get() if REPORT_SECRETS.get() is not None else set()
        self.data = {"started": time.strftime("%Y-%m-%dT%H:%M:%S"), "portal": portal, "dry": dry, "pages": [],
                     "stop_reason": None, "exit_code": None, "review_attachments": None, UNANSWERED_KEY: [],
                     telemetry.REVISION_KEY: telemetry.source_revision(HERE),
                     reuse.MODE_KEY: mode or (reuse.REUSE if portal == "workday" else reuse.FRESH),
                     reuse.LAST_USED_KEY: reuse.UNKNOWN}

    def record_unanswered(self, fields, url):
        entries = []
        for field in unanswered(fields):
            if field.get(RECORD_KEY) is not None or field.get(BLOCKED_KEY) or answer_memory.is_protected(field):
                continue
            options = [str(option.get(LABEL_KEY, "") if isinstance(option, dict) else option)[:QUEUE_LABEL_LIMIT]
                       for option in field.get(OPTIONS_KEY, [])][:QUEUE_OPTIONS_LIMIT]
            entries.append({LABEL_KEY: telemetry.clean_text(field[LABEL_KEY], report_secrets(), QUEUE_LABEL_LIMIT), TYPE_KEY: field[TYPE_KEY],
                            OPTIONS_KEY: [telemetry.clean_text(option, report_secrets(), QUEUE_LABEL_LIMIT) for option in options],
                            HOST_KEY: urlsplit(url).hostname or "", REQUIRED_KEY: True})
        self.data[UNANSWERED_KEY] = entries[:telemetry.FIELD_LIMIT]

    def new_page(self, title):
        event = {"title": telemetry.clean_text(title, report_secrets()), "fields": 0, "filled": 0, "pending_required": [], "blocked_gates": [], "uploads": [], "learned": 0,
                 telemetry.FIELD_RECORDS_KEY: [], reuse.KEPT_KEY: 0, reuse.DIFF_KEY: 0, reuse.FORCED_KEY: 0,
                 reuse.DIFFS_KEY: [], reuse.EXTRAS_KEY: []}
        self.data["pages"].append(event)
        return event

    def finish_report(self, reason, code):
        self.data.update(stop_reason=telemetry.clean_text(reason, report_secrets()), exit_code=code)
        return self

    def write(self, directory=None, path=None):
        directory = Path(directory or RUNS_DIR)
        path = Path(path) if path else directory / f"{time.strftime('%Y%m%d_%H%M%S')}_{self.data['portal']}_{uuid4().hex}.json"
        if "url" in self.data:
            self.data["url"] = telemetry.safe_url(self.data["url"])
        if "notes" in self.data:
            self.data["notes"] = [telemetry.clean_text(note, self._secrets) for note in self.data["notes"][:telemetry.FIELD_LIMIT]]
        atomic_json(path, self.data)
        return path

    def summary(self):
        pages = self.data["pages"]
        filled = sum(page["filled"] for page in pages)
        pending = sum(len(page["pending_required"]) for page in pages)
        lines = [f"{len(pages)} page(s), {filled} field(s) filled, {pending} required still open. Stop: {self.data['stop_reason']} (exit {self.data['exit_code']}).",
                 f"Prefill differences: {sum(page.get(reuse.DIFF_KEY, 0) for page in pages)}; "
                 f"kept {sum(page.get(reuse.KEPT_KEY, 0) for page in pages)}, forced {sum(page.get(reuse.FORCED_KEY, 0) for page in pages)}."]
        differences = [difference for page in pages for difference in page.get(reuse.DIFFS_KEY, [])]
        for difference in differences[:SUMMARY_DIFF_LIMIT]:
            lines.append(f"  {difference[reuse.LABEL_KEY]} ({difference[reuse.TYPE_KEY]}): {difference[reuse.PREVIEW_KEY]}")
        if len(differences) > SUMMARY_DIFF_LIMIT:
            lines.append("  More differences are recorded in the per-job report.")
        return "\n".join(lines)


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def report_secrets():
    return REPORT_SECRETS.get() or set()


def remember_report_secrets(profile, fields=()):
    secrets = REPORT_SECRETS.get()
    if secrets is not None:
        secrets.update(telemetry.answer_strings(profile))
        for field in fields:
            for key in telemetry.ANSWER_KEYS:
                secrets.update(telemetry.answer_strings(field.get(key)))


def page_state(page):
    state = page.evaluate(PAGE_STATE_JS)
    secrets = report_secrets()
    dialog = state.get("dialog")
    return {"title": telemetry.clean_text(step_title(page), secrets), "url": telemetry.safe_url(page.url, secrets),
            "inline_errors": [telemetry.clean_text(text, secrets) for text in state.get("inline_errors", [])[:telemetry.ERROR_LIMIT]],
            "dialog": {key: telemetry.clean_text(dialog.get(key), secrets, telemetry.DIALOG_LIMIT) for key in ("title", "text")} if dialog else None}


def wait_next_outcome(page, before):
    start = time.monotonic()
    after = before
    observation_errors = 0
    error_type = None
    while True:
        try:
            after = page_state(page)
        except Exception as error:
            observation_errors += 1
            error_type = type(error).__name__
        reason = telemetry.next_reason(before, after, time.monotonic() - start >= NEXT_TIMEOUT_SECONDS)
        if reason:
            return {"reason": reason, "before": before, "after": after, "elapsed_seconds": round(time.monotonic() - start, 3),
                    "observation_errors": observation_errors, "last_observation_error_type": error_type}
        time.sleep(NEXT_POLL_SECONDS)


def portal_settings():
    return PORTAL_CONTEXT.get() or PORTAL


def settings_for(portal):
    return {"oracle": portal == "oracle", "greenhouse": portal == "greenhouse", "lever": portal == "lever",
            "frame": portal in FRAME_PORTALS, "single": portal in SINGLE_PAGE_HOSTS and portal not in FRAME_PORTALS,
            "host": SINGLE_PAGE_HOSTS.get(portal, "")}


def plain_workday():
    return not (portal_settings()["oracle"] or portal_settings()["single"] or portal_settings()["frame"])


def reuse_active():
    return plain_workday() and RUN_MODE.get() != reuse.FRESH


def is_workday_url(url):
    parts = urlsplit(url)
    host = parts.hostname or ""
    if parts.scheme != "https":
        return False
    mark = portal_settings()["host"] or (ORACLE_HOST_MARK if portal_settings()["oracle"] else HOST_MARK)
    return host == mark or host.endswith("." + mark)


def dialog_open(page):
    return page.evaluate(DIALOG_TEST_JS)


def is_next_label(text):
    return " ".join(str(text).lower().split()) in NEXT_LABELS


def page_of(browser, url=None, target_id=None):
    tab = select_tab(browser, url, target_id, predicate=is_workday_url)
    if portal_settings()["frame"]:
        best = max(tab.frames, key=lambda frame: frame.evaluate(FORM_FRAME_JS))
        return best
    return tab


def inject(page):
    page.evaluate("names => names.forEach(name => { delete globalThis[name]; })", GLOBALS + ORACLE_GLOBALS + GREENHOUSE_GLOBALS + LEVER_GLOBALS)
    in_frame = hasattr(page, "page")  # iframes share their parent CDP session, so they take the plain evaluate path
    session = None if in_frame else page.context.new_cdp_session(page)
    for name in SCRIPTS + (ORACLE_EXTRA_SCRIPTS if portal_settings()["oracle"] else []) + (GREENHOUSE_EXTRA_SCRIPTS if portal_settings()["greenhouse"] else []) + (LEVER_EXTRA_SCRIPTS if portal_settings()["lever"] else []):
        source = (EXTENSION / name).read_text(encoding="utf-8")
        if in_frame:
            page.evaluate("() => {" + source + chr(10) + "}")
        else:
            session.send("Runtime.evaluate", {"expression": source})  # CDP evaluate is not bound by page CSP


ORACLE_NEXT_SELECTOR = 'button[data-qa="applyFlowPaginationNextButton"]'
ORACLE_TITLE_JS = "() => { const heading = [...document.querySelectorAll('h1,h2')].find(n => n.getClientRects().length); return (location.pathname.split('/apply/')[1] || '') + ' ' + (heading ? heading.textContent : ''); }"


def next_selector():
    if portal_settings()["frame"]:
        return ICIMS_NEXT_SELECTOR
    return ORACLE_NEXT_SELECTOR if portal_settings()["oracle"] else NEXT_SELECTOR


ICIMS_OVERRIDE = "input[name=override][type=checkbox]"


def accept_address_override(page):
    """iCIMS asks 'Use this address anyway?' when it cannot verify city, zip and state; the person chose to accept it."""
    box = page.locator(ICIMS_OVERRIDE)
    if box.count() != 1 or not box.is_visible():
        return False
    box.check()
    return True


def step_title(page):
    if portal_settings()["frame"]:
        return " ".join(page.evaluate(ICIMS_TITLE_JS).split())
    if portal_settings()["single"]:
        return "single page application form"
    if portal_settings()["oracle"]:
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
    if not portal_settings()["frame"] and not is_workday_url(page.url):
        raise DriverStopped("The page left the expected HTTPS host. Continue manually.")
    if dialog_open(page):
        raise DriverStopped("A dialog is open. Continue manually.")
    title = step_title(page)
    if FINAL_STEP_PATTERN.search(title):
        raise ReviewReached("Review page reached.")
    if not title and plain_workday():
        raise DriverStopped("The current step is unknown. Continue manually.")
    return title


def upload_resume(page, resume, event=None, replace_mode=False, slot="resume"):
    """Attach a reviewed file; replacement requires one unambiguous Workday slot."""
    state = page.evaluate(INSPECT_UPLOAD_JS, slot) if replace_mode else None
    found = state.get("status") != "absent" if replace_mode else page.evaluate("!!PortalWorkdayUpload.find()")
    if not found:
        return None
    if not resume and not replace_mode:
        raise DriverStopped("Upload input found but no reviewed resume given. Attach it manually.")
    record = {"file": Path(resume).name if resume else None, "sha256": sha256_file(resume) if resume and not replace_mode else None, "status": "unconfirmed", "subtype": slot,
              "reason": "upload_timeout", "observed_filename": "", "observed_size": None, "elapsed_seconds": 0,
              "container_replaced": False}
    if event is not None:
        event["uploads"].append(record)
    if replace_mode and (state.get("status") != "ready" or not resume):
        record["reason"] = "upload_removal_ambiguous" if state.get("status") != "ready" else "upload_missing_replacement"
        raise DriverStopped(f"Attachment slot {slot}: {record['reason']}. Replace it manually.")
    start = time.monotonic()
    try:
        require_writable_step(page)
        script = REPLACE_UPLOAD_JS if replace_mode else UPLOAD_JS
        attachment = attachment_for(resume)
        if replace_mode:
            record["sha256"] = attachment["sha256"]
        arguments = [attachment, UPLOAD_CONFIRM_SECONDS * 1000] + ([slot] if replace_mode else [])
        outcome = page.evaluate(script, arguments)
    except DriverStopped:
        record["reason"] = "upload_boundary_stopped"
        raise
    except Exception as error:  # noqa: BLE001 - an unconfirmed upload is reported, any other error stops the run
        record["elapsed_seconds"] = round(time.monotonic() - start, 3)
        if "not confirmed" in str(error):
            return record
        record.update(reason="upload_error", error_type=type(error).__name__)
        raise DriverFailed("Upload failed before confirmation. See the upload record; attach it manually.") from error
    record["elapsed_seconds"] = round(time.monotonic() - start, 3)
    if isinstance(outcome, dict):
        record["reason"] = telemetry.upload_reason(outcome)
        record["status"] = outcome.get("status", "unconfirmed") if outcome.get("confirmed") else "unconfirmed"
        record["observed_filename"] = telemetry.clean_text(outcome.get("observed_filename"), report_secrets())
        record["observed_size"] = outcome.get("observed_size") if isinstance(outcome.get("observed_size"), (int, float)) else None
        record["container_replaced"] = outcome.get("container_replaced") is True
        if replace_mode:
            record["removal"] = telemetry.clean_text(outcome.get("removal"))
            if outcome.get("status") == "ambiguous" or outcome.get("removal") in {"ambiguous", "identity_changed", "timeout"}:
                record["reason"] = "upload_removal_ambiguous" if outcome.get("removal") != "timeout" else "upload_removal_timeout"
                raise DriverStopped(f"Attachment slot {slot}: {record['reason']}. Replace it manually.")
            if outcome.get("confirmed") and event is not None:
                event[reuse.FORCED_KEY] = event.get(reuse.FORCED_KEY, 0) + 1
    else:
        record.update(status="already attached" if outcome == "already attached" else "confirmed", reason="upload_confirmed")
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


def scan(page, profile, bindings=None, mode=None):
    if mode is not None:
        return page.evaluate("([profile, bindings, mode]) => PortalEngine.scan(profile, {bindings, mode})", [profile, bindings or {}, mode])
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
    """Add only missing records in reuse mode; fresh mode retains the original row count rule."""
    if portal_settings()["oracle"]:
        return True  # Oracle history sections have no Workday Add buttons
    if reuse_active():
        fields = scan(page, profile)
        for group, heading in HISTORY_SECTIONS.items():
            if not has_heading(page, heading):
                continue
            for _ in range(len(profile.get(group, [])) + 1):
                try:
                    missing = reuse.history_plan(fields, profile)[reuse.MISSING_KEY][group]
                except ValueError as error:
                    raise DriverStopped(str(error)) from error
                if not missing:
                    break
                require_writable_step(page)
                if not click_add(page, heading):
                    return False
                time.sleep(ROW_SETTLE_SECONDS)
                updated = scan(page, profile)
                if len(row_ids(updated, group)) <= len(row_ids(fields, group)):
                    return False
                fields = updated
            else:
                return False
        return True
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
    """Bind by identity in reuse mode and by page order in fresh mode."""
    fields = scan(page, profile)
    if reuse_active():
        try:
            return reuse.history_plan(fields, profile)[reuse.BINDINGS_KEY]
        except ValueError as error:
            raise DriverStopped(str(error)) from error
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
    return [f for f in fields if not f["blocked"] and not answer_memory.is_protected(f) and f["current"] not in ("", False) and f["proposal"] == "" and f["type"] != "checkbox" and f["record"] is None and counts[f["label"]] == 1 and not (f["type"] == "select-one" and str(f["current"]).isdigit()) and f["type"] != "password" and f["label"].strip().lower() not in UNLEARNABLE_LABELS and not IMMIGRATION_LABEL.search(f["label"])]


def learn(page, profile, fields):
    """Store what the person entered for fields that were empty and unanswered before; history rows and file fields never."""
    eligible = {f["id"] for f in fields if f.get("record") is None and not f["blocked"] and f["current"] in ("", False) and f["proposal"] == "" and f["type"] != "file"}
    candidates = [field for field in learnable(scan(page, profile, bind_rows(page, profile))) if field["id"] in eligible]
    if not candidates:
        return 0
    return answer_memory.update_memory(lambda memory: sum(answer_memory.remember(
        memory, field["label"], str(field["current"]), source="manual") for field in candidates))


def run_page(page, profile, dry, event=None, mode=None):
    token = RUN_MODE.set(mode or RUN_MODE.get())
    try:
        return fill_page(page, profile, dry, event)
    finally:
        RUN_MODE.reset(token)


def fill_page(page, profile, dry, event=None):
    event = event if event is not None else {}
    if not dry and not ensure_rows(page, profile):
        raise DriverStopped("Could not add every history row. Add them manually before continuing.")
    bindings = bind_rows(page, profile)
    fields = scan(page, profile, bindings)
    remember_report_secrets(profile, fields)
    todo = prepared(fields)
    preserved = set()
    force_ids = set()
    completed = set()
    if reuse_active():
        try:
            plan = reuse.history_plan(fields, profile)
        except ValueError as error:
            raise DriverStopped(str(error)) from error
        preserved = plan[reuse.PRESERVED_KEY]
        event[reuse.EXTRAS_KEY] = plan[reuse.EXTRAS_KEY][:telemetry.FIELD_LIMIT]
        if len(plan[reuse.EXTRAS_KEY]) > telemetry.FIELD_LIMIT:
            event["extra_history_rows_truncated"] = True
        force_ids = {field["id"] for field in todo if is_sponsorship(field) or reuse.forced(field)}
        reuse.record_classifications(event, fields, force_ids)
        todo = reuse_todo(todo, preserved, force_ids, completed)
    event.update(fields=len(fields), blocked_gates=[telemetry.clean_text(f["label"], report_secrets(), REPORT_LABEL_LIMIT) for f in fields if f["blocked"]][:REPORT_LABEL_LIMIT])
    print(f"  fields {len(fields)} | proposals {len(todo)} | blocked {sum(f['blocked'] for f in fields)}")
    if dry:
        for f in fields:
            print(f"    [{f['status']}] {f['type']:9} {telemetry.clean_text(f['label'], report_secrets(), REPORT_LABEL_LIMIT)!r}")
        return fields
    fill_script = FILL_JS if plain_workday() else FILL_JS_DIALOG_ONLY
    retries = 0
    for round_number in range(FILL_ROUNDS):
        if not todo:
            break
        require_writable_step(page)
        selections = [selection_for(f) for f in todo]
        if reuse_active():
            for selection in selections:
                if selection["id"] in force_ids:
                    selection["overwrite"] = True
        secrets = report_secrets() | {text for field in fields for key in telemetry.ANSWER_KEYS
                                     for text in telemetry.answer_strings(field.get(key))}
        secrets.update(text for selection in selections for text in telemetry.answer_strings(selection.get("value")))
        if REPORT_SECRETS.get() is not None:
            REPORT_SECRETS.get().update(secrets)
        try:
            results = page.evaluate(fill_script, selections)
        except Exception as error:
            results = [{"id": field["id"], "status": "failed", "failure_kind": "error",
                        "reason": "Engine raised " + type(error).__name__} for field in todo]
            telemetry.append_results(event, todo, selections, results, secrets)
            raise DriverFailed("Field engine raised an error. See field_results before continuing manually.") from error
        telemetry.append_results(event, todo, selections, results, secrets)
        counts = {}
        for r in results:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        print(f"  fill round {round_number + 1}:", counts)
        for result in results:
            if result["status"] == "filled" and (not reuse_active() or result.get("id") not in completed):
                category = reuse.FORCED_KEY if reuse_active() and result.get("id") in force_ids else reuse.FILLED_KEY
                event[category] = event.get(category, 0) + 1
                completed.add(result.get("id"))
        for r in results:
            if r["status"] in ("failed", "refused"):
                print("   !", telemetry.clean_text(r.get("message", ""), secrets, 120))
        bad = [r for r in results if r["status"] not in FILL_OK_STATUSES]
        expected_ids = {field["id"] for field in todo}
        if len(results) != len(todo) or {result.get("id") for result in results} != expected_ids:
            event[telemetry.FILL_STOP_KEY] = "result_mismatch"
            raise DriverFailed("Engine result IDs did not match the selected fields. Review field_results manually.")
        rescan_only = bool(bad) and all(telemetry.failure_action(result) == "retry" for result in bad)
        if bad and not rescan_only:
            failed = next((result for result in bad if telemetry.failure_action(result) == "hard"), bad[0])
            field = next(field for field in todo if field["id"] == failed["id"])
            kind = failed.get("failure_kind") or failed.get("reason_code") or failed["status"]
            message = f"Field {telemetry.clean_text(field['label'], secrets)!r} ({telemetry.clean_text(kind)}). Continue manually; see field_results."
            raise (DriverStopped if telemetry.failure_action(failed) == "human" else DriverFailed)(message)
        if bad and retries >= RERENDER_RETRY_CAP:
            event[telemetry.FILL_STOP_KEY] = "retry_cap"
            raise DriverFailed("Rerender retry cap reached. Review field_results manually.")
        if not counts.get("filled") and not bad:
            break
        time.sleep(ROW_SETTLE_SECONDS)
        previous = fields
        fields = scan(page, profile, bindings)
        remember_report_secrets(profile, fields)
        remaining = [f for f in prepared(fields) if f["current"] in ("", False)]
        if reuse_active():
            remaining = reuse_todo(prepared(fields), preserved, force_ids, completed)
        if bad:
            progressed = any(field["id"] in expected_ids and field["current"] not in ("", False) for field in fields
                             if next((old["current"] in ("", False) for old in todo if old["id"] == field["id"]), False))
            if not progressed or not telemetry.row_identity_stable(previous, fields):
                event[telemetry.FILL_STOP_KEY] = "unstable_identity_or_no_progress"
                raise DriverFailed("Rerender has no verified progress or stable row identity. Review field_results manually.")
            retries += 1
            event[telemetry.RETRY_KEY] = retries
        todo = remaining
    else:
        if todo:
            event[telemetry.FILL_STOP_KEY] = "fill_round_cap"
            raise DriverFailed("Fill round cap reached. Review field_results manually.")
    return fields


def reuse_todo(fields, preserved, force_ids, completed):
    return [field for field in fields if (field.get("record") or {}).get("id") not in preserved
            and (field["id"] in force_ids and field["id"] not in completed
                 or field["id"] not in force_ids and reuse.empty(field.get("current")))]


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
    for key in ("expected", "found", "missing", "unexpected"):
        if len(result[key]) > telemetry.FIELD_LIMIT:
            result["truncated"] = True
        result[key] = [telemetry.clean_text(name, report_secrets()) for name in result[key][:telemetry.FIELD_LIMIT]]
    report.data["review_attachments"] = result
    print("  Review attachments:", "match" if result["ok"] else f"MISMATCH missing {result['missing']} unexpected {result['unexpected']}")


def record_upload(event, file_name, path, status):
    event["uploads"].append({"file": file_name, "sha256": sha256_file(path) if path else None, "status": status})


def drive(page, args, report):
    """Walk pages until Review or a stop; every stop is a DriverStopped the caller turns into a report."""
    for _ in range(MAX_PAGES):
        title = step_title(page)
        event = report.new_page(title)
        if dialog_open(page):
            event[telemetry.NEXT_KEY] = {"reason": "dialog_opened", "after": page_state(page)}
            raise DriverStopped("A dialog is open. Stopping so nothing is discarded or submitted.")
        print(title)
        if FINAL_STEP_PATTERN.search(title) and not args.dry:
            print("  Review page reached. Nothing is filled here. Check it and submit yourself.")
            check_review(page, args, report)
            raise ReviewReached()
        if not title and plain_workday() and not args.dry:
            raise DriverStopped("The current step is unknown. Continue manually.")
        inject(page)
        profile = build_profile()
        if getattr(args, "batch", False):
            profile["consents"] = []
        if portal_settings()["oracle"] and not args.dry and "section/3" in title:
            result = oracle_history.apply(page, profile)
            for line in result:
                print("  history:", line)
            if not result.ok:
                raise DriverStopped(f"Oracle history: {result.reason}; field={result.field}")
        try:
            fields = run_page(page, profile, args.dry, event)
        except DriverStopped:
            try:
                state = page_state(page)
                if state["dialog"]:
                    event[telemetry.NEXT_KEY] = {"reason": "dialog_opened", "after": state}
                report.record_unanswered(scan(page, profile, bind_rows(page, profile)), page.url)
            except Exception:
                pass
            raise
        report.record_unanswered(fields, page.url)
        if not args.dry:
            if portal_settings()["oracle"]:
                result = oracle_attach.apply(page, args.resume, args.cover, args.no_cover)
                for line in result:
                    print("  attach:", line)
                if not result.ok:
                    raise DriverStopped(f"Oracle attachment: {result.reason}; field={result.field}")
            if portal_settings()["single"]:
                for slot, path in (("resume", args.resume), ("cover", args.cover)):
                    line = single_upload.upload(page, slot, path)
                    if line:
                        print("  upload:", line)
                        record_upload(event, Path(path).name, path, line)
            if not portal_settings()["oracle"] and not portal_settings()["single"]:
                for slot in (UPLOAD_SLOTS if reuse_active() else UPLOAD_SLOTS[:1]):
                    try:
                        record = upload_resume(page, getattr(args, slot), event, replace_mode=reuse_active(), slot=slot)
                    except DriverStopped:
                        state = page_state(page)
                        if state["dialog"]:
                            event[telemetry.NEXT_KEY] = {"reason": "dialog_opened", "after": state}
                        raise
                    if record:
                        print(f"  upload: {record['file']} {record['status']}")
                        if record["status"] == "unconfirmed":
                            raise DriverStopped(f"Attachment slot {record['subtype']}: {record['reason']}. Check it manually.")
        if args.dry:
            raise ReviewReached("Dry run finished; nothing was written.")
        latest = scan(page, profile, bind_rows(page, profile)) if getattr(args, "batch", False) else fields
        batch_gaps = getattr(args, "batch", False) and any(
            field.get(REQUIRED_KEY) and field.get("current") in ("", False) and field.get(TYPE_KEY) != "file" for field in latest)
        if batch_gaps or not wait_for_person(page, profile):
            remaining = scan(page, profile)
            report.record_unanswered(remaining, page.url)
            event["pending_required"] = [telemetry.clean_text(f["label"], report_secrets(), REPORT_LABEL_LIMIT) for f in unanswered(remaining)][:REPORT_LABEL_LIMIT]
            raise DriverStopped("Required answers are still missing. Stopping here for you.")
        report.record_unanswered([], page.url)
        event["learned"] = learn(page, profile, fields)
        if event["learned"]:
            print(f"  learned {event['learned']} answer(s)")
        if portal_settings()["single"]:
            raise ReviewReached("Single-page form filled; submit stays manual.")
        if dialog_open(page):
            event[telemetry.NEXT_KEY] = {"reason": "dialog_opened", "after": page_state(page)}
            raise DriverStopped("A dialog appeared while filling. Stopping before Next.")
        button = page.locator(next_selector())
        label = button.get_attribute("value") if portal_settings()["frame"] and button.count() == 1 else button.inner_text() if button.count() == 1 else ""
        if button.count() != 1 or not is_next_label(label):
            raise DriverFailed("No single Save and Continue button. Stopping.")
        before = page_state(page)
        event[telemetry.NEXT_KEY] = {"reason": "click_pending", "before": before}
        try:
            require_writable_step(page)
        except DriverStopped:
            after = page_state(page)
            event[telemetry.NEXT_KEY] = {"reason": "dialog_opened" if after["dialog"] else "boundary_stopped",
                                         "before": before, "after": after}
            raise
        button.click()
        outcome = wait_next_outcome(page, before)
        event[telemetry.NEXT_KEY] = outcome
        if outcome["reason"] != "step_changed":
            raise DriverStopped(f"Next stopped: {outcome['reason']}. See next_outcome and continue manually.")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume", type=Path, help="Reviewed resume file to attach on the upload step.")
    parser.add_argument("--cover", type=Path, help="Reviewed cover letter; Workday reuse and Oracle can replace an existing attachment.")
    parser.add_argument("--no-cover", action="store_true", help="Oracle: remove any attached cover letter.")
    parser.add_argument("--portal", choices=["workday", "oracle", *SINGLE_PAGE_HOSTS], default="workday")
    parser.add_argument("--dry", action="store_true", help="Scan and print proposals only; write and click nothing.")
    parser.add_argument("--fresh", action="store_true", help="Use the original empty-form behavior for Workday.")
    parser.add_argument("--job-url", help="Select the tab by normalized job URL.")
    parser.add_argument("--target-id", help="Select the exact CDP target, including after navigation.")
    parser.add_argument("--batch", action="store_true", help="Stop at unanswered fields for consolidated review.")
    parser.add_argument("--report-dir", type=Path, default=None, help="Where to write the run report (default data/runs).")
    return parser.parse_args(argv)


def execute(args, url=None, target_id=None):
    """Run once and return its report; the caller persists the report."""
    getattr(sys.stdout, "reconfigure", lambda **_: None)(errors="replace")  # page labels can hold symbols the console codepage lacks
    token = PORTAL_CONTEXT.set(settings_for(args.portal))
    secrets_token = REPORT_SECRETS.set(set())
    mode = reuse.FRESH if getattr(args, "fresh", False) or args.portal != "workday" else reuse.REUSE
    mode_token = RUN_MODE.set(mode)
    report = RunReport(args.portal, args.dry, mode)
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(CDP_URL)
            try:
                drive(page_of(browser, url or getattr(args, "job_url", None), target_id or getattr(args, "target_id", None)), args, report)
            finally:
                browser.close()
        raise DriverStopped("Page limit reached.")
    except DriverStopped as stop:
        code, reason = stop.code, str(stop)
    except SystemExit as stop:
        code, reason = EXIT_FAILURE, str(stop.code)
    except Exception as error:  # noqa: BLE001 - any crash still produces a report and a failure code
        code, reason = EXIT_FAILURE, f"{type(error).__name__}: {str(error)[:160]}"
    finally:
        PORTAL_CONTEXT.reset(token)
        RUN_MODE.reset(mode_token)
    try:
        return report.finish_report(reason, code)
    finally:
        REPORT_SECRETS.reset(secrets_token)


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
