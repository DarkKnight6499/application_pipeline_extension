"""Read approved long-form evidence and validate human-authored drafts."""

from __future__ import annotations

import re
from pathlib import Path


BOILERPLATE = Path("_Reference") / "Application_Boilerplate.md"
SECTIONS = {"role descriptions": "Role Descriptions", "why us": "Why Us"}
ROLE_WORDS = {"project", "projects", "experience", "work", "background", "role", "roles", "duties",
              "responsibilities", "contribution", "contributions", "achievement", "achievements",
              "accomplishment", "accomplishments", "challenge", "challenges", "impact", "initiative"}
WHY_WORDS = {"why", "company", "employer", "organization", "organisation", "interested", "interest",
             "motivation", "join", "fit"}
UNRESOLVED = re.compile(r"\b(?:todo|tbd|tbc|unconfirmed|unknown|pending|verify|placeholder)\b|\[[^]]+\]", re.I)
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
NUMBER = re.compile(
    r"(?<![\w])(?P<prefix>[A-Za-z]*)(?P<sign>[+-]?)(?P<value>"
    r"(?:\d{1,3}(?:,\d{3})+|\d+|\.\d+)(?:\.\d+)?(?:/\d+|[eE][+-]?\d+)?)"
    r"(?P<suffix>[A-Za-z0-9]*)(?P<unit>\s*(?:%|percent(?:age)?\b|thousand\b|million\b|billion\b|trillion\b))?",
    re.I)


def _requested_sections(question: str) -> set[str]:
    if not isinstance(question, str):
        return set()
    words = set(re.findall(r"[a-z]+", question.casefold()))
    requested = set()
    if words & (ROLE_WORDS - {"work"}) or "work" in words and not words & WHY_WORDS:
        requested.add("Role Descriptions")
    if words & WHY_WORDS:
        requested.add("Why Us")
    return requested


def evidence_for(question: str, root: Path) -> list[dict]:
    """Return only resolved lines from approved boilerplate sections.

    Root is the private Resume workflow checkout. Missing source or unrelated
    questions return no evidence and must remain pending in the caller.
    """
    requested = _requested_sections(question)
    if not requested:
        return []
    base = Path(root).resolve()
    source = (base / BOILERPLATE).resolve()
    if not source.is_relative_to(base) or not source.is_file():
        return []
    if source.stat().st_size > 1_000_000:
        raise ValueError("Boilerplate exceeds evidence read limit.")
    section = None
    output = []
    for line_number, raw in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        heading = HEADING.match(raw)
        if heading:
            if len(heading.group(1)) <= 2:
                section = SECTIONS.get(heading.group(2).strip().casefold())
            continue
        if section not in requested:
            continue
        cleaned = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", "", raw).strip()
        cleaned = cleaned.replace("**", "")
        if not cleaned or cleaned == "---" or UNRESOLVED.search(cleaned):
            continue
        output.append({"text": cleaned, "source": f"Application_Boilerplate.md#{section}:L{line_number}"})
    return output


def count_chars(text: str) -> int:
    """Count UTF-16 code units with each newline normalized to CRLF."""
    if not isinstance(text, str):
        raise TypeError("Draft must be text.")
    canonical = text.replace("\r\n", "\n").replace("\r", "\n")
    return len(canonical.encode("utf-16-le")) // 2 + canonical.count("\n")


def _numbers(text: str):
    for match in NUMBER.finditer(text):
        prefix = match.group("prefix")
        sign = match.group("sign")
        if sign and match.start() > 0 and text[match.start() - 1].isalnum():
            sign = ""
        value = match.group("value").replace(",", "")
        suffix = match.group("suffix")
        unit = (match.group("unit") or "").strip().casefold()
        if unit in {"percent", "percentage"}:
            unit = "%"
        token = match.group(0)
        if token and token[0] in "+-" and not sign:
            token = token[1:]
        yield (prefix, sign, value, suffix, unit), token.strip()


def check_numbers(draft: str, evidence: list[dict]) -> list[str]:
    """List each distinct unsupported numeric expression in draft order."""
    if not isinstance(draft, str):
        raise TypeError("Draft must be text.")
    supported = set()
    for item in evidence:
        if isinstance(item, dict) and isinstance(item.get("text"), str):
            supported.update(key for key, _ in _numbers(item["text"]))
    missing = []
    seen = set()
    for key, token in _numbers(draft):
        if key not in supported and key not in seen:
            missing.append(token)
            seen.add(key)
    return missing


def fit(draft: str, limit: int) -> dict:
    """Report exact count against a strict positive field limit."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise ValueError("Character limit must be a positive integer.")
    count = count_chars(draft)
    return {"ok": count <= limit, "count": count, "limit": limit}
