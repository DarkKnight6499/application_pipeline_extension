"""Synthetic listbox availability regressions without candidate or employer data."""
import unittest

from browser_test_support import SyntheticBrowserTest

# Synthetic control configuration
COMBO_MARKUP = """
<div id="combo" role="combobox" aria-label="Are you willing to relocate?"
  aria-controls="choices" aria-expanded="true" aria-valuetext="">Choose</div>
"""
OPTION_MARKUP = '<div id="yes" role="option">Yes</div>'
POPUP_MARKUP = '<div id="choices" role="listbox">{options}</div>'
ANSWER = "Yes"


class PublicListboxTests(SyntheticBrowserTest):
    def open_dropdown(self, popup):
        self.open_markup(COMBO_MARKUP + popup)
        self.page.evaluate("""() => {
          globalThis.optionClicks = 0;
          document.getElementById('yes').onclick = () => {
            optionClicks++;
            document.getElementById('combo').setAttribute('aria-valuetext', 'Yes');
          };
        }""")

    def fill_dropdown(self):
        field = next(field for field in self.scan() if field["type"] == "combobox")
        return self.fill([{"id": field["id"], "value": ANSWER}])

    def assert_refused(self, result):
        self.assertEqual(result[0]["status"], "failed")
        self.assertEqual(self.page.evaluate("optionClicks"), 0)
        self.assertEqual(self.page.locator("#combo").get_attribute("aria-valuetext"), "")

    def test_aria_hidden_option_refused(self):
        option = OPTION_MARKUP.replace('role="option"', 'role="option" aria-hidden="true"')
        self.open_dropdown(POPUP_MARKUP.format(options=option))
        self.assert_refused(self.fill_dropdown())

    def test_aria_hidden_option_ancestor_refused(self):
        self.open_dropdown(POPUP_MARKUP.format(options='<div aria-hidden="true">' + OPTION_MARKUP + '</div>'))
        self.assert_refused(self.fill_dropdown())

    def test_aria_hidden_popup_ancestor_refused(self):
        self.open_dropdown('<div aria-hidden="true">' + POPUP_MARKUP.format(options=OPTION_MARKUP) + '</div>')
        self.assert_refused(self.fill_dropdown())

    def test_hidden_ancestor_refused_despite_css_override(self):
        self.open_dropdown('<style>[hidden]{display:block}</style><div hidden>'
                           + POPUP_MARKUP.format(options=OPTION_MARKUP) + '</div>')
        self.assert_refused(self.fill_dropdown())

    def choose_with_final_guard(self, mutation):
        self.open_dropdown(POPUP_MARKUP.format(options=OPTION_MARKUP))
        return self.page.evaluate("""async mutation => {
          let calls = 0;
          try {
            await PortalListbox.choose(document.getElementById('combo'), 'Yes', () => {
              if (++calls === 3) new Function(mutation)();
            });
            return [{status: 'filled'}];
          } catch (error) {
            return [{status: 'failed', message: error.message}];
          }
        }""", mutation)

    def test_matched_option_hidden_during_final_guard_refused(self):
        self.assert_refused(self.choose_with_final_guard("document.getElementById('yes').setAttribute('aria-hidden', 'true');"))

    def test_popup_closed_during_final_guard_refused(self):
        self.assert_refused(self.choose_with_final_guard("document.getElementById('combo').setAttribute('aria-expanded', 'false');"))

    def test_replaced_option_during_final_guard_refused(self):
        self.assert_refused(self.choose_with_final_guard("const node=document.getElementById('yes');node.replaceWith(node.cloneNode(true));"))

    def test_disabled_option_during_final_guard_refused(self):
        self.assert_refused(self.choose_with_final_guard("document.getElementById('yes').setAttribute('aria-disabled', 'true');"))

    def test_closed_popup_keeps_inventory_and_opens(self):
        self.open_dropdown(POPUP_MARKUP.format(options=OPTION_MARKUP).replace('role="listbox"', 'role="listbox" hidden'))
        self.page.evaluate("""() => {
          const combo = document.getElementById('combo');
          combo.setAttribute('aria-expanded', 'false');
          combo.onclick = () => {
            document.getElementById('choices').hidden = false;
            combo.setAttribute('aria-expanded', 'true');
          };
        }""")
        field = next(field for field in self.scan() if field["type"] == "combobox")
        self.assertEqual([option["label"] for option in field["options"]], [ANSWER])
        self.assertEqual(self.fill([{"id": field["id"], "value": ANSWER}])[0]["status"], "filled")
        self.assertEqual(self.page.evaluate("optionClicks"), 1)

    def test_describe_reports_closed_inventory_without_opening(self):
        self.open_dropdown(POPUP_MARKUP.format(options=OPTION_MARKUP).replace('role="listbox"', 'role="listbox" hidden'))
        self.page.evaluate("""() => {
          globalThis.comboClicks = 0;
          const combo = document.getElementById('combo');
          combo.setAttribute('aria-expanded', 'false');
          combo.onclick = () => comboClicks++;
        }""")
        description = self.page.evaluate("PortalListbox.describe(document.getElementById('combo'))")
        self.assertEqual(description["dropdown_state"], {"popup_present": True, "expanded": False, "options_observed": True})
        self.assertEqual(description["options"][0]["label"], ANSWER)
        self.assertEqual(self.page.evaluate("comboClicks + optionClicks"), 0)
        self.assertTrue(self.page.locator("#choices").evaluate("node => node.hidden"))

    def test_describe_reports_lazy_and_unsupported_states_without_clicks(self):
        self.open_markup(COMBO_MARKUP)
        self.page.evaluate("""() => {
          globalThis.comboClicks = 0;
          const combo = document.getElementById('combo');
          combo.setAttribute('aria-expanded', 'false');
          combo.onclick = () => comboClicks++;
        }""")
        description = self.page.evaluate("PortalListbox.describe(document.getElementById('combo'))")
        self.assertEqual(description["dropdown_state"], {"popup_present": False, "expanded": False, "options_observed": False})
        self.page.evaluate("document.getElementById('combo').setAttribute('aria-readonly', 'true')")
        unsupported = self.page.evaluate("PortalListbox.describe(document.getElementById('combo'))")
        self.assertFalse(unsupported["supported"])
        self.assertIsNone(unsupported["dropdown_state"])
        self.assertEqual(self.page.evaluate("comboClicks"), 0)

    def test_lazy_popup_remains_supported(self):
        self.open_markup(COMBO_MARKUP)
        self.page.evaluate("""() => {
          globalThis.optionClicks = 0;
          const combo = document.getElementById('combo');
          combo.setAttribute('aria-expanded', 'false');
          combo.onclick = () => setTimeout(() => {
            const popup = document.createElement('div');
            popup.id = 'choices';
            popup.setAttribute('role', 'listbox');
            const option = document.createElement('div');
            option.id = 'yes';
            option.setAttribute('role', 'option');
            option.textContent = 'Yes';
            option.onclick = () => {optionClicks++; combo.setAttribute('aria-valuetext', 'Yes');};
            popup.append(option);
            document.body.append(popup);
            combo.setAttribute('aria-expanded', 'true');
          }, 50);
        }""")
        self.assertEqual(self.fill_dropdown()[0]["status"], "filled")
        self.assertEqual(self.page.evaluate("optionClicks"), 1)


if __name__ == "__main__":
    unittest.main()
