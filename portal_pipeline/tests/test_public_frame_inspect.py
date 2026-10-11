"""Read-only same-origin frame inspection in a loaded extension, on fabricated pages only."""
import tempfile
import unittest

from browser_test_support import BROWSER_CHANNEL, HERE, SyntheticBrowserTest

EXTENSION = HERE / "extension"
ORIGIN = "http://127.0.0.1:18766"
TOP_URL = ORIGIN + "/fixture"
TOP = '<h1>Employer</h1><label>Top name<input id="top-name" value="Top untouched"></label><iframe id="form-frame" src="/frame" style="width:400px;height:200px"></iframe>'
FRAME = '<label>Frame name<input id="frame-name" value="Frame untouched"></label><label>Frame email<input id="frame-email" type="email"></label><input type="password" id="frame-secret" value="SYNTHETIC_SECRET">'


class PublicFrameInspectTests(SyntheticBrowserTest):
    def test_static_wiring(self):
        review = (EXTENSION / "review.js").read_text(encoding="utf-8")
        self.assertIn("const send = (frameId, message)", review)
        self.assertIn("await injectFrames();", review)
        self.assertFalse((EXTENSION / "frame-bridge.js").exists())
        bridge = (EXTENSION / "page-bridge.js").read_text(encoding="utf-8")
        self.assertIn('frameAdapter?.frameFill !== true', bridge)
        popup = (EXTENSION / "popup.js").read_text(encoding="utf-8")
        self.assertNotIn("adapters/icims.js", popup)

    def test_loaded_review_inspects_same_origin_frame_read_only(self):
        with tempfile.TemporaryDirectory() as profile:
            context = self.playwright.chromium.launch_persistent_context(
                profile, channel=BROWSER_CHANNEL or "chromium", headless=True,
                args=[f"--disable-extensions-except={EXTENSION}", f"--load-extension={EXTENSION}"])
            try:
                workers = context.service_workers
                worker = workers[0] if workers else context.wait_for_event("serviceworker")
                origin = "chrome-extension://" + worker.url.split("/")[2] + "/"

                def route_request(route):
                    url = route.request.url
                    if url.startswith(origin):
                        route.continue_()
                    elif url == TOP_URL:
                        route.fulfill(content_type="text/html", body=TOP)
                    elif url == ORIGIN + "/frame":
                        route.fulfill(content_type="text/html", body=FRAME)
                    else:
                        route.abort()

                context.route("**/*", route_request)
                target = context.new_page()
                target.goto(TOP_URL)
                review = context.new_page()
                review.goto(origin + "review.html")
                review.evaluate("server => chrome.storage.local.set({server})", ORIGIN)
                tab_id = review.evaluate("async url => (await chrome.tabs.query({})).find(tab => tab.url === url).id", TOP_URL)
                review.goto(origin + f"review.html?tab={tab_id}&mode=inspect")
                review.locator("#portal-panel-host").wait_for()
                heading = review.locator("#portal-panel-host h3").filter(has_text="Read only.")
                heading.wait_for(timeout=8000)
                frame_id = int(heading.inner_text().split()[1])
                text = review.locator("#portal-panel-host").evaluate("node => node.shadowRoot.textContent")
                self.assertIn("Frame name", text)
                self.assertIn("Frame email", text)
                self.assertIn("Top name", text)
                self.assertNotIn("SYNTHETIC_SECRET", text)
                self.assertNotIn("frame-secret", text)
                # The frame answers inspect only; scan, fill and mode messages get no response from it.
                frames = review.evaluate("""async ({tabId, frameId}) => {
                  const out = {};
                  for (const type of ['portal-scan', 'portal-fill', 'portal-mode', 'portal-progress']) {
                    try { out[type] = await chrome.tabs.sendMessage(tabId, {type, tabId, profile: {values: {}}, selections: []}, {frameId}); }
                    catch (error) { out[type] = 'no-response'; }
                  }
                  return out;
                }""", {"tabId": tab_id, "frameId": frame_id})
                for type, value in frames.items():
                    self.assertIn(value, ("no-response", None), type)
                frame = target.frame_locator("#form-frame")
                self.assertEqual(frame.locator("#frame-name").input_value(), "Frame untouched")
                self.assertEqual(frame.locator("#frame-secret").input_value(), "SYNTHETIC_SECRET")
                self.assertEqual(target.locator("#top-name").input_value(), "Top untouched")
            finally:
                context.close()


if __name__ == "__main__":
    unittest.main()
