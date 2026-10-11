"""SuccessFactors preparation on fabricated example.invalid pages only."""
import json
import sys
import unittest

from browser_test_support import HERE, SyntheticBrowserTest

sys.path.insert(0, str(HERE))

SCRIPT = HERE / "extension" / "adapters" / "successfactors.js"
FIXTURES = HERE / "fixtures" / "replay" / "successfactors"
URL = "https://successfactors-fixture.example.invalid/application"
ADAPTER = "PortalAdapters.forLocation(location.href)"


class PublicSuccessFactorsTests(SyntheticBrowserTest):
    def open_sf(self, fixture="page_1.html"):
        self.open_markup((FIXTURES / fixture).read_text(encoding="utf-8"), URL)
        self.page.add_script_tag(path=str(SCRIPT))
        self.page.add_script_tag(content="PortalAdapters.register({...PortalSuccessFactorsAdapter, id: 'sf_fixture', hosts: [/^successfactors-fixture\\.example\\.invalid$/]})")

    def by_id(self, dom_id):
        return next(f for f in self.scan() if f["structure"]["dom_id"] == dom_id)

    def test_no_real_hosts(self):
        self.open_sf()
        entry = next(item for item in self.page.evaluate("PortalAdapters.list()") if item["id"] == "successfactors")
        self.assertEqual(entry["hosts"], [])
        self.assertEqual(self.page.evaluate("PortalAdapters.forLocation('https://career5.successfactors.com/x').id"), "generic")

    def test_profile_preview_lists_parsed_values_read_only(self):
        self.open_sf()
        self.page.evaluate("globalThis.events = 0; ['input','change','focus','click'].forEach(name => document.addEventListener(name, () => events++, true))")
        before = self.page.evaluate("document.body.innerHTML")
        rows = self.page.evaluate(f"{ADAPTER}.profilePreview()")
        self.assertEqual([(r["label"], r["value"]) for r in rows], [("Parsed name", "Synthetic Parsed"), ("Parsed city", "Fabricated City")])
        self.assertEqual(self.page.evaluate("document.body.innerHTML"), before)
        self.assertEqual(self.page.evaluate("events"), 0)

    def test_selected_text_native_select_and_listbox_fill(self):
        self.open_sf()
        first, country = self.by_id("first-name"), self.by_id("country")
        combo = next(f for f in self.scan() if f["type"] == "combobox")
        results = self.fill([{"id": first["id"], "value": "Synthetic"}, {"id": country["id"], "value": "CA"}, {"id": combo["id"], "value": "Yes"}])
        self.assertEqual([r["status"] for r in results], ["filled"] * 3)
        self.assertEqual(self.page.locator("#first-name").input_value(), "Synthetic")
        self.assertEqual(self.page.locator("#country").input_value(), "CA")
        self.assertEqual(self.page.locator("#relocate").get_attribute("aria-valuetext"), "Yes")
        self.assertEqual(self.page.locator("#parsed-name").input_value(), "Synthetic Parsed")
        self.assertEqual(self.page.evaluate("[syntheticSubmitClicks, syntheticSubmitEvents]"), [0, 0])

    def test_unselected_fields_untouched_and_overwrite_off_preserves(self):
        self.open_sf()
        self.page.locator("#first-name").evaluate("node => node.value = 'Existing'")
        self.fill([{"id": self.by_id("first-name")["id"], "value": "Synthetic"}])
        self.assertEqual(self.page.locator("#first-name").input_value(), "Existing")
        self.assertEqual(self.page.locator("#country").input_value(), "")

    def test_sign_in_password_never_written_or_listed(self):
        self.open_sf("sign_in.html")
        self.assertEqual(self.page.evaluate(f"{ADAPTER}.profilePreview().length"), 0)
        field = self.by_id("user")
        self.fill([{"id": field["id"], "value": "Synthetic"}])
        self.assertEqual(self.page.locator("#secret").input_value(), "SYNTHETIC_SECRET")
        self.assertFalse([f for f in self.scan() if f["structure"]["dom_id"] == "secret" and f["status"] != "manual_only"])

    def test_guarded_next_default_off(self):
        self.open_sf()
        self.page.add_script_tag(path=str(HERE / "extension" / "progress.js"))
        self.assertEqual(self.page.evaluate(f"PortalProgress.guardedNext({ADAPTER}).then(result => result.status)"), "refused")
        self.assertEqual(self.page.evaluate("[syntheticSubmitClicks, syntheticSubmitEvents]"), [0, 0])

    def test_replay_cases(self):
        for case in json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))["cases"]:
            with self.subTest(case=case["name"]):
                self.open_sf(case["page"])
                self.assertEqual(self.page.evaluate(f"{ADAPTER}.profilePreview().length"), case["preview_rows"])


if __name__ == "__main__":
    unittest.main()
