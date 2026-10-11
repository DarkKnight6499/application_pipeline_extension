"""Lever preparation on fabricated example.invalid pages only."""
import json
import sys
import unittest

from browser_test_support import HERE, SyntheticBrowserTest

sys.path.insert(0, str(HERE))

LEVER = HERE / "extension" / "adapters" / "lever.js"
FIXTURES = HERE / "fixtures" / "replay" / "lever"
URL = "https://lever-fixture.example.invalid/application"
ADAPTER = "PortalAdapters.forLocation(location.href)"
SNAPSHOT = "JSON.stringify([...document.querySelectorAll('input,textarea')].map(node => [node.id, node.value, node.checked]))"


class PublicLeverTests(SyntheticBrowserTest):
    def open_lever(self, fixture="page_1.html"):
        self.open_markup((FIXTURES / fixture).read_text(encoding="utf-8"), URL)
        self.page.add_script_tag(path=str(LEVER))
        self.page.add_script_tag(content="PortalAdapters.register({...PortalLeverAdapter, id: 'lever_fixture', hosts: [/^lever-fixture\\.example\\.invalid$/]})")

    def field(self, **match):
        return next(f for f in self.scan({"values": {}}) if all(f.get(k) == v for k, v in match.items()))

    def test_lever_has_no_real_hosts(self):
        self.open_lever()
        lever = next(item for item in self.page.evaluate("PortalAdapters.list()") if item["id"] == "lever")
        self.assertEqual(lever["hosts"], [])
        self.assertEqual(self.page.evaluate(f"{ADAPTER}.id"), "lever_fixture")
        self.assertEqual(self.page.evaluate("PortalAdapters.forLocation('https://jobs.lever.co/synthetic/1').id"), "generic")

    def test_lever_scan_is_read_only_and_reads_outside_labels(self):
        self.open_lever()
        self.page.evaluate("globalThis.events = 0; ['input','change','focus','click'].forEach(name => document.addEventListener(name, () => events++, true))")
        before = self.page.evaluate("document.body.innerHTML")
        labels = {f["structure"]["dom_id"]: f["label"] for f in self.scan()}
        self.assertEqual(labels["notes"], "Additional information")
        self.assertEqual(self.page.evaluate("document.body.innerHTML"), before)
        self.assertEqual(self.page.evaluate("events"), 0)

    def test_lever_fills_selected_text_only(self):
        self.open_lever()
        name = next(f for f in self.scan() if f["structure"]["dom_id"] == "name")
        notes = next(f for f in self.scan() if f["structure"]["dom_id"] == "notes")
        result = self.fill([{"id": name["id"], "value": "Synthetic"}])
        self.assertEqual(result[0]["status"], "filled")
        self.assertEqual(self.page.locator("#name").input_value(), "Synthetic")
        self.assertEqual(self.page.locator("#notes").input_value(), "")
        self.assertEqual(self.page.evaluate("[syntheticSubmitClicks, syntheticSubmitEvents]"), [0, 0])

    def test_lever_textarea_fill(self):
        self.open_lever()
        notes = next(f for f in self.scan() if f["structure"]["dom_id"] == "notes")
        self.assertEqual(self.fill([{"id": notes["id"], "value": "Synthetic note"}])[0]["status"], "filled")
        self.assertEqual(self.page.locator("#notes").input_value(), "Synthetic note")

    def test_lever_checkbox_radio_file_are_manual_and_unwritten(self):
        self.open_lever()
        before = self.page.evaluate(SNAPSHOT)
        manual = [f for f in self.scan() if f["type"] in ("radio", "checkbox", "file")]
        self.assertGreaterEqual(len(manual), 3)
        for field in manual:
            with self.subTest(field=field["structure"]["dom_id"] or field["type"]):
                self.assertEqual(field["status"], "manual_only")
                option = field["options"][0]["value"] if field["options"] else "on"
                result = self.fill([{"id": field["id"], "value": option}])
                self.assertEqual(result[0]["status"], "refused")
        self.assertEqual(self.page.evaluate(SNAPSHOT), before)

    def test_lever_upload_refused(self):
        self.open_lever()
        result = self.page.evaluate(f"{ADAPTER}.upload({{field: {{id: 'x'}}}}, {{name: 'reviewed.docx'}}, {{selection: {{id: 'x'}}}})")
        self.assertEqual(result["status"], "refused")

    def test_lever_overwrite_off_preserves(self):
        self.open_lever()
        self.page.locator("#name").evaluate("node => node.value = 'Existing'")
        name = next(f for f in self.scan() if f["structure"]["dom_id"] == "name")
        self.fill([{"id": name["id"], "value": "Synthetic"}])
        self.assertEqual(self.page.locator("#name").input_value(), "Existing")

    def test_lever_submit_never_next(self):
        self.open_lever()
        self.page.add_script_tag(path=str(HERE / "extension" / "progress.js"))
        self.assertNotEqual(self.page.evaluate(f"{ADAPTER}.nextStep().kind"), "next")
        self.assertFalse(self.page.evaluate("PortalProgress.settings.allowGuardedNext"))
        self.assertEqual(self.page.evaluate("[syntheticSubmitClicks, syntheticSubmitEvents]"), [0, 0])

    def test_lever_replay_cases(self):
        for case in json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))["cases"]:
            with self.subTest(case=case["name"]):
                self.open_lever(case["page"])
                gate = self.page.evaluate(f"{ADAPTER}.humanGate(document)")
                self.assertEqual(gate["kind"] if gate else None, case["gate"])
                if gate:
                    field = self.scan()[0]
                    self.assertEqual(self.fill([{"id": field["id"], "value": "Synthetic"}])[0]["status"], "blocked_by_human_gate")
                    self.assertEqual(self.page.locator("#name").input_value(), "")
                self.assertEqual(self.page.evaluate("[syntheticSubmitClicks, syntheticSubmitEvents]"), [0, 0])


if __name__ == "__main__":
    unittest.main()
