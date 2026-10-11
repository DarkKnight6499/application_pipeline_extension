"""Read-only handoff resolution on fabricated pages only."""
import tempfile
import unittest

from browser_test_support import BROWSER_CHANNEL, HERE, SyntheticBrowserTest

EXTENSION = HERE / "extension"
HANDOFF = EXTENSION / "handoff.js"
URL = "https://careers-frontend.example.invalid/job/1"
RESOLVE_CASES = [
    ("https://acme.wd5.myworkdayjobs.com/en/x", "workday", "routed"),
    ("https://job-boards.greenhouse.io/acme/jobs/1", "greenhouse", "routed"),
    ("https://careers.marsh.com/apply", "phenom", "routed"),
    ("https://jobs.lever.co/acme/1", "lever", "prepared"),
    ("https://jobs.ashbyhq.com/acme/1", "ashby", "prepared"),
    ("https://jpmc.fa.oraclecloud.com/hcmUI/x", "oracle", "prepared"),
    ("https://acme.taleo.net/careersection/x", "taleo", "prepared"),
    ("https://career5.successfactors.com/x", "successfactors", "prepared"),
    ("https://jobs.smartrecruiters.com/Acme/1", "smartrecruiters", "prepared"),
    ("https://sjobs.brassring.com/x", "brassring", "prepared"),
    ("https://acme.eightfold.ai/careers", "eightfold", "prepared"),
    ("https://careers-acme.icims.com/jobs/1/apply", "icims", "inspect_only"),
    ("https://acme.avature.net/careers", "other", "fallback"),
    ("https://greenhouse.io.evil.invalid/x", "unknown", "fallback"),
    ("https://evilgreenhouse.io/x", "unknown", "fallback"),
    ("https://myworkdayjobs.com.evil.invalid/x", "unknown", "fallback"),
    ("https://tracker.example.invalid/r/abc", "unknown", "fallback"),
]
REJECTED = ["http://jobs.lever.co/a", "javascript:void(0)", "mailto:a@example.invalid", "https://user:pw@jobs.lever.co/a", "https://", "file:///x"]
PAGE = """<h1>Job</h1>
<a href="https://jobs.lever.co/acme/1">Apply now</a>
<a href="https://acme.wd5.myworkdayjobs.com/en/x">Apply</a>
<a href="https://tracker.example.invalid/r/abc">Apply for this job</a>
<a href="https://jobs.lever.co/acme/1">Apply now</a>
<a href="https://jobs.ashbyhq.com/acme/1" hidden>Apply hidden</a>
<a href="https://jobs.ashbyhq.com/acme/2" style="display:none">Apply none</a>
<a href="http://jobs.lever.co/acme/3">Apply insecure</a>
<a href="https://careers.example.invalid/about">About us</a>
<button type="button" id="b">Apply</button>"""


class PublicHandoffTests(SyntheticBrowserTest):
    def open_handoff(self, markup=PAGE):
        self.open_markup(markup, URL)
        self.page.add_script_tag(path=str(HANDOFF))

    def test_resolve_table(self):
        self.open_handoff()
        for href, ats, support in RESOLVE_CASES:
            with self.subTest(href=href):
                result = self.page.evaluate("href => PortalHandoff.resolve(href)", href)
                self.assertEqual((result["ats"], result["support"]), (ats, support))

    def test_unsafe_targets_rejected(self):
        self.open_handoff()
        for href in REJECTED:
            with self.subTest(href=href):
                self.assertIsNone(self.page.evaluate("href => PortalHandoff.resolve(href)", href))

    def test_scan_is_read_only_deduplicated_and_never_follows(self):
        self.open_handoff()
        self.page.evaluate("globalThis.events = 0; ['click','focus','input','change'].forEach(n => document.addEventListener(n, () => events++, true))")
        before = self.page.evaluate("document.body.innerHTML")
        links = self.page.evaluate("PortalHandoff.scan(document)")
        self.assertEqual([(l["ats"], l["host"]) for l in links],
                         [("lever", "jobs.lever.co"), ("workday", "acme.wd5.myworkdayjobs.com"), ("unknown", "tracker.example.invalid")])
        self.assertEqual(self.page.evaluate("document.body.innerHTML"), before)
        self.assertEqual(self.page.evaluate("events"), 0)
        self.assertEqual(self.page.url, URL)
        self.assertEqual(self.page.evaluate("[syntheticSubmitClicks, syntheticSubmitEvents]"), [0, 0])

    def test_static_wiring(self):
        for name in ("popup.js", "review.js"):
            text = (EXTENSION / name).read_text(encoding="utf-8")
            self.assertLess(text.index("adapters/generic.js"), text.index("handoff.js"), name)
            self.assertLess(text.index("handoff.js"), text.rindex("page-bridge.js"), name)
        frame_line = next(line for line in (EXTENSION / "review.js").read_text(encoding="utf-8").splitlines() if line.startswith("const FRAME_FILES"))
        self.assertNotIn("handoff", frame_line)

    def test_loaded_review_lists_apply_links_without_following(self):
        origin_url = "http://127.0.0.1:18766"
        top = origin_url + "/fixture"
        with tempfile.TemporaryDirectory() as profile:
            context = self.playwright.chromium.launch_persistent_context(
                profile, channel=BROWSER_CHANNEL or "chromium", headless=True,
                args=[f"--disable-extensions-except={EXTENSION}", f"--load-extension={EXTENSION}"])
            try:
                workers = context.service_workers
                worker = workers[0] if workers else context.wait_for_event("serviceworker")
                ext = "chrome-extension://" + worker.url.split("/")[2] + "/"
                hits = []

                def route_request(route):
                    url = route.request.url
                    if url.startswith(ext):
                        route.continue_()
                    elif url == top:
                        route.fulfill(content_type="text/html", body=PAGE)
                    else:
                        hits.append(url)
                        route.abort()

                context.route("**/*", route_request)
                target = context.new_page()
                target.goto(top)
                review = context.new_page()
                review.goto(ext + "review.html")
                review.evaluate("server => chrome.storage.local.set({server})", origin_url)
                tab_id = review.evaluate("async url => (await chrome.tabs.query({})).find(tab => tab.url === url).id", top)
                review.goto(ext + f"review.html?tab={tab_id}&mode=inspect")
                review.locator("#portal-panel-host").wait_for()
                review.locator("#portal-panel-host h3").filter(has_text="Apply links").wait_for(timeout=8000)
                text = review.locator("#portal-panel-host").evaluate("node => node.shadowRoot.textContent")
                self.assertIn("jobs.lever.co: lever, prepared", text)
                self.assertIn("myworkdayjobs.com: workday, routed", text)
                self.assertIn("unrecognized ATS", text)
                self.assertEqual(hits, [])
                self.assertEqual(target.url, top)
            finally:
                context.close()


if __name__ == "__main__":
    unittest.main()
