"""Isolated browser harness with fabricated pages and no workflow dependency."""
import os
import unittest
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

# Test configuration
HERE = Path(__file__).resolve().parents[1]
BROWSER_CHANNEL = os.environ.get("PORTAL_TEST_BROWSER", "")
SYNTHETIC_URL = "https://safety-fixture.myworkdayjobs.com/application"
ENGINE_SCRIPTS = ["adapters/aria-listbox.js", "adapters/greenhouse.js", "engine.js"]
BOUNDARY_MARKUP = """
<label>Untouched field<input id="untouched" value="Keep untouched"></label>
<label>Signature<input id="signature"></label>
<label>I certify this application<input id="certification" type="checkbox"></label>
<button id="submit" type="submit">Submit application</button>
"""


class SyntheticBrowserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sync_playwright is None:
            raise unittest.SkipTest("Install requirements-dev.txt for synthetic browser tests.")
        cls.playwright = sync_playwright().start()
        try:
            cls.browser = cls.playwright.chromium.launch(headless=True, channel=BROWSER_CHANNEL or None)
        except Exception:
            cls.playwright.stop()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context()
        self.context.route("**/*", lambda route: route.abort())
        self.page = self.context.new_page()
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))

    def open_markup(self, markup, url=SYNTHETIC_URL):
        self.context.route(url, lambda route: route.fulfill(content_type="text/html", body=markup + BOUNDARY_MARKUP))
        self.page.goto(url)
        self.page.evaluate("""() => {
          globalThis.syntheticSubmitClicks = 0;
          globalThis.syntheticSubmitEvents = 0;
          document.addEventListener('click', event => {
            if (event.target.closest('button[type=submit],input[type=submit],input[type=image]')) syntheticSubmitClicks++;
          }, true);
          document.addEventListener('submit', event => {syntheticSubmitEvents++; event.preventDefault();}, true);
        }""")
        for script in ENGINE_SCRIPTS:
            self.page.add_script_tag(path=str(HERE / "extension" / script))

    def scan(self, values=None):
        return self.page.evaluate("values => PortalEngine.scan({values})", values or {})

    def fill(self, selections, options=None):
        return self.page.evaluate("async ({selections, options}) => PortalEngine.fill(selections, options)",
                                  {"selections": selections, "options": options or {}})

    def tearDown(self):
        try:
            if self.page.locator("#untouched").count():
                self.assertEqual(self.page.locator("#untouched").input_value(), "Keep untouched")
                self.assertEqual(self.page.locator("#signature").input_value(), "")
                self.assertFalse(self.page.locator("#certification").is_checked())
                self.assertEqual(self.page.evaluate("syntheticSubmitClicks"), 0)
                self.assertEqual(self.page.evaluate("syntheticSubmitEvents"), 0)
            self.assertEqual(self.errors, [])
        finally:
            self.context.close()
