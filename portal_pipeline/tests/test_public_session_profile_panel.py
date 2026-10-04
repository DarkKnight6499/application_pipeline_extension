"""Session profile review state uses synthetic values and pages only."""
from browser_test_support import HERE, SyntheticBrowserTest

SESSION_ID = "a" * 32
DESCRIPTION_ID = "employment.0.description"
GLOBAL_VALUE = "Global profile description"
SESSION_VALUE = "Session profile description"
DRAFT_VALUE = "Tailored synthetic bullets, needing review."
DRAFT_SOURCE = "resume_content.json#experience"


class SessionProfilePanelTests(SyntheticBrowserTest):
    def open_panel(self, fail_scoped=False, scoped_shape="valid", with_draft=False):
        self.open_markup('<label>Job description<textarea id="description"></textarea></label>')
        self.page.add_script_tag(path=str(HERE / "extension/panel.js"))
        self.page.evaluate("""({failScoped, scopedShape, withDraft}) => {
          globalThis.activeDescription = "Session profile description";
          globalThis.failScoped = failScoped;
          globalThis.calls = [];
          globalThis.observedProfiles = [];
          globalThis.saved = {};
          const session = {id: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", mode: "audited_import", company: "Synthetic Employer",
            role: "Synthetic Role", url: location.href};
          const makeProfile = (description, scoped) => ({sponsorship_answer_mode: "truthful", values: {
            "employment.0.description": {value: description, source: scoped ? "Application_Boilerplate.md#Role Descriptions" : "Global profile source", status: "prepared"},
            ...(withDraft ? {"employment.0.description_draft": {value: "Tailored synthetic bullets, needing review.",
              source: "resume_content.json#experience", status: "draft_needs_review"}} : {})
          }});
          const baseProfile = makeProfile("Global profile description", false);
          const api = async (path, body) => {
            calls.push({path, body});
            if (path === "/api/current") return session;
            if (path === "/api/profile") return baseProfile;
            if (path.endsWith("/profile")) {
              if (failScoped) throw new Error("Synthetic session profile unavailable");
              if (scopedShape === "empty") return {values: {}};
              if (scopedShape === "missing") return {};
              if (scopedShape === "null") return {values: null};
              if (scopedShape === "array") return {values: []};
              if (scopedShape === "malformed") return {values: {"employment.0.description": "not a fact object"}};
              return makeProfile(activeDescription, true);
            }
            if (path.endsWith("/preflight")) return {items: [], manual_field_ids: []};
            return {};
          };
          const storage = {load: async () => structuredClone(saved), save: async (key, value) => {saved = structuredClone(value);}};
          const options = {targetUrl: location.href, transport: {
            scan: profile => {
              observedProfiles.push(structuredClone(profile));
              const fact = profile.values["employment.0.description"] || {};
              return [{id: "employment-description", label: "Job description", key: "employment.0.description", section: "employment",
                type: "textarea", current: "", options: [], record: null, required: false, blocked: false, disabled: false,
                proposal: fact.value || "", source: fact.source || "Manual answer required", status: fact.status || "pending", truth: null, structure: {}}];
            },
            fill: async selections => selections.map(item => ({id: item.id, status: "filled", message: "Synthetic completion"})),
            inspect: () => ({host: location.host, fields: [], coverage: {reason_codes: []}})
          }};
          globalThis.reopenSessionPanel = () => PortalPanel.open(api, storage, options);
          reopenSessionPanel();
        }""", {"failScoped": fail_scoped, "scopedShape": scoped_shape, "withDraft": with_draft})
        return self.page.locator("#portal-panel-host")

    def test_scoped_profile_proposals_are_used(self):
        host = self.open_panel()
        self.assertEqual(host.get_by_role("textbox", name="Answer Job description", exact=True).input_value(), SESSION_VALUE)
        self.assertTrue(self.page.evaluate("observedProfiles.at(-1).values['employment.0.description'].source.includes('Application_Boilerplate.md')"))

    def test_scoped_profile_failure_does_not_fall_back_to_global_values(self):
        host = self.open_panel(fail_scoped=True)
        self.assertGreater(host.get_by_text("Synthetic session profile unavailable", exact=True).count(), 0)
        self.assertEqual(host.get_by_text(GLOBAL_VALUE, exact=True).count(), 0)
        self.assertEqual(host.get_by_role("checkbox", name="Select Job description", exact=True).count(), 0)
        self.assertTrue(any(call["path"].endswith("/profile") for call in self.page.evaluate("calls")))

    def test_empty_scoped_values_object_is_valid_and_pending_fields_stay_reviewable(self):
        host = self.open_panel(scoped_shape="empty")
        self.assertEqual(self.page.evaluate("observedProfiles.length"), 1)
        self.assertEqual(host.get_by_role("textbox", name="Answer Job description", exact=True).input_value(), "")
        self.assertEqual(host.get_by_role("checkbox", name="Select Job description", exact=True).count(), 1)

    def test_malformed_scoped_profile_shapes_are_rejected(self):
        for shape in ("missing", "null", "array", "malformed"):
            with self.subTest(shape=shape):
                self.setUp()
                host = self.open_panel(scoped_shape=shape)
                self.assertGreater(host.get_by_text("Invalid session profile", exact=False).count(), 0)
                self.assertEqual(self.page.evaluate("observedProfiles.length"), 0)
                self.tearDown()

    def test_cached_review_is_cleared_when_backend_proposal_changes(self):
        host = self.open_panel()
        checkbox = host.get_by_role("checkbox", name="Select Job description", exact=True)
        checkbox.check()
        self.page.evaluate("activeDescription = 'New per-application override'")
        self.page.evaluate("reopenSessionPanel()")
        host = self.page.locator("#portal-panel-host")
        self.assertEqual(host.get_by_role("textbox", name="Answer Job description", exact=True).input_value(), "New per-application override",
                         self.page.evaluate("({activeDescription, profiles: observedProfiles.map(profile => profile.values['employment.0.description']?.value), saved})"))
        self.assertFalse(host.get_by_role("checkbox", name="Select Job description", exact=True).is_checked())

    def test_tailored_draft_shows_review_status_and_source_without_selection(self):
        host = self.open_panel(with_draft=True)
        host.get_by_text(DRAFT_VALUE, exact=True).wait_for(timeout=2000)
        self.assertTrue(host.get_by_text(DRAFT_SOURCE, exact=True).is_visible())
        self.assertTrue(host.get_by_text("draft_needs_review", exact=True).is_visible())
        self.assertFalse(host.get_by_role("checkbox", name="Select Job description", exact=True).is_checked())
        self.assertEqual(host.get_by_role("textbox", name="Answer Job description", exact=True).input_value(), SESSION_VALUE)
