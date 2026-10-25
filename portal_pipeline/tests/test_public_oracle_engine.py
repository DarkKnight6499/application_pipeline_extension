"""Oracle grid comboboxes scan as dropdowns through the engine and fill with an exact option."""
from pathlib import Path

from browser_test_support import SyntheticBrowserTest

GRID = Path(__file__).resolve().parents[1] / "extension" / "oracle-grid.js"
PAGE = '''<label for="state-1">State*</label><input id="state-1" name="state" role="combobox" aria-haspopup="grid" aria-controls="state-1-listbox" aria-expanded="false" value="">
<div id="host"></div>
<script>
const input = document.getElementById("state-1");
input.addEventListener("click", () => {
  if (document.getElementById("state-1-listbox")) return;
  const grid = document.createElement("div"); grid.id = "state-1-listbox"; grid.setAttribute("role", "grid");
  for (const label of ["New Jersey", "New York"]) {
    const row = document.createElement("div"); row.setAttribute("role", "row"); row.textContent = label;
    row.addEventListener("click", () => { input.value = label; input.setAttribute("aria-expanded", "false"); grid.remove(); });
    grid.append(row);
  }
  document.getElementById("host").append(grid); input.setAttribute("aria-expanded", "true");
});
</script>'''


class OracleEngineTests(SyntheticBrowserTest):
    def field(self):
        self.open_markup(PAGE)
        self.page.add_script_tag(path=str(GRID))
        return self.page.evaluate("PortalEngine.scan({values: {}})")

    def test_grid_combobox_is_a_supported_dropdown_field(self):
        state = [f for f in self.field() if f["structure"]["dom_id"] == "state-1"][0]
        self.assertEqual((state["type"], state["adapter"]), ("combobox", "oracle-grid"))

    def test_grid_combobox_fills_an_exact_option(self):
        state = [f for f in self.field() if f["structure"]["dom_id"] == "state-1"][0]
        result = self.fill([{"id": state["id"], "value": "New Jersey"}])[0]
        self.assertEqual(result["status"], "filled", result)
        self.assertEqual(self.page.locator("#state-1").input_value(), "New Jersey")
