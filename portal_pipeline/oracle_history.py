"""Add selected Oracle history records without navigating or submitting."""
from datetime import datetime

# Configuration keeps profile keys and portal field names together.
EDUCATION, EMPLOYMENT = "education", "employment"
SCHOOL, COMPANY, LOCATION = "school", "company", "location"
DATE, DEGREE, TITLE = "date", "degree", "title"
START, END, BULLETS = "start", "end", "bullets"
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


def card_present(card_texts, record):
    """Match only nonempty school or company names, ignoring case."""
    names = [record.get(key) for key in (SCHOOL, COMPANY)]
    return any(name.strip().casefold() in text.casefold()
               for name in names if isinstance(name, str) and name.strip()
               for text in card_texts)


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
    control = page.locator(selector)
    if control.count() != 1:
        raise ValueError("Ambiguous history field.")
    control.click(timeout=WAIT_MS)
    cell = page.locator('[role="grid"]:visible').get_by_role("gridcell", name=wanted, exact=True)
    cell.click(timeout=WAIT_MS)
    if _value(control) != wanted:
        raise ValueError("History choice did not persist.")


def _cancel(page):
    cancel = page.get_by_role("button", name=CANCEL, exact=True)
    if cancel.count() == 1 and cancel.is_visible():
        cancel.click(timeout=WAIT_MS)


def add_record(page, group, record):
    """Fill one inline record, verify values, save, and observe a new card."""
    opened = False
    try:
        if group not in BUTTONS:
            return False
        before = page.evaluate(CARDS_JS)
        if card_present(before, record):
            return True
        name = record.get(SCHOOL if group == EDUCATION else COMPANY)
        if not isinstance(name, str) or not name.strip():
            return False
        text_fields, choices = [], []
        location = record.get(LOCATION) or ""
        city, separator, country = location.rpartition(",")
        if not separator or not city.strip() or not country.strip():
            return False
        country = US_COUNTRY if country.strip().upper() in US_STATE_CODES else country.strip()  # profile locations end in a state code for US cities
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
            return False
        if page.get_by_role("button", name=CANCEL, exact=True).count():
            return False
        page.get_by_role("button", name=BUTTONS[group], exact=True).click(timeout=WAIT_MS)
        opened = True
        page.get_by_role("button", name=CANCEL, exact=True).wait_for(timeout=WAIT_MS)
        if group == EMPLOYMENT:
            toggle = page.get_by_role("button", name=CURRENT_YES if current else CURRENT_NO, exact=True)
            toggle.click(timeout=WAIT_MS)
            if toggle.get_attribute("aria-pressed") != "true":
                raise ValueError("Current employment choice was not verified.")
        for selector, wanted in choices:
            _choose(page, selector, wanted)
        for selector, wanted in text_fields:
            page.fill(selector, wanted, timeout=WAIT_MS)
        for selector, wanted in choices + text_fields:
            if _value(page.locator(selector)) != wanted:
                raise ValueError("History value changed before saving.")
        if group == EMPLOYMENT and toggle.get_attribute("aria-pressed") != "true":
            raise ValueError("Current employment choice changed before saving.")
        # The inline form repeats the opener label, so save beside its Cancel button.
        form = page.get_by_role("button", name=CANCEL, exact=True).locator(
            "xpath=ancestor::*[.//button[normalize-space(.)='" + BUTTONS[group] + "']][1]")
        form.get_by_role("button", name=BUTTONS[group], exact=True).click(timeout=WAIT_MS)
        page.wait_for_function(NEW_CARD_JS, arg={BEFORE: before}, timeout=WAIT_MS)
        return True
    except Exception:
        if opened:
            try:
                _cancel(page)
            except Exception:
                pass
        return False


def apply(page, profile):
    """Run missing records in order and stop at the first failure."""
    notes = []
    for group, index in plan(page.evaluate(CARDS_JS), profile):
        done = add_record(page, group, profile.get(group, [])[index])
        notes.append(f"add {group} {index}: {'ok' if done else 'FAILED'}")
        if not done:
            break
    return notes
