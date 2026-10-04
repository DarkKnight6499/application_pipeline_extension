"""Session profile facts and cached choices use fabricated browser data only."""
from browser_test_support import HERE, SyntheticBrowserTest
import test_public_session_profile_panel as panel_fixture


class SessionProfileScalarTests(SyntheticBrowserTest):
    def test_object_and_array_fact_values_stop_before_scan_or_fill(self):
        for kind, value in (("object", {"nested": "unsupported"}), ("array", ["unsupported"])):
            with self.subTest(kind=kind):
                if kind != "object":
                    self.setUp()
                self.open_markup('<label>Job description<textarea id="description"></textarea></label>')
                self.page.add_script_tag(path=str(HERE / "extension/panel.js"))
                self.page.evaluate("""value => {
                  globalThis.scanCalls = 0;
                  globalThis.fillCalls = 0;
                  globalThis.apiCalls = [];
                  const session = {id: 'a'.repeat(32), mode: 'audited_import', company: 'Synthetic', role: 'Role', url: location.href};
                  const api = async path => {
                    apiCalls.push(path);
                    if (path === '/api/current') return session;
                    if (path === `/api/sessions/${session.id}/profile`)
                      return {values: {'employment.0.description': {value, source: 'Synthetic source', status: 'prepared'}}};
                    if (path === '/api/profile') throw new Error('Global profile must not load');
                    return {};
                  };
                  PortalPanel.open(api, {load: async () => ({}), save: async () => {}}, {targetUrl: location.href,
                    transport: {scan: () => {scanCalls++; return [];}, fill: () => {fillCalls++; return [];},
                      inspect: () => ({host: location.host, fields: [], coverage: {reason_codes: []}})}});
                }""", value)
                host = self.page.locator("#portal-panel-host")
                host.get_by_text("Invalid session profile", exact=False).wait_for(timeout=1000)
                self.assertEqual(self.page.evaluate("scanCalls"), 0)
                self.assertEqual(self.page.evaluate("fillCalls"), 0)
                self.assertEqual(host.get_by_role("button", name="Fill selected fields", exact=True).count(), 0)
                self.assertNotIn("/api/profile", self.page.evaluate("apiCalls"))
                if kind != "array":
                    self.tearDown()

    def test_changed_proposal_resets_edit_selection_and_overwrite(self):
        host = panel_fixture.SessionProfilePanelTests.open_panel(self)
        answer = host.get_by_role("textbox", name="Answer Job description", exact=True)
        answer.fill("Human reviewed edit")
        answer.dispatch_event("change")
        host.get_by_role("checkbox", name="Select Job description", exact=True).check()
        host.get_by_role("checkbox", name="Replace existing Job description", exact=True).check()
        self.page.evaluate("activeDescription = 'New per-application override'; reopenSessionPanel()")
        host = self.page.locator("#portal-panel-host")
        self.assertEqual(host.get_by_role("textbox", name="Answer Job description", exact=True).input_value(), "New per-application override")
        self.assertFalse(host.get_by_role("checkbox", name="Select Job description", exact=True).is_checked())
        self.assertFalse(host.get_by_role("checkbox", name="Replace existing Job description", exact=True).is_checked())
        self.assertEqual(self.page.evaluate("fillCalls.length"), 0)
