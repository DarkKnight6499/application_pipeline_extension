"""Pure history plans and a fabricated Oracle inline history form."""
import oracle_history as o
from browser_test_support import SyntheticBrowserTest

# Fabricated facts keep browser coverage independent of private profiles.
EDUCATION_RECORD = {o.SCHOOL: "Example University", o.LOCATION: "Boston, United States",
                    o.DATE: "December 2026", o.DEGREE: "Master's Degree"}
EMPLOYMENT_RECORD = {o.COMPANY: "Example Bank", o.TITLE: "Analyst",
                     o.LOCATION: "Boston, United States", o.START: "April 2021",
                     o.END: "November 2024", o.BULLETS: ["Prepared reports.", "Reviewed forecasts."]}
PROFILE = {o.EDUCATION: [EDUCATION_RECORD], o.EMPLOYMENT: [EMPLOYMENT_RECORD]}


def test_card_names_ignore_case_and_allow_surrounding_text():
    assert o.card_present(["Degree | EXAMPLE UNIVERSITY | 12/2026"], EDUCATION_RECORD)
    assert o.card_present(["Analyst | example bank 04/2021 - 11/2024"], EMPLOYMENT_RECORD)
    assert not o.card_present(["Another University"], EDUCATION_RECORD)


def test_empty_names_never_match_every_card():
    for record in ({}, {o.SCHOOL: ""}, {o.COMPANY: " "}, {o.SCHOOL: None}):
        assert not o.card_present(["Existing card"], record)


def test_plan_keeps_group_and_record_order():
    profile = {o.EDUCATION: [EDUCATION_RECORD, {o.SCHOOL: "Other University"}],
               o.EMPLOYMENT: [EMPLOYMENT_RECORD, {o.COMPANY: "Other Bank"}]}
    assert o.plan([], profile) == [(o.EDUCATION, 0), (o.EDUCATION, 1),
                                    (o.EMPLOYMENT, 0), (o.EMPLOYMENT, 1)]
    assert o.plan(["example university", "OTHER BANK"], profile) == [
        (o.EDUCATION, 1), (o.EMPLOYMENT, 0)]
    assert o.plan([], {}) == []
    assert o.plan(["Example University", "Example Bank"], PROFILE) == []


MARKUP = r"""
<div id="cards"></div>
<button type="button" onclick="openForm('education')">ADD EDUCATION</button>
<button type="button" onclick="openForm('employment')">ADD EXPERIENCE</button>
<div id="inline"></div>
<button type="button" onclick="navigation++">Next</button>
<button type="button" onclick="navigation++">Back</button>
<script>
let navigation = 0, saves = 0, cancels = 0, breakChoice = false;
let saved = [];
const options = {
  contentItemId: ["Master's Degree extra", "Master's Degree"],
  educationalEstablishment: ['Example University extra', 'Example University'],
  countryCode: ['United States extra', 'United States'],
  'month-endDate-9': ['December extra', 'December', 'November'],
  'year-endDate-9': ['2026 extra', '2026', '2024'],
  'month-startDate-9': ['April extra', 'April'],
  'year-startDate-9': ['2021 extra', '2021']
};
function combo(name, id = name) {
  return `<input readonly role="combobox" name="${name}" id="${id}" onclick="showGrid(this)">`;
}
function showGrid(input) {
  document.querySelector('[role=grid]')?.remove();
  const grid = document.createElement('div');
  grid.setAttribute('role', 'grid');
  for (const value of options[input.id]) {
    const row = document.createElement('div');
    row.setAttribute('role', 'row');
    const cell = document.createElement('div');
    cell.setAttribute('role', 'gridcell');
    cell.textContent = value;
    cell.onclick = () => {
      input.value = breakChoice ? 'Wrong value' : value;
      input.dispatchEvent(new Event('change', {bubbles: true}));
      grid.remove();
    };
    row.append(cell); grid.append(row);
  }
  document.body.append(grid);
}
function openForm(group) {
  const form = document.createElement('div');
  form.id = 'editor';
  const dates = (kind) => combo(kind, `month-${kind}-9`) + combo(kind, `year-${kind}-9`);
  form.innerHTML = group === 'education'
    ? combo('contentItemId') + combo('educationalEstablishment') + dates('endDate') +
      combo('countryCode') + '<input name="areaOfStudy">'
    : '<input name="employerName"><input name="jobTitle">' + dates('startDate') + dates('endDate') +
      combo('countryCode') + '<input name="employerCity"><textarea name="achievements"></textarea>' +
      '<textarea>Keep unnamed text</textarea><button type="button" aria-pressed="true">No</button>' +
      '<button type="button" aria-pressed="false">Yes</button>';
  form.querySelectorAll('[aria-pressed]').forEach(button => button.onclick = () => {
    form.querySelectorAll('[aria-pressed]').forEach(item => item.setAttribute('aria-pressed', 'false'));
    button.setAttribute('aria-pressed', 'true');
  });
  const cancel = document.createElement('button');
  cancel.type = 'button'; cancel.textContent = 'CANCEL';
  cancel.onclick = () => { cancels++; form.remove(); document.querySelector('[role=grid]')?.remove(); };
  const save = document.createElement('button');
  save.type = 'button'; save.textContent = group === 'education' ? 'ADD EDUCATION' : 'ADD EXPERIENCE';
  save.onclick = () => {
    saved.push(Object.fromEntries([...form.querySelectorAll('[name]')].map(input => [input.name, input.value])));
    if (group === 'employment' && form.querySelector('textarea:not([name])').value !== 'Keep unnamed text')
      throw new Error('Unnamed textarea changed');
    saves++;
    const card = document.createElement('article');
    const label = document.createElement('p');
    label.textContent = group === 'education' ? "Master's Degree | 12/2026" :
      'Analyst | ' + form.querySelector('[name=employerName]').value + ' 04/2021 - 11/2024';
    card.append(label);
    const actions = document.createElement('div');
    actions.innerHTML = '<button type="button">Edit</button><button type="button">Delete</button>';
    actions.querySelectorAll('button').forEach(button => button.onclick = () => { navigation++; });
    card.append(actions);
    form.remove();
    setTimeout(() => document.querySelector('#cards').append(card), 50);
  };
  form.append(cancel, save); document.querySelector('#inline').append(form);
}
</script>
"""


class OracleHistoryBrowserTests(SyntheticBrowserTest):
    def test_add_verify_cancel_and_stop(self):
        self.open_markup(MARKUP)
        self.assertEqual(o.apply(self.page, PROFILE), ["add education 0: ok", "add employment 0: ok"])
        self.assertEqual(len(self.page.evaluate(o.CARDS_JS)), 2)
        self.assertEqual(self.page.evaluate("key => saved[0][key]", o.SCHOOL_FIELD), EDUCATION_RECORD[o.SCHOOL])
        self.assertEqual(self.page.evaluate("key => saved[0][key]", o.AREA_OF_STUDY), "")
        self.assertEqual(self.page.evaluate("key => saved[1][key]", o.ACHIEVEMENTS_FIELD),
                         "\n".join(EMPLOYMENT_RECORD[o.BULLETS]))
        self.assertEqual(self.page.evaluate("key => saved[1][key]", o.CITY_FIELD), "Boston")
        self.assertEqual(o.apply(self.page, {o.EMPLOYMENT: [EMPLOYMENT_RECORD]}), [])
        self.page.evaluate("breakChoice = true")
        self.assertEqual(o.apply(self.page, PROFILE), ["add education 0: FAILED"])
        self.assertEqual(self.page.evaluate("[saves, cancels, navigation]"), [2, 1, 0])
        self.assertEqual(self.page.locator('#editor').count(), 0)
