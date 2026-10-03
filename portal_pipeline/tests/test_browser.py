"""Exercise the browser engine, review panel, dashboard, and real MV3 extension."""
import hashlib
import json
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from portal_profile import resolve_profile
from server import Pipeline, make_server
from playwright.sync_api import sync_playwright

from test_support import audited_fixture, workflow_source
SOURCE = workflow_source()


class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.pipeline = Pipeline(SOURCE, Path(cls.temp.name) / "output")
        cls.server = make_server(cls.pipeline, 0, "browser-test-token")
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.profile = resolve_profile(SOURCE)
        cls.session = cls.pipeline.create({"company": "Synthetic Employer", "role": "Treasury Analyst",
            "jd": "Treasury analyst: Python and SQL. Relevant finance education preferred.",
            "template": "Resume_Draft_ALM_Treasury_Liquidity.json", "url": cls.url + "/fixture"})
        built = cls.pipeline.build(cls.session["id"], {"content": cls.session["content"], "resume_terms": ["Python", "SQL"],
            "eligibility": [], "requirements_reviewed": True, "content_reviewed": True})
        if built["state"] != "built":
            raise AssertionError(built["checks"])
        # Test-only approval for the synthetic upload fixture, not an employer form.
        cls.pipeline.approve_upload(cls.session["id"], {"visual_reviewed": True})
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def setUp(self):
        self.context = self.browser.new_context(viewport={"width": 1440, "height": 1050})
        self.page = self.context.new_page()
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.goto(self.url + "/fixture")

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.errors, [])

    def scan(self, bindings=None):
        return self.page.evaluate("({profile, bindings}) => PortalEngine.scan(profile, {bindings})", {"profile": self.profile, "bindings": bindings or {}})

    def history_bindings(self, group):
        records = {field["record"]["id"]: field["record"] for field in self.scan() if field["record"] and field["record"]["group"] == group}
        # Fixture-specific explicit choices. Production does not infer records from page order.
        return {record_id: index for index, record_id in enumerate(records)}

    def fill_keys(self, keys, bindings=None, **options):
        fields = self.scan(bindings)
        selected = [{"id": field["id"], "value": field["proposal"]} for field in fields if field["key"] in keys]
        return self.page.evaluate("async ({selected, options}) => await PortalEngine.fill(selected, options)",
                                  {"selected": selected, "options": options})

    def test_scan_does_not_change_form(self):
        fields = self.scan()
        self.assertTrue(fields)
        self.assertEqual(self.page.locator("#first").input_value(), "")
        self.assertEqual(self.page.locator("#phone").input_value(), "Keep this existing value")
        by_label = {field["key"]: field for field in fields if field["key"]}
        self.assertEqual(by_label["sponsorship_now"]["proposal"], "No")
        self.assertEqual(by_label["sponsorship_future"]["proposal"], "Yes")
        self.assertTrue(any(field["blocked"] and "Password" in field["label"] for field in fields))
        self.assertFalse(any(field["key"] for field in fields if field["label"].startswith("Do you require sponsorship?")))

    def test_only_selected_fields_fill_and_existing_values_preserve(self):
        results = self.fill_keys({"first_name", "phone", "sponsorship_now", "sponsorship_future"})
        self.assertEqual(self.page.locator("#first").input_value(), self.profile["values"]["first_name"]["value"])
        self.assertEqual(self.page.locator("#last").input_value(), "")
        self.assertEqual(self.page.locator("#phone").input_value(), "Keep this existing value")
        self.assertEqual(self.page.locator("#now").input_value(), "0")
        self.assertEqual(self.page.locator("#future").input_value(), "1")
        self.assertEqual(sum(result["status"] == "filled" for result in results), 3)
        self.assertEqual(sum(result["status"] == "preserved" for result in results), 1)

    def test_explicit_overwrite_and_readback(self):
        self.fill_keys({"phone"}, overwrite=True)
        self.assertEqual(self.page.locator("#phone").input_value(), self.profile["values"]["phone"]["value"])

    def test_unknown_authorization_country_remains_pending(self):
        self.page.evaluate("document.querySelector('label:has(#authorized)').firstChild.textContent = 'Are you authorized to work in the UK?'")
        fields = self.scan()
        field = next(field for field in fields if "UK" in field["label"])
        self.assertIsNone(field["key"])

    def test_authorization_inversion_remains_pending(self):
        self.page.evaluate("document.querySelector('label:has(#authorized)').firstChild.textContent = 'Do you require work authorization in the United States?'")
        field = next(field for field in self.scan() if "require work authorization" in field["label"])
        self.assertIsNone(field["key"])

    def test_changed_question_cannot_use_old_selection(self):
        field = next(field for field in self.scan() if field["key"] == "first_name")
        self.page.evaluate("document.querySelector('label:has(#first)').firstChild.textContent = 'Signature' ")
        results = self.page.evaluate("async field => PortalEngine.fill([{id:field.id, value:field.proposal}])", field)
        self.assertEqual(results[0]["status"], "failed")
        self.assertEqual(self.page.locator("#first").input_value(), "")

    def test_collateral_change_stops_further_filling(self):
        fields = self.scan()
        selected = [{"id": field["id"], "value": field["proposal"]} for field in fields if field["key"] in {"first_name", "last_name"}]
        self.page.evaluate("document.getElementById('first').addEventListener('change', () => {document.getElementById('email').value='unexpected@example.invalid';})")
        results = self.page.evaluate("async selected => PortalEngine.fill(selected)", selected)
        self.assertEqual(results[0]["status"], "failed")
        self.assertIn("unselected field changed", results[0]["message"])
        self.assertEqual(self.page.locator("#last").input_value(), "")

    def test_per_field_overwrite(self):
        self.page.locator("#email").fill("keep@example.invalid")
        fields = self.scan()
        selected = [{"id": field["id"], "value": field["proposal"], "overwrite": field["key"] == "phone"}
                    for field in fields if field["key"] in {"phone", "email"}]
        results = self.page.evaluate("async selected => PortalEngine.fill(selected)", selected)
        self.assertEqual(self.page.locator("#email").input_value(), "keep@example.invalid")
        self.assertEqual(self.page.locator("#phone").input_value(), self.profile["values"]["phone"]["value"])
        self.assertEqual({result["status"] for result in results}, {"filled", "preserved"})

    def test_portal_reverting_a_value_reports_failure(self):
        self.page.evaluate("document.getElementById('first').addEventListener('change', event => {event.target.value = '';})")
        results = self.fill_keys({"first_name"})
        self.assertEqual(results[0]["status"], "failed")
        self.assertIn("did not retain", results[0]["message"])

    def test_repeated_employment_dates_and_manual_next(self):
        self.page.locator("#next-one").click()
        keys = {f"employment.{index}.{key}" for index in range(5) for key in ("company", "title", "start_date", "end_date")}
        results = self.fill_keys(keys, bindings=self.history_bindings("employment"))
        self.assertTrue(all(result["status"] == "filled" for result in results), results)
        self.assertEqual(self.page.locator("#start-2").input_value(), "2023-08")
        self.assertEqual(self.page.locator("#end-4").input_value(), "2022-05")
        self.assertEqual(self.page.locator("#progress").text_content(), "Step 2 of 3")

    def test_history_rows_have_no_implicit_profile_assignment(self):
        self.page.locator("#next-one").click()
        fields = [field for field in self.scan() if field["record"]]
        self.assertTrue(fields)
        self.assertTrue(all(field["key"] is None and field["proposal"] == "" for field in fields))
        result = self.page.evaluate("async id => PortalEngine.fill([{id, value: 'Manual value without row choice'}])", fields[0]["id"])
        self.assertEqual(result[0]["status"], "failed")
        self.assertIn("Choose a profile record", result[0]["message"])
        self.assertEqual(self.page.locator("#company-0").input_value(), "")

    def test_history_binding_survives_dom_reordering_without_changing_record(self):
        self.page.locator("#next-one").click()
        bindings = self.history_bindings("employment")
        fields = self.scan(bindings)
        original = next(field for field in fields if field["key"] == "employment.2.company")
        self.page.evaluate("const jobs = document.getElementById('jobs'); jobs.prepend(jobs.children[2]);")
        reordered = self.scan(bindings)
        after = next(field for field in reordered if field["id"] == original["id"])
        self.assertEqual(after["key"], "employment.2.company")
        result = self.page.evaluate("async selection => PortalEngine.fill([selection])", {"id": after["id"], "value": after["proposal"]})
        self.assertEqual(result[0]["status"], "filled", result)
        self.assertEqual(self.page.locator("#company-2").input_value(), self.profile["values"]["employment.2.company"]["value"])
        self.assertEqual(self.page.locator("#company-0").input_value(), "")

    def test_duplicate_profile_binding_requires_another_record_or_manual_answers(self):
        self.page.locator("#next-one").click()
        bindings = self.history_bindings("employment")
        ids = list(bindings)
        bindings[ids[1]] = bindings[ids[0]]
        fields = self.scan(bindings)
        conflicted = [field for field in fields if field["record"] and field["record"]["id"] in ids[:2]]
        self.assertTrue(all(field["record"]["index"] is None for field in conflicted))
        self.assertTrue(all("multiple visible rows" in field["source"] for field in conflicted))
        result = self.page.evaluate("async id => PortalEngine.fill([{id, value: 'Should not fill'}])", conflicted[0]["id"])
        self.assertEqual(result[0]["status"], "failed")

    def test_replaced_history_node_does_not_inherit_old_binding(self):
        self.page.locator("#next-one").click()
        bindings = self.history_bindings("employment")
        old = next(field for field in self.scan(bindings) if field["key"] == "employment.0.company")
        self.page.evaluate("const row = document.getElementById('jobs').firstElementChild; row.replaceWith(row.cloneNode(true));")
        replacement = next(field for field in self.scan(bindings) if field["structure"]["dom_id"] == "company-0")
        self.assertNotEqual(replacement["record"]["id"], old["record"]["id"])
        self.assertIsNone(replacement["record"]["index"])
        result = self.page.evaluate("async selection => PortalEngine.fill([selection])", {"id": old["id"], "value": old["proposal"]})
        self.assertEqual(result[0]["status"], "failed")
        self.assertEqual(self.page.locator("#company-0").input_value(), "")

    def test_changed_history_wrapper_identity_rejects_cached_field(self):
        self.page.locator("#next-one").click()
        bindings = self.history_bindings("employment")
        field = next(field for field in self.scan(bindings) if field["key"] == "employment.0.company")
        self.page.evaluate("document.getElementById('jobs').firstElementChild.setAttribute('data-automation-id', 'workExperience-replaced')")
        result = self.page.evaluate("async selection => PortalEngine.fill([selection])", {"id": field["id"], "value": field["proposal"]})
        self.assertEqual(result[0]["status"], "failed")
        self.assertIn("history row identity changed", result[0]["message"])

    def test_manual_history_row_has_no_profile_proposals(self):
        self.page.locator("#next-one").click()
        bindings = self.history_bindings("employment")
        first = next(iter(bindings)); bindings = {first: "manual"}
        fields = self.scan(bindings)
        manual = next(field for field in fields if field["record"] and field["record"]["id"] == first and field["label"] == "Employer")
        self.assertIsNone(manual["key"])
        self.assertEqual(manual["proposal"], "")
        result = self.page.evaluate("async id => PortalEngine.fill([{id, value: 'Synthetic manual employer'}])", manual["id"])
        self.assertEqual(result[0]["status"], "filled", result)
        self.assertEqual(self.page.locator("#company-0").input_value(), "Synthetic manual employer")

    def test_history_questions_do_not_borrow_personal_contact_or_salary_answers(self):
        self.page.locator("#next-one").click()
        self.page.evaluate("""() => {
          const row = document.getElementById('jobs').firstElementChild;
          for (const caption of ['Email', 'City', 'Salary expectation']) {
            const label = document.createElement('label'); label.textContent = caption; label.append(document.createElement('input')); row.append(label);
          }
        }""")
        bindings = self.history_bindings("employment")
        fields = self.scan(bindings)
        scoped = [field for field in fields if field["record"] and field["label"] in {"Email", "City", "Salary expectation"}]
        self.assertEqual(len(scoped), 3)
        self.assertTrue(all(field["key"] is None and field["proposal"] == "" for field in scoped))

    def test_education_split_month_year_uses_verified_date_and_visible_month_labels(self):
        self.page.locator("#next-one").click()
        bindings = self.history_bindings("education")
        fields = self.scan(bindings)
        start = next(field for field in fields if field["key"] == "education.0.start_year")
        self.assertEqual(start["proposal"], "")
        result = self.fill_keys({"education.0.end_month", "education.0.end_year"}, bindings=bindings)
        self.assertTrue(all(item["status"] == "filled" for item in result), result)
        year, month = self.profile["values"]["education.0.end_date"]["value"].split("-")
        self.assertEqual(self.page.locator("#education-end-month-0").input_value(), str(int(month) - 1))
        self.assertEqual(self.page.locator("#education-end-year-0").input_value(), year)
        self.assertEqual(self.page.locator("#education-start-year-0").input_value(), "")
        self.assertEqual(self.page.locator("#education-school-1").input_value(), "")

    def test_ambiguous_month_options_do_not_get_a_proposal(self):
        self.page.locator("#next-one").click()
        bindings = self.history_bindings("education")
        self.page.evaluate("""month => {
          const select = document.getElementById('education-end-month-0');
          const option = select.options[Number(month)]; const clone = option.cloneNode(true); clone.value = 'duplicate'; select.append(clone);
        }""", self.profile["values"]["education.0.end_date"]["value"].split("-")[1])
        field = next(field for field in self.scan(bindings) if field["key"] == "education.0.end_month")
        self.assertEqual(field["proposal"], "")
        self.assertEqual(self.page.locator("#education-end-month-0").input_value(), "")

    def test_employment_split_date_components_preserve_axis_role_dates(self):
        self.page.locator("#next-one").click()
        self.page.evaluate("""() => {
          const row = document.getElementById('company-2').closest('fieldset');
          for (const [id, caption] of [['split-month','Start month'], ['split-year','Start year']]) {
            const label = document.createElement('label'); label.textContent = caption;
            const input = document.createElement('input'); input.type = 'number'; input.id = id; label.append(input); row.append(label);
          }
        }""")
        bindings = self.history_bindings("employment")
        result = self.fill_keys({"employment.2.start_month", "employment.2.start_year"}, bindings=bindings)
        self.assertTrue(all(item["status"] == "filled" for item in result), result)
        self.assertEqual(self.page.locator("#split-month").input_value(), "8")
        self.assertEqual(self.page.locator("#split-year").input_value(), "2023")

    def test_full_date_input_does_not_invent_a_day_from_month_fact(self):
        self.page.locator("#next-one").click()
        self.page.locator("#start-0").evaluate("node => node.type = 'date'")
        bindings = self.history_bindings("employment")
        result = self.fill_keys({"employment.0.start_date"}, bindings=bindings)
        self.assertEqual(result[0]["status"], "failed")
        self.assertEqual(self.page.locator("#start-0").input_value(), "")

    def test_panel_record_change_clears_old_edits_and_selections(self):
        self.page.locator("#next-one").click()
        self.page.locator("#scan").click()
        host = self.page.locator("#portal-panel-host")
        chooser = host.get_by_role("combobox", name="Profile record for Employment 1", exact=True)
        chooser.select_option("2")
        first_employer = host.get_by_role("textbox", name="Answer Employer", exact=True).first
        self.assertEqual(first_employer.input_value(), self.profile["values"]["employment.2.company"]["value"])
        first_employer.fill("Synthetic previous edit")
        host.get_by_role("checkbox", name="Select Employer", exact=True).first.check()
        host.get_by_role("checkbox", name="Replace existing Employer", exact=True).first.check()
        chooser = host.get_by_role("combobox", name="Profile record for Employment 1", exact=True)
        chooser.select_option("3")
        self.assertEqual(first_employer.input_value(), self.profile["values"]["employment.3.company"]["value"])
        self.assertFalse(host.get_by_role("checkbox", name="Select Employer", exact=True).first.is_checked())
        self.assertFalse(host.get_by_role("checkbox", name="Replace existing Employer", exact=True).first.is_checked())
        host.get_by_role("button", name="Close", exact=True).click()
        self.page.locator("#scan").click()
        self.assertEqual(host.get_by_role("combobox", name="Profile record for Employment 1", exact=True).input_value(), "")
        self.assertTrue(host.get_by_role("checkbox", name="Select Employer", exact=True).first.is_disabled())

    def test_concurrent_fill_and_rescan_are_rejected_but_inspection_is_allowed(self):
        fields = self.scan()
        first = next(field for field in fields if field["key"] == "first_name")
        last = next(field for field in fields if field["key"] == "last_name")
        result = self.page.evaluate("""async ({first, last, profile}) => {
          const running = PortalEngine.fill([{id:first.id, value:first.proposal}]);
          let scanError = '', fillError = '';
          try {PortalEngine.scan(profile);} catch(error) {scanError = error.message;}
          try {await PortalEngine.fill([{id:last.id, value:last.proposal}]);} catch(error) {fillError = error.message;}
          const report = PortalEngine.inspect();
          return {scanError, fillError, report, filled:await running};
        }""", {"first": first, "last": last, "profile": self.profile})
        self.assertIn("fill is running", result["scanError"])
        self.assertIn("already running", result["fillError"])
        self.assertTrue(result["report"]["fields"])
        self.assertEqual(result["filled"][0]["status"], "filled")
        self.assertEqual(self.page.locator("#last").input_value(), "")

    def test_upload_checksum_and_correct_file(self):
        self.page.locator("#next-one").click()
        field = next(field for field in self.scan() if field["label"] == "Resume")
        data = self.pipeline.resume(self.session["id"], for_upload=True)
        import base64
        attachment = {"name": "Yazad_Madan.docx", "base64": base64.b64encode(data).decode(),
                      "sha256": hashlib.sha256(data).hexdigest(), "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
        result = self.page.evaluate("async ({id, attachment}) => PortalEngine.fill([{id}], {attachment})", {"id": field["id"], "attachment": attachment})
        self.assertEqual(result[0]["status"], "filled", result)
        self.assertEqual(self.page.locator("#upload-state").text_content(), "Attached: Yazad_Madan.docx")
        self.page.locator("#resume").set_input_files([])
        attachment["sha256"] = "0" * 64
        result = self.page.evaluate("async ({id, attachment}) => PortalEngine.fill([{id}], {attachment})", {"id": field["id"], "attachment": attachment})
        self.assertEqual(result[0]["status"], "failed")
        self.assertEqual(self.page.locator("#resume").evaluate("node => node.files.length"), 0)

    def test_ambiguous_upload_is_not_assumed_to_be_resume(self):
        self.page.locator("#next-one").click()
        self.page.evaluate("document.querySelector('label:has(#resume)').firstChild.textContent = 'Supporting documents'")
        field = next(field for field in self.scan() if field["label"] == "Supporting documents")
        result = self.page.evaluate("async id => PortalEngine.fill([{id}], {attachment: {}})", field["id"])
        self.assertEqual(result[0]["status"], "failed")
        self.assertIn("explicitly identified resume field", result[0]["message"])
        self.assertEqual(self.page.locator("#resume").evaluate("node => node.files.length"), 0)

    def test_submission_attestation_and_signature_are_untouched(self):
        self.page.locator("#next-one").click()
        self.page.locator("#next-two").click()
        fields = self.scan()
        self.assertTrue(all(field["blocked"] for field in fields))
        result = self.page.evaluate("async fields => PortalEngine.fill(fields.map(field => ({id: field.id, value: 'Yes'})))", fields)
        self.assertTrue(all(item["status"] == "failed" for item in result))
        self.assertFalse(self.page.locator("#attestation").is_checked())
        self.assertEqual(self.page.locator("#signature").input_value(), "")
        self.assertEqual(self.page.locator("#submit-count").text_content(), "Submit clicks: 0")

    def test_exact_options_never_match_opposite_answer(self):
        result = self.page.evaluate("PortalEngine.optionMatch([{value:'1', label:'Not authorized'}, {value:'2', label:'Authorized with restrictions'}], 'Authorized')")
        self.assertIsNone(result)

    def test_changed_dropdown_options_cannot_use_cached_answers(self):
        field = next(field for field in self.scan() if field["key"] == "sponsorship_future")
        self.page.evaluate("document.querySelector('#future option[value=\"1\"]').textContent = 'No'")
        result = self.page.evaluate("async selection => PortalEngine.fill([selection])", {"id": field["id"], "value": field["proposal"]})
        self.assertEqual(result[0]["status"], "failed")
        self.assertIn("identity changed", result[0]["message"])
        self.assertEqual(self.page.locator("#future").input_value(), "")

    def test_native_radio_group_matches_exact_answer(self):
        self.page.evaluate("""() => {
          const group = document.createElement('fieldset');
          group.innerHTML = '<legend>Do you require sponsorship now?</legend><label><input type="radio" name="radio-sponsorship" value="yes">Yes</label><label><input type="radio" name="radio-sponsorship" value="no">No</label>';
          document.querySelector('main').append(group);
        }""")
        field = next(field for field in self.scan() if field["type"] == "radio")
        result = self.page.evaluate("async selection => PortalEngine.fill([selection])", {"id": field["id"], "value": field["proposal"]})
        self.assertEqual(result[0]["status"], "filled", result)
        self.assertTrue(self.page.locator('input[name="radio-sponsorship"][value="no"]').is_checked())
        self.assertFalse(self.page.locator('input[name="radio-sponsorship"][value="yes"]').is_checked())

    def custom_selection(self, answer="Yes"):
        field = next(field for field in self.scan() if field["type"] == "combobox" and field["label"] == "Are you willing to relocate?")
        return {"id": field["id"], "value": answer}

    def custom_fill(self, answer="Yes", overwrite=False):
        selected = self.custom_selection(answer)
        selected["overwrite"] = overwrite
        return self.page.evaluate("async selection => PortalEngine.fill([selection])", selected)

    def test_custom_dropdown_scan_does_not_open_or_change_it(self):
        field = next(field for field in self.scan() if field["type"] == "combobox")
        self.assertEqual(field["adapter"], "aria-listbox")
        self.assertEqual([option["label"] for option in field["options"]], ["Yes", "No"])
        self.assertEqual(self.page.locator("#custom-relocation").get_attribute("aria-expanded"), "false")
        self.assertEqual(self.page.locator("#custom-relocation").get_attribute("aria-valuetext"), "")

    def test_custom_dropdown_fills_exact_option_and_preserves_other_fields(self):
        result = self.custom_fill("Yes")
        self.assertEqual(result[0]["status"], "filled", result)
        self.assertEqual(self.page.locator("#custom-relocation").get_attribute("aria-valuetext"), "Yes")
        self.assertEqual(self.page.locator("#custom-relocation").get_attribute("aria-expanded"), "false")
        self.assertEqual(self.page.locator("#future").input_value(), "")
        self.assertEqual(self.page.locator("#progress").text_content(), "Step 1 of 3")

    def test_custom_dropdown_preserves_existing_answer_until_explicit_overwrite(self):
        self.page.locator("#custom-relocation").click()
        self.page.locator("#relocation-options").get_by_role("option", name="No", exact=True).click()
        self.assertEqual(self.custom_fill("Yes")[0]["status"], "preserved")
        self.assertEqual(self.page.locator("#custom-relocation").get_attribute("aria-valuetext"), "No")
        self.assertEqual(self.custom_fill("Yes", overwrite=True)[0]["status"], "filled")

    def test_custom_dropdown_does_not_match_substrings(self):
        self.page.evaluate("""() => {
          const options = document.querySelectorAll('#relocation-options [role=option]');
          options[0].textContent = 'Not authorized'; options[1].textContent = 'Authorized with restrictions';
        }""")
        result = self.custom_fill("Authorized")
        self.assertEqual(result[0]["status"], "failed")
        self.assertIn("unique exact", result[0]["message"])
        self.assertEqual(self.page.locator("#custom-relocation").get_attribute("aria-valuetext"), "")

    def test_custom_dropdown_duplicate_or_disabled_options_require_manual_answer(self):
        self.page.evaluate("""() => {
          const options = document.querySelectorAll('#relocation-options [role=option]');
          options[1].textContent = 'Yes';
        }""")
        self.assertEqual(self.custom_fill("Yes")[0]["status"], "failed")
        self.page.evaluate("""() => {
          const options = document.querySelectorAll('#relocation-options [role=option]');
          options[1].textContent = 'No'; options[0].setAttribute('aria-disabled', 'true');
        }""")
        self.assertEqual(self.custom_fill("Yes")[0]["status"], "failed")
        self.assertEqual(self.page.locator("#custom-relocation").get_attribute("aria-valuetext"), "")

    def test_custom_dropdown_changed_ownership_rejects_cached_selection(self):
        selection = self.custom_selection()
        self.page.evaluate("document.getElementById('custom-relocation').setAttribute('aria-controls', 'unrelated-popup')")
        result = self.page.evaluate("async selection => PortalEngine.fill([selection])", selection)
        self.assertEqual(result[0]["status"], "failed")
        self.assertIn("identity changed", result[0]["message"])
        self.assertEqual(self.page.locator("#custom-relocation").get_attribute("aria-expanded"), "false")

    def test_custom_dropdown_submit_control_and_submit_option_are_never_clicked(self):
        self.page.evaluate("""() => {
          const original = document.getElementById('custom-relocation');
          const submit = document.createElement('button');
          [...original.attributes].forEach(attribute => submit.setAttribute(attribute.name, attribute.value));
          submit.type = 'submit'; submit.textContent = original.textContent;
          window.disallowedClicks = 0; submit.onclick = () => window.disallowedClicks++;
          original.replaceWith(submit);
        }""")
        self.assertEqual(self.custom_fill()[0]["status"], "failed")
        self.assertEqual(self.page.evaluate("window.disallowedClicks"), 0)
        self.page.goto(self.url + "/fixture")
        self.page.evaluate("""() => {
          const original = document.querySelector('#relocation-options [role=option]');
          const submit = document.createElement('button'); submit.type = 'submit'; submit.setAttribute('role', 'option'); submit.textContent = 'Yes';
          window.disallowedClicks = 0; submit.onclick = () => window.disallowedClicks++;
          original.replaceWith(submit);
        }""")
        self.assertEqual(self.custom_fill()[0]["status"], "failed")
        self.assertEqual(self.page.evaluate("window.disallowedClicks"), 0)

    def test_custom_dropdown_collateral_change_on_open_stops_before_option_click(self):
        self.page.evaluate("document.getElementById('custom-relocation').addEventListener('click', () => {document.getElementById('last').value = 'Unexpected change';})")
        fields = self.scan()
        selected = [{"id": field["id"], "value": "Yes"} for field in fields if field["type"] == "combobox"]
        selected += [{"id": field["id"], "value": field["proposal"]} for field in fields if field["key"] == "sponsorship_future"]
        result = self.page.evaluate("async selected => PortalEngine.fill(selected)", selected)
        self.assertTrue(all(item["status"] == "failed" for item in result), result)
        self.assertIn("unselected field changed", result[0]["message"])
        self.assertEqual(self.page.locator("#custom-relocation").get_attribute("aria-valuetext"), "")
        self.assertEqual(self.page.locator("#future").input_value(), "")

    def test_custom_dropdown_option_changes_while_opening_stop_selection(self):
        self.page.evaluate("document.getElementById('custom-relocation').addEventListener('click', () => {document.querySelector('#relocation-options [role=option]').textContent = 'Changed';})")
        result = self.custom_fill()
        self.assertEqual(result[0]["status"], "failed")
        self.assertIn("options changed while opening", result[0]["message"])
        self.assertEqual(self.page.locator("#custom-relocation").get_attribute("aria-valuetext"), "")

    def test_custom_dropdown_question_change_while_opening_stops_selection(self):
        self.page.evaluate("document.getElementById('custom-relocation').addEventListener('click', () => {document.getElementById('custom-relocation-label').textContent = 'A different question';})")
        result = self.custom_fill()
        self.assertEqual(result[0]["status"], "failed")
        self.assertIn("question changed while opening", result[0]["message"])
        self.assertEqual(self.page.locator("#custom-relocation").get_attribute("aria-valuetext"), "")

    def test_custom_dropdown_option_inside_submit_button_is_not_clicked(self):
        self.page.evaluate("""() => {
          const option = document.querySelector('#relocation-options [role=option]');
          const submit = document.createElement('button'); submit.type = 'submit';
          option.before(submit); submit.append(option);
          window.disallowedClicks = 0; submit.onclick = () => window.disallowedClicks++;
        }""")
        self.assertEqual(self.custom_fill()[0]["status"], "failed")
        self.assertEqual(self.page.evaluate("window.disallowedClicks"), 0)

    def test_custom_dropdown_lazy_listbox_loads_only_after_selected_fill(self):
        self.page.evaluate("""() => {
          const popup = document.getElementById('relocation-options'), combo = document.getElementById('custom-relocation');
          popup.remove();
          combo.onclick = () => setTimeout(() => {document.body.append(popup); popup.hidden = false; combo.setAttribute('aria-expanded', 'true');}, 100);
        }""")
        self.assertEqual(self.custom_fill()[0]["status"], "filled")
        self.assertEqual(self.page.locator("#custom-relocation").get_attribute("aria-valuetext"), "Yes")

    def test_custom_dropdown_reverted_value_is_reported(self):
        self.page.evaluate("document.querySelector('#relocation-options [role=option]').addEventListener('click', () => {document.getElementById('custom-relocation').setAttribute('aria-valuetext', '');})")
        result = self.custom_fill()
        self.assertEqual(result[0]["status"], "failed")
        self.assertIn("did not retain", result[0]["message"])

    def test_custom_dropdown_distinguishes_punctuation_in_option_labels(self):
        self.page.evaluate("""() => {
          const options = document.querySelectorAll('#relocation-options [role=option]');
          options[0].textContent = 'C++'; options[1].textContent = 'C#';
        }""")
        result = self.custom_fill("C++")
        self.assertEqual(result[0]["status"], "filled", result)
        self.assertEqual(self.page.locator("#custom-relocation").get_attribute("aria-valuetext"), "C++")

    def test_option_matching_distinguishes_negative_codes_and_punctuation(self):
        option = self.page.evaluate("PortalEngine.optionMatch([{value:'-1',label:'Negative'}, {value:'1',label:'Positive'}], '-1')")
        self.assertEqual(option["label"], "Negative")
        option = self.page.evaluate("PortalEngine.optionMatch([{value:'cpp',label:'C++'}, {value:'cs',label:'C#'}], 'C++')")
        self.assertEqual(option["label"], "C++")

    def test_password_with_misleading_combobox_role_stays_protected(self):
        self.page.evaluate("""() => {
          const password = document.getElementById('password');
          password.value = 'Must stay private'; password.setAttribute('role', 'combobox');
          password.id = 'ordinary-looking'; password.name = 'ordinary-looking';
          password.closest('label').firstChild.textContent = 'First name';
        }""")
        fields = self.scan()
        field = next(field for field in fields if field["structure"]["dom_id"] == "ordinary-looking")
        self.assertTrue(field["blocked"])
        self.assertEqual(field["current"], "")
        self.assertNotIn("ordinary-looking", json.dumps(self.page.evaluate("PortalEngine.inspect()")))

    def test_unowned_editable_custom_dropdown_stays_manual(self):
        self.page.locator("#next-one").click()
        field = next(field for field in self.scan() if field["label"] == "Custom department dropdown")
        self.assertIsNone(field["adapter"])
        result = self.page.evaluate("async id => PortalEngine.fill([{id, value: 'Finance'}])", field["id"])
        self.assertEqual(result[0]["status"], "failed")
        self.assertEqual(self.page.locator("#custom").input_value(), "")
        self.assertEqual(self.page.locator("#progress").text_content(), "Step 2 of 3")

    def test_structure_inspection_omits_answers_and_does_not_invalidate_review(self):
        self.page.locator("#first").fill("Private existing answer")
        self.page.locator("#password").fill("Private-password-value")
        self.page.evaluate("history.replaceState(null, '', '/fixture?token=private-query')")
        fields = self.scan()
        report = self.page.evaluate("PortalEngine.inspect()")
        raw = json.dumps(report)
        for excluded in ["Private existing answer", "Private-password-value", "private-query", "proposal", "current", "Password", "Gender"]:
            self.assertNotIn(excluded, raw)
        self.assertGreaterEqual(report["protected_fields_omitted"], 2)
        field = next(field for field in fields if field["key"] == "last_name")
        result = self.page.evaluate("async selection => PortalEngine.fill([selection])", {"id": field["id"], "value": field["proposal"]})
        self.assertEqual(result[0]["status"], "filled", result)
        self.assertEqual(self.page.locator("#first").input_value(), "Private existing answer")

    def test_panel_exports_structure_without_writing_fields(self):
        self.page.locator("#scan").click()
        host = self.page.locator("#portal-panel-host")
        with self.page.expect_download() as download_info:
            host.get_by_role("button", name="Export field structure", exact=True).click()
        report = json.loads(Path(download_info.value.path()).read_text(encoding="utf-8"))
        self.assertEqual(report["schema_version"], 1)
        self.assertTrue(any(field["adapter"] == "aria-listbox" for field in report["fields"]))
        self.assertEqual(self.page.locator("#first").input_value(), "")

    def test_panel_selection_edits_and_restore(self):
        self.page.locator("#scan").click()
        host = self.page.locator("#portal-panel-host")
        host.get_by_role("checkbox", name="Select First name", exact=True).check()
        host.get_by_role("textbox", name="Answer First name", exact=True).fill("Synthetic edited name")
        host.get_by_role("checkbox", name="This page belongs to the selected posting", exact=True).check()
        host.get_by_role("button", name="Fill selected fields").click()
        self.page.wait_for_function("document.getElementById('first').value === 'Synthetic edited name'")
        self.assertEqual(self.page.locator("#email").input_value(), "")
        host.get_by_role("button", name="Close", exact=True).click()
        self.page.locator("#scan").click()
        self.assertTrue(host.get_by_role("checkbox", name="Select First name", exact=True).is_checked())
        self.assertEqual(host.get_by_role("textbox", name="Answer First name", exact=True).input_value(), "Synthetic edited name")

    def test_dashboard_builds_working_copy_and_requires_visual_review(self):
        self.page.goto(self.url)
        self.page.wait_for_function("document.getElementById('status').textContent.startsWith('Ready.')")
        self.page.get_by_text("Develop with a sandbox application", exact=True).click()
        self.page.get_by_role("button", name="Try sample application").click()
        self.page.wait_for_function("document.getElementById('status').textContent.startsWith('Working application created.')")
        self.page.locator("#requirements-reviewed").check()
        self.page.locator("#content-reviewed").check()
        self.page.locator("#terms").fill("Python\nSQL")
        self.page.get_by_role("button", name="Build working resume").click()
        self.page.wait_for_function("document.getElementById('status').textContent.startsWith('Working resume built.')")
        self.page.get_by_role("button", name="Enable this resume for attachment").click()
        self.page.wait_for_function("document.getElementById('status').textContent.includes('review the document in Word')")
        self.page.locator("#visual-reviewed").check()
        self.page.get_by_role("button", name="Enable this resume for attachment").click()
        self.page.wait_for_function("document.getElementById('status').textContent.includes('enabled for attachment')")
        self.assertTrue(self.pipeline.current()["upload_reviewed"])
        self.page.locator("#terms").fill("Python")
        self.assertTrue(self.page.locator("#approve").is_disabled())
        self.assertFalse(self.page.locator("#visual-reviewed").is_checked())

    def test_dashboard_imports_audited_application_without_build_editor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, application = audited_fixture(root, self.pipeline.folder(self.session["id"]), SOURCE)
            pipeline = Pipeline(source, root / "sandbox")
            server = make_server(pipeline, 0, "import-browser-token")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                self.page.goto(f"http://127.0.0.1:{server.server_port}")
                self.page.wait_for_function("document.getElementById('status').textContent.startsWith('Ready.')")
                self.page.locator("#import-form input[name=folder]").fill(str(application))
                self.page.locator("#import-form input[name=portal_url]").fill("https://another.myworkdayjobs.com/job/900001")
                self.page.get_by_role("button", name="Import audited application", exact=True).click()
                self.page.wait_for_function("document.getElementById('status').textContent.startsWith('Audited resume imported.')")
                self.assertTrue(self.page.locator("#build-editor").is_hidden())
                self.assertIn("900001", self.page.locator("#context").text_content())
                self.assertIn("PASS - no blocking issues", self.page.locator("#audit-report").text_content())
                self.page.locator("#visual-reviewed").check()
                self.page.get_by_role("button", name="Enable this resume for attachment").click()
                self.page.wait_for_function("document.getElementById('status').textContent.includes('enabled for attachment')")
                self.assertTrue(pipeline.current()["upload_reviewed"])
                self.assertTrue(pipeline.resume(pipeline.current()["id"], for_upload=True))
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_real_extension_inspects_pages_without_pairing_or_candidate_data(self):
        with tempfile.TemporaryDirectory() as browser_profile:
            extension = Path(browser_profile) / "extension"
            shutil.copytree(HERE / "extension", extension)
            manifest_path = extension / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            # Opening popup.html in a test tab does not grant activeTab. Give only
            # routed synthetic hosts test permissions; production stays unchanged.
            manifest["host_permissions"] += ["https://inspection-fixture.myworkdayjobs.com/*", "https://job-boards.greenhouse.io/*", "https://jobs.lever.co/*"]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            context = self.playwright.chromium.launch_persistent_context(str(Path(browser_profile) / "profile"), channel="chromium", headless=True,
                args=[f"--disable-extensions-except={extension}", f"--load-extension={extension}"])
            try:
                workers = context.service_workers
                worker = workers[0] if workers else context.wait_for_event("serviceworker")
                extension_id = worker.url.split("/")[2]
                # A routed synthetic Workday host exercises the real extension,
                # without accessing an employer or claiming live compatibility.
                target_url = "https://inspection-fixture.myworkdayjobs.com/application"
                context.route(target_url, lambda route: route.fulfill(content_type="text/html", body='''
                  <label>First name<input id="first" value="PRIVATE EXISTING ANSWER"></label>
                  <label>Password<input type="password" value="PRIVATE PASSWORD"></label>
                  <button type="button" id="next">Next</button>
                  <script>document.getElementById('next').onclick = () => {
                    document.body.innerHTML = '<fieldset data-portal-section="employment"><legend>Employment 1</legend><label>Employer<input id="employer"></label></fieldset><button id="review">Review</button>';
                    document.getElementById('review').onclick = () => {document.body.innerHTML = '<label>Signature<input id="signature"></label><button id="submit">Submit</button>';};
                  };</script>'''))
                requests = []
                context.on("request", lambda request: requests.append(request.url))
                page = context.new_page()
                page.goto(target_url)
                popup = context.new_page()
                popup.goto(f"chrome-extension://{extension_id}/popup.html")
                self.assertEqual(popup.evaluate("async () => await chrome.storage.local.get(null)"), {})
                tab_id = popup.evaluate("async () => (await chrome.tabs.query({})).find(tab => tab.url?.includes('inspection-fixture')).id")
                page.bring_to_front()
                with popup.expect_event("close", timeout=10000):
                    popup.locator("#inspect").click()
                review = context.new_page()
                review.goto(f"chrome-extension://{extension_id}/review.html?tab={tab_id}&mode=inspect")
                host = review.locator("#portal-panel-host")
                host.get_by_role("heading", name="First name", exact=True).wait_for()
                self.assertEqual(host.get_by_role("button", name="Fill selected fields").count(), 0)
                self.assertNotIn("PRIVATE", host.locator(".panel").inner_text())
                self.assertEqual(page.locator("#first").input_value(), "PRIVATE EXISTING ANSWER")
                for command_type in ["portal-scan", "portal-fill"]:
                    rejected = review.evaluate("async ({tabId, type}) => await chrome.tabs.sendMessage(tabId, {type, profile: {values: {}}, selections: []})",
                                               {"tabId": tab_id, "type": command_type})
                    self.assertFalse(rejected["ok"])
                    self.assertIn("Inspection mode", rejected["error"])
                for expected, navigation in [("First name", "#next"), ("Employer", "#review"), (None, None)]:
                    with review.expect_download() as download_info:
                        host.get_by_role("button", name="Export field structure", exact=True).click()
                    report = json.loads(Path(download_info.value.path()).read_text(encoding="utf-8"))
                    self.assertEqual(report["host"], "inspection-fixture.myworkdayjobs.com")
                    self.assertNotIn("PRIVATE", json.dumps(report))
                    if expected:
                        self.assertEqual(report["fields"][0]["label"], expected)
                    else:
                        self.assertEqual(report["fields"], [])
                        self.assertEqual(report["protected_fields_omitted"], 1)
                        self.assertIn("No application fields found", host.locator(".panel").inner_text())
                    if navigation:
                        page.locator(navigation).click()
                        review.locator("#rescan").click()
                        host.get_by_role("heading", name="Inspect application fields", exact=True).wait_for()
                        if navigation == "#next":
                            host.get_by_role("heading", name="Employer", exact=True).wait_for()
                        else:
                            host.get_by_text("No application fields found", exact=False).wait_for()
                self.assertEqual(page.locator("#signature").input_value(), "")
                self.assertFalse(any("/api/" in url for url in requests))
                self.assertEqual(review.evaluate("async () => await chrome.storage.local.get(null)"), {})
                greenhouse_url = "https://job-boards.greenhouse.io/synthetic/jobs/123"
                context.route(greenhouse_url, lambda route: route.fulfill(content_type="text/html", body=(HERE / "fixtures/greenhouse.html").read_text(encoding="utf-8")))
                page.goto(greenhouse_url)
                popup = context.new_page()
                popup.goto(f"chrome-extension://{extension_id}/popup.html")
                page.bring_to_front()
                with popup.expect_event("close", timeout=10000):
                    popup.locator("#inspect").click()
                review.reload()
                host.get_by_role("heading", name="Resume/CV", exact=True).wait_for()
                with review.expect_download() as download_info:
                    host.get_by_role("button", name="Export field structure", exact=True).click()
                report = json.loads(Path(download_info.value.path()).read_text(encoding="utf-8"))
                self.assertEqual(report["portal"], "greenhouse")
                self.assertTrue(any(field["structure"]["dom_id"] == "resume" for field in report["fields"]))
                self.assertFalse(any(field["structure"]["dom_id"] in {"newsletter", "required-shadow", "transgender", "survey-education"} for field in report["fields"]))
                self.assertEqual(page.locator("#resume").evaluate("node => node.files.length"), 0)
                self.assertFalse(any("/api/" in url for url in requests))
                # Other portal families remain outside this first-portal run.
                context.route("https://jobs.lever.co/fixture", lambda route: route.fulfill(body="Other portal"))
                page.goto("https://jobs.lever.co/fixture")
                popup = context.new_page()
                popup.goto(f"chrome-extension://{extension_id}/popup.html")
                page.bring_to_front()
                popup.locator("#inspect").click()
                popup.wait_for_function("document.getElementById('status').textContent.includes('limited to Workday')")
                self.assertFalse(page.evaluate("Boolean(globalThis.PortalEngine)"))
            finally:
                context.close()

    def greenhouse_fixture(self):
        url = "https://job-boards.greenhouse.io/synthetic/jobs/123"
        self.page.route(url, lambda route: route.fulfill(content_type="text/html", body=(HERE / "fixtures/greenhouse.html").read_text(encoding="utf-8")))
        self.page.goto(url)
        for name in ["adapters/aria-listbox.js", "adapters/greenhouse.js", "engine.js"]:
            self.page.add_script_tag(path=str(HERE / "extension" / name))

    def test_greenhouse_scopes_application_and_excludes_internal_and_survey_controls(self):
        self.greenhouse_fixture()
        fields = self.scan()
        ids = {field["structure"]["dom_id"] for field in fields}
        self.assertNotIn("newsletter", ids)
        self.assertNotIn("required-shadow", ids)
        for identifier in ["transgender", "survey-education"]:
            field = next(field for field in fields if field["structure"]["dom_id"] == identifier)
            self.assertTrue(field["blocked"])
            self.assertEqual(field["proposal"], "")
        report = self.page.evaluate("PortalEngine.inspect()")
        self.assertEqual(report["portal"], "greenhouse")
        self.assertNotIn("transgender", json.dumps(report))
        self.assertEqual(self.page.locator("#required-shadow").input_value(), "KEEP SHADOW")

    def test_greenhouse_selected_native_fields_and_hidden_reviewed_resume(self):
        self.greenhouse_fixture()
        fields = self.scan()
        resume = next(field for field in fields if field["structure"]["dom_id"] == "resume")
        self.assertEqual(resume["label"], "Resume/CV")
        self.assertTrue(resume["required"])
        attachment = self.pipeline.resume(self.session["id"], for_upload=True)
        import base64
        selected = [{"id": field["id"], "value": field["proposal"]} for field in fields if field["key"] in {"first_name", "email", "phone"}]
        selected.append({"id": resume["id"], "value": "Yazad_Madan.docx"})
        result = self.page.evaluate("async ({selections, attachment}) => PortalEngine.fill(selections, {attachment})", {
            "selections": selected, "attachment": {"name": "Yazad_Madan.docx", "base64": base64.b64encode(attachment).decode(),
                "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "sha256": hashlib.sha256(attachment).hexdigest()}})
        self.assertEqual([entry["status"] for entry in result], ["filled", "filled", "preserved", "filled"])
        self.assertEqual(self.page.locator("#last_name").input_value(), "")
        self.assertEqual(self.page.locator("#phone").input_value(), "KEEP PHONE")
        self.assertEqual(self.page.locator("#resume").evaluate("node => node.files[0].name"), "Yazad_Madan.docx")
        self.assertEqual(self.page.locator("#cover_letter").evaluate("node => node.files.length"), 0)
        self.assertEqual(self.page.evaluate("submitAttempts"), 0)
        self.assertIn("completion indicator", result[-1]["message"])

    def test_greenhouse_editable_dropdowns_and_compound_sponsorship_stay_manual(self):
        self.greenhouse_fixture()
        fields = self.scan()
        country = next(field for field in fields if field["structure"]["dom_id"] == "country")
        self.assertIsNone(country["adapter"])
        self.assertTrue(country["manual_reason"])
        compound = next(field for field in fields if field["structure"]["dom_id"] == "compound")
        self.assertIsNone(compound["key"])
        self.assertEqual(compound["proposal"], "")
        result = self.page.evaluate("async selection => PortalEngine.fill([selection])", {"id": country["id"], "value": "United States"})
        self.assertEqual(result[0]["status"], "failed")
        self.assertEqual(self.page.locator("#country").input_value(), "")

    def test_greenhouse_reparented_field_and_demographic_move_block_stale_fill(self):
        self.greenhouse_fixture()
        first = next(field for field in self.scan() if field["key"] == "first_name")
        self.page.evaluate("document.body.append(document.getElementById('first_name'))")
        result = self.page.evaluate("async selection => PortalEngine.fill([selection])", {"id": first["id"], "value": "Synthetic"})
        self.assertEqual(result[0]["status"], "failed")
        self.assertEqual(self.page.locator("#first_name").input_value(), "")
        self.page.evaluate("document.getElementById('application-form').append(document.getElementById('first_name'))")
        first = next(field for field in self.scan() if field["key"] == "first_name")
        self.page.evaluate("document.getElementById('demographic-section').append(document.getElementById('first_name'))")
        result = self.page.evaluate("async selection => PortalEngine.fill([selection])", {"id": first["id"], "value": "Synthetic"})
        self.assertEqual(result[0]["status"], "failed")
        self.assertEqual(self.page.locator("#first_name").input_value(), "")

    def test_greenhouse_changed_upload_label_and_duplicate_form_require_manual_review(self):
        self.greenhouse_fixture()
        resume = next(field for field in self.scan() if field["structure"]["dom_id"] == "resume")
        self.page.locator("#upload-label-resume").evaluate("node => node.textContent = 'Proof of identity'")
        result = self.page.evaluate("async selection => PortalEngine.fill([selection])", {"id": resume["id"], "value": "Yazad_Madan.docx"})
        self.assertEqual(result[0]["status"], "failed")
        self.assertEqual(self.page.locator("#resume").evaluate("node => node.files.length"), 0)
        self.page.evaluate("const duplicate=document.createElement('form');duplicate.id='application-form';document.body.append(duplicate)")
        self.assertEqual(self.scan(), [])
        self.assertIn("unique supported", self.page.evaluate("PortalEngine.inspect().portal_manual_reason"))

    def test_real_extension_pairs_and_injects_on_user_action(self):
        with tempfile.TemporaryDirectory() as browser_profile:
            extension = HERE / "extension"
            context = self.playwright.chromium.launch_persistent_context(browser_profile, channel="chromium", headless=True,
                args=[f"--disable-extensions-except={extension}", f"--load-extension={extension}"], viewport={"width": 1440, "height": 1050})
            try:
                workers = context.service_workers
                worker = workers[0] if workers else context.wait_for_event("serviceworker")
                extension_id = worker.url.split("/")[2]
                page = context.new_page()
                page.goto(self.url + "/fixture")
                self.assertEqual(page.locator("#portal-panel-host").count(), 0)
                popup = context.new_page()
                popup.goto(f"chrome-extension://{extension_id}/popup.html")
                popup.locator("#server").fill(self.url)
                popup.locator("#token").fill("browser-test-token")
                popup.locator("#pair").click()
                popup.wait_for_function("document.getElementById('status').textContent.startsWith('Paired.')")
                # Test the actual extension-owned review page and page messaging bridge.
                tab_id = popup.evaluate("async () => (await chrome.tabs.query({})).find(tab => tab.url?.includes('/fixture')).id")
                page.bring_to_front()
                with popup.expect_event("close", timeout=10000):
                    popup.locator("#scan").click()
                self.assertTrue(page.evaluate("Boolean(globalThis.PortalEngine)"))
                review = context.new_page()
                review.goto(f"chrome-extension://{extension_id}/review.html?tab={tab_id}")
                host = review.locator("#portal-panel-host")
                host.get_by_role("checkbox", name="Select Last name", exact=True).check()
                host.get_by_role("checkbox", name="Select Are you willing to relocate?", exact=True).check()
                host.get_by_role("combobox", name="Answer Are you willing to relocate?", exact=True).select_option(label="Yes")
                host.get_by_role("checkbox", name="This page belongs to the selected posting", exact=True).check()
                host.get_by_role("button", name="Fill selected fields").click()
                page.wait_for_function("document.getElementById('last').value.length > 0")
                self.assertEqual(page.locator("#first").input_value(), "")
                page.wait_for_function("document.getElementById('custom-relocation').getAttribute('aria-valuetext') === 'Yes'")
                self.assertEqual(page.locator("#portal-panel-host").count(), 0)
                with review.expect_download() as download_info:
                    host.get_by_role("button", name="Export field structure", exact=True).click()
                report = json.loads(Path(download_info.value.path()).read_text(encoding="utf-8"))
                self.assertTrue(any(field["adapter"] == "aria-listbox" for field in report["fields"]))
                page.locator("#next-one").click()
                review.locator("#rescan").click()
                host.get_by_role("combobox", name="Profile record for Employment 1", exact=True).select_option("2")
                host.get_by_role("checkbox", name="Select Employer", exact=True).first.check()
                host.get_by_role("combobox", name="Profile record for Education 1", exact=True).select_option("0")
                host.get_by_role("checkbox", name="Select Graduation month", exact=True).first.check()
                host.get_by_role("checkbox", name="Select Graduation year", exact=True).first.check()
                host.get_by_role("checkbox", name="This page belongs to the selected posting", exact=True).check()
                host.get_by_role("button", name="Fill selected fields").click()
                page.wait_for_function("document.getElementById('education-end-year-0').value.length === 4")
                self.assertEqual(page.locator("#company-0").input_value(), self.profile["values"]["employment.2.company"]["value"])
                self.assertEqual(page.locator("#company-1").input_value(), "")
                self.assertEqual(page.locator("#education-start-year-0").input_value(), "")
                self.assertEqual(page.locator("#progress").text_content(), "Step 2 of 3")
            finally:
                context.close()


if __name__ == "__main__":
    unittest.main()
