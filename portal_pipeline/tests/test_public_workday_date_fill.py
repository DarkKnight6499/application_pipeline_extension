"""Bound Workday rows fill their date spinbuttons through the date module and verify what the page kept."""
from pathlib import Path

from browser_test_support import SyntheticBrowserTest

DATE_SCRIPT = Path(__file__).resolve().parents[1] / "extension" / "workday-date.js"
PAGE = '''<div><label for="workExperience-9--jobTitle">Job Title*</label><input id="workExperience-9--jobTitle">
<label>Month<input id="workExperience-9--startDate-dateSectionMonth-input" role="spinbutton"></label>
<label>Year<input id="workExperience-9--startDate-dateSectionYear-input" role="spinbutton"></label></div>'''
VALUES = {"employment.0.start_date": {"value": "2023-05", "source": "Fabricated"}}


class DateFillTests(SyntheticBrowserTest):
    def bound(self, markup=PAGE):
        self.open_markup(markup)
        self.page.add_script_tag(path=str(DATE_SCRIPT))
        first = self.page.evaluate("values => PortalEngine.scan({values}, {})", VALUES)
        bindings = {f["record"]["id"]: 0 for f in first if f["record"]}
        fields = self.page.evaluate("({values, bindings}) => PortalEngine.scan({values}, {bindings})", {"values": VALUES, "bindings": bindings})
        return {f["structure"]["dom_id"]: f for f in fields}

    def test_month_and_year_are_written_and_verified(self):
        fields = self.bound()
        picks = [fields[i] for i in ("workExperience-9--startDate-dateSectionMonth-input", "workExperience-9--startDate-dateSectionYear-input")]
        results = self.fill([{"id": f["id"], "value": f["proposal"]} for f in picks])
        self.assertEqual([r["status"] for r in results], ["filled", "filled"], results)
        self.assertEqual(self.page.locator("#workExperience-9--startDate-dateSectionMonth-input").input_value(), "05")
        self.assertEqual(self.page.locator("#workExperience-9--startDate-dateSectionYear-input").input_value(), "2023")

    def test_page_that_normalizes_month_still_verifies(self):
        fields = self.bound()
        self.page.evaluate("""() => { const m = document.getElementById('workExperience-9--startDate-dateSectionMonth-input');
          m.addEventListener('blur', () => { m.value = String(Number(m.value)); }); }""")
        month = fields["workExperience-9--startDate-dateSectionMonth-input"]
        result = self.fill([{"id": month["id"], "value": month["proposal"]}])[0]
        self.assertEqual(result["status"], "filled", result)
        self.assertEqual(self.page.locator("#workExperience-9--startDate-dateSectionMonth-input").input_value(), "5")
