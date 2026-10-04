"""Effective availability and inspection coverage on synthetic pages only."""
from browser_test_support import HERE, SyntheticBrowserTest


class PublicAvailabilityTests(SyntheticBrowserTest):
    def test_inherited_fieldset_disable_before_write(self):
        self.open_markup('<fieldset id="group"><label>First name<input id="first"></label></fieldset>')
        field = next(field for field in self.scan() if field["key"] == "first_name")
        self.page.locator("#group").evaluate("node => node.disabled=true")
        result = self.fill([{"id": field["id"], "value": "Synthetic"}])
        self.assertEqual(result[0]["status"], "failed")
        self.assertEqual(self.page.locator("#first").input_value(), "")

    def test_fieldset_first_legend_exception_stays_editable(self):
        self.open_markup('<fieldset disabled><legend><label>First name<input id="first"></label></legend></fieldset>')
        field = next(field for field in self.scan() if field["key"] == "first_name")
        self.assertFalse(field["disabled"])
        result = self.fill([{"id": field["id"], "value": "Synthetic"}])
        self.assertEqual(result[0]["status"], "filled")

    def test_radio_target_late_aria_disable_or_readonly_refused(self):
        for attribute in ("aria-disabled", "aria-readonly"):
            with self.subTest(attribute=attribute):
                self.open_markup('''<fieldset><legend>Are you willing to relocate?</legend>
                  <label><input type="radio" name="move" value="No">No</label>
                  <label><input id="yes" type="radio" name="move" value="Yes">Yes</label></fieldset>''')
                field = next(field for field in self.scan() if field["type"] == "radio")
                self.page.locator("#yes").evaluate("(node, attribute) => node.setAttribute(attribute,'true')", attribute)
                result = self.fill([{"id": field["id"], "value": "Yes"}])
                self.assertEqual(result[0]["status"], "failed")
                self.assertFalse(self.page.locator("#yes").is_checked())

    def test_disabled_optgroup_is_not_an_available_answer(self):
        self.open_markup('''<label>Are you willing to relocate?<select id="move"><option value=""></option>
          <optgroup disabled><option>Yes</option></optgroup><option>No</option></select></label>''')
        field = next(field for field in self.scan() if field["key"] == "relocation")
        self.assertTrue(next(option for option in field["options"] if option["label"] == "Yes")["disabled"])
        result = self.fill([{"id": field["id"], "value": "Yes"}])
        self.assertEqual(result[0]["status"], "failed")
        self.assertEqual(self.page.locator("#move").input_value(), "")

    def test_optgroup_disabled_after_scan_refused(self):
        self.open_markup('''<label>Are you willing to relocate?<select id="move"><option value=""></option>
          <optgroup id="group"><option>Yes</option></optgroup></select></label>''')
        field = next(field for field in self.scan() if field["key"] == "relocation")
        self.page.locator("#group").evaluate("node => node.disabled=true")
        result = self.fill([{"id": field["id"], "value": "Yes"}])
        self.assertEqual(result[0]["status"], "failed")
        self.assertEqual(self.page.locator("#move").input_value(), "")

    def test_duplicate_native_values_cannot_select_wrong_label(self):
        self.open_markup('''<label>Are you willing to relocate?<select id="move"><option value=""></option>
          <optgroup disabled><option value="same">No</option></optgroup>
          <option value="same">Yes</option></select></label>''')
        field = next(field for field in self.scan() if field["key"] == "relocation")
        result = self.fill([{"id": field["id"], "value": "Yes"}])
        self.assertEqual(result[0]["status"], "failed")
        self.assertEqual(self.page.locator("#move").input_value(), "")

    def test_duplicate_radio_values_cannot_select_wrong_label(self):
        self.open_markup('''<fieldset><legend>Are you willing to relocate?</legend>
          <label><input id="no" type="radio" name="move" value="same">No</label>
          <label><input id="yes" type="radio" name="move" value="same">Yes</label></fieldset>''')
        field = next(field for field in self.scan() if field["type"] == "radio")
        result = self.fill([{"id": field["id"], "value": "Yes"}])
        self.assertEqual(result[0]["status"], "failed")
        self.assertFalse(self.page.locator("#no").is_checked())
        self.assertFalse(self.page.locator("#yes").is_checked())


class PublicInspectionTests(SyntheticBrowserTest):
    def test_reports_unsupported_surfaces_without_contents(self):
        self.open_markup('''<label>First name<input value="VALUE_SENTINEL"></label>
          <iframe srcdoc="<input value='FRAME_SENTINEL'>"></iframe>
          <iframe hidden></iframe><div id="shadow-host"></div>
          <div role="spinbutton" aria-label="SECRET_SPIN_LABEL">5</div>
          <label>Password<input type="password" value="PASSWORD_SENTINEL"></label>
          <script>document.getElementById('shadow-host').attachShadow({mode:'open'}).innerHTML='<input value="SHADOW_SENTINEL">';</script>''')
        report = self.page.evaluate("PortalEngine.inspect()")
        self.assertEqual(report["coverage"]["scope"], "visible_light_dom_current_page")
        self.assertEqual(report["coverage"]["visible_iframes"], 1)
        self.assertEqual(report["coverage"]["visible_open_shadow_hosts"], 1)
        self.assertEqual(report["coverage"]["unsupported_spinbuttons"], 1)
        self.assertEqual(set(report["coverage"]["reason_codes"]), {"iframe_uninspected", "open_shadow_uninspected", "spinbutton_unsupported"})
        for sentinel in ("VALUE_SENTINEL", "FRAME_SENTINEL", "SHADOW_SENTINEL", "PASSWORD_SENTINEL", "SECRET_SPIN_LABEL"):
            self.assertNotIn(sentinel, str(report))
        self.assertEqual(report["protected_fields_omitted"], 3)

    def test_inspection_panel_shows_coverage_and_unopened_choices(self):
        self.open_markup('''<iframe></iframe><div role="combobox" aria-label="Are you willing to relocate?"
          aria-controls="lazy" aria-expanded="false" aria-valuetext="">Choose</div>''')
        report = self.page.evaluate("PortalEngine.inspect()")
        combo = next(field for field in report["fields"] if field["type"] == "combobox")
        self.assertEqual(combo["dropdown_state"], {"popup_present": False, "expanded": False, "options_observed": False})
        self.page.add_script_tag(path=str(HERE / "extension/panel.js"))
        self.page.evaluate("async () => PortalPanel.open(null,null,{inspectionOnly:true,transport:{inspect:()=>PortalEngine.inspect()}})")
        text = self.page.locator("#portal-panel-host").evaluate("node => node.shadowRoot.textContent")
        self.assertIn("1 visible iframe", text)
        self.assertIn("Choices have not been inspected", text)
        self.assertIn("current-page snapshot", text)
