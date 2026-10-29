"""Author: Yazad Madan. Bind one driver to one browser tab."""
import re
from urllib.parse import unquote, urlsplit, urlunsplit

# Config
TARGET_INFO_COMMAND = "Target.getTargetInfo"
TARGET_INFO_KEY = "targetInfo"
TARGET_ID_KEY = "targetId"
JOB_PATH_MARKERS = frozenset({"job", "jobs", "position", "positions", "requisition"})
JOB_SUFFIXES = frozenset({"apply", "application", "usemylastapplication", "applymanually"})
REQUISITION_PATTERN = re.compile(r"(?:^|[_-])((?:jr|req|r)[_-]?\d+)$", re.I)


def sync_playwright():
    from playwright.sync_api import sync_playwright as start
    return start()


def normalize_url(url):
    parts = urlsplit(str(url))
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def job_identity(url):
    parts = [unquote(part).casefold() for part in urlsplit(str(url)).path.split("/") if part]
    for index, part in enumerate(parts):
        if part in JOB_PATH_MARKERS:
            job_parts = parts[index + 1:]
            job_parts = job_parts[:next((i for i, item in enumerate(job_parts) if item in JOB_SUFFIXES), len(job_parts))]
            if job_parts:
                slug = job_parts[-1]
                match = REQUISITION_PATTERN.search(slug)
                return (slug[:match.start()] if match else slug), (match.group(1) if match else "")
    return "", ""


def same_job_url(expected, candidate):
    original, current = urlsplit(str(expected)), urlsplit(str(candidate))
    if (original.scheme.lower(), original.netloc.lower()) != (current.scheme.lower(), current.netloc.lower()):
        return False
    slug, requisition = job_identity(expected)
    other_slug, other_requisition = job_identity(candidate)
    if requisition and other_requisition:
        return requisition == other_requisition
    return bool(slug and other_slug and slug == other_slug)


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
        tabs = [page for page in tabs if normalize_url(page.url) == normalize_url(url) or same_job_url(url, page.url)]
    if predicate:
        tabs = [page for page in tabs if predicate(page.url)]
    if len(tabs) != 1:
        raise SystemExit(f"Expected exactly one matching application tab, found {len(tabs)}. Select its URL or target id.")
    return next(iter(tabs))
