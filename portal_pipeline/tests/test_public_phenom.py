"""Phenom adapter checks on fabricated pages only (synthetic only, no Phenom export exists)."""
import json
import sys
import unittest

from browser_test_support import HERE
from replay_support import PAGES, ReplayBrowserTest, compare

sys.path.insert(0, str(HERE))
import answer_sheet

# Phenom test configuration
ADAPTER_SCRIPT = HERE / "extension" / "adapters" / "phenom.js"
PHENOM_DIR = PAGES / "phenom"
MANIFEST = PHENOM_DIR / "manifest.json"
MARSH_URL = "https://careers.marsh.com/synthetic/apply"
FRANKLIN_URL = "https://careers.franklintempleton.com/synthetic/apply"
HOST_SOURCES = {r"(^|\.)careers\.marsh\.com$", r"(^|\.)careers\.franklintempleton\.com$"}
STEP_PAGES = [f"page_{number}.html" for number in range(1, 6)]
INJECTION_FILES = ["popup.js", "review.js", "popup.html", "review.html"]
GATE_IFRAME = '<iframe title="reCAPTCHA" src="https://www.google.com/recaptcha/api2/anchor?synthetic=1"></iframe>'
GATE_WIDGET = '<div class="g-recaptcha" data-sitekey="synthetic"></div>'
HCAPTCHA_WIDGET = '<iframe title="hCaptcha" src="https://hcaptcha.com/synthetic"></iframe>'
TURNSTILE_WIDGET = '<div class="cf-turnstile"></div>'
FIRST_ID = "[id='name.first']"
LAST_ID = "[id='name.last']"
ADAPTER_CALL = "PortalAdapters.forLocation(location.href)"
COUNTERS = "[syntheticSubmitClicks, syntheticSubmitEvents, anyClicks]"


def page(name):
    return (PHENOM_DIR / name).read_text(encoding="utf-8")


class PhenomBase(ReplayBrowserTest):
    def open_markup(self, markup, url=MARSH_URL):
        super().open_markup(markup, url)
        self.page.add_script_tag(path=str(ADAPTER_SCRIPT))
        self.page.evaluate("globalThis.anyClicks = 0; document.addEventListener('click', () => anyClicks++, true)")

    def by_key(self, key):
        return next(field for field in self.scan() if field["key"] == key)

    def step(self):
        return self.page.evaluate(f"{ADAPTER_CALL}.stepInfo(document)")


class PublicPhenomTests(PhenomBase):
    def test_phenom_routes_to_adapter(self):
        self.open_markup(page("page_1.html"))
        route = lambda url: self.page.evaluate("url => PortalAdapters.forLocation(url).id", url)
        self.assertEqual(route(MARSH_URL), "phenom")
        self.assertEqual(route(FRANKLIN_URL), "phenom")
        for other in ("https://careers.marsh.com.evil.invalid/", "https://evilcareers.marsh.com.invalid/", "https://other.example.invalid/", "not a URL"):
            self.assertEqual(route(other), "generic", other)
        entry = next(item for item in self.page.evaluate("PortalAdapters.list()") if item["id"] == "phenom")
        self.assertEqual(set(entry["hosts"]), HOST_SOURCES)
        self.assertEqual(entry["mode"], "fill")

    def test_phenom_scan_is_read_only(self):
        self.open_markup(page("page_1.html"))
        snapshot = "JSON.stringify([...document.querySelectorAll('input,select,textarea')].map(el => [el.id, el.value, el.checked]))"
        self.page.evaluate("globalThis.events = 0; ['input','change','focus','click'].forEach(name => document.addEventListener(name, () => events++, true))")
        before = self.page.evaluate(snapshot)
        markup = self.page.evaluate("document.body.innerHTML")
        self.assertTrue(self.scan())
        self.page.evaluate(f"{ADAPTER_CALL}.detectFinalReview(); {ADAPTER_CALL}.nextStep(); {ADAPTER_CALL}.stepInfo(document)")
        self.assertEqual(self.page.evaluate(snapshot), before)
        self.assertEqual(self.page.evaluate("document.body.innerHTML"), markup)
        self.assertEqual(self.page.evaluate("events"), 0)

    def test_phenom_answer_sheet_mode_writes_nothing(self):
        self.open_markup(page("page_1.html"))
        self.page.evaluate("globalThis.events = 0; ['input','change','focus','click'].forEach(name => document.addEventListener(name, () => events++, true))")
        snapshot = "JSON.stringify([...document.querySelectorAll('input,select,textarea')].map(el => [el.id, el.value, el.checked]))"
        before = self.page.evaluate(snapshot)
        fields = self.scan({"first_name": {"value": "Synthetic", "source": "Fabricated fixture"}})
        sheet = answer_sheet.build_answer_sheet(
            {"company": "Synthetic Co", "role": "Synthetic Role", "resume_path": "Yazad_Madan.docx"},
            fields, url=MARSH_URL, heading=self.step()["heading"], now="2026-10-04T12:00:00+00:00")
        self.assertEqual(sheet["mode"], "answer_sheet_only")
        self.assertEqual(sheet["portal"], "phenom")
        self.assertEqual(sheet["page_key"], "careers.marsh.com/synthetic/apply#my information")
        self.assertIn("First name", answer_sheet.render_html(sheet))
        self.assertEqual(self.page.evaluate(snapshot), before)
        self.assertEqual(self.page.evaluate("events"), 0)

    def test_phenom_selected_only_fill(self):
        self.open_markup(page("page_1.html"))
        first = self.by_key("first_name")
        results = self.fill([{"id": first["id"], "value": "Synthetic"}])
        self.assertEqual([item["status"] for item in results], ["filled"])
        self.assertEqual(self.page.locator(FIRST_ID).input_value(), "Synthetic")
        for selector in (LAST_ID, "[id='contact.email']", "[id='phoneWidget.phoneNumber']", "[id='cntryFields.city']", "[id='cntryFields.country']"):
            self.assertEqual(self.page.locator(selector).input_value(), "", selector)

    def test_phenom_overwrite_off_preserves(self):
        self.open_markup(page("page_1.html"))
        self.page.evaluate("document.getElementById('name.first').value = 'Existing'")
        first = self.by_key("first_name")
        kept = self.fill([{"id": first["id"], "value": "Synthetic"}])
        self.assertNotEqual(kept[0]["status"], "filled")
        self.assertEqual(self.page.locator(FIRST_ID).input_value(), "Existing")
        first = self.by_key("first_name")
        forced = self.fill([{"id": first["id"], "value": "Synthetic"}], {"overwrite": True})
        self.assertEqual(forced[0]["status"], "filled")
        self.assertEqual(self.page.locator(FIRST_ID).input_value(), "Synthetic")

    def test_phenom_human_gate_blocks(self):
        for widget in (GATE_WIDGET, GATE_IFRAME):
            with self.subTest(widget=widget[:30]):
                self.open_markup(page("page_1.html").replace("<button", widget + "<button", 1))
                gate = self.page.evaluate(f"{ADAPTER_CALL}.humanGate(document)")
                self.assertEqual(gate["kind"], "captcha")
                fields = self.scan()
                results = self.fill([{"id": field["id"], "value": "Synthetic"} for field in fields if field["key"] in ("first_name", "last_name")])
                self.assertEqual({item["status"] for item in results}, {"blocked_by_human_gate"})
                self.assertEqual(self.page.locator(FIRST_ID).input_value(), "")
                self.assertEqual(self.page.locator(LAST_ID).input_value(), "")

    def test_phenom_other_captcha_gates_block(self):
        for widget in (HCAPTCHA_WIDGET, TURNSTILE_WIDGET):
            with self.subTest(widget=widget[:30]):
                self.open_markup(page("page_1.html").replace("<button", widget + "<button", 1))
                self.assertEqual(self.page.evaluate(f"{ADAPTER_CALL}.humanGate(document)")["kind"], "captcha")
                first = self.by_key("first_name")
                self.assertEqual(self.fill([{"id": first["id"], "value": "Synthetic"}])[0]["status"], "blocked_by_human_gate")
                self.assertEqual(self.page.locator(FIRST_ID).input_value(), "")

    def test_phenom_final_control_takes_priority_over_next(self):
        for label in ("Submit", "Apply", "Finish", "Review and Submit"):
            with self.subTest(label=label):
                markup = page("page_1.html").replace('<button type="button" id="next">Next</button>',
                    '<button type="button" id="next">Next</button><button type="submit" id="submit">' + label + '</button>')
                self.open_markup(markup)
                adapter = self.page.evaluate(f"""() => {{const a = {ADAPTER_CALL}; return {{review: a.detectFinalReview(), next: a.nextStep()}};}}""")
                self.assertTrue(adapter["review"]["final"])
                self.assertEqual(adapter["next"]["kind"], "final_review")
                self.assertEqual(self.page.evaluate(COUNTERS), [0, 0, 0])

    def test_phenom_final_review_detected(self):
        for name in STEP_PAGES:
            with self.subTest(page=name):
                self.open_markup(page(name))
                review = self.page.evaluate(f"{ADAPTER_CALL}.detectFinalReview()")
                self.assertEqual(review["final"], name == "page_5.html")
                self.assertEqual(bool(review["reasons"]), review["final"])
        step = self.page.evaluate(f"{ADAPTER_CALL}.nextStep()")
        self.assertEqual((step["kind"], step["label"]), ("final_review", "Submit"))

    def test_phenom_submit_counter_zero(self):
        for name in STEP_PAGES:
            with self.subTest(page=name):
                self.open_markup(page(name))
                fields = self.scan()
                if fields:
                    self.fill([{"id": field["id"], "value": "Synthetic"} for field in fields[:3]])
                self.page.evaluate(f"const a = {ADAPTER_CALL}; a.nextStep(); a.detectFinalReview(); a.humanGate(document)")
                self.assertEqual(self.page.evaluate(COUNTERS), [0, 0, 0])

    def test_phenom_wizard_page_keys_distinct(self):
        keys, indexes = [], []
        for name in STEP_PAGES:
            self.open_markup(page(name))
            info = self.step()
            indexes.append((info["index"], info["total"]))
            keys.append(answer_sheet.page_key(MARSH_URL, info["heading"]))
        self.assertEqual(indexes, [(number, 5) for number in range(1, 6)])
        self.assertEqual(len(set(keys)), 5, keys)
        self.assertEqual(keys[0], "careers.marsh.com/synthetic/apply#my information")

    def test_phenom_linkedin_iframe_ignored(self):
        self.open_markup(page("page_1.html"))
        fields = self.scan()
        self.assertFalse([field for field in fields if "linkedin import" in field["label"].lower()])
        self.assertEqual(self.page.evaluate("document.querySelectorAll('iframe').length"), 1)
        self.assertTrue(self.fill([{"id": field["id"], "value": "Synthetic"} for field in fields]))
        self.assertEqual(self.page.frames[1].locator("#li-frame-input").input_value(), "")
        self.assertIsNone(self.page.evaluate(f"{ADAPTER_CALL}.humanGate(document)"))

    def test_phenom_recaptcha_blocks(self):
        self.open_markup(page("gate_recaptcha.html"))
        gate = self.page.evaluate(f"{ADAPTER_CALL}.humanGate(document)")
        self.assertEqual((gate["kind"], bool(gate["evidence"])), ("captcha", True))
        results = self.fill([{"id": field["id"], "value": "Synthetic"} for field in self.scan()])
        self.assertEqual({item["status"] for item in results}, {"blocked_by_human_gate"})
        self.assertEqual(self.page.locator(FIRST_ID).input_value(), "")
        self.assertEqual(self.page.locator("[id='cntryFields.country']").input_value(), "")
        self.assertEqual(self.page.evaluate(COUNTERS), [0, 0, 0])


class PublicPhenomReplayAndWiringTests(PhenomBase):
    def test_phenom_replay_cases(self):
        text = MANIFEST.read_text(encoding="utf-8")
        cases = json.loads(text)["cases"]
        self.assertEqual(len({case["name"] for case in cases}), len(cases))
        self.assertNotIn(chr(0x2014), text)
        for case in cases:
            with self.subTest(case=case["name"]):
                observed = self.replay(case, (PAGES / case["pages"][0]).read_text(encoding="utf-8"))
                self.assertEqual(compare(case, observed), [])
                self.assertEqual(observed["adapter"], "phenom")
                self.assertEqual(observed["submit_counts"], [0, 0, 0])

    def test_phenom_native_select_and_phone_fill(self):
        self.open_markup(page("page_1.html"))
        phone = self.by_key("phone")
        self.assertEqual(self.fill([{"id": phone["id"], "value": "5550100"}])[0]["status"], "filled")
        self.assertEqual(self.page.locator("[id='phoneWidget.phoneNumber']").input_value(), "5550100")
        code = next(field for field in self.scan() if field["label"] == "Phone country code")
        self.assertIsNone(code["key"])
        self.assertEqual(self.page.locator("[id='phoneWidget.countryCode']").input_value(), "")

    def test_phenom_demographic_and_consent_stay_manual(self):
        self.open_markup(page("page_4.html"))
        fields = [field for field in self.scan() if not field["structure"]["dom_id"].startswith("guard-")]
        self.assertEqual(len(fields), 3)
        self.assertTrue(all(field["blocked"] for field in fields))

    def test_phenom_adapter_is_in_every_injection_list(self):
        for name in INJECTION_FILES:
            text = (HERE / "extension" / name).read_text(encoding="utf-8")
            self.assertIn("adapters/phenom.js", text, name)
            self.assertLess(text.index("adapters/generic.js"), text.index("adapters/phenom.js"), name)
        manifest = json.loads((HERE / "extension" / "manifest.json").read_text(encoding="utf-8"))
        self.assertNotIn("<all_urls>", json.dumps(manifest))
        self.assertEqual(manifest["host_permissions"], ["http://127.0.0.1/*"])


if __name__ == "__main__":
    unittest.main()
