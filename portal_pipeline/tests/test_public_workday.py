"""Workday adapter checks against fabricated pages only."""
import sys
import unittest

from browser_test_support import HERE
from replay_support import PAGES, ReplayBrowserTest


WORKDAY_SCRIPT = HERE / "extension" / "adapters" / "workday.js"
PROGRESS_SCRIPT = HERE / "extension" / "progress.js"
PAGE = PAGES / "workday" / "page_1.html"
URL = "https://synthetic.myworkdayjobs.com/synthetic/apply"
sys.path.insert(0, str(HERE))
import answer_sheet


class PublicWorkdayTests(ReplayBrowserTest):
    def open_page(self, markup=None):
        self.open_markup(markup if markup is not None else PAGE.read_text(encoding="utf-8"), URL)
        self.page.add_script_tag(path=str(WORKDAY_SCRIPT))
        self.page.add_script_tag(path=str(PROGRESS_SCRIPT))
        self.page.evaluate("globalThis.anyClicks = 0; document.addEventListener('click', () => anyClicks++, true)")

    def adapter(self, expression):
        return self.page.evaluate("() => { const a = PortalAdapters.forLocation(location.href); return " + expression + "; }")

    def field(self, key):
        return next(item for item in self.scan() if item["key"] == key)

    def test_workday_routes_to_adapter(self):
        self.open_page()
        self.assertEqual(self.adapter("a.id"), "workday")
        self.assertEqual(self.adapter("a.mode"), "fill")
        self.assertEqual(self.page.evaluate("PortalAdapters.forLocation('https://synthetic.myworkdaysite.com/').id"), "generic")

    def test_workday_scan_is_read_only(self):
        self.open_page()
        self.page.evaluate("globalThis.events = 0; ['input','change','focus','click'].forEach(name => document.addEventListener(name, () => events++, true))")
        before = self.page.evaluate("document.body.innerHTML")
        self.assertTrue(self.adapter("a.scan({values:{}}, {register:false}).length > 0"))
        self.adapter("a.nextStep(); a.detectFinalReview(); a.humanGate(document)")
        self.assertEqual(self.page.evaluate("document.body.innerHTML"), before)
        self.assertEqual(self.page.evaluate("events"), 0)

    def test_workday_selected_only_fill(self):
        self.open_page()
        first = self.field("first_name")
        self.assertEqual(self.fill([{"id": first["id"], "value": "Synthetic"}])[0]["status"], "filled")
        self.assertEqual(self.page.locator("#first").input_value(), "Synthetic")
        self.assertEqual(self.page.locator("#last").input_value(), "")
        self.assertEqual(self.page.locator("#email").input_value(), "")

    def test_workday_overwrite_off_preserves(self):
        self.open_page()
        self.page.evaluate("document.querySelector('#first').value = 'Existing'")
        first = self.field("first_name")
        self.assertNotEqual(self.fill([{"id": first["id"], "value": "Synthetic"}])[0]["status"], "filled")
        self.assertEqual(self.page.locator("#first").input_value(), "Existing")

    def test_workday_human_gate_blocks(self):
        markup = PAGE.read_text(encoding="utf-8").replace("<form>", '<form><div class="cf-turnstile" style="width:120px;height:50px"></div>')
        self.open_page(markup)
        self.assertEqual(self.adapter("a.humanGate(document).kind"), "captcha")
        first = self.field("first_name")
        self.assertEqual(self.fill([{"id": first["id"], "value": "Synthetic"}])[0]["status"], "blocked_by_human_gate")
        self.assertEqual(self.page.locator("#first").input_value(), "")

    def test_workday_final_review_detected(self):
        self.open_page('<h1>Review</h1><form><button type="submit">Submit</button></form>')
        self.assertTrue(self.adapter("a.detectFinalReview().final"))
        self.assertNotEqual(self.adapter("a.nextStep().kind"), "next")

    def test_workday_submit_counter_zero(self):
        self.open_page()
        self.fill([{"id": self.field("first_name")["id"], "value": "Synthetic"}])
        self.adapter("a.nextStep(); a.detectFinalReview()")
        self.assertEqual(self.page.evaluate("[syntheticSubmitClicks, syntheticSubmitEvents, anyClicks]"), [0, 0, 0])

    def test_workday_answer_sheet_mode_writes_nothing(self):
        self.open_page()
        before = self.page.evaluate("document.body.innerHTML")
        fields = self.adapter("a.scan({values:{}}, {register:false})")
        sheet = answer_sheet.build_answer_sheet(
            {"company": "Synthetic Co", "role": "Synthetic Role", "resume_path": "synthetic.docx"},
            fields, url=URL, heading="Synthetic Workday application", now="2026-10-05T12:00:00+00:00")
        self.assertEqual(sheet["portal"], "workday")
        self.assertEqual(sheet["mode"], "answer_sheet_only")
        self.assertEqual(self.page.evaluate("document.body.innerHTML"), before)
        self.assertEqual(self.page.evaluate("anyClicks"), 0)

    def test_workday_hidden_block_required_found_by_sweep(self):
        self.open_page('<h1>Personal Information</h1><form><label>First name<input id="first" required></label>'
                       '<section id="hidden" hidden><label>Last name<input id="last" required></label></section></form>')
        self.page.evaluate("setTimeout(() => { document.querySelector('#hidden').hidden = false; }, 60)")
        sweep = self.page.evaluate("async () => PortalProgress.requiredSweep(PortalAdapters.forLocation(location.href))")
        self.assertEqual({item["label"] for item in sweep["missing"]}, {"First name", "Last name"})

    def test_workday_yes_no_order_reversed_still_matches(self):
        self.open_page('<form><label>Do you require sponsorship now?<select id="now">'
                       '<option value="">Select</option><option value="n">No</option><option value="y">Yes</option>'
                       '</select></label></form>')
        field = self.field("sponsorship_now")
        self.assertEqual(self.fill([{"id": field["id"], "value": "Yes"}])[0]["status"], "filled")
        self.assertEqual(self.page.locator("#now").input_value(), "y")

    def test_workday_add_row_never_clicked(self):
        self.open_page('<h1>Experience</h1><form><section data-automation-id="workExperience-1">'
                       '<label>Employer<input id="employer"></label></section><button type="button" id="add">Add</button></form>')
        self.page.evaluate("globalThis.addClicks = 0; document.querySelector('#add').addEventListener('click', () => addClicks++)")
        self.adapter("a.scan({values:{}}, {register:false}); a.nextStep()")
        self.assertEqual(self.page.evaluate("addClicks"), 0)

    def test_workday_existing_row_split_date_requires_binding(self):
        self.open_page('<h1>Experience</h1><form><section data-automation-id="workExperience-1">'
                       '<label>Start month<select id="month"><option value="">Select</option>'
                       '<option value="01">January</option><option value="02">February</option></select></label>'
                       '<label>Start year<input id="year" type="number"></label></section>'
                       '<button type="button" id="add">Add</button></form>')
        values = {"employment.0.start_date": {"value": "2024-02", "source": "Fabricated profile"}}
        unbound = self.scan(values)
        self.assertFalse(any(item["key"] for item in unbound if item["structure"]["dom_id"] in ("month", "year")))
        record_id = next(item["record"]["id"] for item in unbound if item["structure"]["dom_id"] == "month")
        bound = self.page.evaluate("({values, recordId}) => PortalEngine.scan({values}, {bindings: {[recordId]: 0}})",
                                   {"values": values, "recordId": record_id})
        actual = {item["structure"]["dom_id"]: (item["key"], item["proposal"]) for item in bound}
        self.assertEqual(actual["month"], ("employment.0.start_month", "February"))
        self.assertEqual(actual["year"], ("employment.0.start_year", "2024"))
        self.assertEqual(self.page.locator("#month").input_value(), "")
        self.assertEqual(self.page.locator("#year").input_value(), "")

    def test_workday_autofill_with_resume_never_clicked(self):
        self.open_page('<h1>My Information</h1><form><label>First name<input id="first"></label>'
                       '<button type="button" id="autofill">Autofill with Resume</button>'
                       '<button type="button" id="last-app">Use my last application</button></form>')
        self.adapter("a.scan({values:{}}, {register:false}); a.nextStep(); a.detectFinalReview()")
        self.assertEqual(self.page.evaluate("anyClicks"), 0)

    def test_workday_value_revert_reported(self):
        self.open_page('<form><label>First name<input id="first"></label></form>')
        self.page.evaluate("document.querySelector('#first').addEventListener('input', event => { setTimeout(() => { event.target.value = ''; }, 0); })")
        result = self.fill([{"id": self.field("first_name")["id"], "value": "Synthetic"}])[0]
        self.assertEqual(result["failure_kind"], "reverted")
        self.assertNotEqual(result["status"], "filled")


if __name__ == "__main__":
    unittest.main()
