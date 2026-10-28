"""Add selected Oracle history records without navigating or submitting."""
from datetime import datetime
import re
from typing import TypedDict

from portal_profile import UNRESOLVED_ANSWER

# Config
EDUCATION, EMPLOYMENT = "education", "employment"
SCHOOL, COMPANY, LOCATION = "school", "company", "location"
DATE, DEGREE, TITLE = "date", "degree", "title"
START, END, BULLETS = "start", "end", "bullets"
VALUES, VALUE, SOURCE = "values", "value", "source"
START_DATE, END_DATE, DESCRIPTION = "start_date", "end_date", "description"
MISSING, SOURCES = "missing", "sources"
AREA_OF_STUDY = "areaOfStudy"
DEGREE_FIELD, SCHOOL_FIELD = "contentItemId", "educationalEstablishment"
COUNTRY_FIELD = "countryCode"
COMPANY_FIELD, TITLE_FIELD = "employerName", "jobTitle"
CITY_FIELD, ACHIEVEMENTS_FIELD = "employerCity", "achievements"
START_FIELD, END_FIELD = "startDate", "endDate"
MONTH, YEAR = "month", "year"
BUTTONS = {EDUCATION: "ADD EDUCATION", EMPLOYMENT: "ADD EXPERIENCE"}
CANCEL, EDIT, DELETE = "CANCEL", "Edit", "Delete"
CURRENT_YES, CURRENT_NO = "Yes", "No"
US_COUNTRY = "United States"
US_STATE_CODES = {"AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"}
CURRENT_ENDS = {"present", "current"}
WAIT_MS = 5000
DATE_FORMATS = ("%B %Y", "%b %Y", "%Y-%m")
RECORD_FIELDS = (SCHOOL, COMPANY, LOCATION, DATE, DEGREE, TITLE, START, END, BULLETS, AREA_OF_STUDY)
FACT_FIELDS = {SCHOOL: SCHOOL, COMPANY: COMPANY, LOCATION: LOCATION, DEGREE: DEGREE, TITLE: TITLE,
               START: START_DATE, END: END_DATE, DATE: END_DATE, BULLETS: DESCRIPTION}
REQUIRED_FIELDS = {EDUCATION: (SCHOOL, LOCATION, DEGREE, DATE),
                   EMPLOYMENT: (COMPANY, TITLE, LOCATION, START, END)}
CARD_DATE = re.compile(r"\b(?:\d{4}-\d{2}|\d{1,2}/\d{4}|(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})\b", re.I)
CARD_DATE_FORMATS = DATE_FORMATS + ("%m/%Y",)
CARD_SEPARATOR = re.compile(r"[|\n\r]+")
CARD_ACTIONS = re.compile(r"^(?:edit|delete)(?:\s*(?:edit|delete))*$", re.I)
CARD_TRIM = " \t-:;,/()"
DIALOG_JS = """() => [...document.querySelectorAll('[role="dialog"],dialog[open],[aria-modal="true"]')].some(node => {
  for (let item = node; item; item = item.parentElement) {
    const style = getComputedStyle(item);
    if (item.hidden || item.getAttribute('aria-hidden') === 'true' || style.display === 'none'
        || style.visibility === 'hidden' || Number(style.opacity) === 0) return false;
  }
  return node.getClientRects().length > 0;
})"""
CARDS_JS = r"""() => {
  const cards = new Set();
  for (const edit of document.querySelectorAll('button')) {
    if (edit.textContent.trim().toLowerCase() !== 'edit') continue;
    let node = edit.parentElement;
    while (node && node !== document.body) {
      const content = node.cloneNode(true);
      content.querySelectorAll('button').forEach(button => button.remove());
      if (content.textContent.trim() && [...node.querySelectorAll('button')].some(
          button => button.textContent.trim().toLowerCase() === 'delete')) {
        cards.add(node);
        break;
      }
      node = node.parentElement;
    }
  }
  return [...cards].map(node => node.innerText.trim());
}"""
NEW_CARD_JS = """({before}) => {
  const cards = (""" + CARDS_JS + """)();
  return cards.length > before.length && cards.some(text =>
    cards.filter(item => item === text).length > before.filter(item => item === text).length);
}"""
BEFORE = "before"
SAFE_CLICK_JS = """node => !node.closest('a[href],input[type="submit"],input[type="image"],button[type="submit"]')
  && !(node.tagName === 'BUTTON' && node.type === 'submit' && node.form)"""


class OracleRecord(TypedDict):
    school: str
    company: str
    location: str
    date: str
    degree: str
    title: str
    start: str
    end: str
    bullets: str | list[str]
    areaOfStudy: str
    missing: dict[str, str]
    sources: dict[str, str]


class OracleResult(list):
    """Keep printable notes iterable while exposing a checked operation result."""

    def __init__(self, ok: bool = True, reason: str = "ok", field: str = "", notes=()):
        super().__init__(notes if ok or notes else (f"{field}: FAILED ({reason})",))
        self.ok = ok
        self.reason = reason
        self.field = field

    def __bool__(self):
        return self.ok


class OracleError(ValueError):
    def __init__(self, reason, field):
        super().__init__(reason)
        self.reason = reason
        self.field = field


def require_no_dialog(page):
    if page.evaluate(DIALOG_JS):
        raise OracleError("unknown_dialog", "dialog")


def click_control(page, control, field):
    require_no_dialog(page)
    if control.count() != 1:
        raise OracleError("ambiguous_control", field)
    if not control.evaluate(SAFE_CLICK_JS):
        raise OracleError("protected_control", field)
    control.click(timeout=WAIT_MS)
    require_no_dialog(page)


def _text(value):
    return value.strip() if isinstance(value, str) and not UNRESOLVED_ANSWER.search(value) else ""


def records(profile) -> dict[str, list[OracleRecord]]:
    """Read the resolver's sourced facts; raw selected records support standalone callers."""
    found = {EDUCATION: [], EMPLOYMENT: []}
    for group in found:
        for index, raw in enumerate(profile.get(group, []) or []):
            record = {key: "" for key in RECORD_FIELDS}
            record[MISSING], record[SOURCES] = {}, {}
            for key in RECORD_FIELDS:
                if VALUES in profile and key in FACT_FIELDS:
                    fact = profile[VALUES].get(f"{group}.{index}.{FACT_FIELDS[key]}", {})
                    value = _text(fact.get(VALUE)) if _text(fact.get(SOURCE)) else ""
                    source = _text(fact.get(SOURCE))
                else:
                    value, source = raw.get(key), "selected record"
                    if key == BULLETS and isinstance(value, list):
                        value = "\n".join(value) if all(_text(item) for item in value) else ""
                    value = _text(value)
                record[key] = value
                if value:
                    record[SOURCES][key] = source
                else:
                    record[MISSING][key] = "missing"
            for key in (START, END, DATE):
                if not record[key] or key == END and record[key].casefold() in CURRENT_ENDS:
                    continue
                try:
                    month, year = _date(record[key])
                    record[key] = datetime.strptime(f"{month} {year}", "%B %Y").strftime("%Y-%m")
                except ValueError:
                    record[key] = ""
                    record[MISSING][key] = "invalid_date"
            if record[START] and record[END] and record[END].casefold() not in CURRENT_ENDS and record[START] > record[END]:
                for key in (START, END):
                    record[key] = ""
                    record[MISSING][key] = "invalid_date_range"
            found[group].append(record)
    return found


def _normalize(value):
    return " ".join(str(value or "").casefold().split())


def _contains(text, label):
    return bool(label and re.search(r"(?<!\w)" + re.escape(_normalize(label)) + r"(?!\w)", _normalize(text)))


def _card_parts(text):
    return [_normalize(CARD_ACTIONS.sub("", CARD_DATE.sub("", part)).strip(CARD_TRIM))
            for part in CARD_SEPARATOR.split(text)]


def _card_start(text):
    dates = CARD_DATE.findall(text)
    if len(dates) != 2 and not (len(dates) == 1 and any(_contains(text, word) for word in CURRENT_ENDS)):
        return ""
    parsed = []
    for value in dates:
        for pattern in CARD_DATE_FORMATS:
            try:
                parsed.append(datetime.strptime(value, pattern).strftime("%Y-%m"))
                break
            except ValueError:
                pass
        else:
            return ""
    return parsed[0] if len(parsed) == 1 or parsed[0] <= parsed[1] else ""


def card_present(card_texts, record):
    """Require role identity and refuse incomplete or duplicate candidate matches."""
    school, company = _text(record.get(SCHOOL)), _text(record.get(COMPANY))
    name = school or company
    if not name:
        return False
    candidates = [text for text in card_texts if _normalize(name) in _card_parts(text)]
    if not candidates:
        if any(_contains(text, name) for text in card_texts):
            raise OracleError("ambiguous_card", SCHOOL if school else COMPANY)
        return False
    if school:
        if len(candidates) != 1:
            raise OracleError("ambiguous_card", SCHOOL)
        return True
    title = _text(record.get(TITLE))
    if not title:
        raise OracleError("ambiguous_card", TITLE)
    matches = []
    for text in candidates:
        parts = [part for part in _card_parts(text) if part]
        company_index = parts.index(_normalize(company))
        if _normalize(title) in parts and abs(parts.index(_normalize(title)) - company_index) == 1:
            matches.append(text)
        elif _normalize(title) in parts or company_index != 1:
            raise OracleError("ambiguous_card", TITLE)
    start = _text(record.get(START))
    if start and matches:
        month, year = _date(start)
        expected = datetime.strptime(f"{month} {year}", "%B %Y").strftime("%Y-%m")
        if any(not _card_start(text) for text in matches):
            raise OracleError("ambiguous_card", START)
        matches = [text for text in matches if _card_start(text) == expected]
    if len(matches) > 1:
        raise OracleError("ambiguous_card", TITLE)
    return len(matches) == 1


def plan(card_texts, profile):
    """Return missing education followed by missing employment, in profile order."""
    return [(group, index) for group in (EDUCATION, EMPLOYMENT)
            for index, record in enumerate(profile.get(group, []) or [])
            if not card_present(card_texts, record)]


def _date(value):
    for pattern in DATE_FORMATS:
        try:
            parsed = datetime.strptime(value or "", pattern)
            return parsed.strftime("%B"), parsed.strftime("%Y")
        except (TypeError, ValueError):
            pass
    raise ValueError("A confirmed month and year are required.")


def _field(name):
    return f'[name="{name}"]:visible'


def _date_field(part, name):
    return f'[id^="{part}-{name}-"]:visible'


def _value(control):
    if control.evaluate("node => 'value' in node"):
        return control.input_value().strip()
    return control.inner_text().strip()


def _choose(page, selector, wanted):
    require_no_dialog(page)
    control = page.locator(selector)
    if control.count() != 1:
        raise ValueError("Ambiguous history field.")
    click_control(page, control, selector)
    cell = page.locator('[role="grid"]:visible').get_by_role("gridcell", name=wanted, exact=True)
    click_control(page, cell, selector)
    if _value(control) != wanted:
        raise ValueError("History choice did not persist.")


def _cancel(page):
    cancel = page.get_by_role("button", name=CANCEL, exact=True)
    if cancel.count() == 1 and cancel.is_visible():
        click_control(page, cancel, CANCEL)


def add_record(page, group, record: OracleRecord) -> OracleResult:
    """Fill one inline record, verify values, save, and observe a new card."""
    opened = False
    field = group
    try:
        require_no_dialog(page)
        if group not in BUTTONS:
            return OracleResult(False, "unknown_group", group)
        if MISSING not in record:
            record = records({group: [record]})[group][0]
        before = page.evaluate(CARDS_JS)
        if card_present(before, record):
            return OracleResult()
        for field in REQUIRED_FIELDS[group]:
            if not _text(record.get(field)):
                return OracleResult(False, record.get(MISSING, {}).get(field, "missing"), field)
        name = record.get(SCHOOL if group == EDUCATION else COMPANY)
        if not isinstance(name, str) or not name.strip():
            return OracleResult(False, "missing", SCHOOL if group == EDUCATION else COMPANY)
        text_fields, choices = [], []
        location = record.get(LOCATION) or ""
        city, separator, country = location.rpartition(",")
        if not separator or not city.strip() or not country.strip():
            return OracleResult(False, "invalid_location", LOCATION)
        country = US_COUNTRY if country.strip().upper() in US_STATE_CODES else country.strip()
        choices.append((_field(COUNTRY_FIELD), country))
        if group == EDUCATION:
            choices.extend(((_field(DEGREE_FIELD), record.get(DEGREE)),
                            (_field(SCHOOL_FIELD), name)))
            month, year = _date(record.get(DATE))
            choices.extend(((_date_field(MONTH, END_FIELD), month),
                            (_date_field(YEAR, END_FIELD), year)))
            if record.get(AREA_OF_STUDY):
                text_fields.append((_field(AREA_OF_STUDY), record.get(AREA_OF_STUDY)))
        else:
            text_fields.extend(((_field(COMPANY_FIELD), name),
                                (_field(TITLE_FIELD), record.get(TITLE)),
                                (_field(CITY_FIELD), city.strip())))
            bullets = record.get(BULLETS) or []
            if bullets:
                description = bullets if isinstance(bullets, str) else "\n".join(bullets)
                text_fields.append((_field(ACHIEVEMENTS_FIELD), description))
            month, year = _date(record.get(START))
            choices.extend(((_date_field(MONTH, START_FIELD), month),
                            (_date_field(YEAR, START_FIELD), year)))
            current = str(record.get(END) or "").strip().casefold() in CURRENT_ENDS
            if not current:
                month, year = _date(record.get(END))
                choices.extend(((_date_field(MONTH, END_FIELD), month),
                                (_date_field(YEAR, END_FIELD), year)))
        if any(not isinstance(value, str) or not value.strip() for _, value in text_fields + choices):
            return OracleResult(False, "missing", field)
        if page.get_by_role("button", name=CANCEL, exact=True).count():
            return OracleResult(False, "editor_open", group)
        require_no_dialog(page)
        click_control(page, page.get_by_role("button", name=BUTTONS[group], exact=True), group)
        opened = True
        page.get_by_role("button", name=CANCEL, exact=True).wait_for(timeout=WAIT_MS)
        require_no_dialog(page)
        if group == EMPLOYMENT:
            toggle = page.get_by_role("button", name=CURRENT_YES if current else CURRENT_NO, exact=True)
            click_control(page, toggle, END)
            if toggle.get_attribute("aria-pressed") != "true":
                raise ValueError("Current employment choice was not verified.")
        for selector, wanted in choices:
            field = selector
            _choose(page, selector, wanted)
        for selector, wanted in text_fields:
            field = selector
            require_no_dialog(page)
            page.fill(selector, wanted, timeout=WAIT_MS)
        for selector, wanted in choices + text_fields:
            if _value(page.locator(selector)) != wanted:
                raise ValueError("History value changed before saving.")
        if group == EMPLOYMENT and toggle.get_attribute("aria-pressed") != "true":
            raise ValueError("Current employment choice changed before saving.")
        # Cancel scopes the save button because its label also appears outside the editor.
        form = page.get_by_role("button", name=CANCEL, exact=True).locator(
            "xpath=ancestor::*[.//button[normalize-space(.)='" + BUTTONS[group] + "']][1]")
        require_no_dialog(page)
        click_control(page, form.get_by_role("button", name=BUTTONS[group], exact=True), group)
        page.wait_for_function(NEW_CARD_JS, arg={BEFORE: before}, timeout=WAIT_MS)
        require_no_dialog(page)
        return OracleResult()
    except Exception as error:
        if opened:
            try:
                require_no_dialog(page)
                _cancel(page)
            except Exception:
                pass
        return OracleResult(False, error.reason if isinstance(error, OracleError) else "history_error",
                            error.field if isinstance(error, OracleError) else field)


def apply(page, profile) -> OracleResult:
    """Stop on the first failure; callers must inspect ok before proceeding."""
    notes = []
    try:
        require_no_dialog(page)
        prepared = records(profile)
        for group, index in plan(page.evaluate(CARDS_JS), prepared):
            done = add_record(page, group, prepared[group][index])
            notes.append(f"add {group} {index}: {'ok' if done.ok else 'FAILED'}")
            if not done.ok:
                return OracleResult(False, done.reason, done.field, notes)
        return OracleResult(notes=notes)
    except Exception as error:
        return OracleResult(False, error.reason if isinstance(error, OracleError) else "history_error",
                            error.field if isinstance(error, OracleError) else "history", notes)
