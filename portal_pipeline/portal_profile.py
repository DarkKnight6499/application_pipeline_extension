"""Resolve portal values from the existing read-only resume references."""
from __future__ import annotations

import datetime
import json
import os
import re
import tempfile
from pathlib import Path

# Answer validation configuration
UNRESOLVED_ANSWER = re.compile(
    r"\b(confirm|confirmation|unconfirmed|unknown|pending|tbd|tbc|unsure)\b|\?"
    r"|\bnot\s+(?:yet\s+)?(?:specified|provided|known|confirmed|sure)\b"
    r"|\bto\s+be\s+(?:determined|confirmed)\b|\[(?:verify|tailor)\]", re.I)
BOOLEAN_ANSWER_KEYS = {"authorized_us", "sponsorship_now", "sponsorship_future", "relocation"}
EMAIL_PATTERN = re.compile(r"[^\s@|]+@[^\s@|]+\.[^\s@|]+")
PHONE_PATTERN = re.compile(r"\+?[\d().\s-]+(?:\s*(?:ext\.?|x)\s*\d+)?", re.I)
MIN_PHONE_DIGITS = 7
# Leading yes or no, optionally followed by a bracketed or dashed qualifier such as "No (on F-1 OPT)".
BOOLEAN_LEAD = re.compile(r"(yes|no)(?:\s*[(,:;–-].*)?", re.I | re.S)
CONTACT_FIELD_NAMES = ("email", "phone", "location")
# Resolver v2 configuration
ELIGIBILITY_KEYS = {"authorized_us", "sponsorship_now", "sponsorship_future", "sponsorship_now_or_future", "visa_type", "citizenship"}
MASTER_FILE = "Resume_Content_Master.json"
BOILER_FILE = "Application_Boilerplate.md"
INTERNALS_FILE = "Builder_Internals.md"
ANSWERS_SECTION = "Standard Boilerplate Answers"
DESCRIPTIONS_SECTION = "Role Descriptions"
OVERRIDES_FILENAME = "overrides.json"
SESSION_FILENAME = "session.json"
TAILORED_FILENAME = "resume_content.json"
OVERRIDES_SCHEMA_VERSION = 1
OVERRIDE_KEY_PATTERN = re.compile(r"[a-z][a-z_]*(?:\.\d+\.[a-z][a-z_]*)?")
MAX_OVERRIDE_CHARS = 4000
OVERRIDE_TIER, IDENTITY_TIER, HISTORY_TIER, DESCRIPTION_TIER, DRAFT_TIER = 1, 2, 3, 4, 5
DRAFT_STATUS = "draft_needs_review"
ALWAYS_PENDING_KEYS = ("street_address", "postal_code")


def source_ref(file: str, section: str, line: int | None = None) -> str:
    return f"{file}#{section}" + (f":L{line}" if line else "")


def plain(value: str) -> str:
    return value.replace("**", "").replace("\u2014", ",").strip()


def month(value: str) -> str | None:
    import datetime
    for pattern in ("%B %Y", "%b %Y"):
        try:
            return datetime.datetime.strptime(value.strip(), pattern).strftime("%Y-%m")
        except ValueError:
            pass
    return None


def resolve_profile(root: Path) -> dict:
    reference = root / "_Reference"
    master = json.loads((reference / "Resume_Content_Master.json").read_text(encoding="utf-8"))
    boiler = (reference / "Application_Boilerplate.md").read_text(encoding="utf-8")
    internals = (reference / "Builder_Internals.md").read_text(encoding="utf-8")
    values = {}

    def add(key, value, source):
        if isinstance(value, str):
            value = value.strip()
            if UNRESOLVED_ANSWER.search(value):
                return
        if value is not None and value != "":
            values[key] = {"value": value, "source": source}

    header = master["header"]
    raw_name = header.get("name", "")
    name = [] if UNRESOLVED_ANSWER.search(raw_name) else raw_name.split(",")[0].strip().title().split()
    segments = header.get("contact", "").split("|")
    source = source_ref(MASTER_FILE, "header")
    add("first_name", name[0] if name else None, source)
    add("last_name", " ".join(name[1:]), source)
    add("full_name", " ".join(name), source)
    if len(segments) == len(CONTACT_FIELD_NAMES):
        contact = dict(zip(CONTACT_FIELD_NAMES, (segment.strip() for segment in segments)))
        email = contact["email"]
        phone = contact["phone"]
        location = contact["location"]
        valid_contact = (EMAIL_PATTERN.fullmatch(email) and PHONE_PATTERN.fullmatch(phone)
                         and sum(character.isdigit() for character in phone) >= MIN_PHONE_DIGITS
                         and location and not EMAIL_PATTERN.fullmatch(location)
                         and not PHONE_PATTERN.fullmatch(location)
                         and not any(UNRESOLVED_ANSWER.search(value) for value in contact.values()))
        if valid_contact:
            for key, value in contact.items():
                add(key, value, source)
            add("city", location.split(",")[0].strip(), source)
    add("linkedin", header.get("linkedin"), source)
    add("github", header.get("github"), source)

    answers = {}
    answer_refs = {}
    conflicts = set()
    section = ANSWERS_SECTION
    for number, line in enumerate(boiler.splitlines(), 1):
        heading = re.fullmatch(r"## (.+?)\s*", line)
        if heading:
            section = plain(heading.group(1))
        match = re.fullmatch(r"- ([^:]+):[ \t]*(.*)", line)
        if not match:
            continue
        label, raw = match.groups()
        answer_refs[label] = source_ref(BOILER_FILE, section, number)
        value = plain(raw)
        if label in answers and answers[label].casefold() != value.casefold():
            conflicts.add(label)
        answers[label] = value
    answer_map = {
        "Work authorized in US": "authorized_us",
        "Require sponsorship now": "sponsorship_now",
        "Require sponsorship in future": "sponsorship_future",
        "Visa type": "visa_type",
        "Open to relocation": "relocation",
        "Salary expectation": "salary",
        "Start date": "available_from",
        "Source": "job_source",
        "Country of citizenship": "citizenship",
    }
    for label, key in answer_map.items():
        if label in conflicts:
            continue
        raw = answers.get(label)
        if raw:
            value = plain(raw)
            if not value or UNRESOLVED_ANSWER.search(value):
                continue
            if key in BOOLEAN_ANSWER_KEYS:
                lead = BOOLEAN_LEAD.fullmatch(value)
                if not lead:
                    continue
                value = lead.group(1).title()
            add(key, value, answer_refs[label])

    now, future = values.get("sponsorship_now"), values.get("sponsorship_future")
    if now and future or (now or future) and "Yes" in (now or future)["value"]:
        needs = "Yes" if "Yes" in [item["value"] for item in (now, future) if item] else "No"
        add("sponsorship_now_or_future", needs, "Derived from the separate sponsorship now and in the future answers")

    descriptions = re.findall(r"^### ([^\n]+)\n+(.+?)(?=\n---|\n##|\Z)", boiler, re.M | re.S)
    heading_lines = {line[4:].rstrip(): number for number, line in enumerate(boiler.splitlines(), 1) if line.startswith("### ")}
    employment = []
    for employer in master["experience"]:
        date_parts = re.split(r"\s+[\u2013\u2014]\s+|\s+to\s+", employer["dateRange"])
        for role in employer["roles"]:
            index = len(employment)
            prefix = f"employment.{index}."
            add(prefix + "company", employer["company"], source_ref(MASTER_FILE, "experience"))
            add(prefix + "title", plain(role["title"]), source_ref(MASTER_FILE, "experience"))
            add(prefix + "location", employer["location"], source_ref(MASTER_FILE, "experience"))
            start = end = None
            date_source = source_ref(MASTER_FILE, "experience")
            if len(employer["roles"]) == 1 and len(date_parts) == 2:
                start, end = map(month, date_parts)
            elif employer["company"] == "Axis Bank Limited":
                key = ("Deputy Manager, Wholesale Banking FP&A" if "Deputy Manager" in role["title"]
                       else "Manager, Basel III Capital Reporting and Credit Risk" if "Basel III" in role["title"]
                       else "Manager, ALM (Liquidity Risk and Treasury)" if "Asset Liability" in role["title"]
                       else None)
                if key:
                    found = re.search(re.escape(key) + r":\s*([A-Za-z]+ \d{4}) to ([A-Za-z]+ \d{4})", internals)
                    if found:
                        start, end = map(month, found.groups())
                        date_source = source_ref(INTERNALS_FILE, "non-overlapping application role dates")
            if start and end and start > end:
                start = end = None
            add(prefix + "start_date", start, date_source)
            add(prefix + "end_date", end, date_source)
            for heading, paragraph in descriptions:
                normalized = plain(heading)
                if employer["company"] in normalized and plain(role["title"]) in normalized:
                    add(prefix + "description", plain(paragraph), source_ref(BOILER_FILE, DESCRIPTIONS_SECTION, heading_lines.get(heading)))
                    break
            employment.append({"company": employer["company"], "title": plain(role["title"])})

    for index, education in enumerate(master["education"]):
        for key, value in {"school": education["school"], "degree": education["degree"],
                           "location": education["location"], "end_date": month(education["date"])}.items():
            add(f"education.{index}.{key}", value, source_ref(MASTER_FILE, "education"))
    return {"values": values, "employment": employment, "education": master["education"],
            "note": "No street address, postal code, education start date, or voluntary demographic default is inferred."}


def hard_fact_errors(content: dict, master: dict) -> list[str]:
    """Allow tailoring while rejecting changed identity, dates, and credentials."""
    errors = []
    for key in ("header", "education", "certifications"):
        if content.get(key) != master.get(key):
            errors.append(f"{key} must match the master. Change facts in the existing workflow first.")
    facts = {item["company"]: item for item in master["experience"]}
    for item in content.get("experience", []):
        original = facts.get(item.get("company"))
        if not original:
            errors.append("An employer is not present in the master.")
            continue
        for key in ("location", "dateRange"):
            if item.get(key) != original[key]:
                errors.append(f"{item['company']}: {key} differs from the master.")
        titles = {role["title"] for role in original["roles"]}
        if any(role.get("title") not in titles for role in item.get("roles", [])):
            errors.append(f"{item['company']}: a role title differs from the master.")
    return errors


def _session_application_id(session_folder: Path):
    path = session_folder / SESSION_FILENAME
    return json.loads(path.read_text(encoding="utf-8")).get("application_id") if path.is_file() else None


def load_overrides(session_folder: Path) -> dict:
    session_folder = Path(session_folder)
    path = session_folder / OVERRIDES_FILENAME
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != OVERRIDES_SCHEMA_VERSION:
        raise ValueError("Unsupported overrides file version.")
    expected = _session_application_id(session_folder)
    if expected is not None and data.get("application_id") != expected:
        raise ValueError("Overrides belong to a different application.")
    return {key: entry for key, entry in data.get("overrides", {}).items()
            if key not in ELIGIBILITY_KEYS and isinstance(entry, dict) and isinstance(entry.get("value"), str)}


def save_override(session_folder: Path, key: str, value: str, reason: str) -> dict:
    session_folder = Path(session_folder)
    if key in ELIGIBILITY_KEYS:
        raise ValueError("Eligibility facts cannot be overridden per application. Change them in the existing workflow.")
    if not isinstance(key, str) or not OVERRIDE_KEY_PATTERN.fullmatch(key):
        raise ValueError("Override key is not a recognized profile key.")
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_OVERRIDE_CHARS:
        raise ValueError("Override value must be non-empty text within the length limit.")
    if UNRESOLVED_ANSWER.search(value):
        raise ValueError("An unresolved or tentative answer cannot be saved as an override.")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("Record the reason for this override.")
    overrides = load_overrides(session_folder)
    record = {"value": value.strip(), "reason": reason.strip(), "edited_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    overrides[key] = record
    payload = {"schema_version": OVERRIDES_SCHEMA_VERSION, "application_id": _session_application_id(session_folder), "overrides": overrides}
    descriptor, temporary = tempfile.mkstemp(dir=session_folder, suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        os.replace(temporary, session_folder / OVERRIDES_FILENAME)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return record


def _tier(key: str) -> int:
    if key.endswith(".description_draft"):
        return DRAFT_TIER
    if key.endswith(".description"):
        return DESCRIPTION_TIER
    if key.startswith(("employment.", "education.")):
        return HISTORY_TIER
    return IDENTITY_TIER


def resolve_for_application(root: Path, session_folder: Path) -> dict:
    """resolve_profile(root) plus overrides and tailored drafts; returns the same shape plus 'precedence' per key."""
    session_folder = Path(session_folder)
    profile = resolve_profile(root)
    values = profile["values"]
    precedence = {key: _tier(key) for key in values}
    tailored_path = session_folder / TAILORED_FILENAME
    tailored = json.loads(tailored_path.read_text(encoding="utf-8")) if tailored_path.is_file() else {}
    bullets = {}
    for employer in tailored.get("experience", []):
        for role in employer.get("roles", []):
            bullets[(employer.get("company"), plain(role.get("title", "")))] = [plain(b) for b in role.get("bullets", []) if isinstance(b, str)]
    for index, record in enumerate(profile["employment"]):
        found = bullets.get((record["company"], record["title"]))
        if found:
            key = f"employment.{index}.description_draft"
            values[key] = {"value": "\n".join(found), "source": source_ref(TAILORED_FILENAME, "experience"), "status": DRAFT_STATUS}
            precedence[key] = DRAFT_TIER
    for key, entry in load_overrides(session_folder).items():
        values[key] = {"value": entry["value"], "source": source_ref(OVERRIDES_FILENAME, key), "reason": entry.get("reason", ""),
                       "edited_at": entry.get("edited_at", "")}
        precedence[key] = OVERRIDE_TIER
    pending = list(ALWAYS_PENDING_KEYS) + [f"education.{index}.start_date" for index in range(len(profile["education"]))]
    return {**profile, "values": values, "precedence": precedence, "pending": [key for key in pending if key not in values]}
