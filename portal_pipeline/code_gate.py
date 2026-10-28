"""Email verification gate for every adapter: type an emailed code, or open an emailed activation link in a separate tab; secrets are never printed or stored."""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

from browser_target import select_tab, sync_playwright, target_id_of

import login_fill
import verification_code

# Config
CDP_URL = login_fill.CDP_URL
# Sender domains verified 2026-10-28 from Gmail samples (sender metadata plus one body each); an adapter with no sample stays refused.
ALLOWED_SENDER_DOMAINS = {
    "workday": ["otp.workday.com"],
    "oracle": ["oracle.com"],
    "icims": ["icims.com"],
    "greenhouse": ["greenhouse-mail.io", "greenhouse-jobs.com"],
    "smartrecruiters": ["smartrecruiters.com"],
    "eightfold": ["eightfold.ai"],
    "lever": [],
    "ashby": [],
    "taleo": [],
}
HOST_PORTAL_HINTS = {"myworkdayjobs.com": "workday", "myworkdaysite.com": "workday", "oraclecloud.com": "oracle", "icims.com": "icims",
                     "greenhouse.io": "greenhouse", "smartrecruiters.com": "smartrecruiters", "eightfold.ai": "eightfold",
                     "lever.co": "lever", "ashbyhq.com": "ashby", "taleo.net": "taleo"}
# Activation links: Workday links land on the employer's own host; iCIMS links go through its click tracker.
LINK_SUFFIXES = {"icims": ["icims.com"]}
LINK_PATH_HINTS = {"workday": r"/activate/"}
LINK_PORTALS = {"workday", "icims"}
LINK_LOAD_WAIT_MS = 8000
EMAIL_KEYS = ("sender", "subject", "body", "sent_at")
# Result codes (strings only; never a secret)
NEEDS_CODE, NO_CODE_PROMPT, SENDER_REFUSED, CODE_STALE, NOTHING_IN_EMAIL, PORTAL_UNKNOWN, BAD_EMAIL_FILE, LINK_OPENED, LINK_FAILED = (
    "needs_code", "no_code_prompt", "sender_refused", "code_stale", "nothing_in_email", "portal_unknown", "bad_email_file", "link_opened", "link_failed")
KIND_CODE, KIND_LINK = "code", "link"


def portal_for_host(host):
    return next((portal for suffix, portal in HOST_PORTAL_HINTS.items() if host == suffix or host.endswith("." + suffix)), None)


def has_code_prompt(page):
    """True when exactly one visible field is labeled as a verification code."""
    fields = [f for f in login_fill.visible(page, login_fill.CODE_INPUT_SELECTOR) if login_fill.CODE_LABEL.search(f.evaluate(login_fill.LABEL_JS) or "")]
    return len(fields) == 1


def detect(browser, session_url):
    """Tabs on the session host with their target ids and whether each shows a code prompt."""
    out = []
    for context in browser.contexts:
        for page in context.pages:
            if login_fill.same_host(page.url, session_url):
                out.append({"target_id": target_id_of(page), "needs_code": has_code_prompt(page)})
    return out


def vet_email(portal, email, session_host, now=None):
    """Sender, age and content gates; returns (kind, value, None) with kind code or link, or (None, None, result_code)."""
    if not all(key in email for key in EMAIL_KEYS):
        return None, None, BAD_EMAIL_FILE
    if not verification_code.sender_allowed(email["sender"], ALLOWED_SENDER_DOMAINS.get(portal, [])):
        return None, None, SENDER_REFUSED
    try:
        sent = datetime.fromisoformat(str(email["sent_at"]).replace("Z", "+00:00"))
    except ValueError:
        return None, None, BAD_EMAIL_FILE
    if sent.tzinfo is None:
        sent = sent.replace(tzinfo=timezone.utc)
    if not verification_code.fresh_enough(sent, now):
        return None, None, CODE_STALE
    code = verification_code.extract_code(email["subject"], email["body"])
    if code:
        return KIND_CODE, code, None
    if portal in LINK_PORTALS:
        link = verification_code.extract_link(email["body"], session_host, LINK_SUFFIXES.get(portal, ()), LINK_PATH_HINTS.get(portal))
        if link:
            return KIND_LINK, link, None
    return None, None, NOTHING_IN_EMAIL


def open_link(browser, url):
    """Load an activation link in its own tab so the application tab is untouched; the tab is closed afterwards."""
    page = browser.contexts[0].new_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(LINK_LOAD_WAIT_MS)
        return {"result": LINK_OPENED}
    except Exception as error:  # noqa: BLE001 - a failed load must not leak the link into logs
        return {"result": LINK_FAILED, "error_type": type(error).__name__}
    finally:
        page.close()


def enter(browser, session_url, email, target_id=None, now=None):
    host = login_fill.host_of(session_url)
    portal = portal_for_host(host)
    if portal is None:
        return {"result": PORTAL_UNKNOWN}
    kind, value, refusal = vet_email(portal, email, host, now)
    if refusal:
        return {"result": refusal}
    if kind == KIND_LINK:
        return open_link(browser, value)
    page = select_tab(browser, target_id=target_id, predicate=lambda url: login_fill.same_host(url, session_url))
    return login_fill.enter_code(page, session_url, value)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    det = sub.add_parser("detect", help="List tabs on the host and whether each is waiting for a code.")
    det.add_argument("url")
    ent = sub.add_parser("enter", help="Vet an email JSON file (sender, subject, body, sent_at) and type its code or open its activation link.")
    ent.add_argument("url")
    ent.add_argument("--email-json", required=True, help="File with sender, subject, body, sent_at (ISO). Deleted after use unless --keep.")
    ent.add_argument("--target-id", help="Tab to use when several tabs share the host.")
    ent.add_argument("--keep", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "enter":
        try:
            with open(args.email_json, encoding="utf-8") as handle:
                email = json.load(handle)
        except (OSError, ValueError):
            print({"result": BAD_EMAIL_FILE})
            return 2
        finally:
            if not args.keep:
                try:
                    os.remove(args.email_json)
                except OSError:
                    pass
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        if args.command == "detect":
            tabs = detect(browser, args.url)
            result = {"result": NEEDS_CODE if any(t["needs_code"] for t in tabs) else NO_CODE_PROMPT, "tabs": tabs}
        else:
            result = enter(browser, args.url, email, args.target_id)
        browser.close()
    print(result)
    return 0 if result["result"] in (NEEDS_CODE, login_fill.CODE_TYPED, LINK_OPENED) else 2


if __name__ == "__main__":
    sys.exit(main())
