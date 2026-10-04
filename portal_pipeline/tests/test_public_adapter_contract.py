"""Adapter interface and registry contract checks on fabricated pages only."""
import json
import re

from browser_test_support import HERE, SYNTHETIC_URL, SyntheticBrowserTest

# Synthetic contract configuration
FIXTURE_HTML = HERE / "fixtures/workday.html"
GREENHOUSE_URL = "https://job-boards.greenhouse.io/synthetic/jobs/1"
UNKNOWN_URL = "https://other.example.invalid/apply"
REQUIRED_METHODS = ["humanGate", "scan", "propose", "fill", "upload", "verify", "nextStep", "detectFinalReview"]
CAPTCHA_MARKUP = '<label>First name<input id="first"></label><iframe src="https://newassets.hcaptcha.com/captcha/v1/frame.html"></iframe>'
# Pre-refactor scan of step one of the synthetic fixture: [field id, classified key].
LEGACY_SNAPSHOT = [
    ["first name|text|0", "first_name"], ["last name|text|0", "last_name"], ["email|email|0", "email"],
    ["phone|text|0", "phone"], ["street address|text|0", None],
    ["are you authorized to work in the us|select-one|0", "authorized_us"],
    ["do you require sponsorship now|select-one|0", "sponsorship_now"],
    ["will you require sponsorship in the future|select-one|0", "sponsorship_future"],
    ["do you require sponsorship|select-one|0", None], ["password|password|0", None],
    ["gender|select-one|0", None], ["are you willing to relocate|combobox|0", "relocation"]]


class PublicAdapterContractTests(SyntheticBrowserTest):
    def test_registry_rejects_missing_method(self):
        self.open_markup("")
        for method in REQUIRED_METHODS:
            with self.subTest(method=method):
                message = self.page.evaluate("""method => {
                  const adapter = {...PortalAdapters.forLocation('https://other.example.invalid/'), id: 'probe-' + method};
                  delete adapter[method];
                  try { PortalAdapters.register(adapter); return ''; } catch (error) { return error.message; }
                }""", method)
                self.assertIn(method, message)
        self.assertNotIn("probe-verify", [item["id"] for item in self.page.evaluate("PortalAdapters.list()")])

    def test_registry_rejects_duplicate_id(self):
        self.open_markup("")
        message = self.page.evaluate("""() => {
          const adapter = {...PortalAdapters.forLocation('https://other.example.invalid/'), id: 'probe-dup'};
          PortalAdapters.register(adapter);
          try { PortalAdapters.register({...adapter}); return ''; } catch (error) { return error.message; }
        }""")
        self.assertIn("probe-dup", message)

    def test_for_location_routes_greenhouse_and_falls_back_to_generic(self):
        self.open_markup("")
        route = lambda url: self.page.evaluate("url => PortalAdapters.forLocation(url).id", url)
        self.assertEqual(route(GREENHOUSE_URL), "greenhouse")
        self.assertEqual(route(SYNTHETIC_URL), "workday")
        self.assertEqual(route(UNKNOWN_URL), "generic")
        self.assertEqual(route("not a URL"), "generic")
        listing = self.page.evaluate("PortalAdapters.list()")
        self.assertEqual({item["id"] for item in listing}, {"generic", "workday", "greenhouse"})
        for item in listing:
            self.assertEqual(set(item), {"id", "version", "mode", "hosts"})

    def test_generic_scan_matches_legacy_scan(self):
        markup = re.sub(r"<script\b[^>]*>.*?</script>", "", FIXTURE_HTML.read_text(encoding="utf-8"), flags=re.DOTALL)
        self.open_markup(markup)
        for expression in ("PortalEngine.scan({values: {}})",
                           "PortalAdapters.forLocation(location.href).scan({values: {}}, {bindings: {}})"):
            with self.subTest(expression=expression):
                fields = self.page.evaluate(expression)
                kept = [field for field in fields if not field["structure"]["dom_id"].startswith("guard-")]
                self.assertEqual([[field["id"], field["key"]] for field in kept], LEGACY_SNAPSHOT)

    def test_human_gate_blocks_all_writes(self):
        self.open_markup(CAPTCHA_MARKUP)
        gate = self.page.evaluate("PortalAdapters.forLocation(location.href).humanGate(document)")
        self.assertEqual(gate["kind"], "captcha")
        fields = self.scan()
        selections = [{"id": field["id"], "value": "Synthetic"} for field in fields if field["key"] == "first_name"]
        self.assertEqual(len(selections), 1)
        results = self.fill(selections)
        self.assertEqual([item["status"] for item in results], ["blocked_by_human_gate"])
        self.assertEqual(self.page.locator("#first").input_value(), "")

    def test_no_submit_click_through_interface(self):
        self.open_markup('<form><label>First name<input id="first"></label><button type="button" id="next">Next</button></form>')
        self.page.evaluate("""() => {
          globalThis.anyButtonClicks = 0;
          document.addEventListener('click', event => { if (event.target.closest('button,input[type=submit]')) anyButtonClicks++; }, true);
        }""")
        fields = self.scan()
        first = next(field for field in fields if field["key"] == "first_name")
        self.fill([{"id": first["id"], "value": "Synthetic"}])
        report = self.page.evaluate("""() => {
          const adapter = PortalAdapters.forLocation(location.href);
          return {next: adapter.nextStep(), review: adapter.detectFinalReview(), gate: adapter.humanGate(document)};
        }""")
        self.assertEqual(report["next"]["kind"], "none")
        self.assertEqual(report["review"], {"final": False, "reasons": []})
        self.assertIsNone(report["gate"])
        self.assertEqual(self.page.evaluate("[syntheticSubmitClicks, syntheticSubmitEvents, anyButtonClicks]"), [0, 0, 0])
        self.assertEqual(self.page.locator("#first").input_value(), "Synthetic")

    def test_password_control_is_never_written_or_read(self):
        self.open_markup('<label>First name<input id="first"></label><label>Password<input id="secret" type="password" value="SYNTHETIC_SECRET"></label>')
        fields = self.scan()
        first = next(field for field in fields if field["key"] == "first_name")
        results = self.fill([{"id": first["id"], "value": "Synthetic"}])
        self.assertEqual([item["status"] for item in results], ["filled"])
        self.assertEqual(self.page.locator("#first").input_value(), "Synthetic")
        self.assertEqual(self.page.locator("#secret").input_value(), "SYNTHETIC_SECRET")
        self.assertNotIn("SYNTHETIC_SECRET", json.dumps(fields) + json.dumps(results))
