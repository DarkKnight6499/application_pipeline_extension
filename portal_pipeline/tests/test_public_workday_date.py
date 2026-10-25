"""Workday date spinbuttons: exact values, guarded native writes, and settled readback."""
from pathlib import Path

from browser_test_support import SyntheticBrowserTest

SCRIPT = Path(__file__).resolve().parents[1] / "extension" / "workday-date.js"
MONTH_ID = "workExperience-3--startDate-dateSectionMonth-input"
YEAR_ID = "workExperience-3--endDate-dateSectionYear-input"
PAGE = f'''<input role="spinbutton" id="{MONTH_ID}" name="startMonth" value="03">
<input role="spinbutton" id="{YEAR_ID}" name="endYear" value="2020">
<input role="spinbutton" id="education-2--firstYearAttended-dateSectionYear-input" value="2010">
<input role="spinbutton" id="education-2--lastYearAttended-dateSectionYear-input" value="2014">
<input role="spinbutton" id="workExperience-3--startDate-dateSectionYear-input">
<input role="spinbutton" id="workExperience-3--endDate-dateSectionMonth-input">
<input id="ordinary" type="text">
<input id="other" role="spinbutton">
<input id="ordinary-1--startDate-dateSectionMonth-input" type="text">
<div id="wrong-tag" role="spinbutton"></div>
<script>
window.dateEvents = [];
for (const type of ["input", "change", "blur"]) {{
  document.addEventListener(type, event => window.dateEvents.push({{id: event.target.id, type, bubbles: event.bubbles}}));
}}
</script>'''


class WorkdayDateTests(SyntheticBrowserTest):
    def open_date_page(self):
        self.open_markup(PAGE)
        self.page.add_script_tag(path=str(SCRIPT))

    def write(self, field_id, value):
        return self.page.evaluate("({id, value}) => PortalWorkdayDate.write(document.getElementById(id), value)",
                                  {"id": field_id, "value": value})

    def test_matches_only_supported_date_spinbuttons(self):
        self.open_date_page()
        result = self.page.evaluate("() => [...document.querySelectorAll('input, #wrong-tag')].map(element => PortalWorkdayDate.matches(element))")
        self.assertEqual(result[:10], [True] * 6 + [False] * 4)
        self.assertFalse(self.page.evaluate("PortalWorkdayDate.matches(null)"))

    def test_part_read_and_identity(self):
        self.open_date_page()
        info = self.page.evaluate("id => { const element = document.getElementById(id); return {part: PortalWorkdayDate.part(element), read: PortalWorkdayDate.read(element), identity: PortalWorkdayDate.identity(element)}; }", MONTH_ID)
        self.assertEqual(info, {"part": "month", "read": "03", "identity": f"{MONTH_ID}|startMonth|spinbutton|INPUT"})
        self.assertEqual(self.page.evaluate("id => PortalWorkdayDate.part(document.getElementById(id))", YEAR_ID), "year")
        self.write(MONTH_ID, "5")
        self.assertEqual(self.page.evaluate("id => PortalWorkdayDate.identity(document.getElementById(id))", MONTH_ID), info["identity"])

    def test_write_sets_month_and_year_and_fires_bubbling_events(self):
        self.open_date_page()
        self.assertEqual(self.write(MONTH_ID, "5"), "05")
        self.assertEqual(self.write(YEAR_ID, "2026"), "2026")
        self.assertEqual(self.page.locator(f'[id="{MONTH_ID}"]').input_value(), "05")
        self.assertEqual(self.page.locator(f'[id="{YEAR_ID}"]').input_value(), "2026")
        events = self.page.evaluate("dateEvents.filter(event => event.type !== 'blur')")
        self.assertEqual(events, [{"id": field_id, "type": event_type, "bubbles": True}
                                  for field_id in [MONTH_ID, YEAR_ID] for event_type in ["input", "change"]])

    def test_invalid_values_throw_before_writing(self):
        self.open_date_page()
        for field_id, value, message in [(MONTH_ID, "13", "month"), (MONTH_ID, "ab", "month"),
                                         (MONTH_ID, "0", "month"), (MONTH_ID, " 5", "month"),
                                         (MONTH_ID, "05\n", "month"), (YEAR_ID, "202", "four digits"),
                                         (YEAR_ID, "2026\n", "four digits")]:
            with self.subTest(field_id=field_id, value=value):
                with self.assertRaisesRegex(Exception, message):
                    self.write(field_id, value)
        self.assertEqual(self.page.locator(f'[id="{MONTH_ID}"]').input_value(), "03")
        self.assertEqual(self.page.locator(f'[id="{YEAR_ID}"]').input_value(), "2020")
        self.assertEqual(self.page.evaluate("dateEvents"), [])

    def test_blur_reversion_throws(self):
        self.open_date_page()
        self.page.evaluate("id => { const element = document.getElementById(id); const old = element.value; element.addEventListener('blur', () => { element.value = old; }); }", MONTH_ID)
        with self.assertRaisesRegex(Exception, "The date field did not keep the value. Enter it manually."):
            self.write(MONTH_ID, "05")
        self.assertEqual(self.page.locator(f'[id="{MONTH_ID}"]').input_value(), "03")

    def test_month_readback_accepts_one_digit(self):
        self.open_date_page()
        self.page.evaluate("id => { const element = document.getElementById(id); element.addEventListener('blur', () => { element.value = String(Number(element.value)); }); }", MONTH_ID)
        self.assertEqual(self.write(MONTH_ID, "05"), "05")
        self.assertEqual(self.page.locator(f'[id="{MONTH_ID}"]').input_value(), "5")

    def test_native_setter_bypasses_instance_setter(self):
        self.open_date_page()
        self.page.evaluate("id => { const element = document.getElementById(id); const native = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value'); Object.defineProperty(element, 'value', {get() { return native.get.call(this); }, set() { throw new Error('Instance setter called'); }}); }", MONTH_ID)
        self.assertEqual(self.write(MONTH_ID, "05"), "05")

    def test_guard_aborts_before_any_write(self):
        self.open_date_page()
        with self.assertRaisesRegex(Exception, "Guard stopped"):
            self.page.evaluate("id => PortalWorkdayDate.write(document.getElementById(id), '05', () => { throw new Error('Guard stopped'); })", MONTH_ID)
        self.assertEqual(self.page.locator(f'[id="{MONTH_ID}"]').input_value(), "03")
        self.assertEqual(self.page.evaluate("dateEvents"), [])

    def test_guard_rechecks_after_input_event(self):
        self.open_date_page()
        self.page.evaluate("id => document.getElementById(id).addEventListener('input', () => { window.dateStopped = true; })", MONTH_ID)
        with self.assertRaisesRegex(Exception, "Guard stopped"):
            self.page.evaluate("id => PortalWorkdayDate.write(document.getElementById(id), '05', () => { if (window.dateStopped) throw new Error('Guard stopped'); })", MONTH_ID)
        self.assertEqual(self.page.evaluate("dateEvents.map(event => event.type)"), ["input"])

    def test_unsupported_field_is_refused(self):
        self.open_date_page()
        with self.assertRaisesRegex(Exception, "Not a Workday date field"):
            self.write("ordinary", "05")
        self.assertEqual(self.page.locator("#ordinary").input_value(), "")

    def test_reloading_module_preserves_api(self):
        self.open_date_page()
        self.page.evaluate("window.originalDateApi = PortalWorkdayDate")
        self.page.add_script_tag(path=str(SCRIPT))
        self.assertTrue(self.page.evaluate("PortalWorkdayDate === window.originalDateApi"))
