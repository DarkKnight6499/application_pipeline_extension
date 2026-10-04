"""Regression tests use only synthetic answers and isolated local pages."""
import unittest

from browser_test_support import SyntheticBrowserTest

# Synthetic answer configuration
AUTHORIZATION_FACT = {"authorized_us": {"value": "Yes", "source": "Synthetic fixture"}}


class PublicEngineTests(SyntheticBrowserTest):
    def test_protected_collateral_stops_later_selected_writes(self):
        self.open_markup("""
          <label>First name<input id="first" oninput="document.getElementById('consent').checked=true"></label>
          <label>Last name<input id="last"></label>
          <label>I agree<input id="consent" type="checkbox"></label>
        """)
        fields = {field["label"]: field for field in self.scan()}
        result = self.fill([{"id": fields[label]["id"], "value": "Synthetic"} for label in ["First name", "Last name"]])
        self.assertEqual([item["status"] for item in result], ["failed", "failed"])
        self.assertIn("protected", result[0]["message"].lower())
        self.assertEqual(self.page.locator("#last").input_value(), "")
        self.assertTrue(self.page.locator("#consent").is_checked())

    def test_protected_collateral_value_is_not_returned(self):
        self.open_markup("""
          <label>First name<input id="first" oninput="document.getElementById('secret').value='SYNTHETIC PRIVATE CHANGE'"></label>
          <label>Password<input id="secret" type="password" value="SYNTHETIC PRIVATE ORIGINAL"></label>
        """)
        fields = self.scan()
        first = next(field for field in fields if field["key"] == "first_name")
        result = self.fill([{"id": first["id"], "value": "Synthetic"}])
        self.assertEqual(result[0]["status"], "failed")
        self.assertNotIn("PRIVATE", str(fields) + str(result))

    def test_ordinary_collateral_still_stops_later_writes(self):
        self.open_markup("""
          <label>First name<input id="first" oninput="document.getElementById('side').value='Changed'"></label>
          <label>Last name<input id="last"></label>
          <label>Other field<input id="side" value="Original"></label>
        """)
        fields = {field["label"]: field for field in self.scan()}
        result = self.fill([{"id": fields[label]["id"], "value": "Synthetic"} for label in ["First name", "Last name"]])
        self.assertEqual([item["status"] for item in result], ["failed", "failed"])
        self.assertEqual(self.page.locator("#last").input_value(), "")

    def test_same_name_radios_are_separate_by_form(self):
        self.open_markup("""
          <form id="ordinary"><fieldset>
            <legend>Are you authorized to work in the United States?</legend>
            <label><input type="radio" name="auth" value="no">No</label>
            <label><input id="authorized" type="radio" name="auth" value="yes">Yes</label>
          </fieldset></form>
          <form id="protected"><fieldset>
            <legend>I certify this application</legend>
            <label><input id="other-attestation" type="radio" name="auth" value="certified">Certified</label>
          </fieldset></form>
        """)
        fields = self.scan(AUTHORIZATION_FACT)
        radios = [field for field in fields if field["type"] == "radio"]
        self.assertEqual(len(radios), 2)
        self.assertTrue(next(field for field in radios if "certify" in field["label"])["blocked"])
        ordinary = next(field for field in radios if field["key"] == "authorized_us")
        result = self.fill([{"id": ordinary["id"], "value": "Yes"}])
        self.assertEqual(result[0]["status"], "filled")
        self.assertTrue(self.page.locator("#authorized").is_checked())
        self.assertFalse(self.page.locator("#other-attestation").is_checked())

    def test_other_form_attestation_cannot_supply_selected_radio_option(self):
        self.open_markup("""
          <form><fieldset><legend>Are you authorized to work in the United States?</legend>
            <label><input id="ordinary" type="radio" name="auth" value="no">No</label>
          </fieldset></form>
          <form><fieldset><legend>I certify this application</legend>
            <label><input id="other-attestation" type="radio" name="auth" value="yes">Yes</label>
          </fieldset></form>
        """)
        ordinary = next(field for field in self.scan(AUTHORIZATION_FACT) if field["key"] == "authorized_us")
        result = self.fill([{"id": ordinary["id"], "value": "Yes"}])
        self.assertEqual(result[0]["status"], "failed")
        self.assertFalse(self.page.locator("#other-attestation").is_checked())
        self.assertFalse(self.page.locator("#ordinary").is_checked())

    def test_protected_member_blocks_entire_same_form_radio_group(self):
        self.open_markup("""
          <form><fieldset><legend>Are you authorized to work in the United States?</legend>
            <label><input id="ordinary" type="radio" name="auth" value="no">No</label>
            <label><input id="attest-member" type="radio" name="auth" value="yes">I certify this application</label>
          </fieldset></form>
        """)
        group = next(field for field in self.scan(AUTHORIZATION_FACT) if field["type"] == "radio")
        self.assertTrue(group["blocked"])
        result = self.fill([{"id": group["id"], "value": "Yes"}])
        self.assertEqual(result[0]["status"], "failed")
        self.assertFalse(self.page.locator("#attest-member").is_checked())

    def test_radio_member_moved_to_other_form_invalidates_selection(self):
        self.open_markup("""
          <form id="original"><fieldset><legend>Are you authorized to work in the United States?</legend>
            <label><input type="radio" name="auth" value="no">No</label>
            <label id="yes-label"><input id="yes" type="radio" name="auth" value="yes">Yes</label>
          </fieldset></form><form id="other"></form>
        """)
        group = next(field for field in self.scan(AUTHORIZATION_FACT) if field["key"] == "authorized_us")
        self.page.evaluate("document.getElementById('other').append(document.getElementById('yes-label'))")
        result = self.fill([{"id": group["id"], "value": "Yes"}])
        self.assertEqual(result[0]["status"], "failed")
        self.assertFalse(self.page.locator("#yes").is_checked())


if __name__ == "__main__":
    unittest.main()
