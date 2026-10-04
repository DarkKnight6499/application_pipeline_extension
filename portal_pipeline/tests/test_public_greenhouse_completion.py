"""PF4 Greenhouse completion checks use synthetic markup only."""
from browser_test_support import SyntheticBrowserTest


URL = "https://job-boards.greenhouse.io/synthetic/jobs/456"


class GreenhouseCompletionTests(SyntheticBrowserTest):
    def load_greenhouse(self, body=""):
        markup = f"<!doctype html><html><body><form id='application-form'>{body}</form></body></html>"
        self.open_markup(markup, url=URL)
        self.page.add_script_tag(path=str(self.here / "progress.js"))

    @property
    def here(self):
        from pathlib import Path
        return Path(__file__).resolve().parents[1] / "extension"

    def test_greenhouse_routes_to_adapter(self):
        self.load_greenhouse()
        self.assertEqual(self.page.evaluate("PortalAdapters.forLocation(location.href).id"), "greenhouse")

    def test_greenhouse_scan_is_read_only(self):
        self.load_greenhouse("<label for='auth'>Are you legally authorized to work in the US?<input id='auth' value='Keep'></label>")
        before = self.page.locator("#application-form").inner_html()
        self.page.evaluate("PortalEngine.scan({values: {authorized_us: {value: 'Yes', source: 'synthetic'}}})")
        self.assertEqual(self.page.locator("#application-form").inner_html(), before)

    def test_greenhouse_selected_only_fill(self):
        self.load_greenhouse("<label for='auth'>Are you legally authorized to work in the US?<input id='auth'></label><label for='other'>Other<input id='other'></label>")
        fields = self.page.evaluate("PortalEngine.scan({values: {authorized_us: {value: 'Yes', source: 'synthetic'}}})")
        auth = next(field for field in fields if field["structure"]["dom_id"] == "auth")
        result = self.fill([{"id": auth["id"], "value": "Yes"}])
        self.assertEqual(result[0]["status"], "filled")
        self.assertEqual(self.page.locator("#auth").input_value(), "Yes")
        self.assertEqual(self.page.locator("#other").input_value(), "")

    def test_greenhouse_overwrite_off_preserves(self):
        self.load_greenhouse("<label for='auth'>Are you legally authorized to work in the US?<input id='auth' value='No'></label>")
        fields = self.page.evaluate("PortalEngine.scan({values: {authorized_us: {value: 'Yes', source: 'synthetic'}}})")
        auth = next(field for field in fields if field["structure"]["dom_id"] == "auth")
        result = self.fill([{"id": auth["id"], "value": "Yes"}])
        self.assertEqual(result[0]["status"], "preserved")
        self.assertEqual(self.page.locator("#auth").input_value(), "No")

    def test_greenhouse_human_gate_blocks_fill(self):
        self.load_greenhouse("<label for='auth'>Are you legally authorized to work in the US?<input id='auth'></label><iframe src='https://captcha.example.invalid/hcaptcha'></iframe>")
        fields = self.page.evaluate("PortalEngine.scan({values: {authorized_us: {value: 'Yes', source: 'synthetic'}}})")
        auth = next(field for field in fields if field["structure"]["dom_id"] == "auth")
        result = self.fill([{"id": auth["id"], "value": "Yes"}])
        self.assertEqual(result[0]["status"], "blocked_by_human_gate")
        self.assertEqual(self.page.locator("#auth").input_value(), "")

    def test_greenhouse_final_review_detected(self):
        self.load_greenhouse("<h1>Review your application</h1><button type='submit'>Submit</button>")
        result = self.page.evaluate("PortalAdapters.forLocation(location.href).detectFinalReview(document)")
        self.assertTrue(result["final"])

    def test_greenhouse_submit_counter_stays_zero(self):
        self.load_greenhouse("<label for='auth'>Are you legally authorized to work in the US?<input id='auth'></label><button type='submit'>Submit application</button>")
        fields = self.page.evaluate("PortalEngine.scan({values: {}})")
        result = self.fill([{"id": fields[0]["id"], "value": "Yes"}])
        self.assertEqual(result[0]["status"], "filled")
        self.assertEqual(self.page.evaluate("syntheticSubmitClicks"), 0)
        self.assertEqual(self.page.evaluate("syntheticSubmitEvents"), 0)

    def test_greenhouse_react_select_ref_refreshed_after_rerender(self):
        first = "<label id='first-label'>Authorization</label><div class='select-shell'><div class='select__control'><div class='select__value-container'><input id='first' class='select__input' role='combobox' aria-labelledby='first-label' aria-expanded='false'></div></div></div>"
        self.load_greenhouse(first)
        fields = self.page.evaluate("PortalEngine.scan({values: {}})")
        self.page.evaluate("""() => {
          const attach = input => {
            const shell = input.closest('.select-shell');
            const open = () => {
              input.setAttribute('aria-expanded', 'true'); input.setAttribute('aria-controls', 'current-menu');
              const menu = document.createElement('div'); menu.id = 'current-menu'; menu.setAttribute('role', 'listbox');
              menu.setAttribute('aria-multiselectable', 'false');
              const option = document.createElement('div'); option.setAttribute('role', 'option'); option.textContent = 'Yes';
              option.onclick = () => {
                shell.querySelector('.select__value-container').insertAdjacentHTML('afterbegin', '<div class="select__single-value">Yes</div>');
                input.setAttribute('aria-expanded', 'false'); menu.remove();
              };
              menu.append(option); shell.append(menu);
            };
            input.addEventListener('keydown', event => { if (event.key === 'ArrowDown' && !shell.querySelector('[role=listbox]')) open(); });
          };
          attach(document.querySelector('#first'));
          const oldShell = document.querySelector('.select-shell');
          const freshShell = oldShell.cloneNode(true);
          oldShell.replaceWith(freshShell);
          attach(freshShell.querySelector('input'));
        }""")
        stale = self.fill([{"id": fields[0]["id"], "value": "Yes"}])
        self.assertEqual(stale[0]["status"], "failed")
        self.assertEqual(self.page.locator(".select__single-value").count(), 0)
        refreshed = self.page.evaluate("PortalEngine.scan({values: {}})")
        result = self.fill([{"id": refreshed[0]["id"], "value": "Yes"}])
        self.assertEqual(result[0]["status"], "filled", result)
        self.assertEqual(self.page.locator(".select__single-value").inner_text(), "Yes")

    def test_greenhouse_typeahead_stays_manual_without_contract(self):
        body = "<label for='country'>Country<input id='country' role='combobox' aria-autocomplete='list'></label><label for='city'>City<input id='city' role='combobox' aria-autocomplete='list'></label>"
        self.load_greenhouse(body)
        fields = self.page.evaluate("PortalEngine.scan({values: {}})")
        by_id = {field["structure"]["dom_id"]: field for field in fields}
        for field_id in ("country", "city"):
            self.assertIsNone(by_id[field_id]["adapter"])
            result = self.fill([{"id": by_id[field_id]["id"], "value": "Synthetic value"}])
            self.assertEqual(result[0]["status"], "failed")
            self.assertEqual(self.page.locator(f"#{field_id}").input_value(), "")
