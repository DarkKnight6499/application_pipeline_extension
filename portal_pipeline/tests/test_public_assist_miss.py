"""Author: Yazad Madan. Synthetic unanswered queue, report, and HTTP checks."""
import contextlib
import http.client
import io
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

# Config
HERE = Path(__file__).resolve().parents[1]
TOKEN = "synthetic-assist-token"
ORIGIN = "chrome-extension://" + "a" * 32
LABEL = "Preferred project?"
HOST = "example.myworkdayjobs.com"
COMPANY = "Example Corp"
NODE = shutil.which("node")
HARNESS = Path(__file__).with_name("assist_miss_harness.js")
sys.path.insert(0, str(HERE))

import assist_api
import miss_log
import miss_report
from server import make_server


class MissTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        self.service = assist_api.AssistService(self.data, self.root / "reference", token=TOKEN)

    def payload(self, **changes):
        return dict(label=LABEL, host=HOST, company_hint=COMPANY, type="select-one",
                    options=["Example A", "Example B"], **changes)

    def test_dedupe_caps_allowlist_and_append_only(self):
        body = self.payload()
        body.update(label="  Preferred PROJECT!  ", value="DO_NOT_STORE", answer="DO_NOT_STORE",
                    url="https://example.invalid/DO_NOT_STORE")
        self.assertTrue(miss_log.record(self.data, body))
        prefix = (self.data / miss_log.LOG_FILENAME).read_bytes()
        self.assertTrue(miss_log.record(self.data, self.payload()))
        self.assertTrue((self.data / miss_log.LOG_FILENAME).read_bytes().startswith(prefix))
        rows = miss_log.report(self.data)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["count"], 2)
        self.assertLessEqual(rows[0]["first_seen"], rows[0]["last_seen"])
        self.assertNotIn("DO_NOT_STORE", (self.data / miss_log.LOG_FILENAME).read_text())
        body.update(label="Q" * 400, options=["O" * 150] * 45,
                    company_hint="C" * 200, host="h" * 300, type="combobox")
        miss_log.record(self.data, body)
        row = next(row for row in miss_log.report(self.data) if row["label"].startswith("Q"))
        self.assertEqual(len(row["label"]), 300)
        self.assertEqual(len(row["option_samples"][0]), 40)
        self.assertEqual(len(row["option_samples"][0][0]), 120)
        self.assertEqual(len(row["companies"][0]), 150)
        self.assertEqual(len(row["hosts"][0]), 253)

    def test_blocked_labels_types_and_uncapped_context(self):
        labels = ["Password", "SSN", "S.S.N.", "Social Security Number", "Typed signature", "I attest to accuracy",
                  "I certify this is true", "Sign this agreement", "I confirm this is true",
                  "Need sponsorship now?", "Future sponsorship?", "Work authorization?",
                  "Authorized to work?", "Right to work?", "Eligible for employment?",
                  "Legally permitted to work?", "Veteran status?", "Disability?", "Gender?",
                  "Race/ethnicity?", "Self-ID", "SelfIdentification", "Sexual orientation?", "Visa status?"]
        for label in labels:
            with self.subTest(label=label):
                body = self.payload()
                body["label"] = label
                self.assertFalse(miss_log.record(self.data, body))
        for kind in ("password", "signature", "file"):
            body = self.payload()
            body["type"] = kind
            self.assertFalse(miss_log.record(self.data, body))
        for body in (dict(self.payload(), label="Q" * 310 + " signature"),
                     dict(self.payload(), options=["Example"] * 40 + ["Veteran status"]),
                     dict(self.payload(), options=["O" * 130 + " disability"])):
            self.assertFalse(miss_log.record(self.data, body))
        self.assertEqual(miss_log.report(self.data), [])
        self.assertFalse((self.data / miss_log.LOG_FILENAME).exists())

    def test_concurrent_counts_and_restart(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertTrue(all(pool.map(lambda _: miss_log.record(self.data, self.payload()), range(16))))
        self.assertEqual(miss_log.report(self.data)[0]["count"], 16)
        service = assist_api.AssistService(self.data, self.root / "reference", token=TOKEN)
        self.assertEqual(service.miss(self.payload())["status"], "logged")
        self.assertEqual(miss_log.report(self.data)[0]["count"], 17)

    def test_non_sensitive_questions_and_text_fields_remain_reportable(self):
        for label in ("Which certifications do you hold?", "Expected salary?", "Preferred project?"):
            self.assertTrue(miss_log.record(self.data, dict(self.payload(), label=label, type="text")))
        self.assertTrue(all(not row["option_samples"] for row in miss_log.report(self.data)))

    def test_resolve_normalizes_caps_and_report_ties_are_stable(self):
        for label in ("Z example?", "A example?", "Q" * 400):
            miss_log.record(self.data, dict(self.payload(), label=label))
        self.assertEqual(miss_log.report(self.data)[0]["label"], "A example?")
        miss_log.resolve(self.data, "q" * 400)
        self.assertEqual(len(miss_log.report(self.data)), 2)
        with self.assertRaises(ValueError):
            miss_log.resolve(self.data, " ")

    def test_report_order_across_hosts_companies_and_resolve(self):
        for host, company in ((HOST, COMPANY), ("other.example.invalid", "Other Example"), (HOST, COMPANY)):
            miss_log.record(self.data, dict(self.payload(), host=host, company_hint=company))
        miss_log.record(self.data, dict(self.payload(), label="Another project?"))
        rows = miss_log.report(self.data)
        self.assertEqual([row["count"] for row in rows], [3, 1])
        self.assertEqual(rows[0]["hosts"], sorted([HOST, "other.example.invalid"]))
        self.assertEqual(rows[0]["companies"], [COMPANY, "Other Example"])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(miss_report.main(["--data", str(self.data)]), 0)
        self.assertLess(output.getvalue().index(LABEL), output.getvalue().index("Another project?"))
        self.assertIn("Example A", output.getvalue())
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(miss_report.main(["--data", str(self.data), "--resolve", "preferred PROJECT!", "--json"]), 0)
        self.assertEqual([row["label"] for row in json.loads(output.getvalue())], ["Another project?"])
        self.assertEqual(len((self.data / miss_log.LOG_FILENAME).read_text().splitlines()), 5)
        miss_log.record(self.data, self.payload())
        self.assertEqual(miss_log.report(self.data)[0]["count"], 4)

    def test_answer_logs_only_unanswered_and_logging_failure_does_not_block(self):
        with patch.object(self.service, "draft", return_value=None):
            self.assertEqual(self.service.answer(self.payload())["status"], "none")
        self.assertEqual(miss_log.report(self.data)[0]["count"], 1)
        with patch.object(self.service, "draft", return_value="Example draft."):
            self.assertEqual(self.service.answer(self.payload())["status"], "draft")
        self.service.accept(dict(label=LABEL, answer="Example answer"))
        self.assertEqual(self.service.answer(self.payload())["status"], "stored")
        self.assertEqual(miss_log.report(self.data)[0]["count"], 1)
        with patch.object(self.service, "draft", return_value=None), patch.object(
                miss_log, "record", side_effect=OSError("synthetic disk failure")):
            self.assertEqual(self.service.answer(dict(self.payload(), label="Other project?"))["status"], "none")

    def test_manual_answer_misses_are_filtered_and_keep_non_sensitive_questions(self):
        self.assertEqual(self.service.answer(dict(self.payload(), label="Future sponsorship?"))["status"], "none")
        self.assertEqual(self.service.answer(dict(self.payload(), label="Expected salary?"))["status"], "none")
        self.assertEqual([row["label"] for row in miss_log.report(self.data)], ["Expected salary?"])

    def test_corrupt_log_does_not_break_answer_outcome(self):
        (self.data / miss_log.LOG_FILENAME).write_text('{"event": "miss"}\n', encoding="utf-8")
        with patch.object(self.service, "draft", return_value=None):
            self.assertEqual(self.service.answer(self.payload())["status"], "none")

    def test_malformed_miss_is_rejected(self):
        for body in ([], {}, {"label": " "}, dict(self.payload(), options=[123]),
                     dict(self.payload(), host=123), dict(self.payload(), company_hint=None)):
            with self.subTest(body=body), self.assertRaises(ValueError):
                self.service.miss(body)
        self.assertEqual(miss_log.report(self.data), [])

    def start(self):
        server = make_server(None, 0, assist=self.service)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)
        return server.server_port

    def request(self, port, body=None, token=TOKEN, origin=ORIGIN, host=None, method="POST", size=None):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        self.addCleanup(connection.close)
        headers = {"Content-Type": "application/json", "Access-Control-Request-Method": "POST"}
        if token is not None:
            headers["X-Assist-Token"] = token
        if origin is not None:
            headers["Origin"] = origin
        if host:
            headers["Host"] = host
        if size:
            headers["Content-Length"] = str(size)
        connection.request(method, "/assist/miss", json.dumps(self.payload() if body is None else body), headers)
        response = connection.getresponse()
        return response.status, json.loads(response.read()), response.getheader("Access-Control-Allow-Origin")

    def test_http_auth_origin_host_size_preflight_and_miss(self):
        port = self.start()
        for token in (None, "incorrect", "\u00e9"):
            self.assertEqual(self.request(port, token=token)[0], 401)
        for origin in (None, "https://example.invalid", "chrome-extension://bad"):
            self.assertEqual(self.request(port, origin=origin)[0], 403)
        self.assertEqual(self.request(port, host="localhost:" + str(port))[0], 403)
        self.assertEqual(self.request(port, size=assist_api.MAX_BODY + 1)[0], 413)
        self.assertEqual(self.request(port, token=None, method="OPTIONS")[:1], (200,))
        self.assertEqual(self.request(port, method="GET")[0], 405)
        self.assertFalse((self.data / miss_log.LOG_FILENAME).exists())
        self.assertEqual(self.request(port)[0:2], (200, {"status": "logged"}))
        self.assertEqual(self.request(port, dict(self.payload(), label="Sponsorship?"))[1], {"status": "skipped"})
        self.assertEqual(self.request(port, ["invalid"])[0], 400)
        self.assertEqual(self.request(port)[2], ORIGIN)
        self.assertEqual(miss_log.report(self.data)[0]["count"], 2)

    @unittest.skipUnless(NODE, "Node.js is required for browser-free checks.")
    def test_content_and_worker_miss_contract(self):
        result = subprocess.run([NODE, str(HARNESS)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
