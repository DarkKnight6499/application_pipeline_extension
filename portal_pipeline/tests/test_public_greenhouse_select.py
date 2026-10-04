"""Greenhouse react-select adapter and eligibility classification on synthetic pages only."""
import json
from browser_test_support import SyntheticBrowserTest

# Test configuration
GREENHOUSE_URL = "https://job-boards.greenhouse.io/synthetic/jobs/456"
AUTH_QUESTION = "Are you legally work authorized to work in the US?"
SPONSOR_QUESTION = "Will you now (or in the future) require visa sponsorship in order to work in the US?"
SELECT_FIELDS = [("question_1", AUTH_QUESTION, ["Yes", "No"]), ("question_2", SPONSOR_QUESTION, ["Yes", "No"]),
                 ("question_3", "Have you used Robinhood?", ["Yes", "No"])]
PROFILE_VALUES = {"authorized_us": {"value": "Yes", "source": "synthetic"},
                  "sponsorship_now_or_future": {"value": "Yes", "source": "synthetic"}}

# Verbatim wording seen on real public Greenhouse boards, with the intent we accept; None means stay pending.
CLASSIFICATION_CORPUS = [
    ("Are you legally authorized to work in the United States?", "authorized_us"),
    ("Are you legally work authorized to work in the US?", "authorized_us"),
    ("Are you currently eligible to work legally in the United States of America?", "authorized_us"),
    ("Will you now or in the future require sponsorship for employment visa status?", "sponsorship_now_or_future"),
    ("Will you now (or in the future) require visa sponsorship in order to work in the US?", "sponsorship_now_or_future"),
    ("Do you now, or will you ever, require employment sponsorship to work in the country where this job is located?", None),
    ("Will you require sponsorship for employment visa status now or in the future?", "sponsorship_now_or_future"),
    ("Will you require SoFi to commence (\"sponsor\") an immigration case in order to employ you?", None),
    ("Will you require immigration sponsorship at any point in the future to maintain authorization to work in the United States?", "sponsorship_future"),
    ("Do you require immigration sponsorship to work for Affirm in the United States?", None),
    ("Do you require work authorization?", None),
    ("Do you require a visa to work in the United States?", None),
    ("Are you authorized to work without sponsorship?", None),
    ("Are you authorized to work in the location(s) you selected in your previous response?", None),
    ("Are you legally authorised to work full-time in the country where this job is based?", None),
    ("Do you require sponsorship now", "sponsorship_now"),
]

SELECT_PAGE = """<!doctype html><html><body>
<form id="application-form">
%s
</form>
<script>
globalThis.menuLog = [];
document.querySelectorAll('.select-shell').forEach(shell => {
  const input = shell.querySelector('input'), control = shell.querySelector('.select__control'), container = shell.querySelector('.select__value-container');
  const choices = JSON.parse(shell.dataset.choices);
  function open() {
    if (input.getAttribute('aria-expanded') === 'true') return;
    input.setAttribute('aria-expanded', 'true'); input.setAttribute('aria-controls', 'rs-' + input.id + '-listbox');
    const menu = document.createElement('div'); menu.className = 'select__menu-list'; menu.setAttribute('role', 'listbox');
    menu.setAttribute('aria-multiselectable', 'false'); menu.id = 'rs-' + input.id + '-listbox';
    choices.forEach((text, index) => {
      const option = document.createElement('div'); option.className = 'select__option'; option.setAttribute('role', 'option');
      option.id = 'rs-' + input.id + '-option-' + index; option.setAttribute('aria-selected', 'false'); option.textContent = text;
      option.onclick = () => { menuLog.push(input.id + ':' + text); setValue(text); close(); };
      menu.append(option);
    });
    shell.append(menu);
  }
  function close() {
    input.setAttribute('aria-expanded', 'false'); input.removeAttribute('aria-controls');
    shell.querySelector('.select__menu-list')?.remove();
  }
  function setValue(text) {
    container.querySelector('.select__single-value')?.remove();
    const single = document.createElement('div'); single.className = 'select__single-value'; single.textContent = text; container.prepend(single);
  }
  control.addEventListener('mousedown', event => { if (event.button === 0 && document.activeElement === input) open(); });
  input.addEventListener('keydown', event => { if (event.key === 'ArrowDown') open(); if (event.key === 'Escape') close(); });
  if (shell.dataset.revert) shell.addEventListener('click', () => setTimeout(() => container.querySelector('.select__single-value')?.remove(), 5), true);
});
</script></body></html>"""


def shell(field_id, label, choices, extra=""):
    return (f'<label id="{field_id}-label">{label}</label><div class="select-shell" data-choices=\'{json.dumps(choices)}\' {extra}>'
            f'<div><div class="select__control"><div class="select__value-container"><div class="select__input-container">'
            f'<input class="select__input" id="{field_id}" type="text" role="combobox" aria-expanded="false" aria-haspopup="true" '
            f'aria-labelledby="{field_id}-label" aria-required="true"></div></div></div></div></div>')


class GreenhouseSelectTests(SyntheticBrowserTest):
    def open_select(self, extra_markup="", **attributes):
        body = "".join(shell(*field, extra=attributes.get(field[0], "")) for field in SELECT_FIELDS) + extra_markup
        self.open_markup(SELECT_PAGE % body, url=GREENHOUSE_URL)

    def field(self, dom_id):
        return next(field for field in self.scan(PROFILE_VALUES) if field["structure"]["dom_id"] == dom_id)

    def test_scan_reports_adapter_and_eligibility_proposals(self):
        self.open_select()
        auth, sponsor, other = (self.field(name) for name in ("question_1", "question_2", "question_3"))
        self.assertEqual(auth["adapter"], "greenhouse-select")
        self.assertEqual((auth["key"], auth["proposal"]), ("authorized_us", "Yes"))
        self.assertEqual((sponsor["key"], sponsor["proposal"]), ("sponsorship_now_or_future", "Yes"))
        self.assertEqual((other["key"], other["proposal"]), (None, ""))

    def test_selected_dropdown_fills_and_reads_back_and_unselected_stay_empty(self):
        self.open_select()
        auth = self.field("question_1")
        result = self.fill([{"id": auth["id"], "value": "Yes"}])
        self.assertEqual(result[0]["status"], "filled", result)
        self.assertEqual(self.page.locator("#question_1").evaluate("n => n.closest('.select-shell').querySelector('.select__single-value').textContent"), "Yes")
        self.assertEqual(self.page.evaluate("menuLog"), ["question_1:Yes"])
        self.assertEqual(self.page.locator("#question_2").evaluate("n => n.closest('.select-shell').querySelectorAll('.select__single-value').length"), 0)
        self.assertEqual(self.page.locator("#question_1").get_attribute("aria-expanded"), "false")

    def test_existing_value_is_preserved_without_overwrite(self):
        self.open_select()
        auth = self.field("question_1")
        self.assertEqual(self.fill([{"id": auth["id"], "value": "No"}])[0]["status"], "filled")
        auth = self.field("question_1")
        result = self.fill([{"id": auth["id"], "value": "Yes"}])
        self.assertEqual(result[0]["status"], "preserved")
        self.assertEqual(self.page.evaluate("menuLog"), ["question_1:No"])

    def test_missing_or_inexact_option_fails_closed_and_closes_menu(self):
        self.open_select()
        auth = self.field("question_1")
        for answer in ("Maybe", "yes please"):
            result = self.fill([{"id": auth["id"], "value": answer}])
            self.assertEqual(result[0]["status"], "failed")
        self.assertEqual(self.page.evaluate("menuLog"), [])
        self.assertEqual(self.page.locator("#question_1").get_attribute("aria-expanded"), "false")

    def test_reverting_portal_is_reported_not_filled(self):
        self.open_select(question_1="data-revert='1'")
        auth = self.field("question_1")
        result = self.fill([{"id": auth["id"], "value": "Yes"}])
        self.assertEqual(result[0]["status"], "failed")

    def test_question_change_while_opening_is_refused(self):
        self.open_select()
        auth = self.field("question_1")
        self.page.evaluate("document.querySelector('#question_1').addEventListener('keydown', () => {document.getElementById('question_1-label').textContent = 'Something else';})")
        result = self.fill([{"id": auth["id"], "value": "Yes"}])
        self.assertEqual(result[0]["status"], "failed")
        self.assertEqual(self.page.evaluate("menuLog"), [])

    def test_demographic_and_unwrapped_comboboxes_stay_manual(self):
        self.open_select('<div id="demographic-section"><label for="g">Gender</label><input id="g" role="combobox" class="select__input" aria-expanded="false" type="text"></div>'
                         '<label for="bare">Country</label><input id="bare" role="combobox" class="select__input" aria-expanded="false" type="text">')
        fields = self.scan(PROFILE_VALUES)
        bare = next(field for field in fields if field["structure"]["dom_id"] == "bare")
        self.assertIsNone(bare["adapter"])
        gender = next(field for field in fields if field["structure"]["dom_id"] == "g")
        self.assertTrue(gender["blocked"])
        self.assertNotIn("Gender", json.dumps(self.page.evaluate("PortalEngine.inspect()")))

    def test_honeypot_inputs_are_never_offered_for_filling(self):
        self.open_markup('<label>Email Address<input id="primary-email-0" type="email"></label>'
                         '<label>Enter website. This input is for robots only, do not enter if you are human.<input id="bee" name="website" data-automation-id="beecatcher" type="text"></label>'
                         '<label>Comments<input id="honey-pot-1" name="honey-pot" type="text"></label>')
        fields = self.scan(PROFILE_VALUES)
        by_id = {field["structure"]["dom_id"]: field for field in fields}
        self.assertFalse(by_id["primary-email-0"]["blocked"])
        for name in ("bee", "honey-pot-1"):
            self.assertTrue(by_id[name]["blocked"], name)
        result = self.fill([{"id": by_id["bee"]["id"], "value": "x"}])
        self.assertEqual(result[0]["status"], "failed")
        self.assertEqual(self.page.locator("#bee").input_value(), "")
        self.assertNotIn("honey-pot", json.dumps(self.page.evaluate("PortalEngine.inspect()")))

    def test_survey_section_options_are_protected_by_their_container(self):
        self.open_markup('<label>Full name<input id="n" name="name"></label>'
                         '<div id="countrySurvey_abc"><ul data-qa="checkboxes"><li><label><input type="checkbox" id="w">White</label></li>'
                         '<li><label><input type="checkbox" id="a">Asian</label></li></ul></div>')
        fields = {field["structure"]["dom_id"]: field for field in self.scan(PROFILE_VALUES)}
        self.assertFalse(fields["n"]["blocked"])
        for name in ("w", "a"):
            self.assertTrue(fields[name]["blocked"], name)
        raw = json.dumps(self.page.evaluate("PortalEngine.inspect()"))
        self.assertNotIn("White", raw)
        self.assertNotIn("Asian", raw)

    def test_classification_corpus_is_negation_safe(self):
        rows = "".join(f'<label>{label}<select><option></option><option>Yes</option><option>No</option></select></label>' for label, _ in CLASSIFICATION_CORPUS)
        self.open_markup(rows)
        keys = {field["label"]: field["key"] for field in self.scan(PROFILE_VALUES)}
        for label, expected in CLASSIFICATION_CORPUS:
            with self.subTest(label=label):
                self.assertEqual(keys[label], expected)
