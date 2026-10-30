"""Author: Yazad Madan. Single read-write pass per Workday step: visit each field once, write only if wrong, then advance.

Usage: py -3 -u step_pass.py "<Company>" --target-id <tab id> [--salary N] [--resume file] [--history-file rows.json]
       [--unknowns-out file.json] [--report-path file.json] [--overwrite] [--no-advance]
Unknown questions (full text, options, intent id) are written to --unknowns-out; the run stops so Yazad answers them once.
Stored answers never replace a different filled value unless --overwrite is passed. Never submits.
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import answer_memory
import intent_layer

# Config
REFERENCE_DIR = r"D:\Code\Resume\_Reference"
CDP_URL = "http://127.0.0.1:9223"
FIELD = '[data-automation-id^="formField-"]'
LISTBOX = 'button[aria-haspopup="listbox"]'
STEP = '[data-automation-id="progressBarActiveStep"]'
INVALID = '[aria-invalid="true"]'
NEXT_SELECTOR = '[data-automation-id="pageFooterNextButton"], [data-automation-id="bottom-navigation-next-button"], button:has-text("Save and Continue")'
EMPTY_CHOICE = "select one"
OPTIONS = "[role=option]"
# Search widgets render promptOption rows only after Enter; skip wrappers that contain one to avoid duplicates.
SEARCH_OPTIONS = '[data-automation-id="promptOption"], [role=option]:not(:has([data-automation-id="promptOption"]))'
MULTISELECT = '[data-automation-id="multiSelectContainer"]'
MULTI_SELECTED = '[data-automation-id="selectedItem"], [data-automation-id="selectedItemList"]'
DATE_INPUTS = {
    "month": 'input[id$="dateSectionMonth-input"], input[data-automation-id="dateSectionMonth-input"]',
    "day": 'input[id$="dateSectionDay-input"], input[data-automation-id="dateSectionDay-input"]',
    "year": 'input[id$="dateSectionYear-input"], input[data-automation-id="dateSectionYear-input"]',
}
DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y")
CONTROL_TIMEOUT_MS = 1500
OPTION_WAIT_MS = 4000
UPLOAD_CONFIRM_SECONDS = 15
HERE = Path(__file__).resolve().parent
RUNS_DIR = HERE / "data" / "runs"
HISTORY_ROW_ID = re.compile(r"^(workExperience|education)-\d+$")
HISTORY_GROUPS = {"employment": ("Work Experience", "workExperience-"), "education": ("Education", "education-")}
ROW_SETTLE_MS = 1500
# History field label -> entry key, per group; first match wins.
HISTORY_FIELDS = {
    "employment": [("current", re.compile(r"currently work", re.I)), ("title", re.compile(r"job title|^title", re.I)),
                   ("company", re.compile(r"company|employer", re.I)), ("location", re.compile(r"^location", re.I)),
                   ("description", re.compile(r"description|responsibilit", re.I)),
                   ("start", re.compile(r"^from", re.I)), ("end", re.compile(r"^to\b", re.I))],
    "education": [("school", re.compile(r"school|university|institution", re.I)), ("degree", re.compile(r"^degree", re.I)),
                  ("field", re.compile(r"field of study", re.I)), ("start_year", re.compile(r"from|first year", re.I)),
                  ("end_year", re.compile(r"^to\b|last year|graduat", re.I))],
}
MONTH_FORMATS = ("%Y-%m", "%m/%Y")
CONFLICT_PREFIX = "CONFLICT"
LAST_STEP_TITLE = "Review"
SETTLE_MS = 450
ADVANCE_WAIT_MS = 6000
MAX_STEPS = 6
QUIET_SECONDS = 5  # Simplify keeps filling in the same profile; read only after values stop changing
QUIET_MAX_SECONDS = 90
SNAPSHOT_JS = "() => [...document.querySelectorAll('input,textarea,button[aria-haspopup=listbox]')].map(e => (e.value || e.innerText || '') + (e.checked ? '1' : '')).join('|')"
# Self-ID answers come from the local intent store (answer memory), never from this public file.
ACK_LABEL = re.compile(r"acknowledg|consent to the terms|give your consent|have read and|^i accept", re.I)
ACK_OPTION = re.compile(r"^(i acknowledge|yes)", re.I)
# Per-company consents Yazad approved to auto-tick (2026-10-29).
CONSENT_BY_COMPANY = {"keybank": re.compile(r"arbitration agreement", re.I)}
SUBMIT_LABEL = re.compile(r"submit|send application", re.I)
SKIP_LABEL = re.compile(r"signature|password", re.I)
SALARY_LABEL = re.compile(r"(?:minimum|desired|expected)\s+(?:(?:base|total)\s+)?(?:pay|salary|compensation)|salary expectation", re.I)
SALARY_NUMBER = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")
SALARY_BELOW = re.compile(r"less than|below|under|<", re.I)
SALARY_AT_LEAST = re.compile(r"and (?:above|over)|or more|at least|from|\+|>=", re.I)
SALARY_AT_MOST = re.compile(r"up to|at most|<=", re.I)
SALARY_ABOVE = re.compile(r"more than|greater than|above|over|>", re.I)


def is_company_consent(company, label):
    pattern = CONSENT_BY_COMPANY.get(company.lower())
    return bool(pattern and pattern.search(label))


def resolve(company, memory, label):
    """Known answer for a question label, or None. Order: exact answer memory, company KB, then intent."""
    answer = answer_memory.lookup(memory, label)
    if answer:
        return answer.split("|") if "|" in answer else answer
    if REFERENCE_DIR not in sys.path:
        sys.path.insert(0, REFERENCE_DIR)
    import company_kb

    row = company_kb.find_answer(company, label)
    if row and row.get(company_kb.Q_ANSWER_COLUMN):
        return row[company_kb.Q_ANSWER_COLUMN]
    return intent_layer.lookup(memory, label)


def normalized_option(value):
    return " ".join(str(value).split()).casefold()


def answer_matches(current, wanted):
    """Recognize stored alternatives without treating a rank rule as a literal answer."""
    current = normalized_option(current)
    return bool(current and current != EMPTY_CHOICE) and any(
        current == target or (len(target) > 3 and current.startswith(target))
        for target in map(normalized_option, intent_layer.expand(wanted))
        if target not in intent_layer.OPTION_RULES
    )


def choose_option(names, wanted):
    """Choose one unambiguous option, honoring alternative order and explicit rank rules."""
    available = [name for name in names if normalized_option(name) not in ("", EMPTY_CHOICE)]
    for want in intent_layer.expand(wanted):
        target = normalized_option(want)
        if target in intent_layer.OPTION_RULES:
            return (available[-1] if target == "highest" else available[0]) if available else None
        matches = [name for name in available if normalized_option(name) == target]
        if not matches:
            matches = [name for name in available if normalized_option(name).startswith(target)]
        if matches:
            return matches[0] if len(matches) == 1 else None
    return None


def salary_band_contains(option, salary):
    """Test inclusive ranges and explicit open-ended compensation bands."""
    try:
        amount = Decimal(str(salary).replace(",", "").replace("$", "").strip())
    except InvalidOperation:
        return False
    if not amount.is_finite() or amount < 0:
        return False
    numbers = [Decimal(value.replace(",", "")) for value in SALARY_NUMBER.findall(option)]
    if len(numbers) == 2:
        low, high = numbers
        return low <= amount <= high
    if len(numbers) != 1:
        return False
    boundary = numbers[0]
    if SALARY_AT_MOST.search(option):
        return amount <= boundary
    if SALARY_BELOW.search(option):
        return amount < boundary
    if SALARY_AT_LEAST.search(option):
        return amount >= boundary
    if SALARY_ABOVE.search(option):
        return amount > boundary
    return False


def choose_salary_option(names, salary):
    """Leave gaps and overlapping bands pending rather than guessing."""
    matches = [name for name in names if salary_band_contains(name, salary)]
    return matches[0] if len(matches) == 1 else None


def pick_option(page, button, wanted, salary=None):
    button.scroll_into_view_if_needed()
    button.click()
    page.wait_for_timeout(SETTLE_MS)
    options = page.locator(OPTIONS)
    names = [options.nth(i).inner_text().strip() for i in range(options.count())]
    chosen = choose_salary_option(names, salary) if salary is not None else choose_option(names, wanted)
    if chosen is None:
        page.keyboard.press("Escape")
        return None, names
    if normalized_option(button.inner_text()) == normalized_option(chosen):
        page.keyboard.press("Escape")
        return chosen, names
    options.nth(names.index(chosen)).click()
    page.wait_for_timeout(SETTLE_MS)
    return chosen, names


def fill_date(page, parts, wanted):
    """Use keyboard focus so off-screen date widgets never trigger click retries."""
    parsed = None
    for format_string in DATE_FORMATS:
        try:
            parsed = datetime.strptime(str(wanted), format_string)
            break
        except ValueError:
            continue
    if parsed is None:
        raise ValueError("Stored date must be a valid ISO or month/day/year date.")
    values = {"month": parsed.strftime("%m"), "day": parsed.strftime("%d"), "year": parsed.strftime("%Y")}
    if all(parts[name].input_value().strip().lstrip("0") == value.lstrip("0") for name, value in values.items()):
        return False
    type_date_parts(page, parts["month"], values.values())
    return True


def type_date_parts(page, first_box, values):
    """Focus the first box, then per part select-all, type with no delay, Tab; Enter is never pressed in date fields."""
    first_box.focus(timeout=CONTROL_TIMEOUT_MS)
    for value in values:
        page.keyboard.press("ControlOrMeta+A")
        page.keyboard.type(value)
        page.keyboard.press("Tab")


def parse_month(value):
    """(MM, YYYY) from YYYY-MM or MM/YYYY, else None."""
    for format_string in MONTH_FORMATS:
        try:
            parsed = datetime.strptime(str(value).strip(), format_string)
            return parsed.strftime("%m"), parsed.strftime("%Y")
        except ValueError:
            continue
    return None


def fill_month_year(page, parts, wanted):
    """Month/year widgets (work history); skip when the boxes already hold the value."""
    parsed = parse_month(wanted)
    if parsed is None:
        raise ValueError("History date must be YYYY-MM or MM/YYYY.")
    values = dict(zip(("month", "year"), parsed))
    if all(parts[name].input_value().strip().lstrip("0") == value.lstrip("0") for name, value in values.items()):
        return False
    type_date_parts(page, parts["month"], values.values())
    return True


def pick_search_option(page, container, wanted):
    box = container.locator("input").first
    names = []
    for text in intent_layer.expand(wanted):
        if normalized_option(text) in intent_layer.OPTION_RULES:
            continue
        box.fill(text)
        box.press("Enter")  # typing alone shows "No Items"; Workday searches on Enter
        options = page.locator(SEARCH_OPTIONS)
        try:
            options.first.wait_for(state="visible", timeout=OPTION_WAIT_MS)
        except Exception:
            continue
        names = [options.nth(i).inner_text().strip() for i in range(options.count())]
        chosen = choose_option(names, wanted)
        if chosen:
            options.nth(names.index(chosen)).click()
            page.wait_for_timeout(SETTLE_MS)
            return chosen, names
    box.fill("")
    page.keyboard.press("Escape")
    return None, names


def advance_step(page, title):
    """Fail closed when the step or navigation control cannot be read safely."""
    if not title.strip() or LAST_STEP_TITLE.casefold() in title.casefold():
        return False
    try:
        button = page.locator(NEXT_SELECTOR).first
        label = button.inner_text(timeout=CONTROL_TIMEOUT_MS).strip()
        accessible_label = button.get_attribute("aria-label") or ""
        button_type = button.get_attribute("type") or ""
        if not label or button_type.casefold() == "submit" or SUBMIT_LABEL.search(label + " " + accessible_label):
            return False
    except Exception:
        return False
    button.click()
    return True


def wait_until_quiet(page):
    """Block until the form values are unchanged for QUIET_SECONDS, so Simplify has finished."""
    last, still, waited = None, 0.0, 0.0
    while waited < QUIET_MAX_SECONDS:
        now = page.evaluate(SNAPSHOT_JS)
        still = still + 1 if now == last else 0
        if still >= QUIET_SECONDS:
            return waited
        last = now
        page.wait_for_timeout(1000)
        waited += 1
    return waited


def has_literal(wanted):
    """True when the answer names real option text rather than only a rank rule such as highest."""
    return any(normalized_option(value) not in intent_layer.OPTION_RULES for value in intent_layer.expand(wanted))


def pass_over_step(page, company, memory, log, salary=None, overwrite=False, conflicts=None, details=None):
    """One read-write pass. conflicts and details are optional out-lists: stale-answer conflicts and full text per unknown label."""
    unknowns = []
    conflicts = [] if conflicts is None else conflicts
    details = {} if details is None else details

    def unknown(label, options):
        unknowns.append({"label": label, "options": options})
        details[label] = current_text[0]

    def conflict(label, current, wanted):
        conflicts.append({"label": label, "current": current, "wanted": wanted if isinstance(wanted, str) else list(wanted)})

    current_text = [""]
    fields = page.locator(FIELD)
    for i in range(fields.count()):
        field = fields.nth(i)
        text = re.sub(r"\s+", " ", field.inner_text()).strip()
        label = re.sub(r"\s+", " ", next((ln for ln in field.inner_text().splitlines() if ln.strip()), "")).strip()
        current_text[0] = text
        if SKIP_LABEL.search(label):
            continue
        button, checkbox = field.locator(LISTBOX), field.locator("input[type=checkbox]")
        date_boxes = {name: field.locator(selector) for name, selector in DATE_INPUTS.items()}
        multiselect = field.locator(MULTISELECT)
        if any(boxes.count() for boxes in date_boxes.values()):
            required = "*" in label or field.get_attribute("aria-required") == "true" or any(
                boxes.count() and (boxes.first.get_attribute("required") is not None or boxes.first.get_attribute("aria-required") == "true")
                for boxes in date_boxes.values()
            )
            if not required:
                continue
            present = [boxes.first for boxes in date_boxes.values() if boxes.count()]
            if present and all(box.input_value().strip() for box in present):
                continue  # already filled by prefill
            wanted = resolve(company, memory, label)
            if wanted is None or not all(boxes.count() == 1 for boxes in date_boxes.values()):
                unknown(label, [])
                continue
            try:
                if fill_date(page, {name: boxes.first for name, boxes in date_boxes.items()}, wanted):
                    log.append(f"date | {label[:60]} | {wanted}")
            except ValueError:
                unknown(label, [])
        elif multiselect.count():
            container = multiselect.first
            wanted = resolve(company, memory, label)
            if wanted is None:
                if "*" in label and not container.locator(MULTI_SELECTED).count():
                    unknown(label, [])
                continue
            chips = [value for chip in container.locator(MULTI_SELECTED).all_inner_texts() for value in chip.splitlines() if value.strip()]
            if any(answer_matches(value, wanted) for value in chips):
                continue
            if chips and has_literal(wanted) and not overwrite:
                conflict(label, chips[0], wanted)
                continue
            chosen, names = pick_search_option(page, container, wanted)
            log.append(f"{'set' if chosen else 'NO MATCH'} | {label[:60]} | {chosen or wanted} | {names[:6]}")
        elif button.count():
            current = button.first.inner_text().strip()
            ack = ACK_LABEL.search(label) or is_company_consent(company, label)
            salary_value = salary if SALARY_LABEL.search(label) and salary is not None else None
            wanted = "I acknowledge" if ack else salary_value if salary_value is not None else resolve(company, memory, label)
            if wanted is None:
                if current.lower() == EMPTY_CHOICE and "*" in label:
                    button.first.click()
                    page.wait_for_timeout(SETTLE_MS)
                    options = page.locator(OPTIONS)
                    unknown(label, [options.nth(j).inner_text().strip() for j in range(options.count())])
                    page.keyboard.press("Escape")
                continue
            if (salary_value is None and answer_matches(current, wanted)) or (ack and ACK_OPTION.match(current)):
                continue
            stored = not ack and salary_value is None
            if stored and not overwrite and has_literal(wanted) and current and current.lower() != EMPTY_CHOICE:
                conflict(label, current, wanted)  # a stale stored answer once overwrote a correct value
                continue
            chosen, names = pick_option(page, button.first, wanted, salary=salary_value)
            if chosen is None or normalized_option(current) != normalized_option(chosen):
                log.append(f"{'set' if chosen else 'NO MATCH'} | {label[:60]} | {chosen or wanted} | {names[:6]}")
        elif field.locator("input[type=radio]").count():
            radios = field.locator("input[type=radio]")
            if any(radios.nth(j).is_checked() for j in range(radios.count())):
                continue
            wanted = resolve(company, memory, label)
            choices = [ln.strip() for ln in field.inner_text().splitlines() if ln.strip()][1:]
            if wanted is None:
                unknown(label, choices)
                continue
            if wanted in (intent_layer.YES, intent_layer.NO):
                wanted = next((c for c in choices if c.lower() == wanted.lower()), wanted.title())
            field.get_by_label(wanted, exact=True).first.check(timeout=8000)
            log.append(f"radio | {label[:60]} | {wanted}")
        elif field.locator("input[type=text], input[type=number], textarea").count() and not checkbox.count():
            box = field.locator("input[type=text], input[type=number], textarea").first
            wanted = salary if SALARY_LABEL.search(label) and salary is not None else resolve(company, memory, label)
            if wanted is None:
                if not box.input_value() and "*" in label:
                    unknown(label, [])
                continue
            existing = box.input_value().strip()
            if existing and existing != str(wanted) and not (SALARY_LABEL.search(label) and salary is not None) and not overwrite:
                conflict(label, existing, wanted)
                continue
            if existing != str(wanted):
                box.scroll_into_view_if_needed()
                box.fill(str(wanted))
                page.keyboard.press("Tab")
                log.append(f"typed | {label[:60]} | {wanted}")
        elif checkbox.count() and (ACK_LABEL.search(text) or is_company_consent(company, text)):
            if not checkbox.first.is_checked():
                checkbox.first.check()
                log.append(f"ticked | {label[:60]}")
    return unknowns


def resume_slot(page):
    """Resume upload state from the attachment reader: (slots, resume state). KeyBank's only control reads as cover."""
    import workday_attachments
    slots = page.evaluate(workday_attachments.READ_JS)["slots"]
    if not slots["resume"]["inputs"] and slots["cover"]["inputs"]:
        slots = {**slots, "resume": slots["cover"]}
    return slots, slots["resume"]


def ensure_resume(page, resume):
    """Attach the resume when the step shows an empty slot. Returns (status, detail); statuses: absent, ok, uploaded, unknown, failed."""
    import workday_attachments as wa
    _, state = resume_slot(page)
    if not state["inputs"] and not state["items"]:
        return "absent", ""
    if not resume:
        return ("ok", "") if state["items"] else ("unknown", "No --resume given and the step has an empty resume slot.")
    path = Path(resume)
    if not path.is_file():
        return "failed", f"Resume file not found: {path.name}"
    result = wa.compare(path, state["items"])
    if result["status"] == "matched":
        return "ok", ""
    if len(state["items"]) > 1 or (not state["items"] and len(state["inputs"]) != 1):
        return "failed", f"Resume slot is ambiguous ({result['status']})."
    if state["items"]:  # stale copy from an earlier application: delete it first, as workday_attachments does
        item = state["items"][0]
        handle = page.locator(wa.ITEM_SELECTOR).nth(item["index"]).element_handle()
        page.evaluate(wa.DELETE_JS.replace("BOUNDARY()", "(() => {})()"), [handle, item["index"], item.get("identity_text", item["text"])])
        deadline = time.monotonic() + UPLOAD_CONFIRM_SECONDS
        while True:
            _, live = resume_slot(page)
            if not live["items"] and len(live["inputs"]) == 1:
                break
            if time.monotonic() >= deadline:
                return "failed", "Old resume did not delete."
            page.wait_for_timeout(100)
        state = live
    page.locator(wa.INPUT_SELECTOR).nth(state["inputs"][0]).set_input_files(str(path))
    deadline = time.monotonic() + UPLOAD_CONFIRM_SECONDS
    while True:
        _, live = resume_slot(page)
        result = wa.compare(path, live["items"])
        if result["status"] == "matched":
            return "uploaded", f"{result['seen_kb']} KB"
        if time.monotonic() >= deadline:
            return "failed", f"Upload not confirmed ({result['status']}, expected {result['expected_bytes']} bytes, saw {result['seen_kb']} KB)."
        page.wait_for_timeout(100)


def history_group(entry):
    return "education" if entry.get("school") else "employment"


def field_label(field):
    first = next((ln for ln in field.inner_text().splitlines() if ln.strip()), "")
    return re.sub(r"\s+", " ", first).replace("*", "").strip()


def history_key(group, label):
    return next((key for key, pattern in HISTORY_FIELDS[group] if pattern.search(label)), None)


def field_value(field):
    """Current text of a history field; placeholders and unticked boxes read as blank."""
    chips = field.locator(MULTI_SELECTED)
    if chips.count():
        return " ".join(chips.all_inner_texts()).strip()
    inputs = field.locator("input[type=text], input[type=number], textarea")
    if inputs.count():
        return inputs.first.input_value().strip()
    parts = [field.locator(selector) for selector in DATE_INPUTS.values()]
    if any(part.count() for part in parts):
        values = [part.first.input_value().strip() for part in parts if part.count()]
        return "/".join(values) if any(values) else ""
    button = field.locator(LISTBOX)
    if button.count():
        value = button.first.inner_text().strip()
        return "" if value.lower() == EMPTY_CHOICE else value
    return ""


def read_history_rows(page, group):
    """Rows of one history group as {id, section, fields:[{field, key, label, current}]}."""
    prefix = HISTORY_GROUPS[group][1]
    rows = []
    sections = page.locator(f'[data-automation-id^="{prefix}"]')
    for i in range(sections.count()):
        section = sections.nth(i)
        row_id = section.get_attribute("data-automation-id") or ""
        if not HISTORY_ROW_ID.match(row_id):
            continue
        entries = []
        fields = section.locator(FIELD)
        for j in range(fields.count()):
            field = fields.nth(j)
            label = field_label(field)
            entries.append({"field": field, "key": history_key(group, label), "label": label, "current": field_value(field)})
        rows.append({"id": row_id, "section": section, "fields": entries})
    return rows


def plan_history(page, group, wanted):
    """Run reuse_mode.history_plan over the page's rows; returns (plan, rows by id)."""
    import reuse_mode as reuse
    rows = read_history_rows(page, group)
    fields = [{reuse.RECORD_KEY: {reuse.GROUP_KEY: group, reuse.ID_KEY: row["id"]}, reuse.KEY_KEY: item["key"] or "",
               reuse.LABEL_KEY: item["label"], reuse.CURRENT_KEY: item["current"]} for row in rows for item in row["fields"]]
    profile = {"employment": [], "education": [], group: wanted}
    return reuse.history_plan(fields, profile), {row["id"]: row for row in rows}


def entry_value(entry, group, key):
    if group == "education" and key in ("start_year", "end_year"):
        source = key.split("_")[0]
        parsed = parse_month(entry.get(source, ""))
        return str(entry.get(key) or (parsed[1] if parsed else entry.get(source, "")))
    return entry.get(key)


def fill_history_row(page, row, entry, group, log):
    """Fill one blank row from its entry; dates are typed, school and field are search widgets."""
    for item in row["fields"]:
        key, field = item["key"], item["field"]
        value = entry_value(entry, group, key) if key else None
        if key == "current":
            if entry.get("current") and not field.locator("input[type=checkbox]").first.is_checked():
                field.locator("input[type=checkbox]").first.check()
                log.append(f"history | {item['label'][:40]} | ticked")
            continue
        if key == "end" and entry.get("current"):
            continue
        if not value or (item["current"] and key not in ("start", "end")):
            continue
        month, year = field.locator(DATE_INPUTS["month"]), field.locator(DATE_INPUTS["year"])
        container = field.locator(MULTISELECT)
        if key in ("start", "end") and month.count() and year.count():
            if fill_month_year(page, {"month": month.first, "year": year.first}, value):
                log.append(f"history date | {item['label'][:40]} | {value}")
        elif container.count():
            chosen, names = pick_search_option(page, container.first, value)
            log.append(f"history {'set' if chosen else 'NO MATCH'} | {item['label'][:40]} | {chosen or value} | {names[:4]}")
        elif field.locator(LISTBOX).count():
            chosen, names = pick_option(page, field.locator(LISTBOX).first, value)
            log.append(f"history {'set' if chosen else 'NO MATCH'} | {item['label'][:40]} | {chosen or value} | {names[:4]}")
        elif field.locator("input[type=text], input[type=number], textarea").count():
            box = field.locator("input[type=text], input[type=number], textarea").first
            box.scroll_into_view_if_needed()
            box.fill(str(value))
            page.keyboard.press("Tab")
            log.append(f"history typed | {item['label'][:40]} | {str(value)[:40]}")


def fill_history(page, entries, log):
    """Add and fill blank work and education rows; never adds a row when a matching one exists. Returns problem strings."""
    import workday_run
    problems = []
    for group, (heading, _) in HISTORY_GROUPS.items():
        wanted = [entry for entry in entries if history_group(entry) == group]
        if not wanted or not workday_run.has_heading(page, heading):
            continue
        try:
            for _ in range(len(wanted) + 1):
                plan, rows = plan_history(page, group, wanted)
                if not plan["missing"][group]:
                    break
                if not workday_run.click_add(page, heading):
                    problems.append(f"Could not add a {heading} row (no single Add button).")
                    break
                page.wait_for_timeout(ROW_SETTLE_MS)
                if len(read_history_rows(page, group)) <= len(rows):
                    problems.append(f"{heading} row did not appear after Add.")
                    break
            plan, rows = plan_history(page, group, wanted)
        except ValueError as error:
            problems.append(str(error))
            continue
        for record_id, index in plan["bindings"].items():
            if record_id not in plan["preserved"] and record_id in rows:
                fill_history_row(page, rows[record_id], wanted[index], group, log)
    return problems


def unknown_details(unknowns, details):
    """Full question text, options and intent id per unknown, for a one-pass human answer."""
    return [{"label": item["label"], "question": details.get(item["label"], item["label"]), "options": item["options"],
             "intent": intent_layer.classify(item["label"])} for item in unknowns]


def build_report(company, started, steps, unknowns, conflicts, code, reason, final_step, extra=None):
    """Run report in the apply.py schema (RunReport), plus per-step timing and conflicts."""
    import workday_run
    report = workday_run.RunReport("workday")
    report.data["started"] = started
    for step in steps:
        event = report.new_page(step["title"])
        event.update(filled=step["changes"], seconds=step["seconds"], changes=step["changes"],
                     pending_required=[item["label"] for item in step.get("unknown", [])])
    report.data[workday_run.UNANSWERED_KEY] = [{"label": item["label"], "type": "text", "options": item["options"], "host": "",
                                                 "required": True, "visible": True} for item in unknowns]
    report.data.update({"company": company, "finished": time.strftime("%Y-%m-%dT%H:%M:%S"), "driver": "step_pass",
                        "final_step": final_step, "unknowns": unknowns, "conflicts": conflicts, **(extra or {})})
    return report.finish_report(reason, code)


def default_report_path(company):
    slug = re.sub(r"[^A-Za-z0-9]+", "", company) or "company"
    return RUNS_DIR / f"{time.strftime('%Y%m%d_%H%M%S')}_step_pass_{slug}.json"


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("company")
    parser.add_argument("--target-id", required=True)
    parser.add_argument("--salary")
    parser.add_argument("--resume", help="Resume file to upload when a step shows an empty resume slot.")
    parser.add_argument("--history-file", help="JSON list of work and education entries for blank history rows.")
    parser.add_argument("--unknowns-out")
    parser.add_argument("--report-path")
    parser.add_argument("--folder")
    parser.add_argument("--url")
    parser.add_argument("--overwrite", action="store_true", help="Let stored answers replace a different filled value.")
    parser.add_argument("--no-advance", action="store_true")
    return parser.parse_args(argv)


def run_steps(page, args, memory, state):
    """Drive the open tab step by step; state collects steps, unknowns and conflicts for the report. Returns (code, reason)."""
    entries = json.loads(Path(args.history_file).read_text(encoding="utf-8")) if args.history_file else []
    for _ in range(MAX_STEPS):
        title = " ".join(page.locator(STEP).all_inner_texts()).replace("\n", " ")
        state["final_step"] = title
        began, log, details = time.monotonic(), [], {}
        print(f"waited {wait_until_quiet(page):.0f}s for the form to settle")
        status, detail = ensure_resume(page, args.resume)
        if status in ("uploaded", "failed"):
            log.append(f"resume | {status} | {detail}")
        extra_unknowns = []
        if status == "unknown":
            extra_unknowns.append({"label": "Resume/CV upload", "options": []})
            details["Resume/CV upload"] = detail
        problems = fill_history(page, entries, log) if entries else []
        unknowns = pass_over_step(page, args.company, memory, log, args.salary, overwrite=args.overwrite,
                                  conflicts=state["conflicts"], details=details) + extra_unknowns
        step = {"title": title, "seconds": round(time.monotonic() - began, 1), "changes": len(log), "unknown": unknowns}
        state["steps"].append(step)
        print(f"[{title}] changes: {len(log)}, unknown: {len(unknowns)}, conflicts: {len(state['conflicts'])}, invalid: {page.locator(INVALID).count()}")
        for line in log + problems:
            print("  " + line)
        for item in state["conflicts"]:
            print(f"  {CONFLICT_PREFIX} | {item['label'][:60]} | kept the filled value, stored answer differs")
        if status == "failed" or problems:
            return 2, "; ".join(([detail] if status == "failed" else []) + problems)
        if unknowns:
            state["unknowns"] = unknown_details(unknowns, details)
            if args.unknowns_out:
                Path(args.unknowns_out).write_text(json.dumps(state["unknowns"], indent=2, ensure_ascii=False), encoding="utf-8")
            print("STOP: unknown questions written. Answer once, save to answer memory, rerun.")
            return 2, f"{len(unknowns)} unknown question(s) on {title}"
        at_review = LAST_STEP_TITLE.lower() in title.lower()
        if at_review or args.no_advance:
            print("Review reached. Not submitting." if at_review else "Pass done, not advancing.")
            return 0, "Review reached." if at_review else "Pass done, not advancing."
        if page.locator(INVALID).count():
            print("STOP: invalid fields remain (text field or unreadable control). Check manually.")
            return 2, "Invalid fields remain."
        if not advance_step(page, title):
            print("STOP: no readable step title or the button is Submit. Never clicking it.")
            return 2, "No readable step title or the button is Submit."
        page.wait_for_timeout(ADVANCE_WAIT_MS)
        if " ".join(page.locator(STEP).all_inner_texts()).replace("\n", " ") == title:
            print("STOP: step did not advance.")
            return 2, "Step did not advance."
    return 0, "Step limit reached."


def main(argv):
    from playwright.sync_api import sync_playwright
    try:
        args = parse_args(argv[1:])
    except SystemExit as stop:
        return 2 if stop.code else 0
    memory = answer_memory.load_memory()
    started = time.strftime("%Y-%m-%dT%H:%M:%S")
    state = {"steps": [], "unknowns": [], "conflicts": [], "final_step": ""}
    code, reason = 3, "Target tab not found."
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(CDP_URL)
            page = None
            for context in browser.contexts:
                for candidate in context.pages:
                    session = context.new_cdp_session(candidate)
                    try:
                        if session.send("Target.getTargetInfo")["targetInfo"]["targetId"] == args.target_id:
                            page = candidate
                    finally:
                        session.detach()
            if page is None:
                print("Target tab not found.")
            else:
                code, reason = run_steps(page, args, memory, state)
    except Exception as error:
        code, reason = 3, f"{type(error).__name__}: {str(error)[:160]}"
        print(reason)
    extra = {key: value for key, value in (("folder", args.folder), ("url", args.url), ("target_id", args.target_id)) if value}
    report = build_report(args.company, started, state["steps"], state["unknowns"], state["conflicts"], code, reason, state["final_step"], extra)
    print(f"Report: {report.write(path=args.report_path or default_report_path(args.company))}")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
