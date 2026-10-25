"""Workday search pickers verify exact pill labels and remove mismatched results."""
from pathlib import Path

from browser_test_support import SyntheticBrowserTest

SCRIPT = Path(__file__).resolve().parents[1] / "extension" / "workday-picker.js"
PAGE = '''<div id="question"><div data-automation-id="multiselectInputContainer" id="picker">
<ul role="listbox" data-automation-id="selectedItemList"></ul>
<input id="education-school" name="school" data-uxi-widget-type="selectinput" placeholder="Search">
</div><div data-automation-id="multiselectInputContainer" id="other-picker">
<ul role="listbox" data-automation-id="selectedItemList"></ul>
<input id="other" data-uxi-widget-type="selectinput" placeholder="Search">
</div></div><input id="plain">
<script>
window.RESULTS = {"quantitative finance": "Quantitative Finance", "finance": "Finance", "rutgers": "Rutgers University-Newark"};
window.keyEvents = 0;
window.inputEvents = 0;
window.removedLabels = [];
window.addPill = (container, label) => {
  const item = document.createElement("li");
  item.setAttribute("data-automation-id", "menuItem");
  const pill = document.createElement("div");
  pill.setAttribute("role", "option"); pill.setAttribute("data-automation-id", "selectedItem");
  pill.setAttribute("aria-label", label + ", press delete to clear value.");
  const remove = document.createElement("div"); remove.setAttribute("data-automation-id", "DELETE_charm");
  remove.addEventListener("click", () => { window.removedLabels.push(label); item.remove(); });
  const text = document.createElement("p"); text.setAttribute("data-automation-id", "promptOption");
  text.setAttribute("data-automation-label", label); text.textContent = label;
  pill.append(remove, text); item.append(pill);
  container.querySelector('[data-automation-id="selectedItemList"]').append(item);
};
const input = document.getElementById("education-school");
input.addEventListener("input", () => { window.inputEvents++; });
input.addEventListener("keyup", () => { window.keyEvents++; });
input.addEventListener("keydown", event => {
  window.keyEvents++;
  if (event.key !== "Enter") return;
  const query = input.value.toLowerCase();
  setTimeout(() => {
    const label = window.RESULTS[query];
    if (!label) return;
    window.addPill(document.getElementById("picker"), label);
    input.value = "";
  }, 300);
});
</script>'''


class WorkdayPickerTests(SyntheticBrowserTest):
    def open_picker_page(self, results=None):
        self.open_markup(PAGE)
        if results is not None:
            self.page.evaluate("results => { window.RESULTS = results; }", results)
        self.page.add_script_tag(path=str(SCRIPT))

    def choose(self, candidates):
        return self.page.evaluate("candidates => PortalWorkdayPicker.choose(document.getElementById('education-school'), candidates)", candidates)

    def selected(self):
        return self.page.evaluate("PortalWorkdayPicker.selected(document.getElementById('education-school'))")

    def test_exact_first_candidate_is_selected(self):
        self.open_picker_page()
        self.assertEqual(self.choose(["quantitative finance", "finance"]), {
            "status": "selected", "label": "Quantitative Finance", "tried": ["quantitative finance"]})
        self.assertEqual(self.selected(), ["Quantitative Finance"])
        self.assertEqual(self.page.locator("#education-school").input_value(), "")
        self.assertEqual(self.page.evaluate("window.keyEvents"), 2)

    def test_mismatched_pill_is_removed_before_second_candidate(self):
        self.open_picker_page()
        self.assertEqual(self.choose(["rutgers", "finance"]), {
            "status": "selected", "label": "Finance", "tried": ["rutgers", "finance"]})
        self.assertEqual(self.selected(), ["Finance"])
        self.assertEqual(self.page.evaluate("window.removedLabels"), ["Rutgers University-Newark"])

    def test_no_result_leaves_empty_input_and_no_pills(self):
        self.open_picker_page()
        self.assertEqual(self.choose(["missing"]), {"status": "not_found", "tried": ["missing"]})
        self.assertEqual(self.page.locator("#education-school").input_value(), "")
        self.assertEqual(self.page.locator('[data-automation-id="selectedItem"]').count(), 0)

    def test_existing_selection_is_preserved_without_typing(self):
        self.open_picker_page()
        self.page.evaluate("window.addPill(document.getElementById('picker'), 'Existing School')")
        self.assertEqual(self.choose(["finance"]), {"status": "already_selected", "label": "Existing School"})
        self.assertEqual(self.selected(), ["Existing School"])
        self.assertEqual(self.page.evaluate("[window.keyEvents, window.inputEvents]"), [0, 0])

    def test_disabled_input_throws_without_typing(self):
        self.open_picker_page()
        self.page.locator("#education-school").evaluate("input => { input.disabled = true; }")
        with self.assertRaisesRegex(Exception, "cannot be edited"):
            self.choose(["finance"])
        self.assertEqual(self.page.evaluate("[window.keyEvents, window.inputEvents]"), [0, 0])

    def test_guard_aborts_before_typing(self):
        self.open_picker_page()
        with self.assertRaisesRegex(Exception, "Guard stopped"):
            self.page.evaluate("PortalWorkdayPicker.choose(document.getElementById('education-school'), ['finance'], () => { throw new Error('Guard stopped'); })")
        self.assertEqual(self.page.locator("#education-school").input_value(), "")
        self.assertEqual(self.page.evaluate("[window.keyEvents, window.inputEvents]"), [0, 0])

    def test_selected_ignores_other_picker_in_shared_parent(self):
        self.open_picker_page()
        self.page.evaluate("window.addPill(document.getElementById('other-picker'), 'Other School')")
        self.assertEqual(self.selected(), [])
        self.page.evaluate("window.addPill(document.getElementById('picker'), 'Own School')")
        self.assertEqual(self.selected(), ["Own School"])

    def test_selected_falls_back_to_parent_without_other_picker_pills(self):
        self.open_picker_page()
        self.page.evaluate("""() => {
          window.addPill(document.getElementById('other-picker'), 'Other School');
          window.addPill(document.getElementById('picker'), 'Own School');
          document.getElementById('question').append(document.querySelector('#picker ul'));
        }""")
        self.assertEqual(self.selected(), ["Own School"])

    def test_matches_and_identity(self):
        self.open_picker_page()
        info = self.page.evaluate("() => { const input = document.getElementById('education-school'); return {m: PortalWorkdayPicker.matches(input), p: PortalWorkdayPicker.matches(document.getElementById('plain')), i: PortalWorkdayPicker.identity(input)}; }")
        self.assertTrue(info["m"])
        self.assertFalse(info["p"])
        self.assertEqual(info["i"], "education-school|school|selectinput|INPUT")

    def test_unusable_candidates_throw_without_typing(self):
        self.open_picker_page()
        for candidates in ([], ["", "!!!", None], "finance"):
            with self.subTest(candidates=candidates):
                with self.assertRaisesRegex(Exception, "Provide an exact candidate"):
                    self.choose(candidates)
        self.assertEqual(self.page.evaluate("[window.keyEvents, window.inputEvents]"), [0, 0])

    def test_normalized_label_matches_without_fuzzy_matching(self):
        self.open_picker_page({"quantitative-finance": "Quantitative Finance"})
        self.assertEqual(self.choose(["quantitative-finance"]), {
            "status": "selected", "label": "Quantitative Finance", "tried": ["quantitative-finance"]})
