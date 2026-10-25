"""Search pickers try each alias, select only one exact option, and otherwise fall back."""
from pathlib import Path

from browser_test_support import SyntheticBrowserTest

SCRIPT = Path(__file__).resolve().parents[1] / "extension" / "adapters" / "picker-search.js"
PAGE = '''<input id="box"><div id="results"></div>
<script>
const catalog = ["Rutgers University - Newark", "Rutgers University - New Brunswick", "Rutgers Business School", "Newark College"];
const box = document.getElementById("box"), results = document.getElementById("results");
box.addEventListener("input", () => {
  const flat = text => text.toLowerCase().replace(/[^a-z0-9 ]+/g, " ").replace(/ +/g, " ").trim(), q = flat(box.value);
  results.innerHTML = q ? catalog.filter(name => flat(name).includes(q)).map(name => `<div role="option" class="opt">${name}</div>`).join("") : "";
});
results.addEventListener("click", event => { window.picked = event.target.textContent; });
window.run = candidates => PortalPickerSearch.searchAndChoose({input: box, candidates, fallback: "Rutgers",
  options: () => [...document.querySelectorAll(".opt")].map(node => ({label: node.textContent, node})), click: node => node.click(), waitMs: 600, stepMs: 20});
</script>'''


class PickerSearchTests(SyntheticBrowserTest):
    def run_picker(self, candidates):
        self.open_markup(PAGE)
        self.page.add_script_tag(path=str(SCRIPT))
        return self.page.evaluate("candidates => run(candidates)", candidates), self.page.evaluate("window.picked || null")

    def test_first_alias_without_exact_match_is_skipped_then_second_selects(self):
        result, picked = self.run_picker(["Rutgers Newark", "Rutgers University, Newark", "Rutgers University - Newark"])
        self.assertEqual(result["status"], "selected")
        self.assertEqual(picked, "Rutgers University - Newark")

    def test_punctuation_differences_still_match_exactly(self):
        result, picked = self.run_picker(["Rutgers University Newark"])
        self.assertEqual(picked, "Rutgers University - Newark")

    def test_prefix_only_results_are_not_selected(self):
        result, picked = self.run_picker(["Rutgers"])
        self.assertEqual(result["status"], "fallback")
        self.assertIsNone(picked)
        self.assertEqual(result["text"], "Rutgers")
        self.assertEqual(self.page.evaluate("document.getElementById('box').value"), "")

    def test_all_aliases_are_tried_before_fallback(self):
        result, _ = self.run_picker(["Nowhere U", "Nowhere College"])
        self.assertEqual(result["tried"], ["Nowhere U", "Nowhere College"])
        self.assertEqual(result["status"], "fallback")

    def test_two_exact_matches_are_ambiguous(self):
        self.open_markup(PAGE.replace('"Newark College"]', '"Newark College", "Rutgers University Newark"]'))
        self.page.add_script_tag(path=str(SCRIPT))
        result = self.page.evaluate("candidates => run(candidates)", ["Rutgers University Newark"])
        self.assertEqual(result["status"], "ambiguous")
        self.assertIsNone(self.page.evaluate("window.picked || null"))
