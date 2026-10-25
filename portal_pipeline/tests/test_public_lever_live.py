"""Author: Yazad Madan. Synthetic regressions for the observed Lever apply markup."""
from pathlib import Path

from browser_test_support import SyntheticBrowserTest

# Test configuration
EXT = Path(__file__).resolve().parents[1] / "extension"
URL = "https://jobs.lever.co/acme/1/apply"
CARD = "cards[00000000-0000-0000-0000-000000000001]"
LABELS = {
    "field0": "What is your preferred name?",
    "field1": "Are you legally authorized to work in this country?",
    "field2": "Which university did you last attend?",
    "field3": "What was your favorite project? Why?",
    "field4": "Language Skill(s) (Check all that apply)",
}
PAGE = '''<form><div class="section page-centered application-form" data-qa="additional-cards">
<h4 data-qa="card-name">Supplementary Questions</h4>
<input type="hidden" name="cards[card][baseTemplate]"><ul>
<li class="application-question custom-question"><div>
<div class="application-label full-width"><div class="text">What is your preferred name? (optional)</div></div>
<div class="application-field full-width"><input class="card-field-input" name="cards[card][field0]" type="text"></div>
</div></li>
<li class="application-question custom-question"><div>
<div class="application-label full-width multiple-choice"><div class="text">Are you legally authorized to work in this country?<span class="required">&#10033;</span></div></div>
<div class="application-field full-width required-field"><ul data-qa="multiple-choice">
<li><label><input type="radio" name="cards[card][field1]" required="required"><span class="application-answer-alternative">Yes</span></label></li>
<li><label><input type="radio" name="cards[card][field1]" required="required"><span class="application-answer-alternative">No</span></label></li>
</ul></div></div></li>
<li class="application-question custom-question"><div>
<div class="application-label full-width dropdown"><div class="text">Which university did you last attend? * required</div></div>
<div class="application-field full-width required-field"><div class="application-dropdown">
<select name="cards[card][field2]" required><option value="">Choose</option><option value="acme">Acme University</option></select>
</div></div></div></li>
<li class="application-question custom-question"><div>
<div class="application-label full-width textarea"><div class="text">What was your favorite project? Why?</div></div>
<div class="application-field full-width"><textarea class="card-field-input" name="cards[card][field3]"></textarea></div>
</div></li>
<li class="application-question custom-question"><div>
<div class="application-label full-width multiple-select"><div class="text">Language Skill(s) (Check all that apply)<span class="required">&#10033;</span></div></div>
<div class="application-field full-width required-field"><ul data-qa="checkboxes">
<li><label><input type="checkbox" name="cards[card][field4]" required><span class="application-answer-alternative">English (ENG)</span></label></li>
<li><label><input type="checkbox" name="cards[card][field4]" required><span class="application-answer-alternative">French (FRA)</span></label></li>
</ul></div></div></li></ul></div>
<div class="section page-centered application-form"><ul><li><label>
<span><div>Acme has my consent to contact me about future job opportunities.</div></span>
<input type="hidden" name="consent[marketing]"><input type="checkbox" name="consent[marketing]">
</label></li></ul></div>
<label>Resume<input type="file" name="resume"></label>
<div id="h-captcha" class="h-captcha"><textarea name="h-captcha-response" hidden></textarea>
<input type="checkbox" name="captcha-check"><input name="challenge-token"></div>
<button type="submit">Submit application</button></form>'''.replace("cards[card]", CARD)
ANSWERS = {"what is your preferred name": "Alex"}


class LeverLiveTests(SyntheticBrowserTest):
    def scan(self, profile=None):
        self.open_markup(PAGE, url=URL)
        # The harness loads registry, generic, classifier, and engine before portal adapters.
        for name in ("adapters/lever.js", "lever-live.js"):
            self.page.add_script_tag(path=str(EXT / name))
        return self.page.evaluate("profile => PortalEngine.scan(profile)", profile or {"values": {}})

    def test_custom_fields_use_question_text_and_keep_option_labels(self):
        fields = self.scan()
        for suffix, label in LABELS.items():
            matches = [field for field in fields if field["structure"]["name"] == f"{CARD}[{suffix}]"]
            self.assertEqual(len(matches), 1, matches)
            self.assertEqual(matches[0]["label"], label)
        choices = {field["type"]: field for field in fields if field["options"]}
        self.assertEqual([option["label"] for option in choices["radio"]["options"]], ["Yes", "No"])
        self.assertEqual([option["label"] for option in choices["checkbox"]["options"]], ["English (ENG)", "French (FRA)"])

    def test_exact_question_answer_is_proposed_after_relabel(self):
        fields = self.scan({"values": {}, "answers": ANSWERS})
        field = next(field for field in fields if field["structure"]["name"] == f"{CARD}[field0]")
        self.assertEqual((field["label"], field["proposal"], field["status"]), (LABELS["field0"], "Alex", "prepared"))

    def test_consent_ambiguous_radios_and_checkbox_group_stay_manual(self):
        fields = self.scan({"values": {}, "consents": [
            "jobs.lever.co|acme has my consent to contact me about future job opportunities"
        ]})
        for name in ("consent[marketing]", f"{CARD}[field1]", f"{CARD}[field4]", "resume"):
            field = next(field for field in fields if field["structure"]["name"] == name)
            self.assertEqual(field["status"], "manual_only", field)
            self.assertEqual(field["proposal"], "")
            result = self.fill([{"id": field["id"], "value": "Yes"}])[0]
            self.assertFalse(result["ok"], result)
        self.assertFalse(self.page.locator('input[type="checkbox"][name="consent[marketing]"]').is_checked())
        self.assertFalse(any("captcha" in field["structure"]["name"] or field["structure"]["name"] == "challenge-token" for field in fields))

    def test_generic_fills_text_select_and_textarea_without_upload(self):
        fields = self.scan()
        for suffix, value in (("field0", "Alex"), ("field2", "Acme University")):
            field = next(field for field in fields if field["structure"]["name"] == f"{CARD}[{suffix}]")
            result = self.fill([{"id": field["id"], "value": value}])[0]
            self.assertEqual(result["status"], "filled", result)
        draft = next(field for field in fields if field["structure"]["name"] == f"{CARD}[field3]")
        refused = self.fill([{"id": draft["id"], "value": "Built a small tool."}])[0]
        self.assertEqual(refused["status"], "refused")  # free text drafts need review first
        self.assertEqual(self.page.locator('input[name="resume"]').evaluate("node => node.files.length"), 0)

    def test_changed_question_refuses_fill(self):
        fields = self.scan()
        field = next(field for field in fields if field["structure"]["name"] == f"{CARD}[field0]")
        self.page.locator(".application-label .text").first.evaluate("node => node.textContent = 'Different question?'")
        result = self.fill([{"id": field["id"], "value": "Alex"}])[0]
        self.assertFalse(result["ok"], result)
        self.assertEqual(self.page.locator(f'input[name="{CARD}[field0]"]').input_value(), "")

    def test_generic_radio_fill_requires_unique_values(self):
        self.scan()
        self.page.locator('input[type="radio"]').evaluate_all("nodes => nodes.forEach((node, index) => node.value = String(index))")
        fields = self.page.evaluate("PortalEngine.scan({values: {}})")
        field = next(field for field in fields if field["structure"]["name"] == f"{CARD}[field1]")
        self.assertNotEqual(field["status"], "manual_only", field)
        result = self.fill([{"id": field["id"], "value": "Yes"}])[0]
        self.assertEqual(result["status"], "filled", result)
        self.assertTrue(self.page.locator('input[type="radio"]').first.is_checked())

    def test_only_exact_lever_host_routes_to_live_adapter(self):
        self.scan()
        info = self.page.evaluate("""() => {
          const adapter = PortalAdapters.forLocation(location.href);
          return {id: adapter.id, mode: adapter.mode, requiresApplicationMode: adapter.requiresApplicationMode,
            other: PortalAdapters.forLocation('https://jobs.lever.co.example.org/acme/1/apply').id};
        }""")
        self.assertEqual(info, {"id": "lever-live", "mode": "fill", "requiresApplicationMode": False, "other": "generic"})
