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


class RowPrefixShapeTests(SyntheticBrowserTest):
    LIST = '''<ul><li><label for="workExperience-5--jobTitle">Job Title*</label><input id="workExperience-5--jobTitle"></li>
    <li><label for="workExperience-6--jobTitle">Job Title*</label><input id="workExperience-6--jobTitle"></li></ul>'''

    def test_non_div_row_containers_still_group(self):
        self.open_markup(self.LIST)
        fields = [f for f in self.page.evaluate("PortalEngine.inspect()")["fields"] if f["structure"]["dom_id"].startswith("workExperience")]
        self.assertEqual([f["section"] for f in fields], ["employment", "employment"])
        self.assertNotEqual(fields[0]["record"]["id"], fields[1]["record"]["id"])

    def test_row_contexts_are_reported_by_structure(self):
        self.open_markup(self.LIST)
        rows = self.page.evaluate("PortalEngine.inspect()")["coverage"]["row_contexts"]
        self.assertEqual(sorted(row["group"] for row in rows), ["employment", "employment"])
        self.assertEqual({row["container_tag"] for row in rows}, {"li"})
        self.assertTrue(all(row["controls"] == 1 and not row["mixed"] for row in rows))


class WorkdayDatePartTests(SyntheticBrowserTest):
    PAGE = '''<div><label for="workExperience-9--jobTitle">Job Title*</label><input id="workExperience-9--jobTitle">
      <label>Month<input id="workExperience-9--startDate-dateSectionMonth-input" role="spinbutton"></label>
      <label>Year<input id="workExperience-9--startDate-dateSectionYear-input" role="spinbutton"></label>
      <label>Month<input id="workExperience-9--endDate-dateSectionMonth-input" role="spinbutton"></label>
      <label>Year<input id="workExperience-9--endDate-dateSectionYear-input" role="spinbutton"></label></div>
    <div><label for="education-4--school">School*</label><input id="education-4--school">
      <label>Year<input id="education-4--firstYearAttended-dateSectionYear-input" role="spinbutton"></label>
      <label>Year<input id="education-4--lastYearAttended-dateSectionYear-input" role="spinbutton"></label></div>'''
    VALUES = {"employment.0.start_date": {"value": "2023-05", "source": "Fabricated"}, "employment.0.end_date": {"value": "2024-08", "source": "Fabricated"},
              "education.0.start_date": {"value": "2019-09", "source": "Fabricated"}, "education.0.end_date": {"value": "2021-06", "source": "Fabricated"}}

    def proposals(self, bind=True):
        self.open_markup(self.PAGE)
        first = self.page.evaluate("values => PortalEngine.scan({values}, {})", self.VALUES)
        if not bind:
            return {f["structure"]["dom_id"]: (f["key"], f["proposal"]) for f in first}
        bindings = {f["record"]["id"]: 0 for f in first if f["record"]}
        bound = self.page.evaluate("({values, bindings}) => PortalEngine.scan({values}, {bindings})", {"values": self.VALUES, "bindings": bindings})
        return {f["structure"]["dom_id"]: (f["key"], f["proposal"]) for f in bound}

    def test_date_parts_resolve_from_id_once_row_is_bound(self):
        got = self.proposals()
        self.assertEqual(got["workExperience-9--startDate-dateSectionMonth-input"], ("employment.0.start_month", "05"))
        self.assertEqual(got["workExperience-9--startDate-dateSectionYear-input"], ("employment.0.start_year", "2023"))
        self.assertEqual(got["workExperience-9--endDate-dateSectionMonth-input"], ("employment.0.end_month", "08"))
        self.assertEqual(got["workExperience-9--endDate-dateSectionYear-input"], ("employment.0.end_year", "2024"))
        self.assertEqual(got["education-4--firstYearAttended-dateSectionYear-input"], ("education.0.start_year", "2019"))
        self.assertEqual(got["education-4--lastYearAttended-dateSectionYear-input"], ("education.0.end_year", "2021"))

    def test_unbound_rows_propose_nothing(self):
        got = self.proposals(bind=False)
        self.assertIsNone(got["workExperience-9--startDate-dateSectionYear-input"][0])
        self.assertIsNone(got["education-4--lastYearAttended-dateSectionYear-input"][0])


class RowContainerWithoutBoxTests(SyntheticBrowserTest):
    PAGE = '''<div style="display: contents"><label for="workExperience-5--jobTitle">Job Title*</label><input id="workExperience-5--jobTitle"></div>
    <div style="display: contents"><label for="workExperience-6--jobTitle">Job Title*</label><input id="workExperience-6--jobTitle"></div>'''

    def test_rows_group_even_when_container_has_no_box(self):
        self.open_markup(self.PAGE)
        fields = [f for f in self.page.evaluate("PortalEngine.inspect()")["fields"] if f["structure"]["dom_id"].startswith("workExperience")]
        self.assertEqual([f["section"] for f in fields], ["employment", "employment"])
        self.assertNotEqual(fields[0]["record"]["id"], fields[1]["record"]["id"])

    def test_row_with_only_hidden_controls_gets_no_record(self):
        self.open_markup('<div><input id="workExperience-5--jobTitle" style="display:none"></div><input id="other">')
        fields = self.page.evaluate("PortalEngine.inspect()")["fields"]
        self.assertTrue(all(f["record"] is None for f in fields))
