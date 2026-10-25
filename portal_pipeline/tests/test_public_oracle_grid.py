"""Oracle grid comboboxes: choose exact popup labels and verify the input value."""
from pathlib import Path

from browser_test_support import SyntheticBrowserTest

SCRIPT = Path(__file__).resolve().parents[1] / "extension" / "oracle-grid.js"
PAGE = '''<input id="question123" name="workAuthorization" role="combobox" aria-haspopup="grid" aria-controls="question123-listbox" aria-expanded="false">
<div id="host" style="height:60px;overflow:auto"></div>
<script>
window.OPTIONS = ["Yes", "No", "Yes, with sponsorship"];
window.LAYOUT = "listbox";
window.FILTER = false;
window.MISMATCH = false;
window.inputEvents = 0;
window.optionClicks = 0;
window.escapeEvents = 0;
const input = document.getElementById("question123");
function closePopup() {
  document.getElementById("question123-listbox")?.remove();
  input.setAttribute("aria-expanded", "false");
}
function renderPopup(filtered) {
  closePopup();
  const popup = document.createElement("div");
  popup.id = "question123-listbox"; popup.setAttribute("role", window.LAYOUT);
  const labels = window.FILTER && !filtered ? [] : window.OPTIONS;
  for (const label of labels) {
    const item = document.createElement("div");
    item.setAttribute("role", window.LAYOUT === "grid" ? "row" : "option");
    if (window.LAYOUT === "grid") {
      const cell = document.createElement("span"); cell.setAttribute("role", "gridcell"); cell.textContent = label; item.append(cell);
    } else { item.textContent = label; }
    item.addEventListener("click", () => {
      window.optionClicks++;
      input.value = window.MISMATCH ? "Unexpected" : label.replace(/\\s+/g, " ").trim();
      if (!window.MISMATCH) closePopup();
    });
    popup.append(item);
  }
  document.getElementById("host").append(popup);
  input.setAttribute("aria-expanded", "true");
}
input.addEventListener("click", () => renderPopup(false));
input.addEventListener("input", () => { window.inputEvents++; if (window.FILTER) renderPopup(true); });
input.addEventListener("keydown", event => { if (event.key === "Escape") { window.escapeEvents++; closePopup(); } });
</script>'''


class OracleGridTests(SyntheticBrowserTest):
    def open_grid_page(self, layout="listbox", options=None, filtering=False, mismatch=False):
        self.open_markup(PAGE)
        self.page.evaluate("settings => { window.LAYOUT = settings.layout; window.FILTER = settings.filtering; window.MISMATCH = settings.mismatch; if (settings.options !== null) window.OPTIONS = settings.options; }",
                           {"layout": layout, "options": options, "filtering": filtering, "mismatch": mismatch})
        self.page.add_script_tag(path=str(SCRIPT))

    def choose(self, answer):
        return self.page.evaluate("answer => PortalOracleGrid.choose(document.getElementById('question123'), answer)", answer)

    def text(self):
        return self.page.locator("#question123").input_value()

    def test_exact_option_is_chosen_in_both_layouts(self):
        for layout in ("listbox", "grid"):
            with self.subTest(layout=layout):
                self.open_grid_page(layout, ["Yes", "  Yes,   with sponsorship  "])
                self.assertEqual(self.choose(" YES, with   sponsorship "), "Yes, with sponsorship")
                self.assertEqual(self.text(), "Yes, with sponsorship")
                self.assertEqual(self.page.evaluate("inputEvents"), 0)
                self.assertEqual(self.page.evaluate("optionClicks"), 1)

    def test_prefix_option_is_refused_and_popup_closes(self):
        for layout in ("listbox", "grid"):
            with self.subTest(layout=layout):
                self.open_grid_page(layout)
                with self.assertRaisesRegex(Exception, "No unique exact option matches the answer"):
                    self.choose("Yes, with")
                self.assertEqual(self.text(), "")
                self.assertEqual(self.page.evaluate("optionClicks"), 0)
                self.assertEqual(self.page.locator("#question123-listbox").count(), 0)
                self.assertEqual(self.page.evaluate("inputEvents"), 0)

    def test_duplicate_labels_are_refused(self):
        for layout in ("listbox", "grid"):
            with self.subTest(layout=layout):
                self.open_grid_page(layout, ["Yes", " YES "])
                with self.assertRaisesRegex(Exception, "No unique exact option matches the answer"):
                    self.choose("Yes")
                self.assertEqual(self.text(), "")
                self.assertEqual(self.page.evaluate("optionClicks"), 0)

    def test_type_to_filter_uses_input_event_then_exact_choice(self):
        for layout in ("listbox", "grid"):
            with self.subTest(layout=layout):
                self.open_grid_page(layout, filtering=True)
                self.assertEqual(self.choose("yes"), "Yes")
                self.assertEqual(self.page.evaluate("inputEvents"), 1)
                self.assertEqual(self.page.evaluate("optionClicks"), 1)

    def test_filtering_does_not_allow_prefix_match(self):
        self.open_grid_page(filtering=True)
        with self.assertRaisesRegex(Exception, "No unique exact option matches the answer"):
            self.choose("Yes, with")
        self.assertEqual(self.page.evaluate("optionClicks"), 0)
        self.assertEqual(self.page.evaluate("escapeEvents"), 1)

    def test_read_back_mismatch_throws_and_closes_with_escape(self):
        self.open_grid_page(mismatch=True)
        with self.assertRaisesRegex(Exception, "The menu did not show the chosen option"):
            self.choose("Yes")
        self.assertEqual(self.text(), "Unexpected")
        self.assertEqual(self.page.evaluate("escapeEvents"), 1)
        self.assertEqual(self.page.locator("#question123-listbox").count(), 0)

    def test_guard_aborts_before_option_click(self):
        self.open_grid_page()
        with self.assertRaisesRegex(Exception, "Guard stopped"):
            self.page.evaluate("""() => PortalOracleGrid.choose(document.getElementById('question123'), 'Yes', () => {
              if (document.getElementById('question123').getAttribute('aria-expanded') === 'true') throw new Error('Guard stopped');
            })""")
        self.assertEqual(self.text(), "")
        self.assertEqual(self.page.evaluate("optionClicks"), 0)
        self.assertEqual(self.page.evaluate("inputEvents"), 0)
        self.assertEqual(self.page.evaluate("escapeEvents"), 1)

    def test_describe_reads_options_only_while_expanded(self):
        for layout in ("listbox", "grid"):
            with self.subTest(layout=layout):
                self.open_grid_page(layout)
                info = self.page.evaluate("() => { const input = document.getElementById('question123'); input.value = ' Yes '; return {m: PortalOracleGrid.matches(input), d: PortalOracleGrid.describe(input), r: PortalOracleGrid.read(input), i: PortalOracleGrid.identity(input)}; }")
                self.assertTrue(info["m"])
                self.assertEqual(info["r"], "Yes")
                self.assertIn("workAuthorization", info["i"])
                self.assertEqual(info["d"]["options"], [])
                self.page.locator("#question123").click()
                info = self.page.evaluate("PortalOracleGrid.describe(document.getElementById('question123'))")
                self.assertEqual([option["label"] for option in info["options"]], ["Yes", "No", "Yes, with sponsorship"])
                self.assertTrue(info["dropdown_state"]["options_observed"])
                self.page.evaluate("document.getElementById('question123').setAttribute('aria-expanded', 'false')")
                self.assertEqual(self.page.evaluate("PortalOracleGrid.describe(document.getElementById('question123')).options"), [])

    def test_ordinary_listbox_combobox_does_not_match(self):
        self.open_grid_page()
        self.assertFalse(self.page.evaluate("() => { const input = document.getElementById('question123'); input.setAttribute('aria-haspopup', 'listbox'); return PortalOracleGrid.matches(input); }"))

    def test_missing_options_throw_after_filter_attempt(self):
        self.open_grid_page(options=[])
        with self.assertRaisesRegex(Exception, "The menu popup did not open"):
            self.choose("Yes")
        self.assertEqual(self.page.evaluate("optionClicks"), 0)
        self.assertEqual(self.page.evaluate("inputEvents"), 1)
        self.assertEqual(self.page.evaluate("escapeEvents"), 1)
