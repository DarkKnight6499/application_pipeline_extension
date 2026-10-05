"""Application restrictions on fabricated pages. Author: Yazad Madan."""
import base64
import hashlib

from browser_test_support import HERE, SyntheticBrowserTest


URL = "https://mode-fixture.example.invalid/apply"
MARKUP = '''<h1>Personal information</h1><form>
<label>First name<input id="first"></label>
<label>Last name<input id="last"></label>
<label>Resume<input id="resume" type="file"></label>
<button id="next" type="button">Next</button></form>'''


class ApplicationModeBrowserTests(SyntheticBrowserTest):
    def open_mode(self, journal=None):
        self.open_markup(MARKUP, URL)
        self.page.evaluate("""journal => {
          globalThis.journal = journal || {};
          globalThis.helper = {id:'a'.repeat(32), application_id:11,
            mode:'fill', reason:'unrestricted', postFails:false, calls:[]};
          globalThis.listeners = [];
          globalThis.contentSender = {id:'mode-extension',frameId:0,
            tab:{id:3,url:location.href},url:location.href};
          globalThis.chrome = {
            storage:{local:{get:async key => typeof key === 'string' ? {[key]:journal[key]}
              : Object.fromEntries(key.map(k=>[k,k==='server'?'http://127.0.0.1:8766':k==='token'?'fabricated-token':journal[k]])),
              set:async values => Object.assign(journal,values)}},
            runtime:{id:'mode-extension',getURL:path=>'chrome-extension://mode-extension/'+path,
              onMessage:{addListener:fn=>listeners.push(fn)},
              sendMessage:message=>new Promise(resolve=>listeners[0](message,contentSender,resolve))}
          };
          globalThis.fetch = async (url, options) => {
            helper.calls.push([url,options.method||'GET']);
            let value;
            if(url.endsWith('/api/current')) value={id:helper.id,application_id:helper.application_id,
              mode:'audited_import',url:location.origin+'/apply'};
            else if(options.method==='POST') {
              if(helper.postFails) throw Error('Fabricated persistence failure');
              helper.mode='answer_sheet_only';helper.reason='captcha';
              value={schema_version:1,application_id:helper.application_id,mode:helper.mode,reason:helper.reason};
            } else {
              value=helper.response || {schema_version:1,application_id:helper.application_id,mode:helper.mode,reason:helper.reason};
              if(helper.holdMode) {helper.holdMode=false;await new Promise(resolve=>helper.release=resolve);}
            }
            return {ok:true,json:async()=>value};
          };
          globalThis.activeAdapter=PortalAdapters.register({...PortalAdapters.forLocation(''),
            id:'mode_fixture',hosts:[/^mode-fixture\\.example\\.invalid$/],requiresApplicationMode:true});
          globalThis.applicationContext={sessionId:helper.id,applicationId:11,targetUrl:location.href};
        }""", journal or {})
        for script in ["background.js", "application-mode.js", "progress.js"]:
            self.page.add_script_tag(path=str(HERE / "extension" / script))
        self.page.evaluate("PortalApplicationMode.bind(applicationContext)")

    def field(self, key):
        return next(row for row in self.scan() if row["key"] == key)

    def broker(self, action="read"):
        return self.page.evaluate("action=>chrome.runtime.sendMessage({type:'portal-application-mode',action,"
                                  "sessionId:helper.id,applicationId:helper.application_id,reason:'captcha'})", action)

    def test_unloaded_guard_refuses_without_write(self):
        self.open_mode()
        self.page.evaluate("delete globalThis.PortalApplicationMode")
        result = self.fill([{"id": self.field("first_name")["id"], "value": "Synthetic"}])
        self.assertEqual(result[0]["status"], "refused")
        self.assertEqual(self.page.locator("#first").input_value(), "")

    def test_fill_allowed_only_with_matching_unrestricted_identity(self):
        self.open_mode()
        result = self.fill([{"id": self.field("first_name")["id"], "value": "Synthetic"}])
        self.assertEqual(result[0]["status"], "filled")
        self.assertEqual(self.page.locator("#last").input_value(), "")

    def test_partial_batch_retains_results_and_stops_later_writes(self):
        self.open_mode()
        fields = self.scan()
        ids = {row["key"]: row["id"] for row in fields}
        self.page.evaluate("document.querySelector('#first').addEventListener('input',()=>{helper.mode='answer_sheet_only';helper.reason='captcha';})")
        result = self.fill([{"id": ids["first_name"], "value": "Synthetic"},
                            {"id": ids["last_name"], "value": "Untouched"}])
        self.assertEqual([row["status"] for row in result], ["filled", "refused"])
        self.assertEqual(self.page.locator("#first").input_value(), "Synthetic")
        self.assertEqual(self.page.locator("#last").input_value(), "")

    def test_helper_failure_journal_survives_reload_and_port_change(self):
        self.open_mode()
        self.page.evaluate("helper.postFails=true")
        reply = self.broker("restrict")
        self.assertFalse(reply["ok"])
        journal = self.page.evaluate("journal")
        self.assertTrue(journal["application-mode:application:11"])
        self.open_mode(journal)
        self.page.evaluate("() => { chrome.storage.local.get=async key=>typeof key==='string'?{[key]:journal[key]}:"
                           "Object.fromEntries(key.map(k=>[k,k==='server'?'http://127.0.0.1:8777':'fabricated-token'])); }")
        reply = self.broker()
        self.assertTrue(reply["ok"])
        self.assertEqual(reply["value"]["mode"], "answer_sheet_only")
        result = self.fill([{"id": self.field("first_name")["id"], "value": "Synthetic"}])
        self.assertEqual(result[0]["status"], "refused")

    def test_stale_read_cannot_restore_concurrent_journal_restriction(self):
        self.open_mode()
        reply = self.page.evaluate("""async()=>{
          helper.holdMode=true;
          const read=chrome.runtime.sendMessage({type:'portal-application-mode',action:'read',sessionId:helper.id,applicationId:11});
          while(!helper.release) await new Promise(resolve=>setTimeout(resolve,0));
          await chrome.runtime.sendMessage({type:'portal-application-mode',action:'restrict',sessionId:helper.id,applicationId:11,reason:'captcha'});
          helper.release();return read;
        }""")
        self.assertEqual(reply["value"]["mode"], "answer_sheet_only")

    def test_session_changed_during_get_refuses_stale_response(self):
        self.open_mode()
        reply = self.page.evaluate("""async()=>{
          helper.holdMode=true;
          const read=chrome.runtime.sendMessage({type:'portal-application-mode',action:'read',sessionId:helper.id,applicationId:11});
          while(!helper.release) await new Promise(resolve=>setTimeout(resolve,0));
          helper.id='b'.repeat(32);helper.application_id=12;helper.release();return read;
        }""")
        self.assertFalse(reply["ok"])

    def test_captcha_after_await_is_latched_and_persisted(self):
        self.open_mode()
        error = self.page.evaluate("""async()=>{
          helper.holdMode=true;
          const check=PortalApplicationMode.check(activeAdapter).then(()=>'',error=>error.message);
          while(!helper.release) await new Promise(resolve=>setTimeout(resolve,0));
          document.body.insertAdjacentHTML('afterbegin','<div class="cf-turnstile" style="height:40px">Gate</div>');
          helper.release();return check;
        }""")
        self.assertTrue(error)
        self.assertTrue(self.page.evaluate("journal['application-mode:application:11']"))
        self.page.locator(".cf-turnstile").evaluate("node=>node.remove()")
        self.assertEqual(self.broker()["value"]["mode"], "answer_sheet_only")

    def test_other_application_does_not_inherit_local_latch(self):
        self.open_mode()
        self.page.evaluate("document.body.insertAdjacentHTML('afterbegin','<div class=\"cf-turnstile\" style=\"height:40px\">Gate</div>')")
        self.page.evaluate("PortalApplicationMode.check(activeAdapter).catch(()=>{})")
        self.page.locator(".cf-turnstile").evaluate("node=>node.remove()")
        self.page.evaluate("helper.application_id=12;helper.id='b'.repeat(32);helper.mode='fill';helper.reason='unrestricted';"
                           "PortalApplicationMode.bind({sessionId:helper.id,applicationId:12,targetUrl:location.href})")
        result = self.fill([{"id": self.field("first_name")["id"], "value": "Synthetic"}])
        self.assertEqual(result[0]["status"], "filled")

    def test_attachment_restriction_after_hash_stops_assignment(self):
        self.open_mode()
        self.page.evaluate("() => { const digest=crypto.subtle.digest.bind(crypto.subtle);crypto.subtle.digest=async(...args)=>{"
                           "const result=await digest(...args);helper.mode='answer_sheet_only';helper.reason='captcha';return result;}; }")
        data = b"fabricated resume"
        attachment = {"name": "fabricated.docx", "mime": "application/octet-stream",
                      "base64": base64.b64encode(data).decode(), "sha256": hashlib.sha256(data).hexdigest()}
        result = self.fill([{"id": next(row["id"] for row in self.scan() if row["type"] == "file"), "value": "fabricated.docx"}], {"attachment": attachment})
        self.assertEqual(result[0]["status"], "failed")
        self.assertEqual(self.page.locator("#resume").evaluate("node=>node.files.length"), 0)

    def test_malformed_mode_and_journal_refuse_writes(self):
        for response in [{"schema_version": True, "application_id": 11, "mode": "fill", "reason": "unrestricted"},
                         {"schema_version": 1, "application_id": 12, "mode": "fill", "reason": "unrestricted"},
                         {"schema_version": 1, "application_id": 11, "mode": "fill", "reason": "captcha"}]:
            with self.subTest(response=response):
                self.open_mode()
                self.page.evaluate("response=>helper.response=response", response)
                result = self.fill([{"id": self.field("first_name")["id"], "value": "Synthetic"}])
                self.assertEqual(result[0]["status"], "refused")
                self.assertEqual(self.page.locator("#first").input_value(), "")
        self.open_mode({"application-mode:application:11": False})
        self.assertFalse(self.broker()["ok"])

    def test_enabled_next_rechecks_mode_before_click(self):
        self.open_mode({"application-mode:application:11": True})
        self.page.evaluate("() => { document.querySelector('#guard-submit').hidden=true;"
                           "PortalProgress.settings.allowGuardedNext=true;globalThis.nextClicks=0;"
                           "document.querySelector('#next').onclick=()=>nextClicks++; }")
        result = self.page.evaluate("PortalProgress.guardedNext(activeAdapter)")
        self.assertEqual(result["status"], "refused")
        self.assertEqual(self.page.evaluate("nextClicks"), 0)

    def test_inspection_bridge_rejects_fill_without_new_context(self):
        self.open_mode()
        self.page.add_script_tag(path=str(HERE / "extension/page-bridge.js"))
        reply = self.page.evaluate("""()=>new Promise(resolve=>{
          setTimeout(()=>resolve({ok:true,error:'No response'}),100);
          listeners[1]({type:'portal-fill',selections:[]},
            {id:'mode-extension',url:chrome.runtime.getURL('review.html')+'?tab=3&mode=inspect'},resolve);
        })""")
        self.assertFalse(reply["ok"])
        self.assertIn("Inspection mode", reply["error"])

    def test_bridge_rejects_wrong_review_document_and_missing_identity(self):
        self.open_mode()
        self.page.add_script_tag(path=str(HERE / "extension/page-bridge.js"))
        result = self.page.evaluate("""async()=>{
          let called=false;
          listeners[1]({type:'portal-fill',tabId:3,selections:[]},
            {id:'mode-extension',url:chrome.runtime.getURL('review.html.evil')+'?tab=3'},()=>called=true);
          const denied=await new Promise(resolve=>listeners[1]({type:'portal-fill',tabId:3,selections:[]},
            {id:'mode-extension',url:chrome.runtime.getURL('review.html')+'?tab=3'},resolve));
          return {called,denied};
        }""")
        self.assertFalse(result["called"])
        self.assertFalse(result["denied"]["ok"])

    def test_restriction_journal_precedes_helper_outage(self):
        self.open_mode()
        self.page.evaluate("() => { globalThis.fetch=async()=>{throw Error('Helper offline');}; }")
        reply = self.broker("restrict")
        self.assertFalse(reply["ok"])
        self.assertTrue(self.page.evaluate("journal['application-mode:application:11']"))

    def test_journal_write_failure_still_latches_current_worker(self):
        self.open_mode()
        self.page.evaluate("() => { chrome.storage.local.set=async()=>{throw Error('Journal unavailable');}; }")
        reply = self.broker("restrict")
        self.assertFalse(reply["ok"])
        self.assertEqual(self.broker()["value"]["mode"], "answer_sheet_only")
        result = self.fill([{"id": self.field("first_name")["id"], "value": "Synthetic"}])
        self.assertEqual(result[0]["status"], "refused")
        self.assertEqual(self.page.locator("#first").input_value(), "")

    def test_journal_read_failure_refuses_without_write(self):
        self.open_mode()
        self.page.evaluate("() => { const get=chrome.storage.local.get;chrome.storage.local.get=async key=>{"
                           "if(typeof key==='string') throw Error('Journal unreadable');return get(key);}; }")
        result = self.fill([{"id": self.field("first_name")["id"], "value": "Synthetic"}])
        self.assertEqual(result[0]["status"], "refused")
        self.assertEqual(self.page.locator("#first").input_value(), "")

    def test_length_limit_changed_during_mode_await_prevents_write(self):
        self.open_mode()
        self.page.evaluate("""() => {
          const check=PortalApplicationMode.check;let calls=0;
          PortalApplicationMode.check=async adapter=>{
            const result=await check(adapter);
            if(++calls===3) document.querySelector('#first').maxLength=2;
            return result;
          };
        }""")
        result = self.fill([{"id": self.field("first_name")["id"], "value": "Synthetic"}])
        self.assertEqual(result[0]["status"], "failed")
        self.assertEqual(self.page.locator("#first").input_value(), "")

    def test_captcha_at_final_next_check_prevents_click(self):
        self.open_mode()
        self.page.evaluate("""() => {
          document.querySelector('#guard-submit').hidden=true;
          PortalProgress.settings.allowGuardedNext=true;
          globalThis.nextClicks=0;document.querySelector('#next').onclick=()=>nextClicks++;
          const check=PortalApplicationMode.check;let calls=0;
          PortalApplicationMode.check=async adapter=>{
            if(++calls===2) document.body.insertAdjacentHTML('afterbegin',
              '<div class="cf-turnstile" style="height:40px">Gate</div>');
            return check(adapter);
          };
        }""")
        result = self.page.evaluate("PortalProgress.guardedNext(activeAdapter)")
        self.assertEqual(result["status"], "refused")
        self.assertEqual(self.page.evaluate("nextClicks"), 0)
        self.assertTrue(self.page.evaluate("journal['application-mode:application:11']"))

    def test_location_change_during_mode_check_refuses_write(self):
        self.open_mode()
        error = self.page.evaluate("""async()=>{
          helper.holdMode=true;
          const check=PortalApplicationMode.check(activeAdapter).then(()=>'',error=>error.message);
          while(!helper.release) await new Promise(resolve=>setTimeout(resolve,0));
          history.replaceState({},'', '/different-page');helper.release();return check;
        }""")
        self.assertTrue(error)
        self.assertEqual(self.page.locator("#first").input_value(), "")

    def test_panel_sheet_mode_keeps_export_available_and_fill_disabled(self):
        self.open_mode()
        self.page.add_script_tag(path=str(HERE / "extension/panel.js"))
        self.page.evaluate("""async()=>{
          const profile={values:{first_name:{value:'Synthetic',source:'Fabricated'}}};
          const api=async(path)=>path==='/api/current'?{id:helper.id,application_id:11,
            mode:'audited_import',url:location.href,company:'Fabricated',role:'Synthetic'}:
            path.endsWith('/profile')?profile:path.endsWith('/preflight')?{gates:[],manual_field_ids:[]}:{};
          await PortalPanel.open(api,{load:async()=>null,save:async()=>{}},{targetUrl:location.href,
            transport:{scan:()=>PortalEngine.scan(profile),mode:async()=>({schema_version:1,
              application_id:11,mode:'answer_sheet_only',reason:'captcha'})}});
        }""")
        panel = self.page.locator("#portal-panel-host")
        self.assertTrue(panel.get_by_role("button", name="Fill selected fields", exact=True).is_disabled())
        self.assertTrue(panel.get_by_role("button", name="Export answer sheet", exact=True).is_enabled())
        self.assertEqual(self.page.locator("#first").input_value(), "")
