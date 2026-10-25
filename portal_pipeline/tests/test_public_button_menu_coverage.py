"""Inspection reports unsupported button menus (Workday style) as coverage, never as fillable fields."""
from browser_test_support import SyntheticBrowserTest

MENUS = '''<label>First name<input value="VALUE_SENTINEL"></label>
  <button type="button" id="country" aria-haspopup="listbox" aria-expanded="false" aria-label="Country Required" data-automation-id="countryDropdown">Select One</button>
  <button type="button" aria-haspopup="menu" aria-label="Phone Device Type" data-automation-id="phone-device-type">Select One</button>
  <button type="button" aria-label="Plain button">Next</button>
  <button type="button" hidden aria-haspopup="listbox" aria-label="Hidden menu">x</button>'''


class ButtonMenuCoverageTests(SyntheticBrowserTest):
    def report(self, markup):
        self.open_markup(markup)
        return self.page.evaluate("PortalEngine.inspect()")

    def test_button_menus_are_counted_with_structure_samples(self):
        coverage = self.report(MENUS)["coverage"]
        self.assertEqual(coverage["unsupported_button_menus"], 2)
        self.assertIn("button_menu_unsupported", coverage["reason_codes"])
        sample = {item["automation_id"]: item for item in coverage["button_menu_samples"]}
        self.assertEqual(set(sample), {"countryDropdown", "phone-device-type"})
        self.assertEqual(sample["countryDropdown"]["haspopup"], "listbox")
        self.assertEqual(sample["countryDropdown"]["expanded"], "false")

    def test_button_menus_never_become_fields(self):
        report = self.report(MENUS)
        self.assertEqual({field["structure"]["tag"] for field in report["fields"]}, {"input"})
        self.assertNotIn("VALUE_SENTINEL", str(report["coverage"]))

    def test_page_without_button_menus_reports_zero(self):
        coverage = self.report('<label>Name<input></label><button type="button">Next</button>')["coverage"]
        self.assertEqual(coverage["unsupported_button_menus"], 0)
        self.assertEqual(coverage["button_menu_samples"], [])
        self.assertNotIn("button_menu_unsupported", coverage["reason_codes"])
