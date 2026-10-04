"""Attestation controls and signature headings use fabricated pages and answers only."""
from browser_test_support import SyntheticBrowserTest


class AttestationBoundaryTests(SyntheticBrowserTest):
    def test_authorization_question_keeps_its_confirmed_proposal(self):
        self.open_markup('<label>Are you legally authorized to work in the United States?<select id="authorized"><option value="">Choose</option><option value="yes">Yes</option><option value="no">No</option></select></label>')
        field = next(field for field in self.scan({"authorized_us": {"value": "Yes", "source": "Fabricated fixture"}}) if field["key"] == "authorized_us")
        self.assertFalse(field["blocked"])
        result = self.fill([{"id": field["id"], "value": field["proposal"]}])
        self.assertEqual(result[0]["status"], "filled")

    def test_explicit_attestation_phrases_protect_select_radio_and_text(self):
        phrases = ["Attestation", "I acknowledge", "I certify", "Certification", "I consent", "I agree", "Acknowledgement", "Acknowledgment",
                   "I declare", "Declaration", "Terms", "Privacy policy", "I authorize", "I understand", "I confirm",
                   "True and complete", "True and accurate", "Signature"]
        markup = []
        for index, phrase in enumerate(phrases):
            markup.append(f'<label>{phrase}<select id="statement-select-{index}"><option value="">Choose</option><option value="yes">Yes</option></select></label>')
            markup.append(f'<fieldset><legend>{phrase}</legend><label>Yes<input id="statement-radio-{index}" type="radio" name="statement-{index}" value="yes"></label></fieldset>')
            markup.append(f'<label>{phrase}<input id="statement-text-{index}"></label>')
        self.open_markup("".join(markup))
        fields = [field for field in self.scan() if field["structure"]["dom_id"].startswith("statement-")]
        self.assertEqual(len(fields), len(phrases) * 3)
        self.assertTrue(all(field["blocked"] and not field["proposal"] for field in fields))

    def test_acknowledgment_select_and_radio_are_manual(self):
        self.open_markup("""
          <label>I acknowledge the information is accurate<select id="ack"><option value="">Choose</option><option value="yes">Yes</option></select></label>
          <fieldset><legend>I acknowledge this application statement</legend>
            <label>Yes<input id="ack-radio" type="radio" name="statement" value="yes"></label>
          </fieldset>
        """)
        fields = self.scan()
        attestations = [field for field in fields if "acknowledge" in field["label"].lower() or field["type"] == "radio"]
        self.assertEqual(len(attestations), 2)
        self.assertTrue(all(field["blocked"] and field["status"] == "manual_only" for field in attestations))
        results = self.fill([{"id": field["id"], "value": "yes", "overwrite": True} for field in attestations])
        self.assertTrue(all(result["status"] != "filled" for result in results))
        self.assertEqual(self.page.locator("#ack").input_value(), "")
        self.assertFalse(self.page.locator("#ack-radio").is_checked())

    def test_legal_name_under_signature_heading_has_no_proposal(self):
        self.open_markup("""
          <section><h2>Contact information</h2><label>Legal name<input id="legal-one"></label></section>
          <section><h2>E-Signature</h2><label>Legal name<input id="legal-two"></label></section>
        """)
        fields = self.scan({"full_name": {"value": "Synthetic Person", "source": "Fabricated fixture"}})
        names = [field for field in fields if field["label"] == "Legal name"]
        self.assertEqual(len(names), 2)
        self.assertFalse(names[0]["blocked"])
        self.assertEqual(names[0]["proposal"], "Synthetic Person")
        self.assertTrue(names[1]["blocked"])
        self.assertEqual(names[1]["proposal"], "")
        result = self.fill([{"id": names[1]["id"], "value": "Synthetic Person"}])
        self.assertNotEqual(result[0]["status"], "filled")
        self.assertEqual(self.page.locator("#legal-two").input_value(), "")

    def test_signature_heading_without_section_stops_at_next_heading(self):
        self.open_markup("""
          <h2>Electronic signature</h2><label>Legal name<input id="legal-two"></label>
          <h2>Contact information</h2><label>First name<input id="first"></label>
        """)
        fields = self.scan({"first_name": {"value": "Synthetic", "source": "Fabricated fixture"}})
        signature = next(field for field in fields if field["label"] == "Legal name")
        first = next(field for field in fields if field["label"] == "First name")
        self.assertTrue(signature["blocked"])
        self.assertFalse(first["blocked"])
        result = self.fill([{"id": first["id"], "value": first["proposal"]}])
        self.assertEqual(result[0]["status"], "filled")
        self.assertEqual(self.page.locator("#legal-two").input_value(), "")

    def test_signature_heading_added_after_scan_refuses_write(self):
        self.open_markup('<section id="scope"><h2>Contact information</h2><label>Legal name<input id="name"></label></section>')
        field = next(field for field in self.scan() if field["label"] == "Legal name")
        self.page.evaluate("document.querySelector('#scope h2').textContent = 'E-Signature'")
        result = self.fill([{"id": field["id"], "value": "Synthetic Person"}])
        self.assertNotEqual(result[0]["status"], "filled")
        self.assertIn("manual", result[0]["message"].lower())
        self.assertEqual(self.page.locator("#name").input_value(), "")
