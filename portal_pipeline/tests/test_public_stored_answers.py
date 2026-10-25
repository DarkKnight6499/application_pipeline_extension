"""Stored answers (profile.answers, keyed by normalized label) propose and fill by exact label only."""
from browser_test_support import SyntheticBrowserTest

PAGE = '''<form>
<label for="age">Are you at least 18 years of age?*</label><select id="age"><option value="">Select</option><option value="y">Yes</option><option value="n">No</option></select>
<label for="kind">Pick a kind</label><select id="kind"><option value="">Select</option><option value="a">Alpha</option></select>
<label for="free">Preferred nickname</label><input id="free">
<label><input type="checkbox" id="asian"> Asian (United States of America)</label>
<label><input type="checkbox" id="white"> White (United States of America)</label>
<label><input type="checkbox" id="certify"> I certify that the above is true and agree to the terms.*</label>
<fieldset><legend>Do you have relatives here?</legend><label><input type="radio" name="rel" value="Yes"> Yes</label><label><input type="radio" name="rel" value="No"> No</label></fieldset>
</form>'''
ANSWERS = {"are you at least 18 years of age": "Yes", "pick a kind": "Gamma", "preferred nickname": "Yaz",
           "asian united states of america": "Yes", "white united states of america": "No",
           "i certify that the above is true and agree to the terms": "Yes", "do you have relatives here": "No",
           "preferred nick": "Nope"}


class StoredAnswerTests(SyntheticBrowserTest):
    def scan(self, answers=ANSWERS, values=None):
        self.open_markup(PAGE)
        fields = self.page.evaluate("profile => PortalEngine.scan(profile)", {"values": values or {}, "answers": answers})
        return {f["structure"]["dom_id"] or f["label"]: f for f in fields}

    def test_exact_label_proposes_for_select_text_and_radio(self):
        fields = self.scan()
        self.assertEqual((fields["age"]["proposal"], fields["age"]["status"]), ("Yes", "prepared"))
        self.assertEqual(fields["free"]["proposal"], "Yaz")
        self.assertEqual(fields["Do you have relatives here?"]["proposal"], "No")
        self.assertIn("Stored answer", fields["age"]["source"])

    def test_answer_that_is_not_an_option_stays_pending(self):
        field = self.scan()["kind"]
        self.assertEqual((field["proposal"], field["status"]), ("", "pending"))

    def test_similar_label_does_not_match(self):
        self.assertEqual(self.scan({"preferred nick": "Yaz"})["free"]["proposal"], "")

    def test_attestation_checkbox_is_never_proposed_from_memory(self):
        field = self.scan()["certify"]
        self.assertTrue(field["blocked"])
        self.assertEqual(field["proposal"], "")

    def test_stored_answer_beats_profile_value(self):
        fields = self.scan({"preferred nickname": "No"}, {"preferred_name": {"value": "Yes", "source": "x"}})
        self.assertEqual(fields["free"]["proposal"], "No")

    def test_fill_sets_select_text_radio_and_checkboxes(self):
        fields = self.scan()
        selections = [{"id": fields[k]["id"], "value": fields[k]["proposal"]} for k in ("age", "free", "Do you have relatives here?", "asian", "white")]
        results = self.fill(selections)
        self.assertEqual([r["status"] for r in results], ["filled"] * 5, results)
        self.assertEqual(self.page.locator("#age").input_value(), "y")
        self.assertEqual(self.page.locator("#free").input_value(), "Yaz")
        self.assertTrue(self.page.locator("#asian").is_checked())
        self.assertFalse(self.page.locator("#white").is_checked())
        self.assertTrue(self.page.locator("input[name=rel][value=No]").is_checked())

    def test_unchecked_checkbox_with_no_answer_is_left_alone(self):
        fields = self.scan()
        result = self.fill([{"id": fields["white"]["id"], "value": "No"}])[0]
        self.assertIn(result["status"], {"filled", "preserved"})
        self.assertFalse(self.page.locator("#white").is_checked())


class DemographicAndGridTests(SyntheticBrowserTest):
    PAGE = '''<form>
<label for="gender">Gender</label><select id="gender"><option value="">Select</option><option value="m">Male</option></select>
<label for="eth">Ethnicity</label><select id="eth"><option value="">Select</option><option value="a">Asian</option></select>
<div role="grid" aria-readonly="true"><label><input type="checkbox" id="grid-box"> Asian (United States of America)</label></div>
<label><input type="checkbox" id="consent"> I certify and consent to the above.*</label>
</form>'''

    def scan(self, answers):
        self.open_markup(self.PAGE)
        return {f["structure"]["dom_id"]: f for f in self.page.evaluate("profile => PortalEngine.scan(profile)", {"values": {}, "answers": answers})}

    def test_demographic_field_stays_manual_without_a_stored_answer(self):
        fields = self.scan({})
        self.assertTrue(fields["gender"]["blocked"])

    def test_demographic_field_with_exact_stored_answer_is_proposed(self):
        fields = self.scan({"gender": "Male"})
        self.assertEqual((fields["gender"]["blocked"], fields["gender"]["proposal"]), (False, "Male"))
        self.assertTrue(fields["eth"]["blocked"])

    def test_attestation_stays_blocked_even_with_stored_answer(self):
        self.assertTrue(self.scan({"i certify and consent to the above": "Yes"})["consent"]["blocked"])

    def test_checkbox_inside_readonly_grid_is_available(self):
        self.assertFalse(self.scan({})["grid-box"]["disabled"])


class ConsentTests(SyntheticBrowserTest):
    PAGE = '''<form><label><input type="checkbox" id="consent"> Yes, I have read and consent to the above.*</label>
<label><input type="checkbox" id="other"> I certify that all statements are true.*</label></form>'''
    HOST = "workday.synthetic.test"

    def scan(self, consents):
        self.open_markup(self.PAGE)
        host = self.page.evaluate("location.hostname")
        keys = [f"{host}|{k}" for k in consents]
        return {f["structure"]["dom_id"]: f for f in self.page.evaluate("profile => PortalEngine.scan(profile)", {"values": {}, "answers": {}, "consents": keys})}

    def test_recorded_consent_for_this_host_and_label_is_proposed_and_filled(self):
        fields = self.scan(["yes i have read and consent to the above"])
        self.assertEqual((fields["consent"]["blocked"], fields["consent"]["proposal"]), (False, "Yes"))
        self.assertEqual(self.fill([{"id": fields["consent"]["id"], "value": "Yes"}])[0]["status"], "filled")
        self.assertTrue(self.page.locator("#consent").is_checked())

    def test_other_attestations_stay_manual(self):
        self.assertTrue(self.scan(["yes i have read and consent to the above"])["other"]["blocked"])

    def test_consent_for_another_host_is_ignored(self):
        self.open_markup(self.PAGE)
        fields = {f["structure"]["dom_id"]: f for f in self.page.evaluate("profile => PortalEngine.scan(profile)", {"values": {}, "answers": {}, "consents": ["other.example|yes i have read and consent to the above"]})}
        self.assertTrue(fields["consent"]["blocked"] and fields["other"]["blocked"])
