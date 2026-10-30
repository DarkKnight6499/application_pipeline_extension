"""Author: Yazad Madan. Browser-free batch limits and separate-window checks."""
import contextlib
import io
import sys
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Config
HERE = Path(__file__).resolve().parents[1]
URL = "https://sample.myworkdayjobs.com/jobs/one"
OTHER_URL = "https://other.myworkdayjobs.com/jobs/one"
WAIT_SECONDS = 5
sys.path.insert(0, str(HERE))

import apply as application
import batch_apply


class BatchLimitTests(unittest.TestCase):
    def test_folder_count_bounds_and_duplicates(self):
        for count in range(1, batch_apply.MAX_WORKERS + 1):
            folders = [f"folder_{index}" for index in range(count)]
            self.assertEqual(len(batch_apply.parse_args(["--folders", *folders]).folders), count)
        for argv in ([], ["--folders"], ["--folders", *[f"folder_{index}" for index in range(9)]],
                     ["--folders", "one", "one"]):
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                batch_apply.parse_args(argv)

    def test_worker_default_override_and_clamp(self):
        self.assertEqual(batch_apply.DEFAULT_WORKERS, 6)
        self.assertEqual(batch_apply.MAX_WORKERS, 8)
        self.assertEqual(batch_apply.parse_args(["--folders", "one"]).workers, 6)
        for requested, expected in ((1, 1), (3, 3), (6, 6), (8, 8), (99, 8)):
            self.assertEqual(batch_apply.parse_args(["--folders", "one", "--workers", str(requested)]).workers, expected)
        for workers in (0, -1):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                batch_apply.parse_args(["--folders", "one", "--workers", str(workers)])

    def test_host_extraction(self):
        for url, host in ((URL, "sample.myworkdayjobs.com"),
                          ("https://SAMPLE.myworkdayjobs.com.:8443/jobs/two?source=x#part", "sample.myworkdayjobs.com"),
                          ("https://user:secret@example.invalid:443/job", "example.invalid"),
                          ("http://[::1]:8000/job", "::1")):
            self.assertEqual(batch_apply.extract_host(url), host)
        for url in ("", "jobs/one", "https:///job"):
            with self.assertRaises(ValueError):
                batch_apply.extract_host(url)

    def test_per_host_limit_and_parallel_hosts_preserve_report_order(self):
        jobs = [{"url": url, "index": index} for index, url in enumerate([URL] * 4 + [OTHER_URL] * 2)]
        lock = threading.Lock()
        active, peaks, seen = {}, {}, []
        initial_wave_done = threading.Event()
        initial_wave = threading.Barrier(4, action=initial_wave_done.set, timeout=WAIT_SECONDS)

        def fake_job(job, **options):
            host = batch_apply.extract_host(job["url"])
            with lock:
                active[host] = active.get(host, 0) + 1
                peaks[host] = max(peaks.get(host, 0), active[host])
                seen.append(job["index"])
            try:
                if not initial_wave_done.is_set():
                    initial_wave.wait()
                return job
            finally:
                with lock:
                    active[host] -= 1

        with patch.object(batch_apply, "run_job", side_effect=fake_job), \
             patch.object(batch_apply, "STAGGER_SECONDS", 0), \
             patch.object(batch_apply, "finish_batch", return_value=2) as finish:
            self.assertEqual(batch_apply.execute_jobs(jobs), 2)
        self.assertEqual(peaks, {batch_apply.extract_host(URL): 2, batch_apply.extract_host(OTHER_URL): 2})
        self.assertCountEqual(seen, range(6))
        self.assertEqual([job["index"] for job in finish.call_args.args[0]], list(range(6)))
        self.assertTrue(all(job["new_window"] for job in finish.call_args.args[0]))
        self.assertTrue(all("new_window" not in job for job in jobs))

    def test_execute_clamps_workers_and_selects_windows_by_concurrency(self):
        for count, workers, dry, resume, expected in ((3, 6, False, False, False),
                                                     (4, 6, False, False, True),
                                                     (6, 3, False, False, False),
                                                     (8, 99, False, False, True),
                                                     (6, 6, True, False, False),
                                                     (6, 6, False, True, False)):
            jobs = [{"url": URL} for _ in range(count)]
            with self.subTest(count=count, workers=workers, dry=dry, resume=resume), \
                 patch.object(batch_apply, "ThreadPoolExecutor", wraps=ThreadPoolExecutor) as pool, \
                 patch.object(batch_apply, "run_job", side_effect=lambda job, **options: job), \
                 patch.object(batch_apply, "STAGGER_SECONDS", 0), patch.object(batch_apply, "finish_batch") as finish:
                batch_apply.execute_jobs(jobs, workers=workers, dry=dry, resume=resume)
                pool.assert_called_once_with(max_workers=min(workers, 8))
                self.assertTrue(all(job["new_window"] is expected for job in finish.call_args.args[0]))

    def test_child_window_flag_only_for_new_writable_jobs(self):
        job = {"url": URL, "folder": "invented", "report_path": "unused.json", "new_window": True}
        for dry, resume, scan_only, expected in ((False, False, False, True), (True, False, False, False),
                                                (False, True, False, False), (True, False, True, False)):
            with patch.object(batch_apply.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as child, \
                 patch.object(Path, "read_text", return_value='{"exit_code": 0}'):
                batch_apply.run_job({**job, "scan_only": scan_only}, dry=dry, resume=resume)
            self.assertEqual("--new-window" in child.call_args.args[0], expected)

    def test_apply_cli_forwards_new_window(self):
        with patch.object(application, "run", return_value=0) as run:
            self.assertEqual(application.main([URL, "--new-window"]), 0)
        self.assertTrue(run.call_args.kwargs["new_window"])

    def test_open_job_creates_window_in_existing_context(self):
        for new_window in (False, True):
            playwright, browser, context, page = MagicMock(), MagicMock(), MagicMock(), MagicMock()
            playwright.chromium.connect_over_cdp.return_value = browser
            browser.contexts = [context]
            context.new_page.return_value = page
            context.expect_page.return_value.__enter__.return_value.value = page
            page.url = URL
            with patch.object(application, "sync_playwright", return_value=contextlib.nullcontext(playwright)), \
                 patch.object(application, "target_id_of", return_value="invented-target"):
                opened = application.open_job({"url": URL, "portal": "lever"}, new_window=new_window)
            self.assertEqual(opened["target_id"], "invented-target")
            page.goto.assert_called_once_with(URL + "/apply", wait_until="domcontentloaded", timeout=60000)
            page.locator.assert_not_called()
            browser.close.assert_called_once_with()
            if new_window:
                context.new_page.assert_not_called()
                session = browser.new_browser_cdp_session.return_value
                window_url = session.send.call_args.args[1]["url"]
                self.assertTrue(window_url.startswith("about:blank#"))
                session.send.assert_called_once_with("Target.createTarget", {"url": window_url, "newWindow": True})
                predicate = context.expect_page.call_args.kwargs["predicate"]
                self.assertTrue(predicate(SimpleNamespace(url=window_url)))
                self.assertFalse(predicate(SimpleNamespace(url="about:blank#other-job")))
                session.detach.assert_called_once_with()
            else:
                context.new_page.assert_called_once_with()
                browser.new_browser_cdp_session.assert_not_called()

    def test_new_window_failure_detaches_and_disconnects(self):
        playwright = MagicMock()
        browser = playwright.chromium.connect_over_cdp.return_value
        session = browser.new_browser_cdp_session.return_value
        session.send.side_effect = RuntimeError("Invented window failure")
        with patch.object(application, "sync_playwright", return_value=contextlib.nullcontext(playwright)), \
             self.assertRaisesRegex(RuntimeError, "Invented window failure"):
            application.open_job({"url": URL, "portal": "lever"}, new_window=True)
        session.detach.assert_called_once_with()
        browser.close.assert_called_once_with()

    def test_run_forwards_window_hook_inside_existing_login_lock(self):
        order = []

        @contextlib.contextmanager
        def lock(key):
            order.append("lock")
            yield
            order.append("unlock")

        job = {"url": URL, "portal": "workday", "resume": None, "cover": None}
        with patch.object(application, "resolve", return_value=job), \
             patch.object(application, "file_lock", side_effect=lock), \
             patch.object(application, "open_job", side_effect=lambda *args, **kwargs: order.append("window") or
                          {"notes": [], "url": URL, "target_id": "invented-target"}) as opened, \
             patch.object(application, "login_step", side_effect=lambda job: order.append("login") or "manual"), \
             patch.object(application.workday_run, "execute") as execute, \
             contextlib.redirect_stdout(io.StringIO()):
            execute.return_value.data = {"exit_code": 0}
            self.assertEqual(application.run(URL, batch=True, new_window=True), 0)
        opened.assert_called_once_with(job, dry=False, new_window=True)
        self.assertEqual(order, ["lock", "window", "login", "unlock"])


if __name__ == "__main__":
    unittest.main()
