"""Workday rows without a history container are grouped by control id prefix (workExperience-N--, education-N--)."""
from browser_test_support import SyntheticBrowserTest

ROWS = '''<div><label>Name<input></label></div>
<div class="a"><label for="workExperience-78--jobTitle">Job Title*</label><input id="workExperience-78--jobTitle">
  <input id="workExperience-78--startDate-dateSectionYear-input" role="spinbutton" aria-label="Year"></div>
<div class="b"><label for="workExperience-79--jobTitle">Job Title*</label><input id="workExperience-79--jobTitle">
  <input id="workExperience-79--startDate-dateSectionYear-input" role="spinbutton" aria-label="Year"></div>
<div class="c"><label for="education-83--school">School or University*</label><input id="education-83--school"></div>'''


class RowPrefixTests(SyntheticBrowserTest):
    def fields(self, markup=ROWS):
        self.open_markup(markup)
        return self.page.evaluate("PortalEngine.inspect()")["fields"]

    def test_rows_get_records_and_sections(self):
        by_id = {f["structure"]["dom_id"]: f for f in self.fields()}
        self.assertEqual(by_id["workExperience-78--jobTitle"]["section"], "employment")
        self.assertEqual(by_id["education-83--school"]["section"], "education")
        self.assertEqual(by_id["workExperience-78--startDate-dateSectionYear-input"]["record"]["group"], "employment")

    def test_each_row_is_its_own_record(self):
        by_id = {f["structure"]["dom_id"]: f["record"]["id"] for f in self.fields() if f["record"]}
        self.assertEqual(by_id["workExperience-78--jobTitle"], by_id["workExperience-78--startDate-dateSectionYear-input"])
        self.assertNotEqual(by_id["workExperience-78--jobTitle"], by_id["workExperience-79--jobTitle"])

    def test_unrelated_fields_stay_contact(self):
        other = [f for f in self.fields() if not f["structure"]["dom_id"]]
        self.assertTrue(other and all(f["record"] is None and f["section"] == "contact" for f in other))
