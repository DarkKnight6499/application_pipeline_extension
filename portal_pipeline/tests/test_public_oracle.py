"""Oracle preparation on fabricated example.invalid pages only."""
import json
import sys
import unittest

from browser_test_support import HERE, SyntheticBrowserTest

sys.path.insert(0, str(HERE))
import answer_sheet


ORACLE = HERE / "extension" / "adapters" / "oracle.js"
FIXTURES = HERE / "fixtures" / "replay" / "oracle"
URL = "https://oracle-fixture.example.invalid/application"
ADAPTER = "PortalAdapters.forLocation(location.href)"


class PublicOracleTests(SyntheticBrowserTest):
    def open_oracle(self, fixture="page_1.html"):
        self.open_markup((FIXTURES / fixture).read_text(encoding="utf-8"), URL)
        self.page.add_script_tag(path=str(ORACLE))
        self.page.add_script_tag(content="PortalAdapters.register({...PortalOracleAdapter, id: 'oracle_fixture', hosts: [/^oracle-fixture\\.example\\.invalid$/]})")

    def test_oracle_routes_only_synthetic_host(self):
        self.open_oracle()
        entries = self.page.evaluate("PortalAdapters.list()")
        oracle = next(item for item in entries if item["id"] == "oracle")
        self.assertEqual(oracle["hosts"], [])
        self.assertEqual(oracle["mode"], "answer_sheet_only")
        self.assertEqual(self.page.evaluate(f"{ADAPTER}.id"), "oracle_fixture")
        self.assertEqual(self.page.evaluate("PortalAdapters.forLocation('https://example.fa.us2.oraclecloud.com/').id"), "generic")

    def test_oracle_scan_is_read_only(self):
        self.open_oracle()
        self.page.evaluate("globalThis.events = 0; ['input','change','focus','click'].forEach(name => document.addEventListener(name, () => events++, true))")
        before = self.page.evaluate("document.body.innerHTML")
        fields = self.scan()
        self.assertEqual({field["key"] for field in fields if not field["structure"]["dom_id"].startswith("guard-")}, {"first_name", "last_name", "email"})
        self.assertEqual(self.page.evaluate("document.body.innerHTML"), before)
        self.assertEqual(self.page.evaluate("events"), 0)

    def test_oracle_answer_sheet_mode_writes_nothing(self):
        self.open_oracle()
        before = self.page.evaluate("JSON.stringify([...document.querySelectorAll('input')].map(node => node.value))")
        fields = self.scan({"first_name": {"value": "Synthetic", "source": "Fabricated fixture"}})
        sheet = answer_sheet.build_answer_sheet(
            {"company": "Synthetic Company", "role": "Synthetic Role", "resume_path": "Yazad_Madan.docx"},
            fields, url=URL, heading="Personal Information", now="2026-10-05T12:00:00+00:00")
        self.assertEqual(self.page.evaluate(f"{ADAPTER}.mode"), "answer_sheet_only")
        self.assertEqual(sheet["mode"], "answer_sheet_only")
        self.assertEqual(self.page.evaluate("JSON.stringify([...document.querySelectorAll('input')].map(node => node.value))"), before)
        self.assertNotIn("beeCatcher", str(sheet))

    def test_oracle_selected_only_fill_refused_without_writes(self):
        self.open_oracle()
        first = next(field for field in self.scan() if field["key"] == "first_name")
        result = self.fill([{"id": first["id"], "value": "Synthetic"}])
        self.assertEqual(result[0]["status"], "refused")
        self.assertEqual(self.page.locator("#first-name").input_value(), "")
        self.assertEqual(self.page.locator("#last-name").input_value(), "")

    def test_oracle_upload_writer_refused(self):
        self.open_oracle()
        result = self.page.evaluate(f"{ADAPTER}.upload({{field: {{id: 'synthetic-file'}}}}, {{name: 'reviewed.docx'}}, {{selection: {{id: 'synthetic-file'}}}})")
        self.assertEqual(result["status"], "refused")
        self.assertEqual(self.page.evaluate("[syntheticSubmitClicks, syntheticSubmitEvents]"), [0, 0])

    def test_oracle_guarded_next_default_off(self):
        self.open_oracle()
        self.page.add_script_tag(path=str(HERE / "extension" / "progress.js"))
        self.assertFalse(self.page.evaluate("PortalProgress.settings.allowGuardedNext"))
        self.assertEqual(self.page.evaluate(f"PortalProgress.guardedNext({ADAPTER}).then(result => result.status)"), "refused")
        self.assertEqual(self.page.evaluate("[syntheticSubmitClicks, syntheticSubmitEvents]"), [0, 0])

    def test_oracle_overwrite_off_preserves(self):
        self.open_oracle()
        self.page.locator("#first-name").evaluate("node => node.value = 'Existing'")
        first = next(field for field in self.scan() if field["key"] == "first_name")
        result = self.fill([{"id": first["id"], "value": "Synthetic"}])
        self.assertEqual(result[0]["status"], "refused")
        self.assertEqual(self.page.locator("#first-name").input_value(), "Existing")

    def test_oracle_email_gate_detected_as_human_gate(self):
        self.open_oracle("email_gate.html")
        self.assertEqual(self.page.evaluate(f"{ADAPTER}.humanGate(document).kind"), "email_code")
        self.page.evaluate(f"() => {{ globalThis.writerCalls = 0; {ADAPTER}.fill = () => {{ writerCalls++; throw Error('writer reached'); }}; }}")
        first = next(field for field in self.scan() if field["key"] == "first_name")
        result = self.fill([{"id": first["id"], "value": "Synthetic"}])
        self.assertEqual(result[0]["status"], "blocked_by_human_gate")
        self.assertEqual(self.page.locator("#first-name").input_value(), "")
        self.assertEqual(self.page.locator("#verification-code").input_value(), "")
        self.assertEqual(self.page.evaluate("writerCalls"), 0)

    def test_oracle_hcaptcha_mid_flow_stops_and_degrades_to_sheet(self):
        self.open_oracle("hcaptcha_form.html")
        gate = self.page.evaluate(f"{ADAPTER}.humanGate(document)")
        self.assertEqual(gate["kind"], "captcha")
        self.page.evaluate(f"() => {{ globalThis.writerCalls = 0; {ADAPTER}.fill = () => {{ writerCalls++; throw Error('writer reached'); }}; }}")
        first = next(field for field in self.scan() if field["key"] == "first_name")
        self.assertEqual(self.fill([{"id": first["id"], "value": "Synthetic"}])[0]["status"], "blocked_by_human_gate")
        self.assertEqual(self.page.locator("#first-name").input_value(), "")
        self.assertEqual(self.page.evaluate("writerCalls"), 0)
        self.assertEqual(self.page.evaluate("PortalOracleAdapter.nextMode('fill', {kind: 'captcha'})"), "answer_sheet_only")
        self.page.locator("iframe").evaluate("node => node.remove()")
        self.assertIsNone(self.page.evaluate(f"{ADAPTER}.humanGate(document)"))
        self.assertEqual(self.page.evaluate("PortalOracleAdapter.nextMode('answer_sheet_only', null)"), "answer_sheet_only")

    def test_oracle_unknown_previous_mode_fails_closed(self):
        self.open_oracle()
        for previous in (None, "", "unknown"):
            with self.subTest(previous=previous):
                result = self.page.evaluate("mode => PortalOracleAdapter.nextMode(mode, null)", previous)
                self.assertEqual(result, "answer_sheet_only")

    def test_oracle_honeypot_never_listed(self):
        self.open_oracle()
        fields = self.scan()
        self.assertFalse([field for field in fields if "bee" in str(field).lower() or "leave this field" in str(field).lower()])
        self.assertEqual(self.page.locator("#beeCatcher").input_value(), "")

    def test_oracle_final_review_and_submit_counter_zero(self):
        self.open_oracle()
        self.page.locator("#next").evaluate("node => node.insertAdjacentHTML('afterend', '<button type=submit>Submit</button>')")
        self.page.add_script_tag(path=str(HERE / "extension" / "progress.js"))
        self.assertTrue(self.page.evaluate(f"{ADAPTER}.detectFinalReview().final"))
        self.assertNotEqual(self.page.evaluate(f"{ADAPTER}.nextStep().kind"), "next")
        self.assertEqual(self.page.evaluate("[syntheticSubmitClicks, syntheticSubmitEvents]"), [0, 0])

    def test_oracle_replay_cases(self):
        cases = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))["cases"]
        self.assertEqual(len(cases), 3)
        for case in cases:
            with self.subTest(case=case["name"]):
                self.open_oracle(case["page"])
                fields = [field for field in self.scan() if not field["structure"]["dom_id"].startswith("guard-")]
                gate = self.page.evaluate(f"{ADAPTER}.humanGate(document)")
                self.assertEqual(len(fields), case["fields"])
                self.assertEqual(gate["kind"] if gate else None, case["gate"])
                self.assertEqual(self.page.evaluate("[syntheticSubmitClicks, syntheticSubmitEvents]"), [0, 0])


if __name__ == "__main__":
    unittest.main()
