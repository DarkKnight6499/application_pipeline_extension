"""Author: Yazad Madan. Fill the Workday Skills search-and-add field: read first, add only missing, verify each chip.

Usage: py workday_skills.py "<Company>" --target-id <tab id> [--max 15] [--dry]
Skill lists come from Resume\\_Reference\\Work_Experience_Form_Data.json (base list, then the company list).
Never presses Enter; each skill is picked by clicking its exact-match menu option.
"""
import json
import sys
from pathlib import Path

# Config
DATA_FILE = Path(r"D:\Code\Resume\_Reference\Work_Experience_Form_Data.json")
CDP_URL = "http://127.0.0.1:9223"
SKILLS_FIELD = '[data-automation-id="formField-skills"]'
SEARCH_BOX = 'input[id="skills--skills"]'
MENU_OPTION = '[data-automation-id="promptOption"]'
SELECTED_CHIP = '[data-automation-id="selectedItem"]'
DEFAULT_MAX = 15
SETTLE_MS = 900


def skill_plan(company, limit):
    skills = json.loads(DATA_FILE.read_text(encoding="utf-8"))["skills"]
    plan = []
    for name in skills["base"] + skills["by_company"].get(company, []):
        if name.lower() not in [p.lower() for p in plan]:
            plan.append(name)
    return plan[:limit]


def existing_chips(page):
    texts = page.locator(f"{SKILLS_FIELD} {SELECTED_CHIP}").all_inner_texts()
    return {t.strip().lower() for t in texts}


def add_skill(page, name):
    box = page.locator(f"{SKILLS_FIELD} {SEARCH_BOX}").first
    box.click()
    box.fill(name)
    page.wait_for_timeout(SETTLE_MS)
    options = page.locator(MENU_OPTION)
    exact = [options.nth(i) for i in range(options.count()) if options.nth(i).inner_text().strip().lower() == name.lower()]
    if len(exact) != 1:
        box.fill("")
        return f"skipped: {len(exact)} exact menu matches"
    exact[0].click()
    page.wait_for_timeout(SETTLE_MS)
    return "added" if name.lower() in existing_chips(page) else "not confirmed"


def main(argv):
    from playwright.sync_api import sync_playwright
    flags = {argv[i]: argv[i + 1] for i in range(len(argv) - 1) if argv[i].startswith("--")}
    args = [a for i, a in enumerate(argv[1:], 1) if not a.startswith("--") and not argv[i - 1].startswith("--")]
    if not args or "--target-id" not in flags:
        print(__doc__)
        return 2
    plan = skill_plan(args[0], int(flags.get("--max", DEFAULT_MAX)))
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
        have = existing_chips(page)
        missing = [s for s in plan if s.lower() not in have]
        print(f"on form: {sorted(have)}; to add: {missing}")
        if "--dry" in argv:
            return 0
        for name in missing:
            print(f"  {name}: {add_skill(page, name)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
