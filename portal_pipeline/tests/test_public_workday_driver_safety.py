"""Synthetic safety probes for Claude's handoff. No live browser or private data."""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Config
SOURCE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE_DIR))
import workday_run as driver


class DriverSafetyTests(unittest.TestCase):
    def run_main(self, title="My Information", results=None, dialog_after_fill=False):
        page = MagicMock(url="https://safety-fixture.myworkdayjobs.com/application")
        page.locator.return_value.count.return_value = 0
        dialog = MagicMock()
        dialog.count.side_effect = lambda: int(dialog_after_fill and fill.called)
        button = MagicMock()
        button.count.return_value = 1
        button.inner_text.return_value = "Save and Continue"
        page.locator.side_effect = lambda selector: button if selector == driver.NEXT_SELECTOR else dialog
        reports = tempfile.TemporaryDirectory()
        self.addCleanup(reports.cleanup)
        browser = MagicMock()
        playwright = MagicMock()
        playwright.chromium.connect_over_cdp.return_value = browser
        fill = MagicMock(return_value=results or [])
        upload = MagicMock(return_value=None)
        with contextlib.ExitStack() as stack:
            for name, value in {
                "page_of": MagicMock(return_value=page),
                "inject": MagicMock(),
                "step_title": MagicMock(return_value=title),
                "build_profile": MagicMock(return_value={}),
                "run_page": fill,
                "upload_resume": upload,
                "wait_for_person": MagicMock(return_value=True),
                "learn": MagicMock(return_value=0),
                "MAX_PAGES": 1,
                "dialog_open": MagicMock(side_effect=lambda _page: bool(dialog_after_fill and fill.called)),
                "RUNS_DIR": Path(reports.name),
            }.items():
                stack.enter_context(patch.object(driver, name, value))
            stack.enter_context(patch.object(driver, "sync_playwright", return_value=contextlib.nullcontext(playwright)))
            stack.enter_context(patch.object(driver.time, "sleep"))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            driver.main([])
        return fill, upload, button

    def test_review_stops_before_any_fill_or_upload(self):
        fill, upload, _ = self.run_main(title="Review")
        self.assertEqual((fill.call_count, upload.call_count), (0, 0))

    def test_dialog_appearing_during_fill_blocks_next(self):
        _, _, button = self.run_main(dialog_after_fill=True)
        button.click.assert_not_called()

    def test_failed_row_creation_stops_fill_for_page(self):
        field = {"id": "synthetic", "status": "prepared", "proposal": "invented", "blocked": False,
                 "type": "text", "disabled": False, "current": ""}
        page = MagicMock()
        page.evaluate.return_value = [{"status": "failed"}]
        with patch.object(driver, "ensure_rows", return_value=False), \
             patch.object(driver, "bind_rows", return_value={}), \
             patch.object(driver, "scan", return_value=[field]), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertRaises(driver.DriverStopped, driver.run_page, page, {}, False)
        page.evaluate.assert_not_called()

    def test_untrusted_hostname_is_not_selected(self):
        page = MagicMock()
        page.url = "https://myworkdayjobs.com.attacker.invalid/application"
        browser = MagicMock()
        browser.contexts = [MagicMock(pages=[page])]
        with self.assertRaises(SystemExit):
            driver.page_of(browser)

    def test_multiple_workday_tabs_require_selection(self):
        pages = [MagicMock(url="https://one.myworkdayjobs.com/application"),
                 MagicMock(url="https://two.myworkdayjobs.com/application")]
        browser = MagicMock()
        browser.contexts = [MagicMock(pages=pages)]
        with self.assertRaises(SystemExit):
            driver.page_of(browser)

    def test_history_values_do_not_enter_global_question_memory(self):
        field = {"id": "synthetic-history", "blocked": False, "current": "Invented Employer", "proposal": "", "type": "text",
                 "label": "Company", "record": {"id": "employment:synthetic", "group": "employment", "index": None}}
        memory = {"schema_version": 1, "answers": {}}
        with patch.object(driver, "scan", return_value=[field]), \
             patch.object(driver.answer_memory, "load_memory", return_value=memory), \
             patch.object(driver.answer_memory, "save_memory"):
            driver.learn(MagicMock(), {}, [])
        self.assertEqual(memory["answers"], {})

    def test_history_values_remain_excluded_after_manual_entry(self):
        field = {"id": "history", "blocked": False, "current": "Invented Employer", "proposal": "", "type": "text",
                 "label": "Company", "record": {"id": "employment:synthetic", "group": "employment"}}
        memory = {"schema_version": 1, "answers": {}}
        with patch.object(driver, "scan", return_value=[field]), \
             patch.object(driver.answer_memory, "load_memory", return_value=memory), \
             patch.object(driver.answer_memory, "save_memory") as save:
            driver.learn(MagicMock(), {}, [{**field, "current": ""}])
        self.assertEqual(memory["answers"], {})
        save.assert_not_called()

    def test_new_manual_contact_answer_is_learned(self):
        field = {"id": "contact", "blocked": False, "current": "Invented source", "proposal": "", "type": "text",
                 "label": "How did you hear about us?", "record": None}
        memory = {"schema_version": 1, "answers": {}}
        with patch.object(driver, "scan", return_value=[field]), \
             patch.object(driver.answer_memory, "load_memory", return_value=memory), \
             patch.object(driver.answer_memory, "save_memory") as save:
            count = driver.learn(MagicMock(), {}, [{**field, "current": ""}])
        self.assertEqual(count, 1)
        self.assertEqual(driver.answer_memory.lookup(memory, field["label"]), field["current"])
        save.assert_called_once_with(memory)

    def test_contact_page_does_not_require_history_add_buttons(self):
        page = MagicMock()
        with patch.object(driver, "has_heading", return_value=False), patch.object(driver, "click_add") as click:
            self.assertTrue(driver.ensure_rows(page, {"employment": [{}], "education": [{}]}))
        click.assert_not_called()

    def test_unknown_step_cannot_be_written(self):
        fill, upload, button = self.run_main(title="")
        fill.assert_not_called()
        upload.assert_not_called()
        button.click.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
