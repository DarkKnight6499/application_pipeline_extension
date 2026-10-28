"""Author: Yazad Madan. Browser-free batch and shared-memory regressions."""
import contextlib
import io
import json
import multiprocessing
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

# Config
HERE = Path(__file__).resolve().parents[1]
URL = "https://sample.myworkdayjobs.com/jobs/one"
OTHER_URL = "https://sample.myworkdayjobs.com/jobs/two"
LABEL = "Preferred office?"
sys.path.insert(0, str(HERE))

import answer_memory
import apply as application
import batch_apply
import browser_target
import edge_launch
import learning_queue
import shared_storage
import workday_run


def save_worker(directory, label, ready, go):
    data = answer_memory.load_memory(directory)
    answer_memory.remember(data, label, "Reviewed")
    ready.put(True)
    go.wait(10)
    answer_memory.save_memory(data, directory)


class BatchTests(unittest.TestCase):
    def test_tab_url_normalization_and_ambiguity(self):
        one = SimpleNamespace(url=URL + "/?source=test")
        two = SimpleNamespace(url=OTHER_URL)
        browser = SimpleNamespace(contexts=[SimpleNamespace(pages=[one, two])])
        self.assertIs(workday_run.page_of(browser, url=URL), one)
        with self.assertRaises(SystemExit):
            workday_run.page_of(browser)
        with self.assertRaises(SystemExit):
            workday_run.page_of(browser, url=URL + "/missing")
        browser.contexts.append(SimpleNamespace(pages=[SimpleNamespace(url=URL)]))
        with self.assertRaises(SystemExit):
            workday_run.page_of(browser, url=URL)

    def test_target_id_survives_url_change(self):
        one = SimpleNamespace(url=URL)
        two = SimpleNamespace(url=OTHER_URL)
        browser = SimpleNamespace(contexts=[SimpleNamespace(pages=[one, two])])
        with patch.object(browser_target, "target_id_of", side_effect=lambda page: "one" if page is one else "two"):
            self.assertIs(workday_run.page_of(browser, url=URL, target_id="two"), two)

    def test_two_processes_merge_stale_snapshots(self):
        with tempfile.TemporaryDirectory() as directory:
            context = multiprocessing.get_context("spawn")
            ready, go = context.Queue(), context.Event()
            workers = [context.Process(target=save_worker, args=(directory, label, ready, go))
                       for label in ("Preferred office", "Notice period")]
            for worker in workers:
                worker.start()
            try:
                for worker in workers:
                    self.assertTrue(ready.get(timeout=20))
                go.set()
                for worker in workers:
                    worker.join(20)
                    self.assertEqual(worker.exitcode, 0)
                self.assertEqual(len(answer_memory.load_memory(directory)["answers"]), 2)
            finally:
                for worker in workers:
                    if worker.is_alive():
                        worker.terminate()
                    worker.join()
                ready.close()

    def test_queue_deduplicates_counts_jobs_and_filters(self):
        data = {"schema_version": 1, "answers": {}}
        answer_memory.remember(data, "Known answer", "Yes")
        fields = [{"label": label, "type": "text"} for label in
                  (LABEL, "Signature", "Password", "I attest this is true", "Visa sponsorship", "Known answer", "Login")]
        fields.append({"label": "Employer", "record": {"group": "employment"}})
        reports = [{"job": "one", "portal": "workday", "unanswered": fields + fields},
                   {"job": "two", "portal": "workday", "unanswered": [{"label": "preferred OFFICE!", "type": "text"}]}]
        queue = learning_queue.collect(reports, data)
        self.assertEqual(len(queue["questions"]), 1)
        self.assertEqual(queue["questions"][0]["job_count"], 2)
        self.assertEqual(queue["questions"][0]["answer"], "")

    def test_args_and_exit_codes(self):
        args = batch_apply.parse_args(["--folders", "one", "two", "--workers", "9", "--dry"])
        self.assertEqual(args.workers, 3)
        self.assertTrue(args.dry)
        for argv in (["--folders", "one"], ["--folders", "one", "two", "--workers", "0"], []):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                batch_apply.parse_args(argv)
        self.assertTrue(batch_apply.parse_args(["--learn-only"]).learn_only)
        self.assertEqual(batch_apply.worst_exit_code([0, 2, 3]), 3)
        self.assertEqual(batch_apply.worst_exit_code([0, -1]), 3)

    def test_subprocess_failure_without_report_is_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.json"
            job = {"folder": "one", "portal": "workday", "url": URL, "report_path": str(path)}
            with patch.object(batch_apply.subprocess, "run", return_value=SimpleNamespace(returncode=2)) as run:
                result = batch_apply.run_job(job, dry=True)
            command = run.call_args.args[0]
            self.assertIn("--no-open", command)
            self.assertNotIn("--launch", command)
            self.assertEqual(result["exit_code"], 3)
            self.assertTrue(path.is_file())

    def test_stale_snapshot_does_not_revert_another_answer(self):
        with tempfile.TemporaryDirectory() as directory:
            original = answer_memory.load_memory(directory)
            for label in ("Office", "Notice period"):
                answer_memory.remember(original, label, "Old")
            answer_memory.save_memory(original, directory)
            first, second = answer_memory.load_memory(directory), answer_memory.load_memory(directory)
            answer_memory.remember(first, "Office", "New office")
            answer_memory.remember(second, "Notice period", "New notice")
            answer_memory.save_memory(first, directory)
            answer_memory.save_memory(second, directory)
            stored = answer_memory.load_memory(directory)
            self.assertEqual(answer_memory.lookup(stored, "Office"), "New office")
            self.assertEqual(answer_memory.lookup(stored, "Notice period"), "New notice")

    def test_lock_timeout_and_release(self):
        entered, release = threading.Event(), threading.Event()
        key = "synthetic-lock-timeout"
        def hold():
            with shared_storage.file_lock(key):
                entered.set()
                release.wait(5)
        worker = threading.Thread(target=hold)
        worker.start()
        try:
            self.assertTrue(entered.wait(5))
            with self.assertRaises(TimeoutError):
                with shared_storage.file_lock(key, timeout=0.01):
                    self.fail("Lock should remain held")
        finally:
            release.set()
            worker.join(5)
        with shared_storage.file_lock(key, timeout=0.1):
            pass

    def test_failed_replace_preserves_previous_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            data = answer_memory.load_memory(directory)
            answer_memory.remember(data, "Office", "Old")
            answer_memory.save_memory(data, directory)
            answer_memory.remember(data, "Office", "New")
            with patch.object(shared_storage.os, "replace", side_effect=OSError("Synthetic replacement failure")):
                with self.assertRaises(OSError):
                    answer_memory.save_memory(data, directory)
            self.assertEqual(answer_memory.lookup(answer_memory.load_memory(directory), "Office"), "Old")

    def test_import_records_source_and_rejects_protected_or_invalid_options(self):
        with tempfile.TemporaryDirectory() as directory:
            report = {"job": "one", "folder": "synthetic", "target_id": "one", "url": URL,
                      "unanswered": [{"label": LABEL, "type": "select-one", "options": ["Alpha", "Beta"]}]}
            queue = learning_queue.write_queue([report], directory)
            path = Path(directory) / "reviewed.json"
            question = next(iter(queue["questions"]))
            question["answer"] = "Unknown"
            path.write_text(json.dumps(queue), encoding="utf-8")
            with self.assertRaises(ValueError):
                learning_queue.import_answers(path, directory)
            question["answer"] = "Alpha"
            path.write_text(json.dumps(queue), encoding="utf-8")
            count, jobs = learning_queue.import_answers(path, directory)
            stored = answer_memory.load_memory(directory)
            self.assertEqual(count, 1)
            self.assertEqual(stored["answers"]["preferred office"]["source"], "batch-review")
            self.assertEqual(jobs[0]["target_id"], "one")
            question["label"] = "Signature"
            path.write_text(json.dumps(queue), encoding="utf-8")
            with self.assertRaises(ValueError):
                learning_queue.import_answers(path, directory)

    def test_import_cli_resumes_jobs_after_store(self):
        jobs = [{"folder": "synthetic", "target_id": "one"}]
        with patch.object(learning_queue, "import_answers", return_value=(1, jobs)), \
             patch.object(batch_apply, "resume_jobs", return_value=2) as resume, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(answer_memory.main(["--import-answers", "reviewed.json"]), 2)
        resume.assert_called_once_with(jobs)

    def test_report_persists_question_structure_without_values(self):
        report = workday_run.RunReport()
        base = {"required": True, "blocked": False, "current": "", "proposal": "", "type": "text"}
        report.record_unanswered([{**base, "label": LABEL, "options": [{"label": "Alpha", "value": "private-id"}]},
                                  {**base, "label": "Password", "type": "password"},
                                  {**base, "label": "Company", "record": {"group": "employment"}}], URL)
        self.assertEqual(len(report.data["unanswered"]), 1)
        self.assertEqual(report.data["unanswered"][0]["options"], ["Alpha"])
        self.assertNotIn("private-id", json.dumps(report.data))
        with tempfile.TemporaryDirectory() as directory:
            self.assertNotEqual(report.write(directory), report.write(directory))

    def test_execute_isolates_portal_context_and_restores_defaults(self):
        import unittest.mock as mock
        browser = mock.MagicMock()
        playwright = mock.MagicMock()
        playwright.chromium.connect_over_cdp.return_value = browser
        seen = []
        def drive(page, args, report):
            seen.append(workday_run.portal_settings()["host"])
            raise workday_run.ReviewReached()
        with patch.object(workday_run, "sync_playwright", return_value=contextlib.nullcontext(playwright)), \
             patch.object(workday_run, "page_of"), patch.object(workday_run, "drive", side_effect=drive):
            for portal in ("lever", "workday"):
                result = workday_run.execute(workday_run.parse_args(["--portal", portal]))
                self.assertEqual(result.data["exit_code"], 0)
                self.assertIsNone(workday_run.PORTAL_CONTEXT.get())
        self.assertEqual(seen, ["lever.co", ""])

    def test_manual_login_never_calls_credential_filler(self):
        from unittest.mock import MagicMock
        tab = MagicMock(url=URL)
        playwright = MagicMock()
        browser = playwright.chromium.connect_over_cdp.return_value
        browser.contexts = [SimpleNamespace(pages=[tab])]
        with patch.object(application, "sync_playwright", return_value=contextlib.nullcontext(playwright)), \
             patch.object(application, "password_box_visible", side_effect=[True, False]), \
             patch.object(application.login_fill, "gate_on", return_value=None), \
             patch.object(application.login_fill, "login") as login:
            result = application.login_step({"url": URL}, wait=lambda seconds: None)
        self.assertIn("manual", result)
        login.assert_not_called()

    def test_manual_verification_waits_without_typing_a_code(self):
        from unittest.mock import MagicMock
        tab = MagicMock(url=URL)
        playwright = MagicMock()
        browser = playwright.chromium.connect_over_cdp.return_value
        browser.contexts = [SimpleNamespace(pages=[tab])]
        waits = []
        with patch.object(application, "sync_playwright", return_value=contextlib.nullcontext(playwright)), \
             patch.object(application, "password_box_visible", return_value=False), \
             patch.object(application.login_fill, "gate_on", return_value=None), \
             patch.object(application, "verification_visible", side_effect=[True, False]), \
             patch.object(application.login_fill, "enter_code") as code:
            application.login_step({"url": URL}, wait=waits.append)
        self.assertEqual(waits, [application.LOGIN_POLL_SECONDS])
        code.assert_not_called()

    def test_batch_launches_edge_once_and_propagates_worst_result(self):
        jobs = [{"url": URL, "portal": "workday"}, {"url": OTHER_URL, "portal": "workday"}]
        with patch.object(application, "resolve", side_effect=jobs), \
             patch.object(batch_apply.edge_launch, "ensure_edge") as edge, \
             patch.object(batch_apply, "execute_jobs", return_value=3) as execute:
            self.assertEqual(batch_apply.main(["--folders", "one", "two"]), 3)
        edge.assert_called_once_with()
        self.assertNotEqual(execute.call_args.args[0][0]["report_path"], execute.call_args.args[0][1]["report_path"])

    def test_dry_batch_does_not_launch_edge(self):
        jobs = [{"url": URL, "portal": "workday"}, {"url": OTHER_URL, "portal": "workday"}]
        with patch.object(application, "resolve", side_effect=jobs), \
             patch.object(batch_apply.edge_launch, "ensure_edge") as edge, \
             patch.object(batch_apply, "execute_jobs", return_value=0):
            self.assertEqual(batch_apply.main(["--folders", "one", "two", "--dry"]), 0)
        edge.assert_not_called()

    def test_batch_subprocesses_produce_distinct_reports_and_one_queue(self):
        def child(command, **kwargs):
            args = application.parse_args(command[3:])
            report = workday_run.RunReport("workday").finish_report("Required answers pending", 2)
            report.data.update(folder=str(args.folder), url=args.url, target_id=str(args.folder),
                               unanswered=[{"label": LABEL, "type": "text", "portal_host": "sample.myworkdayjobs.com"}])
            report.write(path=args.report_path)
            return SimpleNamespace(returncode=2)
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            jobs = [{"url": URL, "portal": "workday"}, {"url": OTHER_URL, "portal": "workday"}]
            with patch.object(application, "resolve", side_effect=jobs), \
                 patch.object(batch_apply, "DATA_DIR", data_dir), patch.object(batch_apply, "RUNS_DIR", data_dir / "runs"), \
                 patch.object(batch_apply.edge_launch, "ensure_edge"), patch.object(batch_apply, "STAGGER_SECONDS", 0), \
                 patch.object(batch_apply.subprocess, "run", side_effect=child) as run, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(batch_apply.main(["--folders", "one", "two"]), 2)
            self.assertEqual(run.call_count, 2)
            queue = json.loads((data_dir / learning_queue.QUEUE_FILENAME).read_text(encoding="utf-8"))
            self.assertEqual(queue["questions"][0]["job_count"], 2)
            self.assertEqual(len(list((data_dir / "runs").glob("*.json"))), 2)
            with patch.object(batch_apply, "DATA_DIR", data_dir), patch.object(batch_apply.edge_launch, "ensure_edge") as edge, \
                 patch.object(batch_apply, "execute_jobs") as execute, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(batch_apply.main(["--learn-only"]), 2)
            edge.assert_not_called()
            execute.assert_not_called()

    def test_login_lock_wraps_open_and_manual_login_only(self):
        order = []
        @contextlib.contextmanager
        def lock(key):
            self.assertEqual(key, "portal-login:sample.myworkdayjobs.com")
            order.append("lock")
            yield
            order.append("unlock")
        def execute(args):
            order.append("fill")
            self.assertEqual(args.target_id, "one")
            return workday_run.RunReport().finish_report("Review", 0)
        with tempfile.TemporaryDirectory() as directory:
            job = {"url": URL, "portal": "workday", "resume": None, "cover": None}
            with patch.object(application, "resolve", return_value=job), patch.object(application, "file_lock", side_effect=lock), \
                 patch.object(application, "open_job", side_effect=lambda job: order.append("open") or
                              {"notes": [], "url": URL, "target_id": "one"}), \
                 patch.object(application, "login_step", side_effect=lambda job: order.append("login") or "manual"), \
                 patch.object(workday_run, "execute", side_effect=execute), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(application.run(folder="synthetic", batch=True, report_path=Path(directory) / "run.json"), 0)
        self.assertEqual(order, ["lock", "open", "login", "unlock", "fill"])

    def test_batch_stops_at_questions_without_waiting_or_advancing(self):
        from unittest.mock import MagicMock
        args = workday_run.parse_args(["--batch"])
        report = workday_run.RunReport()
        page = MagicMock(url=URL)
        field = {"label": LABEL, "type": "text", "required": True, "current": "", "blocked": False, "record": None}
        profile = {"consents": ["synthetic prior attestation"]}
        with patch.object(workday_run, "dialog_open", return_value=False), \
             patch.object(workday_run, "step_title", return_value="My Information"), \
             patch.object(workday_run, "inject"), patch.object(workday_run, "build_profile", return_value=profile), \
             patch.object(workday_run, "run_page", return_value=[field]), patch.object(workday_run, "scan", return_value=[field]), \
             patch.object(workday_run, "upload_resume", return_value=None), patch.object(workday_run, "wait_for_person") as wait, \
             contextlib.redirect_stdout(io.StringIO()), self.assertRaises(workday_run.DriverStopped):
            workday_run.drive(page, args, report)
        wait.assert_not_called()
        page.locator.assert_not_called()
        self.assertEqual(profile["consents"], [])
        self.assertEqual(report.data["unanswered"][0]["label"], LABEL)

    def test_edge_refusal_still_reports_every_job(self):
        jobs = [{"url": URL, "portal": "workday"}, {"url": OTHER_URL, "portal": "workday"}]
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            with patch.object(application, "resolve", side_effect=jobs), \
                 patch.object(batch_apply, "DATA_DIR", data_dir), patch.object(batch_apply, "RUNS_DIR", data_dir / "runs"), \
                 patch.object(batch_apply.edge_launch, "ensure_edge", side_effect=edge_launch.EdgeRefused("Synthetic refusal")), \
                 patch.object(batch_apply.subprocess, "run") as child, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(batch_apply.main(["--folders", "one", "two"]), 3)
            child.assert_not_called()
            reports = [json.loads(path.read_text(encoding="utf-8")) for path in (data_dir / "runs").glob("*.json")]
            self.assertEqual(len(reports), 2)
            self.assertTrue(all(report["exit_code"] == 3 for report in reports))

    def test_resume_uses_original_targets_and_never_launches_edge(self):
        jobs = [{"folder": "one", "url": URL, "portal": "workday", "target_id": "original", "dry": False},
                {"folder": "two", "url": OTHER_URL, "portal": "workday", "dry": True}]
        with patch.object(batch_apply, "execute_jobs", return_value=2) as execute, \
             patch.object(batch_apply.edge_launch, "ensure_edge") as edge:
            self.assertEqual(batch_apply.resume_jobs(jobs), 2)
        resumed = execute.call_args.args[0]
        self.assertEqual(len(resumed), 1)
        self.assertEqual(resumed[0]["target_id"], "original")
        self.assertTrue(execute.call_args.kwargs["resume"])
        edge.assert_not_called()


if __name__ == "__main__":
    unittest.main()
