"""Synthetic coverage for attestation headings above nested fieldsets."""
from browser_test_support import SyntheticBrowserTest


class AttestationHeadingAncestryTests(SyntheticBrowserTest):
    def test_form_level_signature_heading_protects_legal_name_in_fieldset(self):
        self.open_markup("""
          <form>
            <h2>Electronic signature</h2>
            <fieldset><label>Legal name<input id="legal-one"></label></fieldset>
          </form>
        """)
        field = next(field for field in self.scan({"full_name": {"value": "Synthetic Person", "source": "Fabricated fixture"}})
                     if field["structure"]["dom_id"] == "legal-one")
        self.assertTrue(field["blocked"])
        self.assertEqual((field["proposal"], field["status"]), ("", "manual_only"))
        result = self.fill([{"id": field["id"], "value": "Synthetic Person"}])
        self.assertNotEqual(result[0]["status"], "filled")
        self.assertEqual(self.page.locator("#legal-one").input_value(), "")

    def test_later_contact_heading_in_nested_section_ends_signature_scope(self):
        self.open_markup("""
          <form>
            <h2>Electronic signature</h2>
            <fieldset><label>Legal name<input id="legal-one"></label></fieldset>
            <section>
              <h2>Contact information</h2>
              <fieldset><label>Legal name<input id="legal-two"></label></fieldset>
            </section>
          </form>
        """)
        fields = self.scan({"full_name": {"value": "Synthetic Person", "source": "Fabricated fixture"}})
        signature = next(field for field in fields if field["structure"]["dom_id"] == "legal-one")
        contact = next(field for field in fields if field["structure"]["dom_id"] == "legal-two")
        self.assertTrue(signature["blocked"])
        self.assertFalse(contact["blocked"])
        self.assertEqual(contact["proposal"], "Synthetic Person")
