"""Taleo preparation on fabricated example.invalid pages only."""
import json
import sys
import unittest

from browser_test_support import HERE, SyntheticBrowserTest

sys.path.insert(0, str(HERE))

SCRIPT = HERE / "extension" / "adapters" / "taleo.js"
FIXTURES = HERE / "fixtures" / "replay" / "taleo"
URL = "https://taleo-fixture.example.invalid/application"
ADAPTER = "PortalAdapters.forLocation(location.href)"


class PublicTaleoTests(SyntheticBrowserTest):
    def open_taleo(self, fixture="page_1.html"):
        self.open_markup((FIXTURES / fixture).read_text(encoding="utf-8"), URL)
        self.page.add_script_tag(path=str(SCRIPT))
        self.page.add_script_tag(content="PortalAdapters.register({...PortalTaleoAdapter, id: 'taleo_fixture', hosts: [/^taleo-fixture\\.example\\.invalid$/]})")

    def by_id(self, dom_id):
        return next(f for f in self.scan() if f["structure"]["dom_id"] == dom_id)

    def test_no_real_hosts(self):
        self.open_taleo()
        entry = next(item for item in self.page.evaluate("PortalAdapters.list()") if item["id"] == "taleo")
        self.assertEqual(entry["hosts"], [])
        self.assertEqual(self.page.evaluate("PortalAdapters.forLocation('https://x.taleo.net/careersection').id"), "generic")

    def test_sign_in_blocks_all_writes(self):
        self.open_taleo("sign_in.html")
        self.assertEqual(self.page.evaluate(f"{ADAPTER}.humanGate(document).kind"), "sign_in")
        result = self.fill([{"id": self.by_id("user")["id"], "value": "Synthetic"}])
        self.assertEqual(result[0]["status"], "blocked_by_human_gate")
        self.assertEqual(self.page.locator("#user").input_value(), "")
        self.assertEqual(self.page.locator("#secret").input_value(), "SYNTHETIC_SECRET")

    def test_form_fill_selected_only(self):
        self.open_taleo()
        self.assertEqual(self.page.evaluate(f"{ADAPTER}.pageKind()"), "form")
        result = self.fill([{"id": self.by_id("first-name")["id"], "value": "Synthetic"}])
        self.assertEqual(result[0]["status"], "filled")
        self.assertEqual(self.page.locator("#email").input_value(), "")
        self.assertEqual(self.page.evaluate("[syntheticSubmitClicks, syntheticSubmitEvents]"), [0, 0])

    def test_overwrite_off_preserves(self):
        self.open_taleo()
        self.page.locator("#first-name").evaluate("node => node.value = 'Existing'")
        self.fill([{"id": self.by_id("first-name")["id"], "value": "Synthetic"}])
        self.assertEqual(self.page.locator("#first-name").input_value(), "Existing")

    def test_native_submit_labelled_next_never_offered(self):
        self.open_taleo()
        self.page.add_script_tag(path=str(HERE / "extension" / "progress.js"))
        self.assertNotEqual(self.page.evaluate(f"{ADAPTER}.nextStep().kind"), "next")
        self.assertEqual(self.page.evaluate(f"PortalProgress.guardedNext({ADAPTER}).then(result => result.status)"), "refused")
        self.assertEqual(self.page.evaluate("[syntheticSubmitClicks, syntheticSubmitEvents]"), [0, 0])

    def test_review_page_is_final_review(self):
        self.open_taleo("review.html")
        self.page.add_script_tag(path=str(HERE / "extension" / "progress.js"))
        self.assertEqual(self.page.evaluate(f"{ADAPTER}.nextStep().kind"), "final_review")
        self.assertEqual(self.page.evaluate("[syntheticSubmitClicks, syntheticSubmitEvents]"), [0, 0])

    def test_replay_cases(self):
        for case in json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))["cases"]:
            with self.subTest(case=case["name"]):
                self.open_taleo(case["page"])
                gate = self.page.evaluate(f"{ADAPTER}.humanGate(document)")
                self.assertEqual(gate["kind"] if gate else None, case["gate"])
                self.assertEqual(self.page.evaluate(f"{ADAPTER}.pageKind()"), case["kind"])


if __name__ == "__main__":
    unittest.main()
