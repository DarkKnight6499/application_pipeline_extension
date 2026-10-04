"""Regression coverage for unanswered select values in synthetic answer sheet exports."""

from browser_test_support import HERE, SyntheticBrowserTest
from test_public_answer_sheet import MARKUP


class PlaceholderExportTests(SyntheticBrowserTest):
    def test_unanswered_select_exports_empty_pending_value(self):
        self.open_markup(MARKUP + '''
<label>Favorite synthetic beverage<select id="beverage"><option value="">Choose an option</option><option value="tea">Tea</option></select></label>
''')
        self.page.add_script_tag(path=str(HERE / "extension/panel.js"))
        self.page.evaluate("""async () => {
          globalThis.calls = [];
          const session = {id: 'a'.repeat(32), mode: 'audited_import', company: 'Synthetic Co', role: 'Synthetic Role', url: location.href};
          const api = async (path, body) => {
            calls.push({path, body});
            if (path === '/api/profile') return {values: {}};
            if (path === '/api/current') return session;
            if (path.endsWith('/preflight')) return {items: [], manual_field_ids: [], ack_required: false};
            if (path.endsWith('/answer-sheet')) return {html: '<p>synthetic</p>', sheet: {rows: []}};
            return {};
          };
          await PortalPanel.open(api, {load: async () => null, save: async () => {}}, {targetUrl: location.href});
        }""")
        host = self.page.locator("#portal-panel-host")
        answer = host.get_by_role("combobox", name="Answer Favorite synthetic beverage", exact=True)
        answer.wait_for()
        self.assertEqual(answer.input_value(), "")
        with self.page.expect_download():
            host.get_by_role("button", name="Export answer sheet", exact=True).click()
        request = next(call for call in self.page.evaluate("calls") if call["path"].endswith("/answer-sheet"))
        exported = next(item for item in request["body"]["fields"] if item["label"] == "Favorite synthetic beverage")
        self.assertEqual(exported["proposal"], "")
        self.assertEqual(exported["status"], "pending")
        self.assertNotEqual(exported["source"], "Edited in review panel")
