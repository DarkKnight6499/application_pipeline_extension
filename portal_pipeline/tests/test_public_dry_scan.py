"""Author: Yazad Madan. Browser-free queue scanning and learning review checks."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Config
HERE = Path(__file__).resolve().parents[1]
URL = "https://sample.myworkdayjobs.com/jobs/one"
OTHER_URL = "https://sample.myworkdayjobs.com/jobs/two"
UNSUPPORTED_URL = "https://unsupported.example.invalid/job"
LABEL = "Preferred office?"
OPTIONAL_LABEL = "Additional interests?"
sys.path.insert(0, str(HERE))

import answer_memory
import apply as application
import batch_apply
import dry_scan
import learning_queue as learning
import workday_run


def field(label=LABEL, **changes):
    return {"id": label, "label": label, "type": "text", "options": [], "required": True,
            "blocked": False, "protected": False, "record": None, "current": "", "proposal": "",
            "status": "pending", "disabled": False, **changes}


def report(url=URL, fields=None, **changes):
    return {"url": url, "portal": "workday", "dry": True, "exit_code": 0, "pages": [{}],
            "pages_scanned": 1, "pages_not_reached": None,
            "unanswered": fields if fields is not None else [field()], **changes}


class DryScanTests(unittest.TestCase):
    def test_normalized_dedupe_ranking_and_distinct_job_urls(self):
        reports = [report(fields=[field("Notice period?"), field(), field("preferred OFFICE!")]),
                   report(OTHER_URL), report(URL + "?source=repeat")]
        queue = learning.collect(reports, {"answers": {}})
        self.assertEqual([item["label"] for item in queue["questions"]], [LABEL, "Notice period?"])
        question = queue["questions"][0]
        self.assertEqual(question["job_count"], 2)
        self.assertEqual(question["job_urls"], [URL, OTHER_URL])
        self.assertEqual(question["answer"], "")

    def test_filtering_memory_protected_immigration_and_history(self):
        labels = ["Password", "Verification code", "I attest this is true", "Signature", "Visa type",
                  "Future sponsorship", "Are you authorized to work in the US?", "Work authorization",
                  "Citizenship", "Known question", "Login"]
        fields = [field(label) for label in labels]
        fields += [field("Employer", record={"group": "employment"}), field("Private", protected=True),
                   field("Blocked", blocked=True), field("Attachment", type="file"),
                   field(OPTIONAL_LABEL, required=False)]
        memory = {"answers": {}}
        answer_memory.remember(memory, "Known question", "Reviewed")
        queue = learning.collect([report(fields=fields)], memory)
        self.assertEqual([question["label"] for question in queue["questions"]], [OPTIONAL_LABEL])
        self.assertEqual(learning.collect([report(fields=fields, dry=False)], memory)["questions"], [])

    def test_sheet_header_reports_scanned_failed_and_unknown_pages(self):
        reports = [report(), report(OTHER_URL, pages=[], pages_scanned=0, exit_code=3)]
        with tempfile.TemporaryDirectory() as directory:
            queue = learning.write_queue(reports, directory)
            sheet = (Path(directory) / learning.SHEET_FILENAME).read_text(encoding="utf-8")
        self.assertEqual(queue["jobs_scanned"], 1)
        self.assertEqual(queue["jobs_total"], 2)
        self.assertIsNone(queue["pages_not_reached"])
        self.assertIn("Jobs scanned: 1 / 2", sheet)
        self.assertIn("Pages not reached: unknown", sheet)
        self.assertIn(URL, sheet)
        self.assertIn("current page", sheet)

    def test_queue_file_skips_missing_links_and_keeps_order(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "queue.json"
            path.write_text(json.dumps([{}, {"link": None}, {"link": " "}, {"link": URL},
                                        {"link": 8}, {"link": OTHER_URL}]), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()) as output:
                urls = dry_scan.read_queue(path)
        self.assertEqual(urls, [URL, OTHER_URL])
        self.assertIn("4", output.getvalue())

    def test_default_cap_override_and_duplicates(self):
        urls = [URL + str(index) for index in range(dry_scan.DEFAULT_MAX_JOBS + 2)]
        args = dry_scan.parse_args(["--urls", *urls])
        jobs = dry_scan.build_jobs(args.urls, args.max_jobs)
        self.assertEqual(len(jobs), dry_scan.DEFAULT_MAX_JOBS)
        self.assertEqual(len(dry_scan.build_jobs([URL, URL + "?source=x", OTHER_URL], 2)), 2)
        self.assertEqual(len(dry_scan.build_jobs(urls, 1)), 1)
        for argv in (["--urls", URL, "--max", "0"], ["--urls", URL, "--queue-file", "queue.json"], []):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                dry_scan.parse_args(argv)
        with self.assertRaises(ValueError):
            dry_scan.build_jobs([], 1)

    def test_coordinator_uses_serial_dry_subprocesses_without_edge(self):
        with patch.object(batch_apply, "execute_jobs", return_value=0) as execute, \
             patch.object(application.edge_launch, "ensure_edge") as edge:
            self.assertEqual(dry_scan.main(["--urls", URL, OTHER_URL]), 0)
        jobs = execute.call_args.args[0]
        self.assertEqual(len(jobs), 2)
        self.assertEqual(execute.call_args.kwargs, {"workers": 1, "dry": True})
        self.assertTrue(all(job["scan_only"] for job in jobs))
        self.assertNotEqual(jobs[0]["report_path"], jobs[1]["report_path"])
        edge.assert_not_called()

    def test_scan_child_uses_existing_dry_entry_and_never_writes(self):
        page = MagicMock()
        page.url = URL
        browser = MagicMock()
        browser.contexts = [SimpleNamespace(pages=[page])]
        playwright = MagicMock()
        playwright.__enter__.return_value.chromium.connect_over_cdp.return_value = browser
        fields = [field(), field(OPTIONAL_LABEL, required=False), field("Already entered", current="Keep"),
                  field("Visa type"), field("Employer", record={"group": "employment", "id": "row-one"})]
        original_report = workday_run.RunReport
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.json"
            with patch.object(workday_run, "sync_playwright", return_value=playwright), \
                 patch.object(workday_run, "step_title", return_value="My Information"), \
                 patch.object(workday_run, "dialog_open", return_value=False), \
                 patch.object(workday_run, "inject"), patch.object(workday_run, "build_profile", return_value={}), \
                 patch.object(workday_run, "scan", return_value=fields), \
                 patch.object(workday_run, "upload_resume") as upload, \
                 patch.object(application, "open_job") as open_job, \
                 patch.object(application, "login_step") as login, \
                 patch.object(application.edge_launch, "ensure_edge") as edge, \
                 patch.object(answer_memory, "update_memory") as remember, \
                 contextlib.redirect_stdout(io.StringIO()):
                code = dry_scan.scan_job(URL, path)
            saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(code, 0)
        self.assertIs(workday_run.RunReport, original_report)
        self.assertTrue(saved["dry"])
        self.assertEqual(saved["pages_scanned"], 1)
        self.assertIsNone(saved["pages_not_reached"])
        self.assertEqual([entry["label"] for entry in saved["unanswered"]], [LABEL, OPTIONAL_LABEL])
        for name in ("fill", "click", "type", "upload", "set_input_files", "goto", "press", "locator", "evaluate"):
            getattr(page, name).assert_not_called()
        for action in (upload, open_job, login, edge, remember):
            action.assert_not_called()
        browser.new_page.assert_not_called()

    def test_missing_or_ambiguous_tab_writes_failure_report(self):
        for pages in ([], [SimpleNamespace(url=URL), SimpleNamespace(url=URL)]):
            browser = MagicMock()
            browser.contexts = [SimpleNamespace(pages=pages)]
            playwright = MagicMock()
            playwright.__enter__.return_value.chromium.connect_over_cdp.return_value = browser
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "run.json"
                with patch.object(workday_run, "sync_playwright", return_value=playwright), \
                     patch.object(workday_run, "drive") as drive, contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(dry_scan.scan_job(URL, path), 3)
                saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["pages_scanned"], 0)
            self.assertEqual(saved["unanswered"], [])
            drive.assert_not_called()

    def test_batch_scan_command_failure_is_still_a_dry_report(self):
        with tempfile.TemporaryDirectory() as directory:
            job = {"url": URL, "portal": "workday", "scan_only": True,
                   "report_path": str(Path(directory) / "run.json")}
            with patch.object(batch_apply.subprocess, "run", return_value=SimpleNamespace(returncode=3)) as child:
                saved = batch_apply.run_job(job, dry=True)
        command = child.call_args.args[0]
        self.assertEqual(Path(command[2]).name, "dry_scan.py")
        self.assertIn("--scan-job", command)
        self.assertNotIn("--launch", command)
        self.assertTrue(saved["dry"])
        self.assertEqual(saved["exit_code"], 3)
        self.assertEqual(saved["pages_scanned"], 0)

    def test_unsupported_links_report_failure_without_stopping_queue_or_browser(self):
        jobs = dry_scan.build_jobs([URL, UNSUPPORTED_URL, OTHER_URL])
        self.assertEqual(len(jobs), 3)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.json"
            with patch.object(workday_run, "sync_playwright") as browser:
                self.assertEqual(dry_scan.scan_job(UNSUPPORTED_URL, path), 3)
            saved = json.loads(path.read_text(encoding="utf-8"))
        browser.assert_not_called()
        self.assertTrue(saved["dry"])
        self.assertEqual(saved["pages_scanned"], 0)
        self.assertIn("No adapter", saved["stop_reason"])

    def test_real_subprocesses_report_each_unsupported_job_and_build_sheet(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(dry_scan, "RUNS_DIR", root / "runs"), \
                 patch.object(batch_apply, "DATA_DIR", root), patch.object(batch_apply, "STAGGER_SECONDS", 0), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(dry_scan.main(["--urls", UNSUPPORTED_URL, UNSUPPORTED_URL + "/two"]), 3)
            paths = list((root / "runs").glob("*.json"))
            self.assertEqual(len(paths), 2)
            reports = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
            self.assertTrue(all(item["dry"] and item["pages_scanned"] == 0 for item in reports))
            queue = json.loads((root / learning.QUEUE_FILENAME).read_text(encoding="utf-8"))
            self.assertEqual(queue["jobs_total"], 2)
            self.assertEqual(queue["jobs_scanned"], 0)
            self.assertTrue((root / learning.SHEET_FILENAME).is_file())

    def test_invalid_child_report_is_replaced_and_scan_jobs_refuse_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.json"
            path.write_text("[]", encoding="utf-8")
            job = {"url": URL, "portal": "workday", "scan_only": True, "report_path": str(path)}
            with patch.object(batch_apply.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as child:
                self.assertEqual(batch_apply.run_job(job, dry=True)["exit_code"], 3)
                child.reset_mock()
                for options in ({}, {"dry": True, "resume": True}):
                    with self.assertRaises(ValueError):
                        batch_apply.run_job(job, **options)
                child.assert_not_called()

    def test_from_reports_glob_list_and_no_browser(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, url in enumerate((URL, OTHER_URL)):
                (root / f"scan_{index}.json").write_text(json.dumps(report(url)), encoding="utf-8")
            pattern = str(root / "scan_*.json")
            with patch.object(batch_apply, "DATA_DIR", root), \
                 patch.object(batch_apply, "execute_jobs") as execute, \
                 patch.object(application.edge_launch, "ensure_edge") as edge, \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(batch_apply.main(["--learn-only", "--from-reports", pattern]), 0)
            self.assertEqual(len(batch_apply.load_reports([pattern, str(root / "scan_0.json")])), 2)
            queue = json.loads((root / learning.QUEUE_FILENAME).read_text(encoding="utf-8"))
            self.assertEqual(queue["questions"][0]["job_count"], 2)
            edge.assert_not_called()
            execute.assert_not_called()
            with self.assertRaises(ValueError):
                batch_apply.load_reports([str(root / "missing*.json")])

    def test_optional_review_import_keeps_dry_jobs_nonresumable(self):
        with tempfile.TemporaryDirectory() as directory:
            queue = learning.write_queue([report(fields=[field(OPTIONAL_LABEL, required=False)])], directory)
            queue["questions"][0]["answer"] = "Reviewed"
            path = Path(directory) / "reviewed.json"
            path.write_text(json.dumps(queue), encoding="utf-8")
            stored, jobs = learning.import_answers(path, directory)
            self.assertEqual(stored, 1)
            self.assertEqual(answer_memory.lookup(answer_memory.load_memory(directory), OPTIONAL_LABEL), "Reviewed")
            with patch.object(batch_apply, "execute_jobs") as execute, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(batch_apply.resume_jobs(jobs), 0)
            execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
