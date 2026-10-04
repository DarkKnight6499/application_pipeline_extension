"""P6 fill hardening on fabricated pages: revert and validation failures are reported, overwrite stays explicit."""
from browser_test_support import SyntheticBrowserTest

# Synthetic configuration
KS_URL = "https://keystrokes.example.invalid/application"
REVERT_REASON = "reverted after blur"


class FillHardeningTests(SyntheticBrowserTest):
    def field_id(self, label):
        return next(field["id"] for field in self.scan() if field["label"] == label)

    def test_value_reverted_after_blur_reported_failed(self):
        self.open_markup('<label>First name<input id="first"></label>'
                         '<script>first.addEventListener("blur", () => {first.value = "";});</script>')
        result = self.fill([{"id": self.field_id("First name"), "value": "Ada"}])[0]
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["reason"], REVERT_REASON)
        self.assertEqual(result["failure_kind"], "reverted")
        self.assertIn(REVERT_REASON, result["message"])
        self.assertEqual(result["validation_error"], "")

    def test_validation_error_captured(self):
        self.open_markup('''
          <div class="field"><label>First name<input id="first"></label><span id="first-error" role="alert"></span></div>
          <div class="field"><label>Last name<input id="last"></label><span id="last-error"></span></div>
          <div class="field"><label>City<input id="city" aria-invalid="false"></label></div>
          <script>
            first.addEventListener("blur", () => {first.setAttribute("aria-invalid", "true"); document.getElementById("first-error").textContent = "Name is not valid.";});
            last.addEventListener("blur", () => {document.getElementById("last-error").textContent = "Last name is too short.";});
            city.addEventListener("blur", () => {city.setAttribute("aria-invalid", "true");});
          </script>''')
        results = {item["id"]: item for item in self.fill([
            {"id": self.field_id("First name"), "value": "Ada"},
            {"id": self.field_id("Last name"), "value": "L"},
            {"id": self.field_id("City"), "value": "Testville"}])}
        first, last, city = (results[self.field_id(label)] for label in ("First name", "Last name", "City"))
        self.assertEqual((first["status"], first["failure_kind"]), ("failed", "validation_error"))
        self.assertIn("Name is not valid.", first["validation_error"])
        self.assertEqual((last["status"], last["failure_kind"]), ("failed", "validation_error"))
        self.assertIn("Last name is too short.", last["validation_error"])
        self.assertEqual((city["status"], city["failure_kind"]), ("failed", "validation_error"))
        self.assertTrue(city["validation_error"])

    def test_clean_fill_reports_empty_validation_error(self):
        self.open_markup('<div class="field"><label>First name<input id="first"></label><span id="first-error" role="alert"></span></div>'
                         '<div class="field"><label>Last name<input id="last"></label><span id="last-error" role="alert">Old problem</span></div>')
        result = self.fill([{"id": self.field_id("First name"), "value": "Ada"}])[0]
        self.assertEqual(result["status"], "filled")
        self.assertEqual(result["validation_error"], "")
        self.assertEqual(self.page.locator("#first").input_value(), "Ada")

    def test_overwrite_off_preserves_each_type(self):
        self.open_markup('''
          <label>First name<input id="first" value="Old"></label>
          <label>Work mode<select id="mode"><option value=""></option><option>Remote</option><option>Onsite</option></select></label>
          <fieldset><legend>Preferred shift</legend>
            <label><input type="radio" name="shift" value="Day" checked>Day</label>
            <label><input type="radio" name="shift" value="Night">Night</label></fieldset>
          <div id="combo" role="combobox" aria-label="Are you willing to relocate?" aria-controls="choices"
            aria-haspopup="listbox" aria-expanded="false" aria-valuetext="No">No</div>
          <div id="choices" role="listbox" hidden><div role="option">Yes</div><div role="option">No</div></div>
          <label>Newsletter<input id="news" type="checkbox" checked></label>
          <script>mode.value = "Remote";</script>''')
        fields = {field["label"]: field for field in self.scan()}
        selections = [{"id": fields["First name"]["id"], "value": "New"},
                      {"id": fields["Work mode"]["id"], "value": "Onsite"},
                      {"id": fields["Preferred shift"]["id"], "value": "Night"},
                      {"id": fields["Are you willing to relocate?"]["id"], "value": "Yes"},
                      {"id": fields["Newsletter"]["id"], "value": "on"}]
        results = self.fill(selections)
        self.assertEqual([item["status"] for item in results], ["preserved"] * 5)
        self.assertEqual(self.page.locator("#first").input_value(), "Old")
        self.assertEqual(self.page.locator("#mode").input_value(), "Remote")
        self.assertTrue(self.page.locator("input[value=Day]").is_checked())
        self.assertEqual(self.page.locator("#combo").get_attribute("aria-valuetext"), "No")
        self.assertTrue(self.page.locator("#news").is_checked())

    def test_unselected_fields_untouched(self):
        self.open_markup('<label>First name<input id="first"></label><label>Last name<input id="last"></label>'
                         '<label>City<input id="city" value="Keep city"></label>')
        results = self.fill([{"id": self.field_id("First name"), "value": "Ada"}])
        self.assertEqual([item["status"] for item in results], ["filled"])
        self.assertEqual(self.page.locator("#last").input_value(), "")
        self.assertEqual(self.page.locator("#city").input_value(), "Keep city")

    def test_trusted_keystrokes_not_enabled(self):
        self.open_markup('<label>First name<input id="first"></label>', url=KS_URL)
        field = self.field_id("First name")
        outcome = self.page.evaluate("""async id => {
          const base = PortalAdapters.forLocation(location.href);
          PortalAdapters.register({...base, id: "keystrokes", hosts: [/^keystrokes\\.example\\.invalid$/], fillStrategy: "trusted_keystrokes"});
          try { await PortalEngine.fill([{id, value: "Ada"}]); return ""; } catch (error) { return error.message; }
        }""", field)
        self.assertIn("not enabled", outcome)
        self.assertEqual(self.page.locator("#first").input_value(), "")
