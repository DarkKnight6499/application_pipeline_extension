"""Sponsorship review controls use fabricated profiles and a synthetic page only."""
from browser_test_support import HERE, SyntheticBrowserTest

FUTURE_LABEL = "Will you require sponsorship in the future?"
TOGGLE_LABEL = "Answer No to sponsorship questions for this application"
MARKUP = f"""
<label>{FUTURE_LABEL}<select id="future"><option value="">Choose</option><option value="yes">Yes</option><option value="no">No</option></select></label>
<label>First name<input id="first"></label>
<button type="button" id="rescan">Rescan</button>
"""


class SponsorshipPanelTests(SyntheticBrowserTest):
    def open_panel(self):
        self.open_markup(MARKUP)
        self.page.add_script_tag(path=str(HERE / "extension/panel.js"))
        self.page.evaluate("""async () => {
          globalThis.mode = 'truthful'; globalThis.saved = {}; globalThis.calls = [];
          globalThis.failMode = false; globalThis.holdFill = false;
          const session = {id: 'a'.repeat(32), mode: 'audited_import', company: 'Synthetic Co', role: 'Synthetic Role', url: location.href};
          const profile = () => ({sponsorship_answer_mode: mode, values: {
            first_name: {value: 'Synthetic', source: 'Fabricated fixture'},
            sponsorship_future: {value: mode === 'truthful' ? 'Yes' : 'No', source: 'Fabricated fixture',
              ...(mode === 'screening_no' ? {basis: 'override', truth: {value: 'Yes', source: 'Synthetic boilerplate'}} : {})}
          }});
          const api = async (path, body) => {
            calls.push({path, body});
            if (path === '/api/current') return session;
            if (path === `/api/sessions/${session.id}/profile`) return profile();
            if (path === '/api/profile') throw new Error('Global profile must not load');
            if (path.endsWith('/preflight')) return {items: [], manual_field_ids: []};
            if (path.endsWith('/sponsorship-mode')) {
              if (failMode) throw Error('Synthetic mode save failed');
              mode = body.mode; return {mode};
            }
            return {};
          };
          const storage = {load: async () => structuredClone(saved), save: async (key, value) => {saved = structuredClone(value);}};
          const options = {targetUrl: location.href, transport: {
            scan: (value, bindings) => PortalEngine.scan(value, {bindings}),
            fill: async selections => {
              if (holdFill) await new Promise(resolve => {globalThis.releaseFill = resolve;});
              return selections.map(item => ({id: item.id, status: 'filled', message: 'Synthetic completion'}));
            }, inspect: () => PortalEngine.inspect()
          }};
          globalThis.reopen = () => PortalPanel.open(api, storage, options);
          document.getElementById('rescan').onclick = reopen;
          await reopen();
        }""")
        return self.page.locator("#portal-panel-host")

    def test_default_unchecked_and_truth_shown_after_explicit_toggle(self):
        host = self.open_panel()
        self.assertFalse(host.get_by_role("checkbox", name=TOGGLE_LABEL, exact=True).is_checked())
        self.assertEqual(host.get_by_role("combobox", name=f"Answer {FUTURE_LABEL}", exact=True).input_value(), "yes")
        host.get_by_role("checkbox", name=TOGGLE_LABEL, exact=True).check()
        self.page.wait_for_function("mode === 'screening_no'")
        host.get_by_text("Proposing No by your toggle; boilerplate says Yes (Synthetic boilerplate).", exact=True).wait_for()
        self.assertEqual(host.get_by_role("combobox", name=f"Answer {FUTURE_LABEL}", exact=True).input_value(), "no")
        self.assertFalse(host.get_by_role("checkbox", name=f"Select {FUTURE_LABEL}", exact=True).is_checked())
        self.assertEqual(self.page.locator("#future").input_value(), "")

    def test_mode_change_clears_only_affected_saved_answers_and_selection(self):
        host = self.open_panel()
        host.get_by_role("checkbox", name=f"Select {FUTURE_LABEL}", exact=True).check()
        host.get_by_role("checkbox", name=f"Replace existing {FUTURE_LABEL}", exact=True).check()
        host.get_by_role("textbox", name="Answer First name", exact=True).fill("Edited synthetic name")
        host.get_by_role("checkbox", name="Select First name", exact=True).check()
        host.get_by_role("checkbox", name=TOGGLE_LABEL, exact=True).check()
        host.get_by_text("Proposing No by your toggle; boilerplate says Yes (Synthetic boilerplate).", exact=True).wait_for()
        self.assertEqual(host.get_by_role("combobox", name=f"Answer {FUTURE_LABEL}", exact=True).input_value(), "no")
        self.assertFalse(host.get_by_role("checkbox", name=f"Select {FUTURE_LABEL}", exact=True).is_checked())
        self.assertFalse(host.get_by_role("checkbox", name=f"Replace existing {FUTURE_LABEL}", exact=True).is_checked())
        self.assertEqual(host.get_by_role("textbox", name="Answer First name", exact=True).input_value(), "Edited synthetic name")
        self.assertTrue(host.get_by_role("checkbox", name="Select First name", exact=True).is_checked())
        host.get_by_role("checkbox", name=TOGGLE_LABEL, exact=True).uncheck()
        self.page.wait_for_function("mode === 'truthful'")
        self.page.wait_for_function("document.querySelector('#portal-panel-host').shadowRoot.querySelector('[aria-label=\"Answer Will you require sponsorship in the future?\"]').value === 'yes'")
        self.assertFalse(host.get_by_role("checkbox", name=f"Select {FUTURE_LABEL}", exact=True).is_checked())

    def test_toggle_is_disabled_during_selected_fill(self):
        host = self.open_panel()
        self.page.evaluate("holdFill = true")
        host.get_by_role("checkbox", name="Select First name", exact=True).check()
        host.locator("#match-page").check()
        host.get_by_role("button", name="Fill selected fields", exact=True).click()
        self.page.wait_for_function("typeof releaseFill === 'function'")
        disabled = host.get_by_role("checkbox", name=TOGGLE_LABEL, exact=True).is_disabled()
        self.page.evaluate("releaseFill()")
        self.page.wait_for_function("!document.querySelector('#portal-panel-host').shadowRoot.querySelector('button.primary').disabled")
        self.assertTrue(disabled)
        self.assertFalse(host.get_by_role("checkbox", name=TOGGLE_LABEL, exact=True).is_disabled())

    def test_reopen_discards_sponsorship_cache_from_another_mode(self):
        host = self.open_panel()
        host.get_by_role("checkbox", name=f"Select {FUTURE_LABEL}", exact=True).check()
        host.get_by_role("checkbox", name="Select First name", exact=True).check()
        self.page.evaluate("async () => {mode = 'screening_no'; await reopen();}")
        self.assertEqual(host.get_by_role("combobox", name=f"Answer {FUTURE_LABEL}", exact=True).input_value(), "no")
        self.assertFalse(host.get_by_role("checkbox", name=f"Select {FUTURE_LABEL}", exact=True).is_checked())
        self.assertTrue(host.get_by_role("checkbox", name="Select First name", exact=True).is_checked())
        host.get_by_role("checkbox", name=f"Select {FUTURE_LABEL}", exact=True).check()
        self.page.evaluate("async () => {mode = 'truthful'; await reopen();}")
        self.assertEqual(host.get_by_role("combobox", name=f"Answer {FUTURE_LABEL}", exact=True).input_value(), "yes")
        self.assertFalse(host.get_by_role("checkbox", name=f"Select {FUTURE_LABEL}", exact=True).is_checked())

    def test_failed_mode_save_preserves_review_and_truthful_mode(self):
        host = self.open_panel()
        self.page.evaluate("failMode = true")
        host.get_by_role("checkbox", name=f"Select {FUTURE_LABEL}", exact=True).check()
        host.get_by_role("checkbox", name=TOGGLE_LABEL, exact=True).click()
        host.get_by_text("Synthetic mode save failed", exact=True).wait_for()
        self.assertEqual(self.page.evaluate("mode"), "truthful")
        self.assertFalse(host.get_by_role("checkbox", name=TOGGLE_LABEL, exact=True).is_checked())
        self.assertTrue(host.get_by_role("checkbox", name=f"Select {FUTURE_LABEL}", exact=True).is_checked())
        self.assertEqual(host.get_by_role("combobox", name=f"Answer {FUTURE_LABEL}", exact=True).input_value(), "yes")
