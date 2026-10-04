"""Preflight manual fields remain unwritable at the engine boundary on fabricated pages."""
from browser_test_support import HERE, SyntheticBrowserTest

MARKUP = """
<label>First name<input id="first"></label>
<label>Favorite synthetic answer<input id="manual"></label>
"""


class ManualBoundaryTests(SyntheticBrowserTest):
    def test_forged_selection_of_manual_field_is_refused(self):
        self.open_markup(MARKUP)
        fields = self.scan()
        manual = next(field for field in fields if field["label"] == "Favorite synthetic answer")
        results = self.fill([{"id": manual["id"], "value": "Fabricated answer", "overwrite": True}], {"manualIds": [manual["id"]]})
        self.assertEqual(results[0]["status"], "refused")
        self.assertIn("manual", results[0]["message"].lower())
        self.assertEqual(self.page.locator("#manual").input_value(), "")

    def test_allowed_field_fills_and_manual_field_remains_empty(self):
        self.open_markup(MARKUP)
        fields = self.scan()
        first = next(field for field in fields if field["key"] == "first_name")
        manual = next(field for field in fields if field["label"] == "Favorite synthetic answer")
        results = self.fill([{"id": first["id"], "value": "Synthetic"}, {"id": manual["id"], "value": "Not permitted"}], {"manualIds": [manual["id"]]})
        self.assertEqual([item["status"] for item in results], ["filled", "refused"])
        self.assertEqual(self.page.locator("#first").input_value(), "Synthetic")
        self.assertEqual(self.page.locator("#manual").input_value(), "")

    def test_manual_field_side_effect_is_detected_even_if_forged_as_selected(self):
        self.open_markup(MARKUP)
        fields = self.scan()
        first = next(field for field in fields if field["key"] == "first_name")
        manual = next(field for field in fields if field["label"] == "Favorite synthetic answer")
        self.page.evaluate("document.getElementById('first').addEventListener('input', () => document.getElementById('manual').value = 'Portal side effect')")
        results = self.fill([{"id": first["id"], "value": "Synthetic"}, {"id": manual["id"], "value": "Not permitted"}], {"manualIds": [manual["id"]]})
        self.assertEqual(results[0]["status"], "failed")
        self.assertIn("unselected field changed", results[0]["message"].lower())
        self.assertEqual(results[1]["status"], "refused")
        self.assertEqual(self.page.locator("#manual").input_value(), "Portal side effect")

    def test_invalid_manual_ids_refuse_before_any_write(self):
        self.open_markup(MARKUP)
        first = next(field for field in self.scan() if field["key"] == "first_name")
        for invalid in ("field", None, [1]):
            with self.assertRaisesRegex(Exception, "Manual field IDs"):
                self.fill([{"id": first["id"], "value": "Synthetic"}], {"manualIds": invalid})
            self.assertEqual(self.page.locator("#first").input_value(), "")

    def test_panel_passes_preflight_manual_ids_to_fill_transport(self):
        self.open_markup(MARKUP)
        self.page.add_script_tag(path=str(HERE / "extension/panel.js"))
        self.page.evaluate("""async () => {
          globalThis.fillOptions = null;
          globalThis.manualId = '';
          const profile = {values: {first_name: {value: 'Synthetic', source: 'Fabricated fixture'}}};
          const api = async path => {
            if (path === '/api/current') return {id: 'a'.repeat(32), mode: 'audited_import', url: location.href};
            if (path === `/api/sessions/${'a'.repeat(32)}/profile`) return profile;
            if (path === '/api/profile') throw new Error('Global profile must not load');
            if (path.endsWith('/preflight')) return {items: [], manual_field_ids: [manualId]};
            return {};
          };
          await PortalPanel.open(api, {load: async () => null, save: async () => {}}, {targetUrl: location.href, transport: {
            scan: value => {
              const fields = PortalEngine.scan(value);
              manualId = fields.find(field => field.label === 'Favorite synthetic answer').id;
              return fields;
            },
            fill: async (selections, options) => {fillOptions = options; return PortalEngine.fill(selections, options);},
            inspect: () => PortalEngine.inspect()
          }});
        }""")
        host = self.page.locator("#portal-panel-host")
        host.get_by_role("checkbox", name="Select First name", exact=True).check()
        host.locator("#match-page").check()
        host.get_by_role("button", name="Fill selected fields", exact=True).click()
        self.page.wait_for_function("fillOptions !== null")
        self.assertEqual(self.page.evaluate("fillOptions.manualIds"), [self.page.evaluate("manualId")])
