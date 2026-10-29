"""Author: Yazad Madan. Single read-write pass per Workday step: visit each field once, write only if wrong, then advance.

Usage: py -3 -u step_pass.py "<Company>" --target-id <tab id> [--salary N] [--unknowns-out file.json] [--no-advance]
Unknown questions are collected and written to --unknowns-out; the run stops so Yazad answers them once. Never submits.
"""
import json
import re
import sys

import answer_memory
import intent_layer

sys.path.insert(0, r"D:\Code\Resume\_Reference")
import company_kb  # noqa: E402

# Config
CDP_URL = "http://127.0.0.1:9223"
FIELD = '[data-automation-id^="formField-"]'
LISTBOX = 'button[aria-haspopup="listbox"]'
STEP = '[data-automation-id="progressBarActiveStep"]'
INVALID = '[aria-invalid="true"]'
NEXT_SELECTOR = '[data-automation-id="pageFooterNextButton"], [data-automation-id="bottom-navigation-next-button"], button:has-text("Save and Continue")'
EMPTY_CHOICE = "select one"
LAST_STEP_TITLE = "Review"
SETTLE_MS = 450
ADVANCE_WAIT_MS = 6000
MAX_STEPS = 6
QUIET_SECONDS = 5  # Simplify keeps filling in the same profile; read only after values stop changing
QUIET_MAX_SECONDS = 90
SNAPSHOT_JS = "() => [...document.querySelectorAll('input,textarea,button[aria-haspopup=listbox]')].map(e => (e.value || e.innerText || '') + (e.checked ? '1' : '')).join('|')"
# Self-ID answers come from the local intent store (answer memory), never from this public file.
ACK_LABEL = re.compile(r"acknowledg|consent to the terms|have read and", re.I)
ACK_OPTION = re.compile(r"^(i acknowledge|yes)", re.I)
# Per-company consents Yazad approved to auto-tick (2026-10-29).
CONSENT_BY_COMPANY = {"keybank": re.compile(r"arbitration agreement", re.I)}
SKIP_LABEL = re.compile(r"signature|password", re.I)
SALARY_LABEL = re.compile(r"minimum pay|desired (pay|salary)|salary expectation|expected salary", re.I)


def is_company_consent(company, label):
    pattern = CONSENT_BY_COMPANY.get(company.lower())
    return bool(pattern and pattern.search(label))


def resolve(company, memory, label):
    """Known answer for a question label, or None. Order: shared memory, company KB, self-ID rules."""
    answer = answer_memory.lookup(memory, label)
    if answer:
        return answer
    row = company_kb.find_answer(company, label)
    if row and row.get(company_kb.Q_ANSWER_COLUMN):
        return row[company_kb.Q_ANSWER_COLUMN]
    return intent_layer.lookup(memory, label)


def pick_option(page, button, wanted):
    button.scroll_into_view_if_needed()
    button.click()
    page.wait_for_timeout(SETTLE_MS)
    options = page.locator("[role=option]")
    names = [options.nth(i).inner_text().strip() for i in range(options.count())]
    chosen = []
    for want in ([wanted] if isinstance(wanted, str) else wanted):
        chosen = [n for n in names if n.lower() == want.lower()] or [n for n in names if n.lower().startswith(want.lower())]
        if chosen:
            break
    if len(chosen) != 1:
        page.keyboard.press("Escape")
        return None, names
    page.get_by_role("option", name=chosen[0], exact=True).first.click()
    page.wait_for_timeout(SETTLE_MS)
    return chosen[0], names


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


def pass_over_step(page, company, memory, log, salary=None):
    unknowns = []
    fields = page.locator(FIELD)
    for i in range(fields.count()):
        field = fields.nth(i)
        text = re.sub(r"\s+", " ", field.inner_text()).strip()
        label = re.sub(r"\s+", " ", next((ln for ln in field.inner_text().splitlines() if ln.strip()), "")).strip()
        if SKIP_LABEL.search(label):
            continue
        button, checkbox = field.locator(LISTBOX), field.locator("input[type=checkbox]")
        if button.count():
            current = button.first.inner_text().strip()
            ack = ACK_LABEL.search(label) or is_company_consent(company, label)
            wanted = "I acknowledge" if ack else resolve(company, memory, label)
            if wanted in (intent_layer.YES, intent_layer.NO):
                wanted = intent_layer.expand(wanted)
            if wanted is None:
                if current.lower() == EMPTY_CHOICE:
                    button.first.click()
                    page.wait_for_timeout(SETTLE_MS)
                    options = page.locator("[role=option]")
                    unknowns.append({"label": label, "options": [options.nth(j).inner_text().strip() for j in range(options.count())]})
                    page.keyboard.press("Escape")
                continue
            targets = [w.lower() for w in ([wanted] if isinstance(wanted, str) else wanted)]
            if any(current.lower() == t or (len(t) > 3 and current.lower().startswith(t)) for t in targets) or (ack and ACK_OPTION.match(current)):
                continue
            chosen, names = pick_option(page, button.first, wanted)
            log.append(f"{'set' if chosen else 'NO MATCH'} | {label[:60]} | {chosen or wanted} | {names[:6]}")
        elif field.locator("input[type=radio]").count():
            radios = field.locator("input[type=radio]")
            if any(radios.nth(j).is_checked() for j in range(radios.count())):
                continue
            wanted = resolve(company, memory, label)
            choices = [ln.strip() for ln in field.inner_text().splitlines() if ln.strip()][1:]
            if wanted is None:
                unknowns.append({"label": label, "options": choices})
                continue
            field.get_by_label(wanted, exact=True).first.check()
            log.append(f"radio | {label[:60]} | {wanted}")
        elif field.locator("input[type=text], input[type=number], textarea").count() and not checkbox.count():
            box = field.locator("input[type=text], input[type=number], textarea").first
            wanted = salary if SALARY_LABEL.search(label) and salary else resolve(company, memory, label)
            if wanted is None:
                if not box.input_value() and "*" in label:
                    unknowns.append({"label": label, "options": []})
                continue
            if box.input_value().strip() != str(wanted):
                box.scroll_into_view_if_needed()
                box.fill(str(wanted))
                page.keyboard.press("Tab")
                log.append(f"typed | {label[:60]} | {wanted}")
        elif checkbox.count() and (ACK_LABEL.search(text) or is_company_consent(company, text)):
            if not checkbox.first.is_checked():
                checkbox.first.check()
                log.append(f"ticked | {label[:60]}")
    return unknowns


def main(argv):
    from playwright.sync_api import sync_playwright
    args = [a for i, a in enumerate(argv[1:], 1) if not a.startswith("--") and not argv[i - 1].startswith("--")]
    flags = {argv[i]: argv[i + 1] for i in range(len(argv) - 1) if argv[i].startswith("--") and i + 1 < len(argv)}
    if not args or "--target-id" not in flags:
        print(__doc__)
        return 2
    company, memory = args[0], answer_memory.load_memory()
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        page = None
        for context in browser.contexts:
            for candidate in context.pages:
                session = context.new_cdp_session(candidate)
                try:
                    if session.send("Target.getTargetInfo")["targetInfo"]["targetId"] == flags["--target-id"]:
                        page = candidate
                finally:
                    session.detach()
        if page is None:
            print("Target tab not found.")
            return 3
        for _ in range(MAX_STEPS):
            title = " ".join(page.locator(STEP).all_inner_texts()).replace("\n", " ")
            log = []
            print(f"waited {wait_until_quiet(page):.0f}s for the form to settle")
            unknowns = pass_over_step(page, company, memory, log, flags.get("--salary"))
            print(f"[{title}] changes: {len(log)}, unknown: {len(unknowns)}, invalid: {page.locator(INVALID).count()}")
            for line in log:
                print("  " + line)
            if unknowns:
                if "--unknowns-out" in flags:
                    json.dump(unknowns, open(flags["--unknowns-out"], "w", encoding="utf-8"), indent=2, ensure_ascii=False)
                print("STOP: unknown questions written. Answer once, save to answer memory, rerun.")
                return 2
            if LAST_STEP_TITLE.lower() in title.lower() or "--no-advance" in argv:
                print("Review reached. Not submitting." if LAST_STEP_TITLE.lower() in title.lower() else "Pass done, not advancing.")
                return 0
            if page.locator(INVALID).count():
                print("STOP: invalid fields remain (text field or unreadable control). Check manually.")
                return 2
            page.locator(NEXT_SELECTOR).first.click()
            page.wait_for_timeout(ADVANCE_WAIT_MS)
            if " ".join(page.locator(STEP).all_inner_texts()).replace("\n", " ") == title:
                print("STOP: step did not advance.")
                return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
