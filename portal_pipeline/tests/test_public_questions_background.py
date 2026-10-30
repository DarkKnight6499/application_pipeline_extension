"""Author: Yazad Madan. Synthetic sorter scheduling and promotion race checks."""
import contextlib
import http.client
import json
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

# Config
HERE = Path(__file__).resolve().parents[1]
TOKEN = "synthetic-background-token"
ORIGIN = "chrome-extension://" + "a" * 32
HOST = "example.myworkdayjobs.com"
COMPANY = "Example Corp"
LABEL = "Describe your preferred project"
ANSWER = "Synthetic project answer"
OTHER = "Other synthetic answer"
WAIT_SECONDS = 5
TEST_DEBOUNCE_SECONDS = 0.01
BLOCKED_JOB_SECONDS = 0.05
sys.path.insert(0, str(HERE))

import answer_memory
import assist_api
import assist_jobs
import page_questions
import questions_sort
from server import make_server
from shared_storage import file_lock


class FakeTimer:
    instances = []

    def __init__(self, interval, callback, args=()):
        self.interval, self.callback, self.args = interval, callback, args
        self.cancelled = False
        self.instances.append(self)

    def start(self):
        pass

    def cancel(self):
        self.cancelled = True

    def fire(self):
        self.callback(*self.args)


class BackgroundQuestionsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name) / "data"
        self.service = assist_api.AssistService(self.data, Path(self.temp.name) / "reference", token=TOKEN)
        self.schedule = patch.object(assist_jobs, "schedule").start()
        self.addCleanup(patch.stopall)
        FakeTimer.instances = []

    def body(self, company=COMPANY, answer=ANSWER, **pair):
        return {"host": HOST, "url": "https://" + HOST + "/apply", "company_hint": company,
                "pairs": [{"label": LABEL, "answer": answer, "source": "prefilled", "type": "text", **pair}]}

    def scheduler(self):
        timer_patch = patch.object(assist_jobs.threading, "Timer", FakeTimer)
        timer_patch.start()
        scheduler = assist_jobs.SortScheduler(self.service)
        self.addCleanup(scheduler.close)
        return scheduler

    def test_only_successful_appends_schedule_and_scheduler_failure_is_hidden(self):
        self.assertEqual(self.service.dump(self.body())["saved"], 1)
        self.schedule.assert_called_once_with(self.service)
        self.service.dump(self.body())
        self.assertEqual(self.schedule.call_count, 1)
        with self.assertRaises(ValueError):
            self.service.dump(self.body(source="invalid"))
        self.assertEqual(self.schedule.call_count, 1)
        self.schedule.side_effect = RuntimeError(ANSWER)
        self.assertEqual(self.service.dump(self.body(company="Other Corp"))["saved"], 1)
        log = (self.data / assist_jobs.ERROR_FILENAME).read_text(encoding="utf-8")
        self.assertIn("RuntimeError", log)
        self.assertNotIn(ANSWER, log)

    def test_debounce_uses_last_dump_and_ignores_cancelled_timer_race(self):
        scheduler = self.scheduler()
        with patch.object(assist_jobs, "SORT_DEBOUNCE_SECONDS", TEST_DEBOUNCE_SECONDS), patch.object(questions_sort, "promote") as run:
            scheduler.schedule()
            first = FakeTimer.instances[-1]
            scheduler.schedule()
            last = FakeTimer.instances[-1]
            self.assertEqual(last.interval, TEST_DEBOUNCE_SECONDS)
            self.assertTrue(first.cancelled)
            first.fire()
            run.assert_not_called()
            last.fire()
            run.assert_called_once_with(self.service)

    def test_scheduler_registry_shares_single_flight_between_service_instances(self):
        with patch.object(assist_jobs.threading, "Timer", FakeTimer):
            restarted = assist_api.AssistService(self.data, self.service.reference, token=TOKEN)
            self.real_schedule(self.service)
            first = FakeTimer.instances[-1]
            self.real_schedule(restarted)
            self.addCleanup(assist_jobs.close, self.data)
            self.assertTrue(first.cancelled)
            with patch.object(questions_sort, "promote") as run:
                FakeTimer.instances[-1].fire()
                run.assert_called_once()

    def test_single_flight_coalesces_many_due_dumps_into_one_followup(self):
        scheduler = self.scheduler()
        started, release = threading.Event(), threading.Event()
        calls = []
        def run(service):
            calls.append(service)
            if len(calls) == 1:
                started.set()
                self.assertTrue(release.wait(WAIT_SECONDS))
        with patch.object(questions_sort, "promote", side_effect=run):
            scheduler.schedule()
            thread = threading.Thread(target=FakeTimer.instances[-1].fire)
            thread.start()
            try:
                self.assertTrue(started.wait(WAIT_SECONDS))
                for _ in range(10):
                    scheduler.schedule()
                    FakeTimer.instances[-1].fire()
                self.assertEqual(len(calls), 1)
            finally:
                release.set()
                thread.join(WAIT_SECONDS)
            self.assertFalse(thread.is_alive())
            self.assertEqual(len(calls), 2)

    def test_later_dump_postpones_already_due_followup(self):
        scheduler = self.scheduler()
        def run(service):
            scheduler.schedule()
            FakeTimer.instances[-1].fire()
            scheduler.schedule()
        with patch.object(questions_sort, "promote", side_effect=run) as promote:
            scheduler.schedule()
            FakeTimer.instances[-1].fire()
            self.assertEqual(promote.call_count, 1)
            self.assertFalse(FakeTimer.instances[-1].cancelled)
        with patch.object(questions_sort, "promote") as promote:
            FakeTimer.instances[-1].fire()
            promote.assert_called_once()

    def test_background_error_logged_and_next_run_recovers(self):
        scheduler = self.scheduler()
        with patch.object(questions_sort, "promote", side_effect=ValueError(ANSWER)):
            scheduler.schedule()
            FakeTimer.instances[-1].fire()
        log = (self.data / assist_jobs.ERROR_FILENAME).read_text(encoding="utf-8")
        self.assertIn("ValueError", log)
        self.assertNotIn(ANSWER, log)
        with patch.object(questions_sort, "promote") as run:
            scheduler.schedule()
            FakeTimer.instances[-1].fire()
            run.assert_called_once()

    def test_http_response_does_not_wait_for_sort(self):
        started, release = threading.Event(), threading.Event()
        def run(service):
            started.set()
            release.wait(WAIT_SECONDS)
        self.schedule.side_effect = self.real_schedule
        server = make_server(None, 0, assist=self.service)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=WAIT_SECONDS)
        try:
            with patch.object(assist_jobs, "SORT_DEBOUNCE_SECONDS", TEST_DEBOUNCE_SECONDS), patch.object(questions_sort, "promote", side_effect=run):
                connection.request("POST", "/assist/dump", json.dumps(self.body()),
                                   {"Origin": ORIGIN, "X-Assist-Token": TOKEN})
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read())["saved"], 1)
                self.assertTrue(started.wait(WAIT_SECONDS))
                self.assertFalse(release.is_set())
                release.set()
        finally:
            release.set()
            assist_jobs.close(self.data)
            connection.close()
            server.shutdown()
            thread.join(WAIT_SECONDS)
            server.server_close()

    def test_mid_sort_conflict_blocks_promotion_and_refreshes_conflicts(self):
        for company in (COMPANY, "Other Corp"):
            self.service.dump(self.body(company=company))
        original = questions_sort.build_report
        builds = 0
        def build(*args):
            nonlocal builds
            groups = original(*args)
            builds += 1
            if builds == 2:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    pool.submit(self.service.dump, self.body(company="Third Corp", answer=OTHER)).result(WAIT_SECONDS)
            return groups
        with patch.object(questions_sort, "build_report", side_effect=build):
            self.assertEqual(questions_sort.promote(self.service)["conflict"], 1)
        self.assertFalse(list(self.data.rglob("answer_memory.json")))
        conflicts = json.loads((self.data / questions_sort.CONFLICTS_FILENAME).read_text(encoding="utf-8"))
        answers = {row["answer"]: row["companies"] for row in conflicts["conflicts"][0]["answers"]}
        self.assertEqual(answers[OTHER], ["Third Corp"])
        self.assertEqual(answers[ANSWER], [COMPANY, "Other Corp"])

    def test_recheck_runs_before_each_promotion(self):
        for company in (COMPANY, "Other Corp"):
            self.service.dump(self.body(company=company))
            self.service.dump(self.body(company=company, label="Z preferred hobby"))
        original_checked = questions_sort.checked_report
        count = 0
        @contextlib.contextmanager
        def checked(service):
            nonlocal count
            with original_checked(service) as snapshot:
                yield snapshot
            count += 1
            if count == 1:
                self.service.dump(self.body(company="Third Corp", label="Z preferred hobby", answer=OTHER))
        with patch.object(questions_sort, "checked_report", side_effect=checked):
            result = questions_sort.promote(self.service)
        self.assertEqual((result["shared"], result["conflict"]), (1, 1))
        self.assertIsNone(answer_memory.lookup(answer_memory.load_memory(self.data), "Z preferred hobby"))

    def test_sensitive_arriving_mid_sort_never_promotes_or_fills(self):
        for company in (COMPANY, "Other Corp"):
            self.service.dump(self.body(company=company))
        original = questions_sort.build_report
        builds = 0
        def build(*args):
            nonlocal builds
            groups = original(*args)
            builds += 1
            if builds == 2:
                self.service.dump(self.body(company="Third Corp", protected=True))
            return groups
        with patch.object(questions_sort, "build_report", side_effect=build):
            self.assertEqual(questions_sort.promote(self.service)["sensitive"], 1)
        self.assertFalse(list(self.data.rglob("answer_memory.json")))
        with patch.object(self.service, "draft", return_value=None):
            self.assertEqual(self.service.answer({**self.body(), "label": LABEL})["status"], "none")
        self.assertEqual(json.loads((self.data / questions_sort.CONFLICTS_FILENAME).read_text())["conflicts"], [])

    def test_mid_sort_store_change_blocks_promotion(self):
        for company in (COMPANY, "Other Corp"):
            self.service.dump(self.body(company=company))
        original = questions_sort.build_report
        builds = 0
        def build(*args):
            nonlocal builds
            groups = original(*args)
            builds += 1
            if builds == 2:
                self.service.accept({"label": LABEL, "answer": OTHER})
            return groups
        with patch.object(questions_sort, "build_report", side_effect=build):
            self.assertEqual(questions_sort.promote(self.service)["conflict"], 1)
        self.assertEqual(answer_memory.lookup(answer_memory.load_memory(self.data), LABEL), OTHER)

    def test_conflicts_snapshot_replaced_atomically_including_empty_report(self):
        self.service.dump(self.body())
        self.service.dump(self.body(company="Other Corp", answer=OTHER))
        original = questions_sort.atomic_json
        with patch.object(questions_sort, "atomic_json", wraps=original) as writer:
            questions_sort.report(self.service)
            self.assertTrue(any(call.args[0].name == "conflicts.json" for call in writer.call_args_list))
        path = self.data / questions_sort.CONFLICTS_FILENAME
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(snapshot["author"], "Yazad Madan")
        self.assertEqual(snapshot["conflicts"][0]["label"], LABEL)
        self.assertEqual(len(snapshot["conflicts"][0]["answers"]), 2)
        path.write_text("stale", encoding="utf-8")
        questions_sort.promote(self.service)
        self.assertEqual(json.loads(path.read_text()), snapshot)
        (self.data / page_questions.FILENAME).unlink()
        questions_sort.report(self.service)
        self.assertEqual(json.loads(path.read_text())["conflicts"], [])

    def test_conflicts_include_company_store_answers_and_resolution_status(self):
        self.service.dump(self.body())
        directory = self.service.company_scope(self.body())[0]
        answer_memory.update_memory(lambda memory: answer_memory.remember(memory, LABEL, OTHER), directory)
        questions_sort.report(self.service)
        path = self.data / questions_sort.CONFLICTS_FILENAME
        group = json.loads(path.read_text())["conflicts"][0]
        answers = {row["answer"]: row["companies"] for row in group["answers"]}
        self.assertEqual(answers, {ANSWER: [COMPANY], OTHER: [COMPANY]})
        self.assertFalse(group["resolved"])

    def test_sorting_holds_no_state_or_memory_write_lock(self):
        self.service.dump(self.body())
        original = questions_sort.build_report
        def probe():
            with file_lock(self.data / questions_sort.STATE_FILENAME, timeout=0.1):
                with answer_memory.memory_lock(self.data):
                    return True
        def build(*args):
            with ThreadPoolExecutor(max_workers=1) as pool:
                self.assertTrue(pool.submit(probe).result(WAIT_SECONDS))
            return original(*args)
        with patch.object(questions_sort, "build_report", side_effect=build):
            self.assertEqual(questions_sort.promote(self.service)["company"], 1)

    def test_confirm_sensitive_and_invalid_source_rows_never_append(self):
        body = {**self.body(label="Gender"), "dry_run": False}
        body["pairs"][0]["previous_answer"] = None
        self.assertFalse(self.service.learn(body)["results"][0]["stored"])
        self.assertFalse((self.data / page_questions.FILENAME).exists())
        for source in ("invalid", [], None):
            body = {**self.body(source=source), "dry_run": False}
            body["pairs"][0]["previous_answer"] = None
            with self.assertRaises(ValueError):
                self.service.learn(body)
        self.assertFalse(list(self.data.rglob("answer_memory.json")))

    def test_confirm_appends_selected_successful_rows_with_source_and_parallel_companies(self):
        def confirm(company):
            body = {**self.body(company=company, source="corrected"), "dry_run": True}
            self.assertTrue(self.service.learn(body)["dry_run"])
            return self.service.learn({**body, "dry_run": False,
                                       "pairs": [{**body["pairs"][0], "previous_answer": None}]})
        self.assertFalse((self.data / page_questions.FILENAME).exists())
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(confirm, ["Example " + str(index) for index in range(8)]))
        self.assertTrue(all(result["results"][0]["stored"] for result in results))
        rows = page_questions.read(self.data)
        self.assertEqual(len(rows), 8)
        self.assertEqual({row["source"] for row in rows}, {"corrected"})
        self.assertTrue(all(row["schema_version"] == page_questions.SCHEMA_VERSION for row in rows))
        self.assertEqual(self.schedule.call_count, 8)
        stale = {**self.body(), "dry_run": False, "pairs": [{**self.body()["pairs"][0], "previous_answer": OTHER}]}
        self.assertFalse(self.service.learn(stale)["results"][0]["stored"])
        self.assertEqual(len(page_questions.read(self.data)), 8)

    def test_draft_and_sort_share_three_job_slots_but_dump_stays_available(self):
        started = threading.Barrier(4)
        release, sort_started, sort_attempted = threading.Event(), threading.Event(), threading.Event()
        original = questions_sort._promote
        def draft(body):
            started.wait(WAIT_SECONDS)
            release.wait(WAIT_SECONDS)
        def run(service):
            sort_started.set()
            return original(service)
        def promote():
            sort_attempted.set()
            return questions_sort.promote(self.service)
        with patch.object(self.service, "_draft", side_effect=draft), patch.object(questions_sort, "_promote", side_effect=run) as sort:
            with ThreadPoolExecutor(max_workers=4) as pool:
                futures = [pool.submit(self.service.draft, self.body()) for _ in range(3)]
                try:
                    started.wait(WAIT_SECONDS)
                    pending = pool.submit(promote)
                    self.assertTrue(sort_attempted.wait(WAIT_SECONDS))
                    self.assertFalse(sort_started.wait(BLOCKED_JOB_SECONDS))
                    self.assertEqual(self.service.dump(self.body())["saved"], 1)
                    sort.assert_not_called()
                finally:
                    release.set()
                for future in futures:
                    future.result(WAIT_SECONDS)
                pending.result(WAIT_SECONDS)
                sort.assert_called_once()


BackgroundQuestionsTests.real_schedule = staticmethod(assist_jobs.schedule)

if __name__ == "__main__":
    unittest.main()
