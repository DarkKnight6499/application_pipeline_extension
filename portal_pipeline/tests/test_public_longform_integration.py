"""Synthetic long-form route and write boundaries. Author: Yazad Madan."""
import http.client
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from browser_test_support import HERE, SyntheticBrowserTest

sys.path.insert(0, str(HERE))
from server import make_server
import longform

SESSION = "d" * 32
TOKEN = "fabricated-longform-token"


class LongformRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name)
        (self.source / "_Reference").mkdir()
        (self.source / "_Reference/Application_Boilerplate.md").write_text(
            "# Fabricated evidence\n## Role Descriptions\nBuilt 3 fabricated models.\n"
            "## Why Us\nInterested in the fictional team's research.\n", encoding="utf-8")
        self.current = {"id": SESSION, "mode": "audited_import", "application_id": 21}
        pipeline = SimpleNamespace(source=self.source, lock=threading.RLock(), current=lambda: self.current)
        self.server = make_server(pipeline, 0, TOKEN)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def call(self, body, token=TOKEN):
        client = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        client.request("POST", f"/api/sessions/{SESSION}/longform", json.dumps(body),
                       {"X-Portal-Token": token, "Content-Type": "application/json"})
        response = client.getresponse()
        result = response.status, json.loads(response.read())
        client.close()
        return result

    def test_current_session_and_token_required(self):
        body = {"question": "Describe a project", "draft": "Built 3 models.", "limit": 100}
        self.assertEqual(self.call(body, "wrong")[0], 401)
        self.current["id"] = "e" * 32
        self.assertEqual(self.call(body)[0], 400)

    def test_supported_draft_and_unsupported_number(self):
        body = {"question": "Describe a project", "draft": "Built 3 models.", "limit": 100}
        status, report = self.call(body)
        self.assertEqual(status, 200)
        self.assertEqual(report["status"], "draft_needs_review")
        self.assertTrue(report["selectable"])
        self.assertTrue(report["evidence"])
        self.assertEqual(report["count"], len(body["draft"]))
        body["draft"] = "Built 999 models."
        self.assertFalse(self.call(body)[1]["selectable"])

    def test_no_evidence_and_over_limit_stay_unselectable(self):
        body = {"question": "Unrecognized question", "draft": "Human draft", "limit": 100}
        status, report = self.call(body)
        self.assertEqual(status, 200)
        self.assertEqual(report["status"], "pending")
        self.assertFalse(report["selectable"])
        body.update(question="Describe a project", draft="Built 3 models.", limit=2)
        self.assertFalse(self.call(body)[1]["selectable"])

    def test_strict_body_never_accepts_caller_evidence(self):
        body = {"question": "Describe a project", "draft": "Built 3 models.", "limit": 100}
        for extra in ({"evidence": [{"text": "999", "source": "Caller"}]}, {"limit": True}, {"draft": 3}):
            with self.subTest(extra=extra):
                self.assertEqual(self.call({**body, **extra})[0], 400)


class LongformEngineTests(SyntheticBrowserTest):
    def open_question(self):
        self.open_markup('<label>Describe a project<textarea id="draft" maxlength="100"></textarea></label>')
        return next(field for field in self.scan() if field["type"] == "textarea")

    def test_direct_selection_without_validator_refused(self):
        field = self.open_question()
        result = self.fill([{"id": field["id"], "value": "Built 999 models.", "longformReviewed": True}])
        self.assertEqual(result[0]["status"], "refused")
        self.assertEqual(self.page.locator("#draft").input_value(), "")

    def test_unsupported_draft_cannot_bypass_panel(self):
        field = self.open_question()
        result = self.page.evaluate("""async id=>PortalEngine.fill([{id,value:'Built 999 models.',longformReviewed:true}],
          {validateLongform:async()=>({selectable:false,status:'draft_needs_review',unsupported_numbers:['999']})})""", field["id"])
        self.assertEqual(result[0]["status"], "refused")
        self.assertEqual(self.page.locator("#draft").input_value(), "")

    def test_review_required_even_for_supported_draft(self):
        field = self.open_question()
        result = self.page.evaluate("""async id=>PortalEngine.fill([{id,value:'Built 3 models.'}],
          {validateLongform:async()=>({selectable:true})})""", field["id"])
        self.assertEqual(result[0]["status"], "refused")
        self.assertEqual(self.page.locator("#draft").input_value(), "")

    def test_helper_prompt_vocabulary_cannot_bypass_engine(self):
        for question in ("Tell us about your work", "What interests you about our company?"):
            with self.subTest(question=question):
                self.open_markup(f'<label>{question}<textarea id="draft" maxlength="100"></textarea></label>')
                field = next(field for field in self.scan() if field["type"] == "textarea")
                result = self.fill([{"id": field["id"], "value": "Built 999 models.", "longformReviewed": True}])
                self.assertEqual(result[0]["status"], "refused")
                self.assertEqual(self.page.locator("#draft").input_value(), "")

    def test_engine_guards_every_helper_trigger_word(self):
        self.open_question()
        words = sorted(longform.ROLE_WORDS | longform.WHY_WORDS)
        rejected = self.page.evaluate("words=>words.filter(label=>!PortalEngine.isLongform({type:'textarea',label,key:null}))", words)
        self.assertEqual(rejected, [])

    def test_explicitly_reviewed_supported_draft_fills_only_selected_field(self):
        field = self.open_question()
        result = self.page.evaluate("""async id=>PortalEngine.fill([{id,value:'Built 3 models.',longformReviewed:true}],
          {validateLongform:async request=>({selectable:true,status:'draft_needs_review',limit:request.limit,
            count:15,fit:{ok:true},unsupported_numbers:[],evidence:[{text:'Built 3 models.',source:'Fabricated'}]})})""", field["id"])
        self.assertEqual(result[0]["status"], "filled")
        self.assertEqual(self.page.locator("#draft").input_value(), "Built 3 models.")

    def test_portal_limit_change_during_validation_refuses_stale_check(self):
        field = self.open_question()
        result = self.page.evaluate("""async id=>PortalEngine.fill([{id,value:'Built\\n3\\nmodels.',longformReviewed:true}],
          {validateLongform:async request=>{
            document.querySelector('#draft').maxLength=15;
            return {selectable:true,status:'draft_needs_review',limit:request.limit,
              count:17,fit:{ok:true},unsupported_numbers:[],evidence:[{text:'Built 3 models.',source:'Fabricated'}]};
          }})""", field["id"])
        self.assertEqual(result[0]["status"], "refused")
        self.assertEqual(self.page.locator("#draft").input_value(), "")

    def open_panel(self):
        self.open_question()
        self.page.add_script_tag(path=str(HERE / "extension/panel.js"))
        self.page.evaluate("""async()=>{
          globalThis.draftReport={selectable:true,status:'draft_needs_review',count:15,limit:100,
            fit:{ok:true},unsupported_numbers:[],evidence:[{text:'Built 3 models.',source:'Fabricated'}]};
          const api=async(path)=>path==='/api/current'?{id:'d'.repeat(32),application_id:21,
              mode:'audited_import',url:location.href,company:'Fabricated',role:'Synthetic'}:
            path.endsWith('/profile')?{values:{}}:path.endsWith('/longform')?draftReport:
            path.endsWith('/preflight')?{items:[],manual_field_ids:[]}:{};
          await PortalPanel.open(api,{load:async()=>null,save:async()=>{}},{targetUrl:location.href,
            transport:{scan:profile=>PortalEngine.scan(profile),fill:async(selections,options)=>{
              globalThis.sentDraft={selections,options:structuredClone(options)};
              await new Promise(resolve=>globalThis.releaseFill=resolve);return [];
            }}});
        }""")
        return self.page.locator("#portal-panel-host")

    def test_panel_requires_check_and_invalidates_after_edit(self):
        panel = self.open_panel()
        selection = panel.get_by_role("checkbox", name="Select Describe a project", exact=True)
        answer = panel.get_by_role("textbox", name="Answer Describe a project", exact=True)
        self.assertTrue(selection.is_disabled())
        answer.fill("Built 3 models.")
        panel.get_by_role("button", name="Check draft for Describe a project", exact=True).click()
        self.assertFalse(selection.is_disabled())
        self.assertFalse(selection.is_checked())
        selection.check()
        answer.fill("Built 999 models.")
        self.assertTrue(selection.is_disabled())
        self.assertFalse(selection.is_checked())
        self.page.evaluate("draftReport.selectable=false;draftReport.unsupported_numbers=['999']")
        panel.get_by_role("button", name="Check draft for Describe a project", exact=True).click()
        self.assertTrue(selection.is_disabled())
        self.assertEqual(self.page.locator("#draft").input_value(), "")

    def test_transport_options_are_cloneable_and_draft_check_locks_during_fill(self):
        panel = self.open_panel()
        panel.get_by_role("textbox", name="Answer Describe a project", exact=True).fill("Built 3 models.")
        check = panel.get_by_role("button", name="Check draft for Describe a project", exact=True)
        check.click()
        panel.get_by_role("checkbox", name="Select Describe a project", exact=True).check()
        panel.locator("#match-page").check()
        panel.get_by_role("button", name="Fill selected fields", exact=True).click()
        self.assertTrue(check.is_disabled())
        sent = self.page.evaluate("sentDraft")
        self.assertTrue(sent["selections"][0]["longformReviewed"])
        self.assertNotIn("validateLongform", sent["options"])
        self.page.evaluate("releaseFill()")
        self.assertFalse(check.is_disabled())
