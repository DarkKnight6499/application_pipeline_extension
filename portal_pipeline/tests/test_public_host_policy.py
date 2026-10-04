"""Host-policy checks use isolated synthetic pages and extension storage."""
import tempfile

from browser_test_support import BROWSER_CHANNEL, HERE, SyntheticBrowserTest

# Synthetic host configuration
EXTENSION = HERE / "extension"
PAIRING_ORIGIN = "http://127.0.0.1:18766"
FIXTURE_URL = PAIRING_ORIGIN + "/fixture"
UNSUPPORTED_URL = PAIRING_ORIGIN + "/not-the-paired-fixture"
POLICY_ERROR = "Development is limited to Workday, Greenhouse, or the paired local fixture."
POLICY_CASES = [
    ("https://tenant.myworkdayjobs.com/apply", None, True),
    ("http://myworkdayjobs.com/apply", None, True),
    ("https://job-boards.greenhouse.io/jobs/123", None, True),
    ("https://greenhouse.io/", None, True),
    ("https://myworkdayjobs.com.evil.invalid/", None, False),
    ("https://evilmyworkdayjobs.com/", None, False),
    ("https://greenhouse.io.evil.invalid/", None, False),
    ("https://evilgreenhouse.io/", None, False),
    ("https://other.invalid/", None, False),
    ("file:///fixture", None, False),
    ("not a URL", None, False),
    (FIXTURE_URL, None, False),
    (FIXTURE_URL, PAIRING_ORIGIN, True),
    (FIXTURE_URL + "?page=2#section", PAIRING_ORIGIN, True),
    (FIXTURE_URL + "/", PAIRING_ORIGIN, False),
    (UNSUPPORTED_URL, PAIRING_ORIGIN, False),
    (FIXTURE_URL, "http://127.0.0.1:18767", False),
    (FIXTURE_URL, PAIRING_ORIGIN + "/", False),
]


class PublicHostPolicyTests(SyntheticBrowserTest):
    def test_supported_host_boundaries(self):
        self.page.add_script_tag(path=str(EXTENSION / "host-policy.js"))
        for url, paired_server, expected in POLICY_CASES:
            with self.subTest(url=url, paired_server=paired_server):
                actual = self.page.evaluate(
                    "({url, pairedServer}) => PortalHostPolicy.supported(url, pairedServer)",
                    {"url": url, "pairedServer": paired_server})
                self.assertEqual(actual, expected)

    def test_loaded_review_rejects_initial_and_navigated_unsupported_target(self):
        with tempfile.TemporaryDirectory() as profile:
            context = self.playwright.chromium.launch_persistent_context(
                profile, channel=BROWSER_CHANNEL or "chromium", headless=True,
                args=[f"--disable-extensions-except={EXTENSION}", f"--load-extension={EXTENSION}"])
            try:
                workers = context.service_workers
                worker = workers[0] if workers else context.wait_for_event("serviceworker")
                extension_origin = "chrome-extension://" + worker.url.split("/")[2] + "/"

                def route_request(route):
                    if route.request.url.startswith(extension_origin):
                        route.continue_()
                    elif route.request.url.startswith(PAIRING_ORIGIN + "/"):
                        route.fulfill(content_type="text/html", body='<label>First name<input value="Synthetic untouched"></label>')
                    else:
                        route.abort()

                context.route("**/*", route_request)
                target = context.new_page()
                target.goto(UNSUPPORTED_URL)
                review = context.new_page()
                review.goto(extension_origin + "review.html")
                review.evaluate("chrome.storage.local.clear()")
                tab_id = review.evaluate(
                    "async url => (await chrome.tabs.query({})).find(tab => tab.url === url).id", UNSUPPORTED_URL)
                review_url = extension_origin + f"review.html?tab={tab_id}&mode=inspect"
                review.goto(review_url)
                self.assert_rejected_without_bridge(review, tab_id)
                review.evaluate("server => chrome.storage.local.set({server})", PAIRING_ORIGIN)
                target.goto(FIXTURE_URL)
                review.goto(review_url)
                review.locator("#portal-panel-host").wait_for()
                review.locator("#portal-panel-host .note").filter(has_text="visible, unprotected").wait_for()
                target.goto(UNSUPPORTED_URL)
                review.locator("#rescan").click()
                self.assert_rejected_without_bridge(review, tab_id)
                self.assertEqual(target.locator("input").input_value(), "Synthetic untouched")
            finally:
                context.close()

    def assert_rejected_without_bridge(self, review, tab_id):
        review.locator("#review-status").filter(has_text=POLICY_ERROR).wait_for(timeout=3000)
        self.assertEqual(review.locator("#review-status").inner_text(), POLICY_ERROR)
        result = review.evaluate("""async tabId => {
            try { return await chrome.tabs.sendMessage(tabId, {type: 'portal-inspect'}); }
            catch (error) { return {connectionError: String(error)}; }
        }""", tab_id)
        self.assertIn("connectionError", result)
        self.assertIn("Receiving end does not exist", result["connectionError"])
