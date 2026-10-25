"""Structured run report: synthetic Workday-like pages driven through execute(), apply.run ordering with fakes, zero Submit activity."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Config
SOURCE_DIR = Path(__file__).resolve().parents[1]
TEST_DIR = SOURCE_DIR / "tests"
PROFILE = {"values": {"first_name": {"value": "Invented", "source": "synthetic"}}, "employment": [], "education": [], "answers": {}, "consents": {}, "aliases": {}, "pickers": {}}
STEP = '<div data-automation-id="progressBarActiveStep">{title}</div>'
NEXT = ('<button data-automation-id="pageFooterNextButton" type="button" onclick="document.querySelector(\'[data-automation-id=progressBarActiveStep]\').textContent=\'Review\'">'
        'Save and Continue</button>')
FIRST_NAME = '<label>First Name<input id="first"></label>'
REQUIRED_GAP = '<label>Invented required question<input id="gap" required aria-required="true"></label>'
REPORT_KEYS = {"started": str, "portal": str, "dry": bool, "pages": list, "stop_reason": str, "exit_code": int, "review_attachments": (dict, type(None))}
PAGE_KEYS = {"title": str, "fields": int, "filled": int, "pending_required": list, "blocked_gates": list, "uploads": list, "learned": int}
sys.path.insert(0, str(SOURCE_DIR))
sys.path.insert(0, str(TEST_DIR))
import apply as apply_module
import workday_run as driver
from browser_test_support import SyntheticBrowserTest


def check_schema(data):
    for key, kind in REPORT_KEYS.items():
        assert isinstance(data[key], kind), key
    assert data["exit_code"] in (0, 2, 3)
    for page in data["pages"]:
        for key, kind in PAGE_KEYS.items():
            assert isinstance(page[key], kind), key
        for upload in page["uploads"]:
            assert set(upload) >= {"file", "sha256", "status"}


class ReportFixtureTests(SyntheticBrowserTest):
    def drive(self, markup, gap_wait=0.3):
        self.open_markup(markup)
        browser = MagicMock(contexts=[self.context])
        playwright = MagicMock()
        playwright.chromium.connect_over_cdp.return_value = browser
        reports = tempfile.TemporaryDirectory()
        self.addCleanup(reports.cleanup)
        memory = {"schema_version": 1, "answers": {}}
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(driver, "sync_playwright", return_value=contextlib.nullcontext(playwright)))
            stack.enter_context(patch.object(driver, "build_profile", return_value=PROFILE))
            stack.enter_context(patch.object(driver.answer_memory, "load_memory", return_value=memory))
            stack.enter_context(patch.object(driver.answer_memory, "save_memory"))
            stack.enter_context(patch.object(driver, "GAP_WAIT_SECONDS", gap_wait))
            stack.enter_context(patch.object(driver, "GAP_POLL_SECONDS", 0.1))
            stack.enter_context(patch.object(driver, "PAGE_SETTLE_SECONDS", 0.2))
            stack.enter_context(patch.object(driver, "ROW_SETTLE_SECONDS", 0.1))
            stack.enter_context(patch.object(driver, "RUNS_DIR", Path(reports.name)))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            code = driver.main([])
        files = list(Path(reports.name).glob("*.json"))
        self.assertEqual(len(files), 1)
        data = json.loads(files[0].read_text(encoding="utf-8"))
        check_schema(data)
        self.assertEqual(code, data["exit_code"])
        self.assertEqual((self.page.evaluate("syntheticSubmitClicks"), self.page.evaluate("syntheticSubmitEvents")), (0, 0))
        return data

    def test_review_reached_exits_zero_with_filled_count(self):
        data = self.drive(STEP.format(title="My Information") + FIRST_NAME + NEXT)
        self.assertEqual(data["exit_code"], 0, data)
        self.assertEqual(data["pages"][0]["filled"], 1, data)
        self.assertEqual([page["title"] for page in data["pages"]], ["My Information", "Review"])
        self.assertEqual(self.page.locator("#first").input_value(), "Invented")

    def test_unanswered_required_field_is_a_human_gate(self):
        data = self.drive(STEP.format(title="My Information") + FIRST_NAME + REQUIRED_GAP + NEXT)
        self.assertEqual(data["exit_code"], 2, data)
        self.assertEqual(data["pages"][0]["pending_required"], ["Invented required question"])

    def test_missing_next_button_is_a_failure(self):
        data = self.drive(STEP.format(title="My Information") + FIRST_NAME)
        self.assertEqual(data["exit_code"], 3, data)

    def test_dialog_is_a_human_gate(self):
        data = self.drive(STEP.format(title="My Information") + FIRST_NAME + '<div role="dialog">Invented notice</div>' + NEXT)
        self.assertEqual(data["exit_code"], 2, data)
        self.assertEqual(self.page.locator("#first").input_value(), "")

    def test_report_holds_no_field_values(self):
        data = self.drive(STEP.format(title="My Information") + FIRST_NAME + NEXT)
        self.assertNotIn("Invented", json.dumps(data))


class ApplyLaunchOrderTests(unittest.TestCase):
    def test_launch_runs_edge_then_open_then_login_then_driver(self):
        order = []
        report = driver.RunReport("workday").finish_report("Review page reached.", 0)
        job = {"url": "https://x.myworkdayjobs.com/a", "portal": "workday", "resume": None, "cover": None}
        reports = tempfile.TemporaryDirectory()
        self.addCleanup(reports.cleanup)
        with patch.object(apply_module, "resolve", return_value=job), \
             patch.object(apply_module.edge_launch, "ensure_edge", side_effect=lambda: order.append("edge") or {"started": False}), \
             patch.object(apply_module, "open_job", side_effect=lambda j: order.append("open") or []), \
             patch.object(apply_module, "login_step", side_effect=lambda j: order.append("login") or "filled"), \
             patch.object(apply_module.workday_run, "execute", side_effect=lambda a: order.append("driver") or report), \
             patch.object(apply_module, "RUNS_DIR", Path(reports.name)), contextlib.redirect_stdout(io.StringIO()):
            code = apply_module.run("https://x.myworkdayjobs.com/a", None, launch=True)
        self.assertEqual((code, order), (0, ["edge", "open", "login", "driver"]))
        data = json.loads(next(Path(reports.name).glob("*.json")).read_text(encoding="utf-8"))
        check_schema(data)
        self.assertEqual(data["notes"], ["edge: already running", "login: filled"])

    def test_edge_refusal_is_a_failure_report_and_driver_never_runs(self):
        job = {"url": "https://x.myworkdayjobs.com/a", "portal": "workday", "resume": None, "cover": None}
        reports = tempfile.TemporaryDirectory()
        self.addCleanup(reports.cleanup)
        with patch.object(apply_module, "resolve", return_value=job), \
             patch.object(apply_module.edge_launch, "ensure_edge", side_effect=apply_module.edge_launch.EdgeRefused("other profile")), \
             patch.object(apply_module.workday_run, "execute") as execute, \
             patch.object(apply_module, "RUNS_DIR", Path(reports.name)), contextlib.redirect_stdout(io.StringIO()):
            code = apply_module.run("https://x.myworkdayjobs.com/a", None, launch=True)
        self.assertEqual(code, 3)
        execute.assert_not_called()
        check_schema(json.loads(next(Path(reports.name).glob("*.json")).read_text(encoding="utf-8")))
