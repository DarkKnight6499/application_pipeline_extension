"""Author: Yazad Madan. Regressions for the step_pass driver: report, search widgets, resume, history rows, conflicts, unknowns."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import batch_apply
import step_pass
from browser_test_support import SyntheticBrowserTest
from test_public_step_pass import collection, field_page

# Config
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
RESUME_BYTES = 11822
RESUME_KB = "11.54 KB"
RESUME_NAME = "Resume_Example.docx"
HISTORY = [
    {"title": "Analyst", "company": "Acme Bank", "location": "New York, NY", "start": "2020-03", "end": "2022-08", "description": "Built reports."},
    {"title": "Associate", "company": "Beta Corp", "location": "Boston, MA", "start": "2022-09", "current": True, "description": "Runs models."},
    {"school": "Rutgers University", "field": "Finance", "start": "2023-09", "end": "2025-05"},
]


def attachment_state(items=(), inputs=(0,)):
    empty = {"inputs": [], "items": []}
    return {"slots": {"resume": {"inputs": list(inputs), "items": list(items)}, "cover": dict(empty)}, "items": list(items), "unknown_inputs": []}


def attached(name, kb, index=0):
    return {"index": index, "name": name, "text": f"{name} {kb}", "identity_text": f"{name} {kb}"}


class ReportTests(unittest.TestCase):
    def test_report_has_company_timing_unknowns_and_exit_code(self):
        steps = [{"title": "My Experience", "seconds": 4.2, "changes": 3, "unknown": [{"label": "Q", "options": []}]}]
        unknowns = [{"label": "Q", "question": "Q full", "options": ["A"], "intent": None}]
        report = step_pass.build_report("Example", "2026-01-01T00:00:00", steps, unknowns, [{"label": "L"}], 2, "stopped", "My Experience")
        with tempfile.TemporaryDirectory() as folder:
            path = report.write(path=Path(folder) / "run.json")
            data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual((data["company"], data["exit_code"], data["final_step"]), ("Example", 2, "My Experience"))
        self.assertEqual(data["pages"][0]["title"], "My Experience")
        self.assertEqual((data["pages"][0]["seconds"], data["pages"][0]["changes"]), (4.2, 3))
        self.assertEqual(data["unknowns"], unknowns)
        self.assertEqual(data["conflicts"], [{"label": "L"}])
        self.assertTrue(data["started"] and data["finished"])
        self.assertEqual(data["unanswered"][0]["label"], "Q")

    def test_default_report_path_names_company(self):
        path = step_pass.default_report_path("Acme Bank, Inc.")
        self.assertEqual(path.parent, step_pass.RUNS_DIR)
        self.assertRegex(path.name, r"^\d{8}_\d{6}_step_pass_AcmeBankInc\.json$")


class BatchDriverTests(unittest.TestCase):
    def test_driver_defaults_to_apply_and_step_pass_needs_target_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(batch_apply.parse_args(["--folders", folder]).driver, "apply")
            with self.assertRaises(SystemExit), patch("sys.stderr"):
                batch_apply.parse_args(["--folders", folder, "--driver", "step_pass"])
            args = batch_apply.parse_args(["--folders", folder, "--driver", "step_pass", "--target-ids", "T1"])
            self.assertEqual(args.target_ids, ["T1"])

    def test_step_pass_job_launches_step_pass_with_report_path(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "2026-01-01_Example_Analyst"
            folder.mkdir()
            report = Path(root) / "report.json"
            job = {"folder": str(folder), "url": "https://example.myworkdayjobs.com/job", "target_id": "T1",
                   "report_path": str(report), "driver": "step_pass", "portal": "workday"}
            seen = {}

            def fake_run(command, **kwargs):
                seen["command"] = command
                report.write_text(json.dumps({"exit_code": 0}), encoding="utf-8")
                return SimpleNamespace(returncode=0)

            with patch.object(batch_apply.subprocess, "run", side_effect=fake_run):
                data = batch_apply.run_job(job)
        self.assertEqual(Path(seen["command"][2]).name, "step_pass.py")
        self.assertEqual(seen["command"][3], "Example")
        self.assertIn("--report-path", seen["command"])
        self.assertEqual(seen["command"][seen["command"].index("--target-id") + 1], "T1")
        self.assertEqual(data["exit_code"], 0)

    def test_step_pass_job_without_tab_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            job = {"folder": root, "url": "https://example.myworkdayjobs.com/job", "report_path": str(Path(root) / "r.json"),
                   "driver": "step_pass", "portal": "workday"}
            with patch.object(batch_apply.subprocess, "run") as run:
                data = batch_apply.run_job(job)
            run.assert_not_called()
        self.assertEqual(data["exit_code"], batch_apply.EXIT_FAILURE)


class SearchWidgetBrowserTests(SyntheticBrowserTest):
    def test_enter_reveals_options_and_the_match_is_clicked(self):
        page = self.browser.new_page()
        try:
            page.goto((FIXTURES / "workday_search_widget.html").as_uri())
            container = page.locator(step_pass.MULTISELECT).first
            box = container.locator("input").first
            box.fill("Rutgers")
            self.assertEqual(page.locator("#empty").inner_text(), "No Items")  # typing alone finds nothing
            chosen, names = step_pass.pick_search_option(page, container, "Rutgers University-Newark")
            self.assertEqual(chosen, "Rutgers University-Newark")
            self.assertEqual(names, ["Rutgers University-Newark"])
            self.assertEqual(page.locator(step_pass.MULTI_SELECTED).all_inner_texts(), ["Rutgers University-Newark"])
        finally:
            page.close()


class SearchWidgetMockTests(unittest.TestCase):
    def test_enter_is_pressed_after_typing_and_before_waiting(self):
        order = []
        box, option = Mock(), Mock()
        box.fill.side_effect = lambda text: order.append("fill")
        box.press.side_effect = lambda key: order.append(key)
        option.inner_text.return_value = "Company Website"
        option.wait_for.side_effect = lambda **kwargs: order.append("wait")
        page, container = Mock(), Mock()
        page.locator.return_value = collection([option])
        container.locator.return_value = collection([box])
        self.assertEqual(step_pass.pick_search_option(page, container, "Company Website")[0], "Company Website")
        self.assertEqual(order, ["fill", "Enter", "wait"])
        self.assertEqual(option.wait_for.call_args.kwargs["timeout"], step_pass.OPTION_WAIT_MS)
        page.locator.assert_called_with(step_pass.SEARCH_OPTIONS)


class ResumeTests(unittest.TestCase):
    def make_file(self, folder, size=RESUME_BYTES):
        path = Path(folder) / RESUME_NAME
        path.write_bytes(b"x" * size)
        return path

    def test_empty_slot_uploads_and_verifies_binary_kb(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.make_file(folder)
            page = Mock()
            page.evaluate.side_effect = [attachment_state(), attachment_state([attached(RESUME_NAME, RESUME_KB)])]
            status, detail = step_pass.ensure_resume(page, str(path))
        self.assertEqual((status, detail), ("uploaded", RESUME_KB))
        page.locator.return_value.nth.return_value.set_input_files.assert_called_once_with(str(path))

    def test_wrong_size_after_upload_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.make_file(folder)
            page = Mock()
            page.evaluate.side_effect = [attachment_state()] + [attachment_state([attached(RESUME_NAME, "9.99 KB")])] * 3
            with patch.object(step_pass, "UPLOAD_CONFIRM_SECONDS", 0):
                status, detail = step_pass.ensure_resume(page, str(path))
        self.assertEqual(status, "failed")
        self.assertIn("size_mismatch", detail)

    def test_stale_attachment_is_deleted_before_upload(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.make_file(folder)
            stale = attached(RESUME_NAME, "20.00 KB")
            page = Mock()
            reads = [attachment_state([stale]), attachment_state(), attachment_state([attached(RESUME_NAME, RESUME_KB)])]
            calls = []
            page.evaluate.side_effect = lambda *args: calls.append(args[0][:20]) or (reads.pop(0) if len(args) == 1 else None)
            status, _ = step_pass.ensure_resume(page, str(path))
        self.assertEqual(status, "uploaded")
        self.assertTrue(any("Attachment identity" in call or call.startswith("([item") for call in calls))

    def test_matching_file_is_left_alone(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.make_file(folder)
            page = Mock()
            page.evaluate.return_value = attachment_state([attached(RESUME_NAME, RESUME_KB)])
            self.assertEqual(step_pass.ensure_resume(page, str(path)), ("ok", ""))
        page.locator.assert_not_called()

    def test_missing_resume_flag_is_unknown_not_a_guess(self):
        page = Mock()
        page.evaluate.return_value = attachment_state()
        self.assertEqual(step_pass.ensure_resume(page, None)[0], "unknown")
        page.locator.assert_not_called()

    def test_step_without_upload_control_is_ignored(self):
        page = Mock()
        page.evaluate.return_value = {"slots": {"resume": {"inputs": [], "items": []}, "cover": {"inputs": [], "items": []}}}
        self.assertEqual(step_pass.ensure_resume(page, "anything"), ("absent", ""))


class HistoryBrowserTests(SyntheticBrowserTest):
    def open(self):
        page = self.browser.new_page()
        page.goto((FIXTURES / "workday_history.html").as_uri())
        return page

    def test_blank_rows_are_added_and_filled_with_typed_dates(self):
        page = self.open()
        try:
            log = []
            self.assertEqual(step_pass.fill_history(page, HISTORY, log), [])
            self.assertEqual(page.locator('[data-automation-id^="workExperience-"]').count(), 2)
            self.assertEqual(page.locator('[data-automation-id^="education-"]').count(), 1)
            first = page.locator('[data-automation-id="workExperience-1"]')
            self.assertEqual(first.locator("input[name=title]").input_value(), "Analyst")
            self.assertEqual(first.locator("input[id$=dateSectionMonth-input]").first.input_value(), "03")
            self.assertEqual(first.locator("input[id$=dateSectionYear-input]").first.input_value(), "2020")
            self.assertEqual(first.locator("input[id$=dateSectionMonth-input]").nth(1).input_value(), "08")
            second = page.locator('[data-automation-id="workExperience-2"]')
            self.assertTrue(second.locator("input[name=current]").is_checked())
            self.assertEqual(second.locator("input[id$=dateSectionYear-input]").nth(1).input_value(), "")  # current job has no end date
            school = page.locator('[data-automation-id="education-1"]')
            self.assertEqual(school.locator(step_pass.MULTI_SELECTED).all_inner_texts(), ["Rutgers University-Newark"])
            self.assertEqual(school.locator("input[name=firstYear]").input_value(), "2023")
            self.assertEqual(school.locator("input[name=lastYear]").input_value(), "2025")
            self.assertEqual(page.locator("#add-clicks").inner_text(), "3")
        finally:
            page.close()

    def test_matching_rows_are_never_duplicated(self):
        page = self.open()
        try:
            page.evaluate("seedWork({title: 'Analyst', company: 'Acme Bank Limited'})")
            page.evaluate("seedWork({title: 'Associate', company: 'Beta Corp'})")
            page.evaluate("seedEdu({school: 'Rutgers University-Newark'})")
            log = []
            self.assertEqual(step_pass.fill_history(page, HISTORY, log), [])
            self.assertEqual(page.locator("#add-clicks").inner_text(), "0")
            self.assertEqual(log, [])  # prefilled rows are preserved, not retyped
            self.assertEqual(page.locator('[data-automation-id="workExperience-1"] input[name=location]').input_value(), "")
        finally:
            page.close()

    def test_only_the_missing_entry_adds_a_row(self):
        page = self.open()
        try:
            page.evaluate("seedWork({title: 'Analyst', company: 'Acme Bank'})")
            step_pass.fill_history(page, HISTORY[:2], [])
            self.assertEqual(page.locator("#add-clicks").inner_text(), "1")
            self.assertEqual(page.locator('[data-automation-id="workExperience-2"] input[name=company]').input_value(), "Beta Corp")
        finally:
            page.close()


class ConflictTests(unittest.TestCase):
    def listbox_page(self, current):
        button = Mock()
        button.inner_text.return_value = current
        page, _ = field_page("Will you require sponsorship?*", {step_pass.LISTBOX: collection([button])})
        return page, button

    def test_filled_dropdown_with_different_stored_answer_is_a_conflict(self):
        page, _ = self.listbox_page("Yes")
        conflicts = []
        with patch.object(step_pass, "resolve", return_value="No"), patch.object(step_pass, "pick_option") as picker:
            step_pass.pass_over_step(page, "Example", {}, [], conflicts=conflicts)
        picker.assert_not_called()
        self.assertEqual(conflicts, [{"label": "Will you require sponsorship?*", "current": "Yes", "wanted": "No"}])

    def test_overwrite_flag_lets_the_stored_answer_win(self):
        page, _ = self.listbox_page("Yes")
        conflicts = []
        with patch.object(step_pass, "resolve", return_value="No"), patch.object(step_pass, "pick_option", return_value=("No", ["Yes", "No"])) as picker:
            step_pass.pass_over_step(page, "Example", {}, [], overwrite=True, conflicts=conflicts)
        picker.assert_called_once()
        self.assertEqual(conflicts, [])

    def test_empty_dropdown_is_still_filled(self):
        page, _ = self.listbox_page("Select One")
        with patch.object(step_pass, "resolve", return_value="No"), patch.object(step_pass, "pick_option", return_value=("No", ["Yes", "No"])) as picker:
            step_pass.pass_over_step(page, "Example", {}, [])
        picker.assert_called_once()

    def test_text_box_with_other_value_is_a_conflict(self):
        box = Mock()
        box.input_value.return_value = "Existing"
        page, _ = field_page("Preferred name", {"input[type=text], input[type=number], textarea": collection([box])})
        conflicts = []
        with patch.object(step_pass, "resolve", return_value="Stored"):
            step_pass.pass_over_step(page, "Example", {}, [], conflicts=conflicts)
        box.fill.assert_not_called()
        self.assertEqual(conflicts[0]["current"], "Existing")


class UnknownSweepTests(unittest.TestCase):
    def test_details_carry_full_text_options_and_intent(self):
        page, _ = field_page("Are you willing to travel?*\nPlease pick the closest range", {})
        radio = Mock()
        radio.is_checked.return_value = False
        page, field = field_page("Are you willing to travel?*\nYes\nNo", {"input[type=radio]": collection([radio])})
        details, unknowns = {}, None
        with patch.object(step_pass, "resolve", return_value=None):
            unknowns = step_pass.pass_over_step(page, "Example", {}, [], details=details)
        rows = step_pass.unknown_details(unknowns, details)
        self.assertEqual(rows[0]["options"], ["Yes", "No"])
        self.assertIn("Yes No", rows[0]["question"])
        self.assertEqual(rows[0]["intent"], step_pass.intent_layer.classify("Are you willing to travel?*"))
        self.assertIsNone(step_pass.unknown_details([{"label": "Zzz qqq", "options": []}], {})[0]["intent"])

    def test_run_steps_writes_every_unknown_of_the_step_and_stops(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "unknowns.json"
            args = SimpleNamespace(company="Example", resume=None, history_file=None, salary=None, overwrite=False,
                                   unknowns_out=str(out), no_advance=False)
            page = Mock()
            page.locator.return_value = collection()
            state = {"steps": [], "unknowns": [], "conflicts": [], "final_step": ""}
            found = [{"label": "Q1", "options": ["A"]}, {"label": "Q2", "options": []}]
            with patch.object(step_pass, "wait_until_quiet", return_value=0), patch.object(step_pass, "ensure_resume", return_value=("absent", "")), \
                    patch.object(step_pass, "pass_over_step", return_value=found):
                code, _ = step_pass.run_steps(page, args, {}, state)
            written = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(code, 2)
        self.assertEqual([item["label"] for item in written], ["Q1", "Q2"])
        self.assertEqual(set(written[0]), {"label", "question", "options", "intent"})
        self.assertEqual(state["steps"][0]["changes"], 0)

    def test_missing_resume_flag_becomes_an_unknown(self):
        args = SimpleNamespace(company="Example", resume=None, history_file=None, salary=None, overwrite=False, unknowns_out=None, no_advance=False)
        page = Mock()
        page.locator.return_value = collection()
        state = {"steps": [], "unknowns": [], "conflicts": [], "final_step": ""}
        with patch.object(step_pass, "wait_until_quiet", return_value=0), patch.object(step_pass, "ensure_resume", return_value=("unknown", "no flag")), \
                patch.object(step_pass, "pass_over_step", return_value=[]):
            code, _ = step_pass.run_steps(page, args, {}, state)
        self.assertEqual(code, 2)
        self.assertEqual(state["unknowns"][0]["label"], "Resume/CV upload")


class ResolveDocTests(unittest.TestCase):
    def test_docstring_states_real_lookup_order(self):
        self.assertIn("exact answer memory, company KB, then intent", step_pass.resolve.__doc__)


if __name__ == "__main__":
    unittest.main()
