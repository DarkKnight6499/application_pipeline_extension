"""Author: Yazad Madan. Conservative, browser-free prefill classification."""
import re
import unicodedata
from datetime import datetime

import failure_telemetry as telemetry

# Config
REUSE, FRESH, UNKNOWN = "reuse", "fresh", "unknown"
MODE_KEY, LAST_USED_KEY = "mode", "last_application_used"
KEPT_KEY, FILLED_KEY, DIFF_KEY, FORCED_KEY = "kept", "filled", "diff", "forced"
COUNT_KEYS = (KEPT_KEY, FILLED_KEY, DIFF_KEY, FORCED_KEY)
DIFFS_KEY, EXTRAS_KEY = "diffs", "extra_history_rows"
PREVIEW_KEY, CURRENT_KIND_KEY, PROFILE_KIND_KEY = "prefilled_preview", "prefilled_value_kind", "profile_value_kind"
BINDINGS_KEY, PRESERVED_KEY, MISSING_KEY = "bindings", "preserved", "missing"
LABEL_KEY, TYPE_KEY, KEY_KEY, CURRENT_KEY, PROPOSAL_KEY = "label", "type", "key", "current", "proposal"
RECORD_KEY, GROUP_KEY, ID_KEY, VALUES_KEY, VALUE_KEY = "record", "group", "id", "values", "value"
OPTIONS_KEY, REQUIRED_KEY = "options", "required"
BLOCKED_KEY, DISABLED_KEY = "blocked", "disabled"
DIFF_LIMIT, PREVIEW_LIMIT = 100, 40
FORCED_KEYS = {"authorized_us", "available_from", "salary", "resume", "cover_letter", "cover"}
SENSITIVE_LABEL = re.compile(r"phone|mobile|telephone|email|e.mail|\bid\b|identifier|passport|social security|\bssn\b|licen[cs]e|account|\bname\b|address|birth|postal|\bzip\b", re.I)
ID_VALUE = re.compile(r"(?=.*\d)(?:[\w-]{6,}|[\d ()+.-]{7,})\Z")
PHONE_LABEL = re.compile(r"phone|mobile|telephone", re.I)
DATE_LABEL = re.compile(r"date|available.from|birth", re.I)
DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%Y/%m/%d", "%B %d, %Y", "%b %d, %Y")
MONTH_FORMATS = ("%Y-%m", "%m/%Y", "%B %Y", "%b %Y", "%b. %Y")
HISTORY_IDENTITIES = {"employment": ("company", "title"), "education": ("school", "degree")}
HISTORY_LABELS = {
    "company": {"company", "company name", "employer", "employer name"},
    "title": {"title", "job title", "role title", "position title"},
    "school": {"school", "school name", "university", "institution", "school or university"},
    "degree": {"degree", "degree earned"},
}


def value_kind(value):
    return ("null" if value is None else "boolean" if isinstance(value, bool) else "string" if isinstance(value, str)
            else "number" if isinstance(value, (int, float)) else "array" if isinstance(value, list) else "object")


def empty(value):
    return value is None or value is False or isinstance(value, str) and not value.strip()


def normalize(value, hint=""):
    if value is None:
        return ""
    text = " ".join(unicodedata.normalize("NFKC", str(value)).casefold().split())
    if PHONE_LABEL.search(hint):
        digits = re.sub(r"\D", "", text)
        return digits[1:] if len(digits) == 11 and digits.startswith("1") else digits
    if DATE_LABEL.search(hint):
        for formats, output in ((DATE_FORMATS, "%Y-%m-%d"), (MONTH_FORMATS, "%Y-%m")):
            for pattern in formats:
                try:
                    return datetime.strptime(text, pattern).strftime(output)
                except ValueError:
                    pass
    return "".join(character for character in text if character.isalnum() or character in "+#")


def displayed_value(field):
    current = field.get(CURRENT_KEY)
    matches = [option.get(LABEL_KEY) for option in field.get(OPTIONS_KEY, []) if isinstance(option, dict)
               and str(option.get(VALUE_KEY)) == str(current)]
    return matches[0] if len(matches) == 1 else current


def forced(field):
    key = str(field.get(KEY_KEY) or "")
    return field.get(RECORD_KEY) is None and (key in FORCED_KEYS or "sponsorship" in key or field.get(TYPE_KEY) == "file")


def classify(field, force=False):
    if force or forced(field):
        return FORCED_KEY
    current, proposal = displayed_value(field), field.get(PROPOSAL_KEY)
    if empty(current):
        return FILLED_KEY if field.get(REQUIRED_KEY) or not empty(proposal) else None
    hint = str(field.get(KEY_KEY) or field.get(LABEL_KEY) or "")
    return KEPT_KEY if not empty(proposal) and normalize(current, hint) == normalize(proposal, hint) else DIFF_KEY


def difference(field):
    current = displayed_value(field)
    text = str(current or "")
    if SENSITIVE_LABEL.search(str(field.get(LABEL_KEY)) + " " + str(field.get(KEY_KEY))) or "@" in text or ID_VALUE.fullmatch(text):
        preview = "[masked]"
    else:
        preview = telemetry.clean_text(text, limit=PREVIEW_LIMIT)
        preview = re.sub(r"\d", "*", preview)
    secrets = telemetry.answer_strings(current) | telemetry.answer_strings(field.get(PROPOSAL_KEY))
    return {LABEL_KEY: telemetry.clean_text(field.get(LABEL_KEY), secrets, telemetry.TEXT_LIMIT),
            TYPE_KEY: telemetry.clean_text(field.get(TYPE_KEY), secrets), CURRENT_KIND_KEY: value_kind(current),
            PREVIEW_KEY: preview[:PREVIEW_LIMIT], PROFILE_KIND_KEY: value_kind(field.get(PROPOSAL_KEY))}


def record_classifications(event, fields, force_ids=()):
    for key in COUNT_KEYS:
        event[key] = 0
    event[DIFFS_KEY] = []
    for field in fields:
        if field.get(BLOCKED_KEY) or field.get(DISABLED_KEY):
            continue
        category = classify(field, field.get(ID_KEY) in force_ids)
        if category in (KEPT_KEY, DIFF_KEY):
            event[category] += 1
        if category == DIFF_KEY and len(event[DIFFS_KEY]) < DIFF_LIMIT:
            event[DIFFS_KEY].append(difference(field))


def profile_identity(profile, group, index):
    record = profile.get(group, [])[index]
    return tuple(normalize(record.get(key) or profile.get(VALUES_KEY, {}).get(f"{group}.{index}.{key}", {}).get(VALUE_KEY, ""))
                 for key in HISTORY_IDENTITIES[group])


def history_plan(fields, profile):
    bindings, preserved, extras, missing = {}, set(), [], {}
    for group, identity_keys in HISTORY_IDENTITIES.items():
        rows = {}
        for field in fields:
            record = field.get(RECORD_KEY) or {}
            if record.get(GROUP_KEY) == group:
                rows.setdefault(record[ID_KEY], []).append(field)
        used, blanks = set(), []
        for record_id, members in rows.items():
            if all(empty(member.get(CURRENT_KEY)) for member in members):
                blanks.append(record_id)
                continue
            preserved.add(record_id)
            identity = []
            for key in identity_keys:
                candidates = [member for member in members if str(member.get(KEY_KEY) or "").split(".")[-1] == key
                              or str(member.get(LABEL_KEY) or "").strip().casefold() in HISTORY_LABELS[key]]
                identity.append(normalize(displayed_value(candidates[0])) if len(candidates) == 1 else "")
            matches = [index for index in range(len(profile.get(group, [])))
                       if all(identity) and tuple(identity) == profile_identity(profile, group, index)]
            if len(matches) > 1 or matches and matches[0] in used:
                raise ValueError(f"History identity is ambiguous in {group}. Choose rows manually.")
            if matches:
                bindings[record_id] = matches[0]
                used.add(matches[0])
            else:
                extras.append({GROUP_KEY: group, ID_KEY: telemetry.clean_text(record_id)})
        remaining = [index for index in range(len(profile.get(group, []))) if index not in used]
        for record_id, index in zip(blanks, remaining):
            bindings[record_id] = index
        missing[group] = remaining[len(blanks):]
        extras.extend({GROUP_KEY: group, ID_KEY: telemetry.clean_text(record_id)} for record_id in blanks[len(remaining):])
    return {BINDINGS_KEY: bindings, PRESERVED_KEY: preserved, EXTRAS_KEY: extras, MISSING_KEY: missing}
