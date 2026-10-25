"""Search pickers fill through aliases: school by its alias list, field of study by the row's degree."""
from pathlib import Path

from browser_test_support import SyntheticBrowserTest

PICKER_SCRIPT = Path(__file__).resolve().parents[1] / "extension" / "workday-picker.js"
HOST = "safety-fixture.myworkdayjobs.com"


def box(id_, label):
    return f'''<label for="{id_}">{label}</label><div data-automation-id="multiselectInputContainer"><input id="{id_}" placeholder="Search" data-uxi-widget-type="selectinput" value="">
<ul role="listbox" data-automation-id="selectedItemList"></ul></div>'''


PAGE = f'''<div>{box("education-5--school", "School or University*")}{box("education-5--fieldOfStudy", "Field of Study")}</div>
<script>
const RESULTS = {{"rutgers university-newark": "Rutgers University-Newark", "quantitative finance": "Quantitative Finance"}};
document.addEventListener("keydown", event => {{
  if (event.key !== "Enter" || event.target.tagName !== "INPUT") return;
  const input = event.target, label = RESULTS[input.value.trim().toLowerCase()];
  setTimeout(() => {{
    input.value = "";
    if (!label) return;
    const list = input.closest("[data-automation-id=multiselectInputContainer]").querySelector("ul");
    list.innerHTML = '<li><div role="option" data-automation-id="selectedItem"><div data-automation-id="DELETE_charm"></div><p data-automation-id="promptOption" data-automation-label="' + label + '">' + label + '</p></div></li>';
  }}, 100);
}});
</script>'''
PROFILE = {"values": {"education.0.school": {"value": "RUTGERS BUSINESS SCHOOL", "source": "x"},
                      "education.0.degree": {"value": "Master of Quantitative Finance (MQF)", "source": "x"}},
           "pickers": {"school": [{"names": ["Rutgers University - Newark", "Rutgers Business School", "Rutgers University-Newark"], "fallback": "Rutgers"}],
                       "field_of_study": [{"names": ["Master of Quantitative Finance (MQF)", "Quantitative Finance", "Finance"], "fallback": "Finance"}]}}


class PickerFillTests(SyntheticBrowserTest):
    def bound(self, reopen=True):
        if reopen:
            self.open_markup(PAGE)
            self.page.add_script_tag(path=str(PICKER_SCRIPT))
        first = self.page.evaluate("p => PortalEngine.scan(p)", PROFILE)
        bindings = {f["record"]["id"]: 0 for f in first if f["record"]}
        fields = self.page.evaluate("([p, b]) => PortalEngine.scan(p, {bindings: b})", [PROFILE, bindings])
        return {f["structure"]["dom_id"]: f for f in fields}

    def test_school_and_field_of_study_are_prepared_with_alias_candidates(self):
        fields = self.bound()
        self.assertEqual(fields["education-5--school"]["proposal"], "RUTGERS BUSINESS SCHOOL")
        self.assertIn("Rutgers University-Newark", fields["education-5--school"]["candidates"])
        self.assertEqual(fields["education-5--fieldOfStudy"]["candidates"][:2], ["Master of Quantitative Finance (MQF)", "Quantitative Finance"])
        self.assertEqual(fields["education-5--fieldOfStudy"]["status"], "prepared")

    def test_fill_picks_the_first_alias_the_portal_offers(self):
        fields = self.bound()
        picks = [fields[i] for i in ("education-5--school", "education-5--fieldOfStudy")]
        results = self.fill([{"id": f["id"], "value": f["proposal"]} for f in picks])
        self.assertEqual([r["status"] for r in results], ["filled", "filled"], results)
        labels = self.page.evaluate("[...document.querySelectorAll('[data-automation-id=promptOption]')].map(n => n.dataset.automationLabel)")
        self.assertEqual(labels, ["Rutgers University-Newark", "Quantitative Finance"])

    def test_already_selected_picker_is_preserved(self):
        fields = self.bound()
        self.fill([{"id": fields["education-5--school"]["id"], "value": "x"}])
        again = self.bound(reopen=False)
        self.assertEqual(again["education-5--school"]["current"], "Rutgers University-Newark")
