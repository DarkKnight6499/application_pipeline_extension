"""Loaded MV3 restriction persistence on fabricated application pages."""
import json
import os
import shutil
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from browser_test_support import BROWSER_CHANNEL, HERE, sync_playwright


TARGET = "https://mode-fixture.example.invalid/apply"
TOKEN = "fabricated-mode-token"
SESSIONS = {11: "a" * 32, 12: "b" * 32}
JOURNAL_KEY = "application-mode:application:11"
MARKUP = """<!doctype html><title>Fabricated application</title>
<form><label>First name<input id="first"></label>
<button id="next" type="button">Next</button>
<button id="submit" type="submit">Submit</button></form>
<script>
window.fieldWrites=0;window.nextClicks=0;window.submitClicks=0;window.submitEvents=0;
document.querySelector('#first').addEventListener('input',()=>fieldWrites++);
document.querySelector('#next').addEventListener('click',()=>nextClicks++);
document.querySelector('#submit').addEventListener('click',()=>submitClicks++);
document.querySelector('form').addEventListener('submit',event=>{submitEvents++;event.preventDefault()});
</script>"""
SCRIPTS = ["adapters/registry.js", "adapters/generic.js", "classifier.js", "engine.js",
           "application-mode.js", "progress.js", "adapters/mv3-fixture.js"]


class FabricatedHelper:
    def __init__(self):
        self.application_id = 11
        self.restricted = set()
        self.reject_post = True
        self.requests = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self, code, value):
                body = json.dumps(value).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def handle_request(self):
                owner.requests.append((self.command, self.path))
                if self.headers.get("X-Portal-Token") != TOKEN:
                    return self.reply(403, {"error": "Fabricated token required"})
                app = owner.application_id
                session = SESSIONS[app]
                if self.path == "/api/current" and self.command == "GET":
                    return self.reply(200, {"id": session, "application_id": app,
                                            "mode": "audited_import", "url": TARGET})
                if self.path == f"/api/sessions/{session}/fill-mode":
                    if self.command == "POST":
                        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                        if body != {"mode": "answer_sheet_only", "reason": "captcha"}:
                            return self.reply(400, {"error": "Invalid fabricated restriction"})
                        if owner.reject_post:
                            return self.reply(503, {"error": "Fabricated helper storage outage"})
                        owner.restricted.add(app)
                    return self.reply(200, {"schema_version": 1, "application_id": app,
                                            "mode": "answer_sheet_only" if app in owner.restricted else "fill",
                                            "reason": "captcha" if app in owner.restricted else "unrestricted"})
                self.reply(404, {"error": "Unknown fabricated route"})

            do_GET = handle_request
            do_POST = handle_request

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


class LoadedApplicationModeTests(unittest.TestCase):
    def launch(self, playwright, profile, extension):
        context = playwright.chromium.launch_persistent_context(str(profile),
            channel=BROWSER_CHANNEL or "chromium", headless=True,
            args=[f"--disable-extensions-except={extension}", f"--load-extension={extension}"],
            viewport={"width": 1280, "height": 900})
        workers = context.service_workers
        worker = workers[0] if workers else context.wait_for_event("serviceworker")
        extension_id = worker.url.split("/")[2]
        context.route(TARGET, lambda route: route.fulfill(content_type="text/html", body=MARKUP))
        target = context.new_page()
        target.goto(TARGET)
        control = context.new_page()
        control.goto(f"chrome-extension://{extension_id}/review.html")
        tab_id = control.evaluate("url => chrome.tabs.query({}).then(tabs => tabs.find(tab => tab.url === url).id)", TARGET)
        return context, target, control, tab_id

    def inject(self, control, tab_id, app):
        control.evaluate("""async ({tabId, files}) => {
          for (const file of files) await chrome.scripting.executeScript({target:{tabId},files:[file]});
        }""", {"tabId": tab_id, "files": SCRIPTS})
        result = control.evaluate("""async ({tabId, applicationId, sessionId}) => {
          return (await chrome.scripting.executeScript({target:{tabId},func: args => {
            const adapter=PortalAdapters.forLocation(location.href);
            PortalApplicationMode.bind({applicationId:args.applicationId,
              sessionId:args.sessionId,targetUrl:location.href});
            return {id:adapter.id, mode:adapter.mode, guarded:adapter.requiresApplicationMode};
          },args:[{applicationId,sessionId}]}))[0].result;
        }""", {"tabId": tab_id, "applicationId": app, "sessionId": SESSIONS[app]})
        self.assertEqual(result, {"id": "mv3_fixture", "mode": "fill", "guarded": True})

    def run_action(self, control, tab_id, action):
        return control.evaluate("""async ({tabId, action}) => {
          return (await chrome.scripting.executeScript({target:{tabId},func: async action => {
            const adapter=PortalAdapters.forLocation(location.href);
            if(action==='observe') return PortalApplicationMode.observe(adapter);
            if(action==='read') {
              try { await PortalApplicationMode.check(adapter); return 'allowed'; }
              catch(error) { return error.message; }
            }
            if(action==='fill') {
              const field=PortalEngine.scan({values:{first_name:{value:'Synthetic',source:'Fabricated'}}})
                .find(row=>row.key==='first_name');
              return PortalEngine.fill([{id:field.id,value:'Synthetic'}]);
            }
            PortalProgress.settings.allowGuardedNext=true;
            return PortalProgress.guardedNext(adapter);
          },args:[action]}))[0].result;
        }""", {"tabId": tab_id, "action": action})

    def assert_no_writes(self, target):
        self.assertEqual(target.locator("#first").input_value(), "")
        self.assertEqual(target.evaluate("[fieldWrites,nextClicks,submitClicks,submitEvents]"), [0, 0, 0, 0])

    def test_journal_survives_reload_context_reopen_and_port_change(self):
        if sync_playwright is None:
            self.fail("Playwright is required for loaded MV3 evidence")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            extension = root / "extension"
            shutil.copytree(HERE / "extension", extension)
            manifest_path = extension / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["host_permissions"].append("https://mode-fixture.example.invalid/*")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            if os.environ.get("PORTAL_MV3_MUTATE_INTERSECTION") == "1":
                broker_path = extension / "background.js"
                original = broker_path.read_text(encoding="utf-8")
                removed = original.replace("latest === true || applicationRestrictions.has(key)",
                                           "applicationRestrictions.has(key)")
                self.assertNotEqual(removed, original)
                broker_path.write_text(removed, encoding="utf-8")
            (extension / "adapters/mv3-fixture.js").write_text("""(() => {
              const generic=PortalAdapters.forLocation('');
              PortalAdapters.register({...generic,id:'mv3_fixture',
                hosts:[/^mode-fixture\\.example\\.invalid$/],requiresApplicationMode:true});
            })();\n""", encoding="utf-8")
            first = FabricatedHelper()
            second = FabricatedHelper()
            context = None
            try:
                with sync_playwright() as playwright:
                    context, target, control, tab_id = self.launch(playwright, root / "profile", extension)
                    control.evaluate("({server,token}) => chrome.storage.local.set({server,token})",
                                     {"server": first.url, "token": TOKEN})
                    self.inject(control, tab_id, 11)
                    self.assertEqual(self.run_action(control, tab_id, "read"), "allowed")
                    target.evaluate("document.body.insertAdjacentHTML('afterbegin', '<div class=\"cf-turnstile\" style=\"height:40px\">Gate</div>')")
                    restriction = self.run_action(control, tab_id, "read")
                    self.assertIn("CAPTCHA restriction could not be saved", restriction)
                    self.assertEqual(control.evaluate("key => chrome.storage.local.get(key).then(x => x[key])", JOURNAL_KEY), True)
                    self.assertNotIn(11, first.restricted)
                    target.reload()
                    self.inject(control, tab_id, 11)
                    self.assertIn("restricted", self.run_action(control, tab_id, "read"))
                    self.assertEqual(self.run_action(control, tab_id, "fill")[0]["status"], "refused")
                    self.assertEqual(self.run_action(control, tab_id, "next")["status"], "refused")
                    self.assert_no_writes(target)
                    control.evaluate("server => chrome.storage.local.set({server})", second.url)
                    context.close()
                    context = None
                    context, target, control, tab_id = self.launch(playwright, root / "profile", extension)
                    self.inject(control, tab_id, 11)
                    self.assertEqual(control.evaluate("key => chrome.storage.local.get(key).then(x => x[key])", JOURNAL_KEY), True)
                    self.assertIn("restricted", self.run_action(control, tab_id, "read"))
                    self.assertEqual(self.run_action(control, tab_id, "fill")[0]["status"], "refused")
                    self.assertEqual(self.run_action(control, tab_id, "next")["status"], "refused")
                    self.assert_no_writes(target)
                    second.application_id = 12
                    self.inject(control, tab_id, 12)
                    self.assertEqual(self.run_action(control, tab_id, "read"), "allowed")
                    self.assert_no_writes(target)
                    self.assertTrue(any(method == "GET" and path.endswith("/fill-mode")
                                        for method, path in second.requests))
                    self.assertEqual(second.restricted, set())
                    context.close()
                    context = None
            finally:
                first.close()
                second.close()
