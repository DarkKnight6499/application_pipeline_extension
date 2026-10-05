"""Synthetic long-form broker boundaries. Author: Yazad Madan."""

from browser_test_support import HERE, SyntheticBrowserTest


URL = "https://broker-fixture.example.invalid/apply"
LOCAL_URL = "http://127.0.0.1:8766/fixture"
SESSION = "a" * 32


class LongformBrokerTests(SyntheticBrowserTest):
    def open_broker(self, url=URL, mode="audited_import"):
        self.open_markup("<main>Fabricated application</main>", url)
        self.page.evaluate("""mode => {
          globalThis.broker = {id:'a'.repeat(32), mode, applicationId:17,
            sessionUrl:location.href, calls:[], report:{status:'draft_needs_review',
              selectable:true, evidence:[{text:'Fabricated 3 models.',source:'synthetic:L1'}],
              count:15, limit:100, fit:{ok:true,count:15,limit:100}, unsupported_numbers:[]}};
          globalThis.listeners = [];
          globalThis.sender = {id:'broker-extension',frameId:0,
            tab:{id:4,url:location.href},url:location.href};
          globalThis.chrome = {
            storage:{local:{get:async()=>({server:'http://127.0.0.1:8766',token:'fabricated-token'})}},
            runtime:{id:'broker-extension',onMessage:{addListener:listener=>listeners.push(listener)},
              sendMessage:(message,from=sender)=>new Promise(resolve=>listeners[0](message,from,resolve))}
          };
          globalThis.fetch = async (url, options={}) => {
            broker.calls.push({url, method:options.method||'GET', body:options.body||null});
            let value;
            if(url.endsWith('/api/current')) value={id:broker.id,mode:broker.mode,
              application_id:broker.applicationId,url:broker.sessionUrl};
            else if(url.endsWith('/longform')) {
              value=broker.report;
              if(broker.holdPost) {
                broker.holdPost=false;
                await new Promise(resolve=>broker.releasePost=resolve);
              }
            } else throw Error('Unexpected helper request');
            return {ok:true,json:async()=>value};
          };
        }""", mode)
        self.page.add_script_tag(path=str(HERE / "extension/background.js"))

    def request(self, sender=None, session_id=SESSION):
        return self.page.evaluate("""({sender,sessionId}) => chrome.runtime.sendMessage({
          type:'portal-longform',sessionId,body:{question:'Describe a project',
            draft:'Built 3 models.',limit:100}},sender||globalThis.sender)""",
            {"sender": sender, "sessionId": session_id})

    def test_matching_audited_session_returns_helper_report(self):
        self.open_broker()
        reply = self.request()
        self.assertTrue(reply["ok"])
        self.assertTrue(reply["value"]["selectable"])
        calls = self.page.evaluate("broker.calls")
        self.assertEqual([call["method"] for call in calls], ["GET", "POST", "GET"])
        self.assertTrue(calls[1]["url"].endswith(f"/api/sessions/{SESSION}/longform"))
        self.assertEqual(calls[1]["body"], '{"question":"Describe a project","draft":"Built 3 models.","limit":100}')

    def test_rejects_sender_frame_and_session_before_post(self):
        self.open_broker()
        sender = self.page.evaluate("sender")
        for changed in ({**sender, "id": "other-extension"}, {**sender, "frameId": 2},
                        {**sender, "tab": None}):
            with self.subTest(changed=changed):
                self.assertFalse(self.request(sender=changed)["ok"])
        self.assertFalse(self.request(session_id="invalid")["ok"])
        self.assertEqual(self.page.evaluate("broker.calls"), [])

    def test_rejects_changed_session_during_post(self):
        self.open_broker()
        reply = self.page.evaluate("""async () => {
          broker.holdPost=true;
          const pending=chrome.runtime.sendMessage({type:'portal-longform',
            sessionId:broker.id,body:{question:'Describe a project',draft:'Built 3 models.',limit:100}});
          while(!broker.releasePost) await new Promise(resolve=>setTimeout(resolve,0));
          broker.id='b'.repeat(32);
          broker.releasePost();
          return pending;
        }""")
        self.assertFalse(reply["ok"])
        self.assertIn("changed", reply["error"].lower())
        self.assertEqual([call["method"] for call in self.page.evaluate("broker.calls")], ["GET", "POST", "GET"])

    def test_rejects_wrong_origin_and_nonlocal_sandbox(self):
        self.open_broker()
        self.page.evaluate("broker.sessionUrl='https://other.example.invalid/apply'")
        self.assertFalse(self.request()["ok"])
        self.assertFalse(any(call["method"] == "POST" for call in self.page.evaluate("broker.calls")))
        self.page.evaluate("broker.calls=[];broker.sessionUrl=location.href;broker.mode='sandbox'")
        self.assertFalse(self.request()["ok"])
        self.assertFalse(any(call["method"] == "POST" for call in self.page.evaluate("broker.calls")))

    def test_local_fixture_sandbox_allowed(self):
        self.open_broker(LOCAL_URL, "sandbox")
        self.assertTrue(self.request()["ok"])


class LongformReportBoundaryTests(SyntheticBrowserTest):
    def test_malformed_report_cannot_approve_engine_write(self):
        self.open_markup('<label>Describe a project<textarea id="draft" maxlength="100"></textarea></label>')
        field = next(row for row in self.scan() if row["type"] == "textarea")
        report = {"status": "draft_needs_review", "selectable": True, "limit": 100,
                  "fit": {"ok": True, "count": 15, "limit": 100},
                  "evidence": [{"text": "Fabricated 3 models.", "source": "synthetic:L1"}],
                  "unsupported_numbers": []}
        for changed in ({"status": "prepared"}, {"limit": 99},
                        {"fit": {"ok": False}}, {"evidence": []},
                        {"unsupported_numbers": ["999"]}, {"unsupported_numbers": None}):
            with self.subTest(changed=changed):
                result = self.page.evaluate("""async ({id,report}) => PortalEngine.fill(
                  [{id,value:'Built 3 models.',longformReviewed:true}],
                  {validateLongform:async()=>report})""",
                    {"id": field["id"], "report": {**report, **changed}})
                self.assertEqual(result[0]["status"], "refused")
                self.assertEqual(self.page.locator("#draft").input_value(), "")


if __name__ == "__main__":
    import unittest
    unittest.main()
