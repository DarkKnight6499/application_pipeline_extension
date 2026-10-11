"""Frame fill boundaries for iCIMS-style forms, on fabricated pages and a mocked chrome API only."""
import json
import tempfile
import unittest

from browser_test_support import BROWSER_CHANNEL, HERE, SyntheticBrowserTest

EXTENSION = HERE / "extension"
FILES = ["adapters/registry.js", "adapters/generic.js", "adapters/aria-listbox.js", "adapters/icims.js", "classifier.js", "engine.js", "page-bridge.js"]
TOP_URL = "https://icims-fixture.example.invalid/jobs/1"
FRAME_URL = "https://icims-fixture.example.invalid/frame"
OTHER_URL = "https://other-fixture.example.invalid/frame"
SENDER = {"id": "extid", "url": "chrome-extension://extid/review.html?tab=7"}
FORM = ('<label>First name<input id="first-name" name="firstName" required></label>'
        '<label>Email<input id="email" name="email" type="email"></label>'
        '<input type="password" id="secret" value="SYNTHETIC_SECRET">'
        '<button type="button" id="next">Next</button><button type="submit" id="submit">Submit</button>')
MOCK = """() => {
  globalThis.listeners = [];
  globalThis.chrome = {runtime: {id: 'extid', getURL: path => 'chrome-extension://extid/' + path,
    onMessage: {addListener: fn => listeners.push(fn)}, sendMessage: () => Promise.reject(new Error('no broker in frame'))}};
  globalThis.syntheticSubmits = 0;
  document.addEventListener('submit', event => { event.preventDefault(); syntheticSubmits++; }, true);
  document.addEventListener('click', event => { if (event.target.closest('button[type=submit]')) syntheticSubmits++; }, true);
}"""
SEND = """async ({message, sender, wait}) => new Promise(resolve => {
  const timer = setTimeout(() => resolve('no-response'), wait);
  const answered = listeners[0](message, sender, value => { clearTimeout(timer); resolve(value); });
  if (answered !== true) setTimeout(() => {}, 0);
})"""


class PublicFrameFillTests(SyntheticBrowserTest):
    def open_frame(self, frame_url=FRAME_URL, route_adapter=True):
        self.context.route(frame_url, lambda route: route.fulfill(content_type="text/html", body=FORM))
        self.open_markup(f'<h1>Employer</h1><iframe id="f" src="{frame_url}" style="width:400px;height:200px"></iframe>', TOP_URL)
        self.page.locator("#f").wait_for()
        self.frame = next(f for f in self.page.frames if f.url == frame_url)
        self.frame.evaluate(MOCK)
        for name in FILES:
            self.frame.add_script_tag(path=str(EXTENSION / name))
        if route_adapter:
            host = frame_url.split("/")[2].replace(".", "\\.")
            self.frame.add_script_tag(content=f"PortalAdapters.register({{...PortalIcimsAdapter, id: 'icims_fixture', hosts: [/^{host}$/]}})")

    def send(self, type, frame_url=FRAME_URL, wait=4000, **body):
        message = {"type": type, "tabId": 7, "frameUrl": frame_url, **body}
        return self.frame.evaluate(SEND, {"message": message, "sender": SENDER, "wait": wait})

    def test_inspect_reports_frame_fill_adapter(self):
        self.open_frame()
        result = self.send("portal-inspect")
        self.assertTrue(result["ok"])
        self.assertEqual(result["value"]["frame"], {"url": FRAME_URL, "adapter": "icims_fixture", "fill": True})
        self.assertNotIn("SYNTHETIC_SECRET", json.dumps(result))

    def test_scan_and_selected_fill_in_frame(self):
        self.open_frame()
        scan = self.send("portal-scan", profile={"values": {}}, bindings={})
        self.assertTrue(scan["ok"])
        first = next(f for f in scan["value"] if f["structure"]["dom_id"] == "first-name")
        fill = self.send("portal-fill", selections=[{"id": first["id"], "value": "Synthetic"}], options={})
        self.assertTrue(fill["ok"], fill)
        self.assertEqual(fill["value"][0]["status"], "filled")
        self.assertEqual(self.frame.locator("#first-name").input_value(), "Synthetic")
        self.assertEqual(self.frame.locator("#email").input_value(), "")
        self.assertEqual(self.frame.locator("#secret").input_value(), "SYNTHETIC_SECRET")
        self.assertEqual(self.frame.evaluate("syntheticSubmits"), 0)

    def test_frame_overwrite_off_preserves(self):
        self.open_frame()
        self.frame.locator("#first-name").evaluate("node => node.value = 'Existing'")
        scan = self.send("portal-scan", profile={"values": {}}, bindings={})
        first = next(f for f in scan["value"] if f["structure"]["dom_id"] == "first-name")
        self.send("portal-fill", selections=[{"id": first["id"], "value": "Synthetic"}], options={})
        self.assertEqual(self.frame.locator("#first-name").input_value(), "Existing")

    def test_changed_frame_url_refused(self):
        self.open_frame()
        result = self.send("portal-scan", frame_url=FRAME_URL + "?other", profile={"values": {}}, bindings={})
        self.assertEqual(result["ok"], False)
        self.assertIn("frame changed", result["error"])

    def test_progression_refused_in_frame(self):
        self.open_frame()
        result = self.send("portal-progress", action="next", applicationContext=None)
        self.assertEqual(result["ok"], False)
        self.assertEqual(self.frame.evaluate("syntheticSubmits"), 0)

    def test_mode_is_not_required_for_frame_adapter(self):
        self.open_frame()
        result = self.send("portal-mode", applicationContext=None)
        self.assertEqual(result, {"ok": True, "value": None})

    def test_unmarked_frame_serves_inspect_only(self):
        self.open_frame(route_adapter=False)
        self.assertTrue(self.send("portal-inspect")["ok"])
        for type in ("portal-scan", "portal-fill", "portal-mode", "portal-progress"):
            with self.subTest(type=type):
                self.assertEqual(self.send(type, wait=400, profile={"values": {}}, selections=[], options={}, applicationContext=None), "no-response")
        self.assertEqual(self.frame.locator("#first-name").input_value(), "")

    def test_cross_origin_frame_refused_even_with_frame_adapter(self):
        self.open_frame(frame_url=OTHER_URL)
        result = self.send("portal-scan", frame_url=OTHER_URL, profile={"values": {}}, bindings={})
        self.assertEqual(result["ok"], False)
        self.assertEqual(self.frame.locator("#first-name").input_value(), "")

    def test_icims_adapter_has_no_real_hosts(self):
        self.open_frame()
        entry = next(item for item in self.frame.evaluate("PortalAdapters.list()") if item["id"] == "icims")
        self.assertEqual(entry["hosts"], [])
        self.assertEqual(self.frame.evaluate("PortalAdapters.forLocation('https://careers-acme.icims.com/jobs/1').id"), "generic")

    def test_loaded_fill_mode_does_not_enter_unmarked_frame(self):
        origin = "http://127.0.0.1:18766"
        top = origin + "/fixture"
        with tempfile.TemporaryDirectory() as profile:
            context = self.playwright.chromium.launch_persistent_context(
                profile, channel=BROWSER_CHANNEL or "chromium", headless=True,
                args=[f"--disable-extensions-except={EXTENSION}", f"--load-extension={EXTENSION}"])
            try:
                workers = context.service_workers
                worker = workers[0] if workers else context.wait_for_event("serviceworker")
                ext = "chrome-extension://" + worker.url.split("/")[2] + "/"

                def route_request(route):
                    url = route.request.url
                    if url.startswith(ext):
                        route.continue_()
                    elif url == top:
                        route.fulfill(content_type="text/html", body='<iframe id="f" src="/frame"></iframe>')
                    elif url == origin + "/frame":
                        route.fulfill(content_type="text/html", body=FORM)
                    else:
                        route.abort()

                context.route("**/*", route_request)
                target = context.new_page()
                target.goto(top)
                review = context.new_page()
                review.goto(ext + "review.html")
                review.evaluate("server => chrome.storage.local.set({server})", origin)
                tab_id = review.evaluate("async url => (await chrome.tabs.query({})).find(tab => tab.url === url).id", top)
                review.goto(ext + f"review.html?tab={tab_id}")
                review.locator("#review-status").filter(has_text="Review stays inside").wait_for(timeout=8000)
                self.assertNotIn("Working inside the application frame", review.locator("#review-status").inner_text())
                frame = target.frame_locator("#f")
                self.assertEqual(frame.locator("#first-name").input_value(), "")
                self.assertEqual(frame.locator("#secret").input_value(), "SYNTHETIC_SECRET")
            finally:
                context.close()


if __name__ == "__main__":
    unittest.main()
