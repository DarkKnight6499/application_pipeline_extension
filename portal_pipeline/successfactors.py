"""Author: Yazad Madan. Conservative SuccessFactors RMK identity checks without fetching pages."""
import re
from pathlib import Path
from urllib.parse import urlsplit

# Config
DETECTOR = Path(__file__).resolve().parent / "extension" / "successfactors-detection.js"
VENDOR_DOMAINS = ("successfactors.com", "successfactors.eu", "sapsf.com", "sapsf.eu", "jobs2web.com")
CUSTOM_HOSTS = frozenset({"careers.provident.bank"})
APPLY_PATH = re.compile(r"/talentcommunity/apply/[0-9]+/?")
JOB_PATH = re.compile(r"/job/[^/]+/[0-9]+/?")


def matches_url(url):
    parts = urlsplit(url)
    host = parts.hostname or ""
    return (parts.scheme == "https" and not parts.username and not parts.password
            and (host in CUSTOM_HOSTS or any(host == domain or host.endswith("." + domain) for domain in VENDOR_DOMAINS)
                 or APPLY_PATH.fullmatch(parts.path) is not None))


def matches_page(page):
    """Inspect only asset URLs and generator metadata on the already selected page."""
    return page.evaluate("() => {" + DETECTOR.read_text(encoding="utf-8")
                         + "\nreturn PortalSuccessFactorsDetection.matches(location.href); }") is True
