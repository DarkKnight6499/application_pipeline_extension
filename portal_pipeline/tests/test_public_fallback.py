"""Answer-sheet fallback for unrouted hosts, on fabricated example.invalid pages only."""
import json
import unittest

from browser_test_support import HERE, SyntheticBrowserTest

EXTENSION = HERE / "extension"
FALLBACK = EXTENSION / "adapters" / "fallback.js"
UNROUTED = "https://unrouted-fixture.example.invalid/apply"
PAIRING_ORIGIN = "http://127.0.0.1:18766"
FORM = '<h1>Application</h1><label>First name<input id="first-name" name="firstName"></label><button type="button" id="next">Next</button><button type="button" id="submit-application">Submit application</button>'
MODE_CASES = [
    ("https://tenant.myworkdayjobs.com/apply", None, "native"),
    ("https://job-boards.greenhouse.io/jobs/1", None, "native"),
    ("https://jobs.unknown-ats.example.invalid/apply", None, "fallback"),
    ("https://careers.example.invalid/", None, "fallback"),
    (PAIRING_ORIGIN + "/fixture", PAIRING_ORIGIN, "native"),
    (PAIRING_ORIGIN + "/other", PAIRING_ORIGIN, None),
    ("http://jobs.example.invalid/apply", None, None),
    ("https://localhost/apply", None, None),
    ("https://app.localhost/apply", None, None),
    ("https://intranet/apply", None, None),
    ("https://10.0.0.5/apply", None, None),
    ("https://[::1]/apply", None, None),
    ("https://user:pw@jobs.example.invalid/apply", None, None),
    ("https://printer.local/apply", None, None),
    ("file:///apply", None, None),
    ("not a URL", None, None),
]


class PublicFallbackTests(SyntheticBrowserTest):
    def open_fallback(self, markup=FORM, activate=True):
        self.open_markup(markup, UNROUTED)
        if activate:
            self.page.add_script_tag(path=str(FALLBACK))

    def test_policy_modes(self):
        self.page.add_script_tag(path=str(EXTENSION / "host-policy.js"))
        for url, paired, expected in MODE_CASES:
            with self.subTest(url=url):
                actual = self.page.evaluate("({url, paired}) => PortalHostPolicy.mode(url, paired)", {"url": url, "paired": paired})
                self.assertEqual(actual, expected)

    def test_supported_is_unchanged_by_fallback(self):
        self.page.add_script_tag(path=str(EXTENSION / "host-policy.js"))
        self.assertFalse(self.page.evaluate("PortalHostPolicy.supported('https://jobs.unknown-ats.example.invalid/', null)"))

    def test_fallback_routes_only_when_injected(self):
        self.open_fallback(activate=False)
        self.assertEqual(self.page.evaluate("PortalAdapters.forLocation(location.href).id"), "generic")
        self.page.add_script_tag(path=str(FALLBACK))
        self.assertEqual(self.page.evaluate("PortalAdapters.forLocation(location.href).id"), "fallback")
        self.assertEqual(self.page.evaluate("PortalAdapters.forLocation('https://x.myworkdayjobs.com/a').id"), "workday")
        entry = next(item for item in self.page.evaluate("PortalAdapters.list()") if item["id"] == "fallback")
        self.assertEqual((entry["mode"], entry["hosts"]), ("answer_sheet_only", []))

    def test_scan_is_read_only(self):
        self.open_fallback()
        self.page.evaluate("globalThis.events = 0; ['input','change','focus','click'].forEach(name => document.addEventListener(name, () => events++, true))")
        before = self.page.evaluate("document.body.innerHTML")
        fields = [f for f in self.scan() if not f["structure"]["dom_id"].startswith("guard-")]
        self.assertEqual([f["structure"]["dom_id"] for f in fields], ["first-name"])
        self.assertEqual(self.page.evaluate("document.body.innerHTML"), before)
        self.assertEqual(self.page.evaluate("events"), 0)

    def test_fill_and_upload_never_write(self):
        self.open_fallback()
        field = next(f for f in self.scan() if f["structure"]["dom_id"] == "first-name")
        result = self.fill([{"id": field["id"], "value": "Synthetic"}])
        self.assertEqual(result[0]["status"], "refused")
        self.assertEqual(self.page.locator("#first-name").input_value(), "")
        upload = self.page.evaluate("PortalAdapters.forLocation(location.href).upload({field: {id: 'x'}}, {name: 'a.docx'}, {selection: {id: 'x'}})")
        self.assertEqual(upload["status"], "refused")
        self.assertEqual(self.page.evaluate("[syntheticSubmitClicks, syntheticSubmitEvents]"), [0, 0])

    def test_guarded_next_refused(self):
        self.open_fallback()
        self.page.add_script_tag(path=str(EXTENSION / "progress.js"))
        self.assertEqual(self.page.evaluate("PortalProgress.guardedNext(PortalAdapters.forLocation(location.href)).then(result => result.status)"), "refused")
        self.assertEqual(self.page.evaluate("[syntheticSubmitClicks, syntheticSubmitEvents]"), [0, 0])

    def test_captcha_blocks_before_writer(self):
        self.open_fallback(FORM + '<iframe title="hCaptcha" src="https://hcaptcha.example.invalid/c" style="width:100px;height:80px"></iframe>')
        self.assertEqual(self.page.evaluate("PortalAdapters.forLocation(location.href).humanGate(document).kind"), "captcha")

    def test_manifest_permissions_unchanged(self):
        manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["host_permissions"], ["http://127.0.0.1/*"])
        self.assertNotIn("<all_urls>", json.dumps(manifest))

    def test_injection_lists_add_fallback_only_for_fallback_mode(self):
        for name in ("popup.js", "review.js"):
            text = (EXTENSION / name).read_text(encoding="utf-8")
            self.assertIn('routing === "fallback"', text, name)
            self.assertIn("adapters/fallback.js", text, name)
            self.assertLess(text.index("adapters/generic.js"), text.index("adapters/fallback.js"), name)


if __name__ == "__main__":
    unittest.main()
