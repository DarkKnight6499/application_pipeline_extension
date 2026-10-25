"""Oracle Fusion (oraclecloud.com) live adapter: real grid popup of one gridcell per row, exact choice, honeypot never filled."""
from pathlib import Path

from browser_test_support import SyntheticBrowserTest

EXT = Path(__file__).resolve().parents[1] / "extension"
URL = "https://example-employer.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/1/apply/section/1"
PAGE = '''<form>
<label for="firstName-1">First Name</label><input id="firstName-1" name="firstName" value="">
<label for="honey-1">honeypot</label><input id="honey-1" name="honey-pot" value="">
<label for="region2-37">State *</label><input id="region2-37" name="region2" role="combobox" aria-haspopup="grid" aria-controls="region2-37-listbox" aria-expanded="false" value="NJ">
<div id="host"></div></form>
<script>
const state = document.getElementById("region2-37");
state.addEventListener("click", () => {
  if (document.getElementById("region2-37-listbox")) return;
  const grid = document.createElement("div"); grid.id = "region2-37-listbox"; grid.setAttribute("role", "grid"); grid.setAttribute("aria-label", "State");
  ["NJ", "NY", "NV"].forEach((label, i) => {
    const row = document.createElement("div"); row.setAttribute("role", "row");
    const cell = document.createElement("div"); cell.setAttribute("role", "gridcell"); cell.id = "region2-37-listitem-" + i;
    cell.setAttribute("aria-selected", String(label === state.value)); cell.innerHTML = "<div><span>" + label + "</span></div>";
    cell.addEventListener("click", () => { state.value = label; state.setAttribute("aria-expanded", "false"); grid.remove(); });
    row.append(cell); grid.append(row);
  });
  document.getElementById("host").append(grid); state.setAttribute("aria-expanded", "true");
});
</script></form>'''


class OracleLiveTests(SyntheticBrowserTest):
    def scan(self):
        self.open_markup(PAGE, url=URL)
        for name in ("oracle-grid.js", "adapters/oracle.js", "oracle-live.js"):
            self.page.add_script_tag(path=str(EXT / name))
        return {f["structure"]["name"]: f for f in self.page.evaluate("PortalEngine.scan({values: {}})")}

    def test_state_is_a_grid_dropdown_and_honeypot_is_not_listed(self):
        fields = self.scan()
        self.assertEqual((fields["region2"]["type"], fields["region2"]["adapter"]), ("combobox", "oracle-grid"))
        self.assertNotIn("honey-pot", fields)

    def test_exact_gridcell_option_is_chosen_and_read_back(self):
        state = self.scan()["region2"]
        result = self.fill([{"id": state["id"], "value": "NY"}], {"overwrite": True})[0]
        self.assertEqual(result["status"], "filled", result)
        self.assertEqual(self.page.locator("#region2-37").input_value(), "NY")

    def test_prefix_is_not_chosen(self):
        state = self.scan()["region2"]
        result = self.fill([{"id": state["id"], "value": "N"}], {"overwrite": True})[0]
        self.assertEqual(result["status"], "failed", result)
        self.assertEqual(self.page.locator("#region2-37").input_value(), "NJ")

    def test_adapter_routes_oraclecloud_hosts_in_fill_mode(self):
        self.scan()
        info = self.page.evaluate("PortalAdapters.forLocation(location.href) && {id: PortalAdapters.forLocation(location.href).id, mode: PortalAdapters.forLocation(location.href).mode}")
        self.assertEqual(info, {"id": "oracle-jpmc", "mode": "fill"})

    def test_existing_state_is_preserved_without_overwrite(self):
        state = self.scan()["region2"]
        self.assertEqual(self.fill([{"id": state["id"], "value": "NY"}])[0]["status"], "preserved")
