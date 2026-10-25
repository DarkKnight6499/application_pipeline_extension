"""Workday button menus: open through aria-controls, choose one exact option, read the button back."""
from pathlib import Path

from browser_test_support import SyntheticBrowserTest

SCRIPT = Path(__file__).resolve().parents[1] / "extension" / "workday-menu.js"
PAGE = '''<div class="q"><p>Are you authorized to work here?*</p>
<button type="button" id="primaryQuestionnaire--aaa" name="aaa" aria-haspopup="listbox" aria-expanded="false">Select One Required</button></div>
<div id="host" style="height:60px;overflow:auto"></div>
<script>
window.OPTIONS = ["Select One", "Yes", "No", "Yes, with sponsorship", "Maybe"];
const button = document.getElementById("primaryQuestionnaire--aaa");
let counter = 0;
button.addEventListener("click", () => {
  const open = button.getAttribute("aria-expanded") === "true";
  document.querySelectorAll("ul[role=listbox]").forEach(node => node.remove());
  if (open) { button.setAttribute("aria-expanded", "false"); button.removeAttribute("aria-controls"); return; }
  const id = "t4hi" + (++counter);
  const list = document.createElement("ul");
  list.id = id; list.setAttribute("role", "listbox"); list.tabIndex = -1;
  for (const label of window.OPTIONS) {
    const item = document.createElement("li"); item.setAttribute("role", "option"); item.innerHTML = "<div>" + label + "</div>";
    item.addEventListener("click", () => { button.textContent = label; button.setAttribute("aria-expanded", "false"); button.removeAttribute("aria-controls"); list.remove(); });
    list.append(item);
  }
  document.getElementById("host").append(list);
  button.setAttribute("aria-expanded", "true"); button.setAttribute("aria-controls", id);
});
</script>'''


class WorkdayMenuTests(SyntheticBrowserTest):
    def open_menu_page(self, options=None):
        self.open_markup(PAGE)
        if options is not None:
            self.page.evaluate("options => { window.OPTIONS = options; }", options)
        self.page.add_script_tag(path=str(SCRIPT))

    def choose(self, answer):
        return self.page.evaluate("answer => PortalWorkdayMenu.choose(document.getElementById('primaryQuestionnaire--aaa'), answer)", answer)

    def text(self):
        return self.page.evaluate("document.getElementById('primaryQuestionnaire--aaa').textContent")

    def test_exact_option_is_chosen_and_read_back(self):
        self.open_menu_page()
        self.assertEqual(self.choose("yes"), "Yes")
        self.assertEqual(self.text(), "Yes")

    def test_prefix_option_is_not_chosen_and_menu_closes(self):
        self.open_menu_page()
        with self.assertRaisesRegex(Exception, "No unique exact"):
            self.choose("Yes, with")
        self.assertEqual(self.text(), "Select One Required")
        self.assertEqual(self.page.locator("ul[role=listbox]").count(), 0)

    def test_duplicate_labels_are_refused(self):
        self.open_menu_page(["Select One", "Yes", "Yes"])
        with self.assertRaisesRegex(Exception, "No unique exact"):
            self.choose("Yes")
        self.assertEqual(self.text(), "Select One Required")

    def test_offscreen_option_is_scrolled_into_view_and_chosen(self):
        self.open_menu_page(["Select One"] + [f"Option {i}" for i in range(40)] + ["Target"])
        self.assertEqual(self.choose("Target"), "Target")

    def test_describe_matches_read_and_question(self):
        self.open_menu_page()
        info = self.page.evaluate("() => { const b = document.getElementById('primaryQuestionnaire--aaa'); return {m: PortalWorkdayMenu.matches(b), d: PortalWorkdayMenu.describe(b), r: PortalWorkdayMenu.read(b), q: PortalWorkdayMenu.question(b)}; }")
        self.assertTrue(info["m"])
        self.assertEqual(info["r"], "")
        self.assertEqual(info["d"]["options"], [])
        self.assertEqual(info["q"], "Are you authorized to work here?*")

    def test_question_comes_from_fieldset_legend_despite_mirror_input(self):
        self.open_markup('''<fieldset><legend><div><p><b>Are you legally authorized to work?</b><abbr title="required">*</abbr></p></div></legend>
<div><button type="button" id="primaryQuestionnaire--bbb" value="v1" aria-haspopup="listbox" aria-label=" Yes Required">Yes</button><input type="text" value="v1"></div></fieldset>''')
        self.page.add_script_tag(path=str(SCRIPT))
        self.assertEqual(self.page.evaluate("PortalWorkdayMenu.question(document.getElementById('primaryQuestionnaire--bbb'))"), "Are you legally authorized to work?*")

