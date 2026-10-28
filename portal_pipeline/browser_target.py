"""Author: Yazad Madan. Bind one driver to one browser tab."""
from urllib.parse import urlsplit, urlunsplit

# Config
TARGET_INFO_COMMAND = "Target.getTargetInfo"
TARGET_INFO_KEY = "targetInfo"
TARGET_ID_KEY = "targetId"


def sync_playwright():
    from playwright.sync_api import sync_playwright as start
    return start()


def normalize_url(url):
    parts = urlsplit(str(url))
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def target_id_of(page):
    session = page.context.new_cdp_session(page)
    try:
        return session.send(TARGET_INFO_COMMAND)[TARGET_INFO_KEY][TARGET_ID_KEY]
    finally:
        session.detach()


def select_tab(browser, url=None, target_id=None, predicate=None):
    tabs = [page for context in browser.contexts for page in context.pages]
    if target_id:
        tabs = [page for page in tabs if target_id_of(page) == target_id]
    elif url:
        tabs = [page for page in tabs if normalize_url(page.url) == normalize_url(url)]
    if predicate:
        tabs = [page for page in tabs if predicate(page.url)]
    if len(tabs) != 1:
        raise SystemExit(f"Expected exactly one matching application tab, found {len(tabs)}. Select its URL or target id.")
    return next(iter(tabs))
