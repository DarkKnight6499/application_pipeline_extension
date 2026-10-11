"""Regression tests for the advisor-reviewed hardening items, on fabricated pages only."""
import sys
import tempfile
import unittest
from pathlib import Path

from browser_test_support import HERE, SyntheticBrowserTest

sys.path.insert(0, str(HERE))
import export_intake

EXTENSION = HERE / "extension"
URL = "https://hardening-fixture.example.invalid/page"
CALL = """async ({message, sender}) => new Promise(resolve => {
  const timer = setTimeout(() => resolve('no-response'), 2000);
  listeners[0](message, sender, value => { clearTimeout(timer); resolve(value); });
})"""


class BackgroundSenderTests(SyntheticBrowserTest):
    def setUp(self):
        super().setUp()
        self.open_markup("<h1>Fixture</h1>", URL)
        self.page.evaluate("""() => {
          globalThis.listeners = [];
          globalThis.fetchCalls = 0;
          globalThis.chrome = {storage: {local: {get: async () => ({}), set: async () => {}}},
            runtime: {id: 'extid', getURL: path => 'chrome-extension://extid/' + path, onMessage: {addListener: fn => listeners.push(fn)}}};
          globalThis.fetch = async () => { fetchCalls++; throw Error('network not expected'); };
        }""")
        self.page.add_script_tag(path=str(EXTENSION / "background.js"))

    def call(self, sender):
        return self.page.evaluate(CALL, {"message": {"type": "portal-api", "path": "/api/current"}, "sender": sender})

    def test_content_script_sender_is_refused(self):
        for sender in ({"id": "extid", "url": URL, "tab": {"id": 3}, "frameId": 0},
                       {"id": "extid", "url": URL, "tab": {"id": 3}, "frameId": 4},
                       {"id": "other", "url": "chrome-extension://extid/review.html"},
                       {"id": "extid"},
                       {"id": "extid", "url": "chrome-extension://extid.evil.invalid/review.html"}):
            with self.subTest(sender=sender):
                result = self.call(sender)
                self.assertEqual(result["ok"], False)
                self.assertIn("limited to the extension's own pages", result["error"])
        self.assertEqual(self.page.evaluate("fetchCalls"), 0)

    def test_extension_page_sender_passes_the_sender_check(self):
        result = self.call({"id": "extid", "url": "chrome-extension://extid/review.html?tab=7"})
        self.assertNotIn("own pages", result.get("error", ""))
        self.assertIn("Pair the extension", result["error"])


class HandoffWorkdaySiteTests(SyntheticBrowserTest):
    def test_myworkdaysite_is_fallback_not_routed(self):
        self.open_markup("<h1>x</h1>", URL)
        self.page.add_script_tag(path=str(EXTENSION / "handoff.js"))
        site = self.page.evaluate("PortalHandoff.resolve('https://tenant.myworkdaysite.com/recruiting/x')")
        jobs = self.page.evaluate("PortalHandoff.resolve('https://tenant.myworkdayjobs.com/x')")
        self.assertEqual((site["ats"], site["support"]), ("workday", "fallback"))
        self.assertEqual((jobs["ats"], jobs["support"]), ("workday", "routed"))
        self.assertEqual(self.page.evaluate("PortalHandoff.resolve('https://evilmyworkdaysite.com/x').ats"), "unknown")


class ExportIntakeOutDirTests(unittest.TestCase):
    def test_tracked_repo_paths_are_refused(self):
        root = export_intake.REPO_ROOT
        for path in (root / "docs", root / "portal_pipeline" / "fixtures", root, root / "portal_pipeline" / "extension"):
            with self.subTest(path=path):
                self.assertFalse(export_intake.out_dir_allowed(path))

    def test_outside_and_ignored_paths_are_allowed(self):
        root = export_intake.REPO_ROOT
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(export_intake.out_dir_allowed(Path(tmp) / "drafts"))
        self.assertTrue(export_intake.out_dir_allowed(root / "portal_pipeline" / "data" / "exports" / "drafts"))
        self.assertFalse(export_intake.out_dir_allowed(root / "portal_pipeline" / "data" / ".." / "extension"))


if __name__ == "__main__":
    unittest.main()
