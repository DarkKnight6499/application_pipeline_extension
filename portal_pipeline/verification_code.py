"""Pulls a one-time verification code out of a portal email; sender and age gates keep it from reading unrelated mail."""
import re
from datetime import datetime, timedelta, timezone

# Config
MAX_AGE_MINUTES = 15
CODE_CONTEXT = re.compile(r"(?:verification|security|confirmation|one.?time|access|login|sign.?in)\s*(?:code|pin)|\bcode\b|\botp\b|\bpin\b", re.I)
CODE_PATTERN = re.compile(r"(?<![A-Za-z0-9])(\d{6,8}|\d{3}[ -]\d{3}|[A-Z0-9]{6,8})(?![A-Za-z0-9])")
URL_PATTERN = re.compile(r"https?://\S+")
STOP_WORDS = {"SUBMIT", "ACCOUNT", "PORTAL", "VERIFY", "SECURE", "CITIBA", "WORKDAY"}


def _is_code(token):
    digits = re.sub(r"[ -]", "", token)
    if digits.isdigit():
        return len(set(digits)) > 1
    return token.upper() not in STOP_WORDS and any(c.isdigit() for c in token) and any(c.isalpha() for c in token)


def extract_code(subject, body):
    """Returns the code string (spaces and dashes removed) from the first line that mentions a code, else None."""
    text = URL_PATTERN.sub(" ", f"{subject}\n{body}")
    lines = [line for line in text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if not CODE_CONTEXT.search(line):
            continue
        for candidate in (line, *lines[index + 1:index + 3]):
            for match in CODE_PATTERN.finditer(candidate):
                if _is_code(match.group(1)):
                    return re.sub(r"[ -]", "", match.group(1))
    return None


def fresh_enough(sent_at, now=None, max_age_minutes=MAX_AGE_MINUTES):
    now = now or datetime.now(timezone.utc)
    return timedelta(0) <= now - sent_at <= timedelta(minutes=max_age_minutes)


def sender_allowed(sender, allowed_domains):
    match = re.search(r"@([A-Za-z0-9.-]+)", sender or "")
    host = match.group(1).lower() if match else ""
    return any(host == domain or host.endswith("." + domain) for domain in (d.lower() for d in allowed_domains))
