"""Ashby preparation on fabricated example.invalid pages only."""
import json
import sys
import unittest

from browser_test_support import HERE, SyntheticBrowserTest

sys.path.insert(0, str(HERE))
import answer_sheet


ASHBY = HERE / "extension" / "adapters" / "ashby.js"
FIXTURES = HERE / "fixtures" / "replay" / "ashby"
URL = "https://ashby-fixture.example.invalid/application"
ADAPTER = "PortalAdapters.forLocation(location.href)"


class PublicAshbyTests(SyntheticBrowserTest):
    def open_ashby(self, fixture="page_1.html"):
        self.open_markup((FIXTURES / fixture).read_text(encoding="utf-8"), URL)
        self.page.add_script_tag(path=str(ASHBY))
        self.page.add_script_tag(content="PortalAdapters.register({...PortalAshbyAdapter, id: 'ashby_fixture', hosts: [/^ashby-fixture\\.example\\.invalid$/]})")

    def test_ashby_has_no_real_hosts(self):
        self.open_ashby()
        ashby = next(item for item in self.page.evaluate("PortalAdapters.list()") if item["id"] == "ashby")
        self.assertEqual(ashby["hosts"], [])
        self.assertEqual(ashby["mode"], "answer_sheet_only")
        self.assertEqual(self.page.evaluate(f"{ADAPTER}.id"), "ashby_fixture")
        self.assertEqual(self.page.evaluate("PortalAdapters.forLocation('https://jobs.ashbyhq.com/synthetic/1').id"), "generic")

    def test_ashby_scan_is_read_only_and_skips_honeypot(self):
        self.open_ashby()
        self.page.evaluate("globalThis.events = 0; ['input','change','focus','click'].forEach(name => document.addEventListener(name, () => events++, true))")
        before = self.page.evaluate("document.body.innerHTML")
        fields = self.scan()
        self.assertFalse([field for field in fields if "bee" in str(field).lower()])
        self.assertEqual(self.page.evaluate("document.body.innerHTML"), before)
        self.assertEqual(self.page.evaluate("events"), 0)

    def test_ashby_answer_sheet_mode_writes_nothing(self):
        self.open_ashby()
        before = self.page.evaluate("JSON.stringify([...document.querySelectorAll('input,textarea')].map(node => node.value))")
        fields = self.scan({"email": {"value": "synthetic@example.invalid", "source": "Fabricated fixture"}})
        sheet = answer_sheet.build_answer_sheet(
            {"company": "Synthetic Company", "role": "Synthetic Role", "resume_path": "Yazad_Madan.docx"},
            fields, url=URL, heading="Application", now="2026-10-11T12:00:00+00:00")
        self.assertEqual(sheet["mode"], "answer_sheet_only")
        self.assertEqual(self.page.evaluate("JSON.stringify([...document.querySelectorAll('input,textarea')].map(node => node.value))"), before)
        self.assertNotIn("beeCatcher", str(sheet))

    def test_ashby_fill_and_upload_refused(self):
        self.open_ashby()
        field = next(f for f in self.scan() if f["key"] == "email")
        result = self.fill([{"id": field["id"], "value": "synthetic@example.invalid"}])
        self.assertEqual(result[0]["status"], "refused")
        self.assertEqual(self.page.locator("#email").input_value(), "")
        upload = self.page.evaluate(f"{ADAPTER}.upload({{field: {{id: 'synthetic-file'}}}}, {{name: 'reviewed.docx'}}, {{selection: {{id: 'synthetic-file'}}}})")
        self.assertEqual(upload["status"], "refused")
        self.assertEqual(self.page.evaluate("[syntheticSubmitClicks, syntheticSubmitEvents]"), [0, 0])

    def test_ashby_overwrite_off_preserves(self):
        self.open_ashby()
        self.page.locator("#email").evaluate("node => node.value = 'existing@example.invalid'")
        field = next(f for f in self.scan() if f["key"] == "email")
        result = self.fill([{"id": field["id"], "value": "synthetic@example.invalid"}])
        self.assertEqual(result[0]["status"], "refused")
        self.assertEqual(self.page.locator("#email").input_value(), "existing@example.invalid")

    def test_ashby_guarded_next_default_off(self):
        self.open_ashby()
        self.page.add_script_tag(path=str(HERE / "extension" / "progress.js"))
        self.assertFalse(self.page.evaluate("PortalProgress.settings.allowGuardedNext"))
        self.assertEqual(self.page.evaluate(f"PortalProgress.guardedNext({ADAPTER}).then(result => result.status)"), "refused")
        self.assertEqual(self.page.evaluate("[syntheticSubmitClicks, syntheticSubmitEvents]"), [0, 0])

    def test_ashby_submit_application_is_final_review(self):
        self.open_ashby()
        self.page.add_script_tag(path=str(HERE / "extension" / "progress.js"))
        self.assertNotEqual(self.page.evaluate(f"{ADAPTER}.nextStep().kind"), "next")
        self.assertEqual(self.page.evaluate("[syntheticSubmitClicks, syntheticSubmitEvents]"), [0, 0])

    def test_ashby_replay_cases(self):
        cases = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))["cases"]
        for case in cases:
            with self.subTest(case=case["name"]):
                self.open_ashby(case["page"])
                gate = self.page.evaluate(f"{ADAPTER}.humanGate(document)")
                self.assertEqual(gate["kind"] if gate else None, case["gate"])
                if gate:
                    field = self.scan()[0]
                    self.assertEqual(self.fill([{"id": field["id"], "value": "Synthetic"}])[0]["status"], "blocked_by_human_gate")
                self.assertEqual(self.page.evaluate("[syntheticSubmitClicks, syntheticSubmitEvents]"), [0, 0])


if __name__ == "__main__":
    unittest.main()
