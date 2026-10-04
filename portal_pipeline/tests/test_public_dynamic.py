"""Dynamic form side effects must stop later writes on synthetic pages."""
from browser_test_support import SyntheticBrowserTest


class PublicDynamicTests(SyntheticBrowserTest):
    def selected_names(self):
        fields = {field["key"]: field for field in self.scan() if field["key"]}
        return [{"id": fields[key]["id"], "value": "Synthetic"} for key in ("first_name", "last_name")]

    def test_newly_protected_selected_value_stops_later_writes_and_redacts(self):
        self.open_markup('''<label>First name<input id="first"></label>
          <label id="email-label">Email<input id="email"></label><label>Last name<input id="last"></label>
          <script>document.getElementById('first').oninput=()=>{
            document.getElementById('email-label').firstChild.textContent='I certify PRIVATE_LABEL';
            document.getElementById('email').value='PRIVATE_VALUE';};</script>''')
        fields = {field["key"]: field for field in self.scan() if field["key"]}
        results = self.fill([{"id": fields[key]["id"], "value": "Synthetic"} for key in ("first_name", "email", "last_name")])
        self.assertEqual([item["status"] for item in results], ["failed"] * 3)
        self.assertNotIn("PRIVATE", str(results))
        self.assertEqual(self.page.locator("#last").input_value(), "")

    def test_replaced_nonleading_protected_radio_stops_later_writes(self):
        self.open_markup('''<label>First name<input id="first"></label><label>Last name<input id="last"></label>
          <fieldset><legend>I certify this separate question</legend>
            <label><input name="cert" type="radio" value="No">No</label>
            <label><input id="cert-yes" name="cert" type="radio" value="Yes">Yes</label></fieldset>
          <script>document.getElementById('first').oninput=()=>{
            const old=document.getElementById('cert-yes'), replacement=old.cloneNode(true);
            replacement.checked=true;old.replaceWith(replacement);};</script>''')
        results = self.fill(self.selected_names())
        self.assertEqual([item["status"] for item in results], ["failed", "failed"])
        self.assertEqual(self.page.locator("#last").input_value(), "")
        self.assertTrue(self.page.locator("#cert-yes").is_checked())

    def test_added_checked_agreement_stops_later_writes(self):
        self.open_markup('''<label>First name<input id="first"></label><label>Last name<input id="last"></label>
          <script>document.getElementById('first').oninput=()=>{
            const label=document.createElement('label');label.textContent='I agree';
            const input=document.createElement('input');input.type='checkbox';input.checked=true;
            label.append(input);document.body.append(label);};</script>''')
        results = self.fill(self.selected_names())
        self.assertEqual([item["status"] for item in results], ["failed", "failed"])
        self.assertEqual(self.page.locator("#last").input_value(), "")

    def test_revealed_checked_agreement_stops_later_writes(self):
        self.open_markup('''<label>First name<input id="first"></label><label>Last name<input id="last"></label>
          <label id="hidden-label" hidden>I agree<input id="new-consent" type="checkbox"></label>
          <script>document.getElementById('first').oninput=()=>{
            document.getElementById('hidden-label').hidden=false;
            document.getElementById('new-consent').checked=true;};</script>''')
        results = self.fill(self.selected_names())
        self.assertEqual([item["status"] for item in results], ["failed", "failed"])
        self.assertEqual(self.page.locator("#last").input_value(), "")

    def test_new_control_before_fill_requires_rescan_without_writing(self):
        self.open_markup('<label>First name<input id="first"></label><label>Last name<input id="last"></label>')
        selections = self.selected_names()
        self.page.evaluate("document.body.append(document.createElement('input'))")
        results = self.fill(selections)
        self.assertEqual([item["status"] for item in results], ["failed", "failed"])
        self.assertEqual(self.page.locator("#first").input_value(), "")
        self.assertEqual(self.page.locator("#last").input_value(), "")
