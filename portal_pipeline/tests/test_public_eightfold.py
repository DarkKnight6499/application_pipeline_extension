"""Eightfold preparation on fabricated example.invalid pages only."""
import json
import sys
import unittest

from browser_test_support import HERE, SyntheticBrowserTest

sys.path.insert(0, str(HERE))

EIGHTFOLD = HERE / "extension" / "adapters" / "eightfold.js"
FIXTURES = HERE / "fixtures" / "replay" / "eightfold"
URL = "https://eightfold-fixture.example.invalid/application"
ADAPTER = "PortalAdapters.forLocation(location.href)"


class PublicEightfoldTests(SyntheticBrowserTest):
    def open_eightfold(self, fixture="page_1.html"):
        self.open_markup((FIXTURES / fixture).read_text(encoding="utf-8"), URL)
        self.page.add_script_tag(path=str(EIGHTFOLD))
        self.page.add_script_tag(content="PortalAdapters.register({...PortalEightfoldAdapter, id: 'eightfold_fixture', hosts: [/^eightfold-fixture\\.example\\.invalid$/]})")

    def combo(self):
        return next(f for f in self.scan() if f["type"] == "combobox")

    def test_eightfold_has_no_real_hosts(self):
        self.open_eightfold()
        entry = next(item for item in self.page.evaluate("PortalAdapters.list()") if item["id"] == "eightfold")
        self.assertEqual(entry["hosts"], [])
        self.assertEqual(self.page.evaluate(f"{ADAPTER}.id"), "eightfold_fixture")
        self.assertEqual(self.page.evaluate("PortalAdapters.forLocation('https://nyl.eightfold.ai/careers').id"), "generic")

    def test_eightfold_scan_is_read_only(self):
        self.open_eightfold()
        before = self.page.evaluate("document.body.innerHTML")
        field = self.combo()
        self.assertEqual(field["adapter"], "aria-listbox")
        self.assertEqual(self.page.evaluate("document.body.innerHTML"), before)

    def test_eightfold_selected_dropdown_fill(self):
        self.open_eightfold()
        field = self.combo()
        result = self.fill([{"id": field["id"], "value": "Yes"}])
        self.assertEqual(result[0]["status"], "filled")
        self.assertEqual(self.page.locator("#relocate").get_attribute("aria-valuetext"), "Yes")
        self.assertEqual(self.page.locator("#first-name").input_value(), "")
        self.assertEqual(self.page.evaluate("[syntheticSubmitClicks, syntheticSubmitEvents]"), [0, 0])

    def test_eightfold_unmatched_option_not_guessed(self):
        self.open_eightfold()
        field = self.combo()
        result = self.fill([{"id": field["id"], "value": "Maybe"}])
        self.assertEqual(result[0]["status"], "failed")
        self.assertEqual(self.page.locator("#relocate").get_attribute("aria-valuetext"), "")

    def test_eightfold_cookie_banner_blocks_writes_and_is_not_clicked(self):
        self.open_eightfold("cookie_banner.html")
        self.page.evaluate("globalThis.bannerClicks = 0; document.querySelectorAll('#cookie-banner button').forEach(b => b.addEventListener('click', () => bannerClicks++))")
        self.assertEqual(self.page.evaluate(f"{ADAPTER}.humanGate(document).kind"), "cookie_banner")
        field = next(f for f in self.scan() if f["structure"]["dom_id"] == "first-name")
        self.assertEqual(self.fill([{"id": field["id"], "value": "Synthetic"}])[0]["status"], "blocked_by_human_gate")
        self.assertEqual(self.page.locator("#first-name").input_value(), "")
        self.assertEqual(self.page.evaluate("bannerClicks"), 0)
        self.page.locator("#cookie-banner").evaluate("node => node.remove()")
        self.assertIsNone(self.page.evaluate(f"{ADAPTER}.humanGate(document)"))
        self.assertEqual(self.fill([{"id": field["id"], "value": "Synthetic"}])[0]["status"], "filled")

    def test_eightfold_hidden_banner_does_not_block(self):
        self.open_eightfold("cookie_banner.html")
        self.page.locator("#cookie-banner").evaluate("node => node.hidden = true")
        self.assertIsNone(self.page.evaluate(f"{ADAPTER}.humanGate(document)"))

    def test_eightfold_overwrite_off_preserves(self):
        self.open_eightfold()
        self.page.locator("#first-name").evaluate("node => node.value = 'Existing'")
        field = next(f for f in self.scan() if f["structure"]["dom_id"] == "first-name")
        self.fill([{"id": field["id"], "value": "Synthetic"}])
        self.assertEqual(self.page.locator("#first-name").input_value(), "Existing")

    def test_eightfold_guarded_next_default_off(self):
        self.open_eightfold()
        self.page.add_script_tag(path=str(HERE / "extension" / "progress.js"))
        self.assertFalse(self.page.evaluate("PortalProgress.settings.allowGuardedNext"))
        self.assertEqual(self.page.evaluate(f"PortalProgress.guardedNext({ADAPTER}).then(result => result.status)"), "refused")
        self.assertEqual(self.page.evaluate("[syntheticSubmitClicks, syntheticSubmitEvents]"), [0, 0])

    def test_eightfold_replay_cases(self):
        for case in json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))["cases"]:
            with self.subTest(case=case["name"]):
                self.open_eightfold(case["page"])
                gate = self.page.evaluate(f"{ADAPTER}.humanGate(document)")
                self.assertEqual(gate["kind"] if gate else None, case["gate"])
                self.assertEqual(self.page.evaluate("[syntheticSubmitClicks, syntheticSubmitEvents]"), [0, 0])


if __name__ == "__main__":
    unittest.main()
