"""Oracle readiness regressions use invented facts and synthetic pages only."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest

import answer_sheet
import oracle_attach as attachment
import oracle_history as history
import test_public_oracle_history as history_fixture
from browser_test_support import SyntheticBrowserTest

# Config
COMPANY = "Example Bank"
TITLE = "Analyst"
START = "2021-04"
END = "2024-11"
LOCATION = "Boston, United States"
SOURCE = "Resume_Content_Master.json#experience"
VALUES, VALUE, SOURCE_KEY = "values", "value", "source"
FIRST_PREFIX, EDUCATION_PREFIX = "employment.0.", "education.0."
OLD_START, OLD_END = "January 1990", "December 1999"
REVERSED_START, INVALID_START = "2025-01", "2021"
SCHOOL, DEGREE, EDUCATION_END = "Example University", "Master's Degree", "2026-12"
RECORD = {history.COMPANY: COMPANY, history.TITLE: TITLE, history.LOCATION: LOCATION,
          history.START: START, history.END: END}
CARD = "Analyst | Example Bank | 04/2021 - 11/2024"
OTHER_CARD = "Manager | Example Bank | 01/2018 - 03/2021"
REPEAT_CARD = "Analyst | Example Bank | 01/2018 - 03/2021"
EXTENSION = Path(__file__).resolve().parents[1] / "extension"
ORACLE_URL = "https://jpmc.fa.oraclecloud.com/application"
DIALOG = '<dialog open><p>Unknown decision</p><button type="button">Continue</button></dialog>'
EMPTY_UPLOAD = '<div class="attachment-upload-button"><span>Upload Resume</span><input type="file"></div>'
COUNTERS = """<script>
globalThis.writes = 0;
document.addEventListener('change', () => writes++, true);
document.addEventListener('click', () => writes++, true);
</script>"""


def resolved_profile():
    facts = {history.COMPANY: COMPANY, history.TITLE: TITLE, history.LOCATION: LOCATION,
             history.START_DATE: START, history.END_DATE: END}
    return {history.EMPLOYMENT: [{history.COMPANY: COMPANY, history.TITLE: TITLE}],
            VALUES: {FIRST_PREFIX + key: {VALUE: value, SOURCE_KEY: SOURCE} for key, value in facts.items()}}


def test_record_uses_resolved_facts_without_changing_profile():
    profile = resolved_profile()
    original = deepcopy(profile)
    record = history.records(profile)[history.EMPLOYMENT][0]
    assert {key: record[key] for key in RECORD} == RECORD
    assert record[history.SOURCES][history.START] == SOURCE
    assert profile == original


def test_missing_dates_remain_empty_with_reasons_and_stop_before_opening():
    profile = resolved_profile()
    del profile[VALUES][FIRST_PREFIX + history.START_DATE]
    del profile[VALUES][FIRST_PREFIX + history.END_DATE]
    profile[history.EMPLOYMENT][0].update({history.START: OLD_START, history.END: OLD_END})
    record = history.records(profile)[history.EMPLOYMENT][0]
    assert record[history.START] == record[history.END] == ""
    assert record[history.MISSING][history.START] == record[history.MISSING][history.END] == "missing"
    page = Mock()
    page.evaluate.side_effect = [False, []]
    result = history.add_record(page, history.EMPLOYMENT, record)
    assert (result.ok, result.reason, result.field) == (False, "missing", history.START)
    page.get_by_role.assert_not_called()


def test_invalid_and_reversed_dates_are_not_repaired():
    profile = resolved_profile()
    profile[VALUES][FIRST_PREFIX + history.START_DATE][VALUE] = REVERSED_START
    record = history.records(profile)[history.EMPLOYMENT][0]
    assert record[history.START] == record[history.END] == ""
    assert record[history.MISSING][history.START] == "invalid_date_range"
    profile[VALUES][FIRST_PREFIX + history.START_DATE][VALUE] = INVALID_START
    assert history.records(profile)[history.EMPLOYMENT][0][history.START] == ""


def test_education_uses_sourced_end_date_and_keeps_unknown_start_empty():
    profile = {history.EDUCATION: [{history.SCHOOL: SCHOOL, history.DATE: OLD_END}],
               VALUES: {EDUCATION_PREFIX + key: {VALUE: value, SOURCE_KEY: SOURCE}
                        for key, value in {history.SCHOOL: SCHOOL, history.DEGREE: DEGREE,
                                           history.LOCATION: LOCATION, history.END_DATE: EDUCATION_END}.items()}}
    record = history.records(profile)[history.EDUCATION][0]
    assert record[history.DATE] == EDUCATION_END
    assert record[history.START] == ""
    assert record[history.MISSING][history.START] == "missing"


def test_unsourced_fact_does_not_use_a_raw_date_fallback():
    profile = resolved_profile()
    profile[VALUES][FIRST_PREFIX + history.START_DATE][SOURCE_KEY] = ""
    profile[history.EMPLOYMENT][0][history.START] = START
    record = history.records(profile)[history.EMPLOYMENT][0]
    assert record[history.START] == ""
    assert record[history.MISSING][history.START] == "missing"


def test_protected_control_never_receives_a_click():
    page, control = Mock(), Mock()
    page.evaluate.return_value = False
    control.count.return_value = 1
    control.evaluate.return_value = False
    with pytest.raises(history.OracleError) as error:
        history.click_control(page, control, history.EMPLOYMENT)
    assert (error.value.reason, error.value.field) == ("protected_control", history.EMPLOYMENT)
    control.click.assert_not_called()


def test_reordered_cards_match_company_title_and_start():
    for cards in ([OTHER_CARD, CARD], [CARD, OTHER_CARD]):
        assert history.card_present(cards, RECORD)
        assert history.plan(cards, {history.EMPLOYMENT: [RECORD]}) == []


def test_two_roles_at_one_employer_remain_distinct():
    assert not history.card_present([OTHER_CARD], RECORD)
    assert history.plan([OTHER_CARD], {history.EMPLOYMENT: [RECORD]}) == [(history.EMPLOYMENT, 0)]
    assert history.card_present([REPEAT_CARD, CARD], RECORD)
    assert not history.card_present([REPEAT_CARD], RECORD)


def test_case_and_whitespace_normalize_without_substring_role_matching():
    assert history.card_present(["  ANALYST  | Example   Bank | April 2021 - November 2024"], RECORD)
    assert not history.card_present(["Senior Analyst | Example Bank | 04/2021 - 11/2024"], RECORD)
    with pytest.raises(history.OracleError):
        history.card_present(["Analyst | Example Bank Holdings | 04/2021 - 11/2024"], RECORD)


@pytest.mark.parametrize("cards", [[CARD, CARD], ["Example Bank"],
                                  ["Analyst | Example Bank"], [CARD, "Analyst | Example Bank"],
                                  ["Example Bank | Boston, United States"],
                                  ["Analyst | Example Bank | 11/2024 - 04/2021"],
                                  [CARD + " | 06/2025"]])
def test_ambiguous_cards_stop_before_any_mutation(cards):
    page = Mock()
    page.evaluate.side_effect = [False, cards]
    result = history.apply(page, {history.EMPLOYMENT: [RECORD]})
    assert not result.ok
    assert result.reason == "ambiguous_card"
    page.get_by_role.assert_not_called()


def test_failed_attachment_stops_remaining_actions(monkeypatch):
    page = Mock()
    page.evaluate.side_effect = lambda script: False if script == history.DIALOG_JS else []
    monkeypatch.setattr(attachment, "plan", lambda *args: [("attach", attachment.SLOT_RESUME, Path(__file__)),
                                                         ("remove", attachment.SLOT_COVER, None)])
    attach = Mock(return_value=history.OracleResult(False, "attachment_unconfirmed", attachment.SLOT_RESUME))
    remove = Mock()
    monkeypatch.setattr(attachment, "attach", attach)
    monkeypatch.setattr(attachment, "remove", remove)
    result = attachment.apply(page)
    assert (result.ok, result.reason, result.field) == (False, "attachment_unconfirmed", attachment.SLOT_RESUME)
    remove.assert_not_called()


def test_missing_replacement_file_does_not_remove_existing_file(monkeypatch):
    page = Mock()
    page.evaluate.side_effect = lambda script: False if script == history.DIALOG_JS else [
        {attachment.REMOVE_KEY: "remove resume", attachment.NAME_KEY: "Old.docx"}]
    remove = Mock()
    monkeypatch.setattr(attachment, "remove", remove)
    result = attachment.apply(page, resume=Path(__file__) / "missing.docx")
    assert (result.ok, result.reason, result.field) == (False, "missing_file", attachment.SLOT_RESUME)
    remove.assert_not_called()


def test_duplicate_attachment_slots_require_review():
    rows = [{attachment.REMOVE_KEY: "remove resume", attachment.NAME_KEY: "Old.docx"}] * 2
    with pytest.raises(history.OracleError) as error:
        attachment.existing_slots(rows)
    assert (error.value.reason, error.value.field) == ("ambiguous_slot", attachment.SLOT_RESUME)


@pytest.mark.parametrize("host, expected", [("jpmc.fa.oraclecloud.com", "oracle"), ("ORACLECLOUD.COM", "oracle"),
                                           ("jobs.oraclecloud.com.evil.invalid", "generic"),
                                           ("notoraclecloud.com", "generic")])
def test_answer_sheet_classifies_oracle_hosts(host, expected):
    assert answer_sheet.portal_for(host) == expected


class OracleReadinessBrowserTests(SyntheticBrowserTest):
    def test_cards_remain_matched_after_dom_reordering(self):
        self.open_markup('<section id="cards">' + ''.join(
            '<article><p>' + text + '</p><div><button type="button">Edit</button>'
            '<button type="button">Delete</button></div></article>' for text in (OTHER_CARD, CARD)) + '</section>')
        for _ in range(2):
            result = history.apply(self.page, {history.EMPLOYMENT: [RECORD]})
            self.assertTrue(result.ok)
            self.assertEqual(result, [])
            self.page.evaluate("document.querySelector('#cards').prepend(document.querySelector('article:last-child'))")

    def test_resolved_profile_writes_sourced_dates_and_location(self):
        self.open_markup(history_fixture.MARKUP)
        result = history.apply(self.page, resolved_profile())
        self.assertTrue(result.ok, result.reason)
        self.assertEqual(self.page.evaluate("saved[0].employerCity"), "Boston")
        self.assertEqual(self.page.evaluate("[saves, navigation]"), [1, 0])

    def test_upload_without_confirmation_returns_failure(self):
        self.open_markup(EMPTY_UPLOAD + COUNTERS)
        result = attachment.apply(self.page, resume=Path(__file__))
        self.assertEqual((result.ok, result.reason, result.field),
                         (False, "attachment_unconfirmed", attachment.SLOT_RESUME))
        self.assertEqual(self.page.evaluate("writes"), 1)

    def test_unknown_dialog_blocks_history_and_attachment(self):
        self.open_markup(history_fixture.MARKUP + EMPTY_UPLOAD + DIALOG + COUNTERS)
        for result in (history.apply(self.page, resolved_profile()), attachment.apply(self.page, resume=Path(__file__))):
            self.assertEqual((result.ok, result.reason), (False, "unknown_dialog"))
        self.assertEqual(self.page.evaluate("[writes, saves, navigation]"), [0, 0, 0])

    def test_unknown_dialog_blocks_extension_fill(self):
        self.open_markup('<label>First Name<input id="first" name="firstName"></label>' + DIALOG + COUNTERS, ORACLE_URL)
        for name in ("oracle-grid.js", "adapters/oracle.js", "oracle-live.js"):
            self.page.add_script_tag(path=str(EXTENSION / name))
        field = next(field for field in self.scan() if field["structure"]["dom_id"] == "first")
        result = self.fill([{"id": field["id"], "value": "Synthetic"}])[0]
        self.assertEqual(result["status"], "blocked_by_human_gate")
        self.assertEqual(self.page.locator('#first').input_value(), "")
        self.assertEqual(self.page.evaluate("writes"), 0)
