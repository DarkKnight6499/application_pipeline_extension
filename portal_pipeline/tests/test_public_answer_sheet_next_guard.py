"""Synthetic answer-sheet progression regressions. Author: Yazad Madan."""

from browser_test_support import HERE, SyntheticBrowserTest


class AnswerSheetNextGuardTests(SyntheticBrowserTest):
    def open_page(self):
        self.open_markup('''<form id="details"><h1>Your details</h1>
          <label>First name<input id="first-name" value="Synthetic" required></label>
          <button id="next" type="button">Next</button></form>''')
        self.page.evaluate("""() => {
          document.getElementById('guard-submit').hidden = true;
          globalThis.nextClicks = 0;
          document.addEventListener('click', event => {
            if (event.target.closest('#next')) nextClicks++;
          }, true);
          globalThis.testAdapter = {...PortalAdapters.forLocation(location.href)};
        }""")
        self.page.add_script_tag(path=str(HERE / "extension/progress.js"))

    def assert_counters(self, next_clicks=0):
        self.assertEqual(self.page.evaluate(
            "[nextClicks, syntheticSubmitClicks, syntheticSubmitEvents]"), [next_clicks, 0, 0])

    def guarded(self):
        return self.page.evaluate("PortalProgress.guardedNext(testAdapter)")

    def test_answer_sheet_mode_refuses_next_even_with_completed_required_fields(self):
        self.open_page()
        self.page.evaluate("""() => {
          testAdapter.mode = 'answer_sheet_only';
          testAdapter.nextStep = () => ({kind: 'none', label: '', ref: null});
          PortalProgress.settings.allowGuardedNext = true;
        }""")
        sweep = self.page.evaluate("PortalProgress.requiredSweep(testAdapter)")
        self.assertEqual((sweep["checked"], sweep["missing"]), (1, []))
        self.assertEqual(self.page.evaluate("PortalProgress.nextStep().kind"), "next")
        result = self.guarded()
        self.assert_counters()
        self.assertEqual((result["status"], result["reason"]), ("refused", "answer_sheet_only"))
        self.assertEqual(self.page.locator("#first-name").input_value(), "Synthetic")

    def test_answer_sheet_mode_refuses_before_scanning_or_gate_callbacks(self):
        self.open_page()
        self.page.evaluate("""() => {
          testAdapter.mode = 'answer_sheet_only';
          testAdapter.scan = () => { throw new Error('Must not scan in answer-sheet mode.'); };
          testAdapter.humanGate = () => { throw new Error('Must not call gate in answer-sheet mode.'); };
          PortalProgress.settings.allowGuardedNext = true;
        }""")
        result = self.guarded()
        self.assert_counters()
        self.assertEqual((result["status"], result["reason"]), ("refused", "answer_sheet_only"))

    def test_mode_changed_during_required_sweep_refuses_next(self):
        self.open_page()
        result = self.page.evaluate("""async () => {
          const scan = testAdapter.scan;
          let scans = 0;
          testAdapter.scan = (...args) => {
            const fields = scan(...args);
            if (++scans === 1) setTimeout(() => { testAdapter.mode = 'answer_sheet_only'; }, 0);
            return fields;
          };
          PortalProgress.settings.allowGuardedNext = true;
          return PortalProgress.guardedNext(testAdapter);
        }""")
        self.assertEqual(self.page.evaluate("testAdapter.mode"), "answer_sheet_only")
        self.assert_counters()
        self.assertEqual((result["status"], result["reason"]), ("refused", "answer_sheet_only"))

    def test_fill_mode_still_clicks_next_once(self):
        self.open_page()
        self.assertEqual(self.page.evaluate("testAdapter.mode"), "fill")
        self.page.evaluate("PortalProgress.settings.allowGuardedNext = true")
        self.assertEqual(self.guarded()["status"], "clicked")
        self.assert_counters(next_clicks=1)

    def test_answer_sheet_mode_retains_default_off_reason(self):
        self.open_page()
        self.page.evaluate("testAdapter.mode = 'answer_sheet_only'")
        self.assertFalse(self.page.evaluate("PortalProgress.settings.allowGuardedNext"))
        result = self.guarded()
        self.assertEqual((result["status"], result["reason"]), ("refused", "guarded_next_off"))
        self.assert_counters()
