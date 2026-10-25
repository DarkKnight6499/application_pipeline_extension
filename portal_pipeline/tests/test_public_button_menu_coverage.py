"""Inspection reports unsupported button menus (Workday style) as coverage, never as fillable fields."""
from pathlib import Path

from browser_test_support import SyntheticBrowserTest

MENUS = '''<label>First name<input value="VALUE_SENTINEL"></label>
  <label id="country-label" for="country">Country*</label>
  <button type="button" id="country" name="country" aria-haspopup="listbox" aria-expanded="false" aria-controls="country-options" aria-labelledby="country-label" data-automation-id="countryDropdown">Select One</button>
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
        self.assertEqual(sample["countryDropdown"]["controls"], "country-options")
        self.assertEqual(sample["countryDropdown"]["dom_id"], "country")
        self.assertEqual(sample["countryDropdown"]["name"], "country")
        self.assertEqual(sample["countryDropdown"]["label"], "Country*")
        self.assertTrue(sample["countryDropdown"]["required"])
        self.assertEqual(sample["phone-device-type"]["label"], "Phone Device Type")
        self.assertFalse(sample["phone-device-type"]["required"])

    def test_button_menus_never_become_fields(self):
        report = self.report(MENUS)
        self.assertEqual({field["structure"]["tag"] for field in report["fields"]}, {"input"})
        self.assertNotIn("VALUE_SENTINEL", str(report["coverage"]))

    def test_page_without_button_menus_reports_zero(self):
        coverage = self.report('<label>Name<input></label><button type="button">Next</button>')["coverage"]
        self.assertEqual(coverage["unsupported_button_menus"], 0)
        self.assertEqual(coverage["button_menu_samples"], [])
        self.assertNotIn("button_menu_unsupported", coverage["reason_codes"])


class OpenListboxCoverageTests(SyntheticBrowserTest):
    OPEN = '''<label>Name<input></label>
      <button type="button" id="country--country" aria-haspopup="listbox" aria-expanded="true" aria-labelledby="l">Select One</button><span id="l">Country*</span>
      <div data-automation-id="activeListContainer"><ul role="listbox" id="menu1" aria-labelledby="l">
        <li role="option">OPTION_SENTINEL_A</li><li role="option">OPTION_SENTINEL_B</li><li role="option" aria-selected="true">OPTION_SENTINEL_C</li></ul></div>
      <ul role="listbox" hidden><li role="option">Hidden</li></ul>'''

    def report(self, markup):
        self.open_markup(markup)
        return self.page.evaluate("PortalEngine.inspect()")["coverage"]

    def test_visible_listbox_is_sampled_without_option_text(self):
        coverage = self.report(self.OPEN)
        self.assertEqual(coverage["visible_listboxes"], 1)
        sample = coverage["listbox_samples"][0]
        self.assertEqual(sample["dom_id"], "menu1")
        self.assertEqual(sample["option_count"], 3)
        self.assertEqual(sample["container_automation_id"], "activeListContainer")
        self.assertEqual(sample["labelled_by_text"], "Country*")
        self.assertNotIn("OPTION_SENTINEL", str(coverage))

    def test_utility_menu_buttons_are_page_chrome_not_menus(self):
        coverage = self.report('''<button type="button" id="languageSelectorButton" aria-haspopup="listbox" data-automation-id="utilityMenuButton">Lang</button>
          <button type="button" id="country--country" aria-haspopup="listbox" aria-label="Country*">Select One</button>''')
        self.assertEqual(coverage["unsupported_button_menus"], 1)
        self.assertEqual([s["dom_id"] for s in coverage["button_menu_samples"]], ["country--country"])

    def test_no_listbox_reports_zero(self):
        coverage = self.report('<label>Name<input></label>')
        self.assertEqual((coverage["visible_listboxes"], coverage["listbox_samples"]), (0, []))


class QuestionTextTests(SyntheticBrowserTest):
    MENU_SCRIPT = Path(__file__).resolve().parents[1] / "extension" / "workday-menu.js"

    PAGE = '''<form>
      <div class="q"><div><p>Are you legally authorized to work in the country?<span>*</span></p></div><div><button type="button" id="primaryQuestionnaire--aaa" aria-haspopup="listbox">Select One Required</button></div></div>
      <div class="q"><div><p>Do you have relatives working here?</p><p>(1) Relatives mean spouses.</p></div><div><button type="button" id="primaryQuestionnaire--bbb" aria-haspopup="listbox">Select One Required</button></div></div>
    </form>'''

    def test_each_menu_reports_its_own_question_text(self):
        self.open_markup(self.PAGE)
        self.page.add_script_tag(path=str(self.MENU_SCRIPT))
        samples = {s["dom_id"]: s for s in self.page.evaluate("PortalEngine.inspect()")["coverage"]["button_menu_samples"]}
        self.assertEqual(samples["primaryQuestionnaire--aaa"]["question"], "Are you legally authorized to work in the country?*")
        self.assertTrue(samples["primaryQuestionnaire--bbb"]["question"].startswith("Do you have relatives working here?"))
        self.assertNotIn("legally authorized", samples["primaryQuestionnaire--bbb"]["question"])
        self.assertNotIn("Select One", samples["primaryQuestionnaire--aaa"]["question"])

    def test_menu_without_surrounding_text_reports_empty_question(self):
        self.open_markup('<button type="button" aria-haspopup="listbox">Select One</button>')
        self.page.add_script_tag(path=str(self.MENU_SCRIPT))
        self.assertEqual(self.page.evaluate("PortalEngine.inspect()")["coverage"]["button_menu_samples"][0]["question"], "")
