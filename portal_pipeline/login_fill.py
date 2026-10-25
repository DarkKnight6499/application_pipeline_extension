"""Type the stored login into a portal sign-in form over CDP; secrets are never printed, logged or returned."""
import argparse
import re
import sys
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

import credential_store
import verification_code

# Config
CDP_URL = "http://127.0.0.1:9223"
USERNAME_SELECTOR = ("input:not([type]), input[type=text], input[type=email], input[autocomplete=username], "
                     "input[data-automation-id*=email i], input[data-automation-id*=username i]")
PASSWORD_SELECTOR = "input[type=password]"
CODE_INPUT_SELECTOR = "input:not([type]), input[type=text], input[type=tel], input[type=number], input[inputmode=numeric]"
CAPTCHA_SELECTOR = ("iframe[src*=captcha i], iframe[src*=recaptcha i], iframe[src*=hcaptcha i], iframe[src*=turnstile i], "
                    "[class*=captcha i], [id*=captcha i], [class*=g-recaptcha i], [class*=cf-turnstile i]")
AUTH_PROMPT = re.compile(r"authenticator app|two-?factor|2-?step|multi-?factor|\bmfa\b|security key|approve (?:this )?sign.?in|passkey|push notification", re.I)
CODE_LABEL = re.compile(r"verification code|security code|one.?time (?:code|password)|\bcode\b|\botp\b", re.I)
CODE_VALUE = re.compile(r"[A-Za-z0-9]{4,10}")
ANCESTOR_LEVELS = 5
SIGN_IN_LABEL = re.compile(r"^(sign in|log in|login)$", re.I)
LABEL_JS = ("el => [el.getAttribute('aria-label'), el.getAttribute('placeholder'), el.getAttribute('name'), el.id, el.getAttribute('data-automation-id'),"
            " ...[...(el.labels || [])].map(label => label.textContent)].filter(Boolean).join(' ')")
# Result codes (strings only; never a secret)
FILLED, HOST_MISMATCH, CAPTCHA, AUTHENTICATOR, NO_FORM, NO_CREDENTIALS, ERROR = "filled", "host_mismatch", "captcha", "authenticator", "no_login_form", "no_credentials", "error"
CODE_TYPED, CODE_FIELD_MISSING, CODE_REJECTED = "code_typed", "code_field_missing", "code_rejected"
STOP_RESULTS = {HOST_MISMATCH, CAPTCHA, AUTHENTICATOR}


def host_of(url):
    return (urlsplit(str(url)).hostname or "").lower()


def same_host(page_url, session_url):
    host = host_of(session_url)
    return bool(host) and urlsplit(str(page_url)).scheme == "https" and host_of(page_url) == host


def visible(scope, selector):
    locator = scope.locator(selector)
    return [locator.nth(i) for i in range(locator.count()) if locator.nth(i).is_visible()]


def username_near(password):
    """Visible username candidates in the nearest ancestor of the password box that has any."""
    for level in range(1, ANCESTOR_LEVELS + 1):
        found = visible(password.locator(f"xpath=ancestor::*[{level}]"), USERNAME_SELECTOR)
        if found:
            return found
    return []


def gate_on(page):
    """CAPTCHA or authenticator prompt on the page; returns the stop code or None."""
    if visible(page, CAPTCHA_SELECTOR):
        return CAPTCHA
    if AUTH_PROMPT.search(page.locator("body").inner_text() or ""):
        return AUTHENTICATOR
    return None


def login(page, session_url, get_login=credential_store.get_login, submit=False):
    """Fill username and password on the session's exact host; returns {"result": code} with no secret in it."""
    try:
        if not same_host(page.url, session_url):
            return {"result": HOST_MISMATCH}
        gate = gate_on(page)
        if gate:
            return {"result": gate}
        passwords = visible(page, PASSWORD_SELECTOR)
        users = username_near(passwords[0]) if len(passwords) == 1 else []
        if len(passwords) != 1 or len(users) != 1:
            return {"result": NO_FORM}  # none, or a create-account form with two password boxes
        credentials = get_login(host_of(session_url))
        if not credentials:
            return {"result": NO_CREDENTIALS}
        if not same_host(page.url, session_url):
            return {"result": HOST_MISMATCH}
        users[0].fill(credentials[0])
        passwords[0].fill(credentials[1])
        if submit:
            buttons = [b for b in visible(page, "button, [role=button]") if SIGN_IN_LABEL.match((b.inner_text() or "").strip())]
            if len(buttons) == 1:
                buttons[0].click()
        return {"result": FILLED}
    except Exception as error:  # noqa: BLE001 - Playwright call logs echo the typed value, so only the class name is kept
        return {"result": ERROR, "error_type": type(error).__name__}


def code_from_email(subject, body):
    """Extract a verification code from email text the caller supplies; None when there is none."""
    return verification_code.extract_code(subject, body)


def enter_code(page, session_url, code):
    """Type a verification code only into the one visible field whose label says it is a code."""
    try:
        if not same_host(page.url, session_url):
            return {"result": HOST_MISMATCH}
        if not code or not CODE_VALUE.fullmatch(str(code)):
            return {"result": CODE_REJECTED}
        fields = [f for f in visible(page, CODE_INPUT_SELECTOR) if CODE_LABEL.search(f.evaluate(LABEL_JS) or "")]
        if len(fields) != 1:
            return {"result": CODE_FIELD_MISSING}
        fields[0].fill(str(code))
        return {"result": CODE_TYPED}
    except Exception as error:  # noqa: BLE001 - see login()
        return {"result": ERROR, "error_type": type(error).__name__}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Session URL; the login is stored and typed for this exact host only.")
    parser.add_argument("--submit", action="store_true", help="Click a single Sign In button after typing.")
    parser.add_argument("--code", help="Verification code text from the person's email; typed only into a field labeled as a code.")
    args = parser.parse_args(argv)
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        tabs = [page for context in browser.contexts for page in context.pages if same_host(page.url, args.url)]
        if len(tabs) != 1:
            result = {"result": NO_FORM, "tabs": len(tabs)}
        else:
            result = enter_code(tabs[0], args.url, args.code) if args.code else login(tabs[0], args.url, submit=args.submit)
        browser.close()
    print(result)
    return 0 if result["result"] in (FILLED, CODE_TYPED) else 2


if __name__ == "__main__":
    sys.exit(main())
