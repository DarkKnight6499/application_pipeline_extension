"""Author: Yazad Madan. Synthetic correction storage, draft, privacy, and HTTP contracts."""
import http.client
import json
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
WRONG = "Synthetic old project"
USER = "Synthetic revised project"
sys.path.insert(0, str(HERE))

import answer_memory
import assist_api
import corrections
from server import make_server


class CorrectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        self.service = assist_api.AssistService(self.data, self.root / "reference", token=TOKEN)
        self.draft = patch.object(self.service, "draft", return_value="Synthetic fallback").start()
        self.addCleanup(patch.stopall)

    def payload(self, **changes):
        return {"label": LABEL, "host": HOST, "company_hint": COMPANY, "type": "text",
                "url": f"https://{HOST}/apply", "wrong_value": WRONG, "user_value": USER, **changes}

    def test_two_corrections_override_stored_answer_only_as_draft(self):
        body = self.payload()
        self.service.accept({**body, "answer": WRONG})
        directory = self.service.company_scope(body)[0]
        before = answer_memory.memory_path(directory).read_bytes()
        self.assertEqual(self.service.correction(body), {"status": "recorded"})
        self.assertEqual(self.service.answer(body)["answer"], WRONG)
        self.service.correction(body)
        result = self.service.answer(body)
        self.assertEqual((result["status"], result["reason"], result["answer"]), ("draft", "corrected", USER))
        self.assertIn(USER, result["candidates"])
        self.assertEqual(answer_memory.memory_path(directory).read_bytes(), before)
        self.assertEqual(answer_memory.load_memory(self.data)["answers"], {})
        log = (self.data / assist_api.LOG_FILENAME).read_text()
        self.assertNotIn(USER, log)
        self.assertNotIn(WRONG, log)
        self.draft.assert_not_called()

    def test_counts_same_user_across_wrong_values_restart_and_new_choice(self):
        body = self.payload()
        self.service.correction(body)
        self.service.correction({**body, "wrong_value": "Other synthetic old project"})
        restarted = assist_api.AssistService(self.data, self.root / "reference", token=TOKEN)
        self.assertEqual(restarted.answer(body)["answer"], USER)
        self.assertEqual(corrections.report(self.data)[0]["count"], 2)
        self.service.correction({**body, "user_value": "New synthetic choice"})
        self.assertIsNone(corrections.suggestion(self.data, body))
        self.service.correction({**body, "user_value": "New synthetic choice"})
        self.assertEqual(corrections.suggestion(self.data, body), "New synthetic choice")
        store = json.loads((self.data / corrections.FILENAME).read_text())
        self.assertEqual(store["author"], "Yazad Madan")
        row = next(iter(store["questions"].values()))
        self.assertEqual(row["count"], 4)
        self.assertEqual(row["changes"][0]["wrong_value"], WRONG)

    def test_exact_question_company_host_isolation(self):
        body = self.payload()
        self.service.correction(body)
        self.service.correction(body)
        for change in ({"label": "Preferred different project?"}, {"host": "other.myworkdayjobs.com"},
                       {"company_hint": "Other Corp"}):
            self.assertIsNone(corrections.suggestion(self.data, {**body, **change}))
        self.assertEqual(corrections.suggestion(self.data, {**body, "label": " Preferred PROJECT! "}), USER)

    def test_blocked_labels_options_and_types_never_record_or_fill(self):
        labels = ["Password", "SSN", "S.S.N.", "Signature", "I attest", "I certify", "I confirm",
                  "Need sponsorship now?", "Future sponsorship?", "Work authorization", "Authorized to work?",
                  "Eligible for employment?", "Right to work?", "Veteran status", "Disability", "Gender",
                  "Race or ethnicity", "Self-ID", "Visa status", "Active duty", "Uniformed services",
                  "Religious affiliation", "Marital status", "Criminal history", "Expected salary"]
        for label in labels:
            with self.subTest(label=label):
                body = self.payload(label=label)
                self.assertEqual(self.service.correction(body)["status"], "skipped")
        bodies = [self.payload(type=kind) for kind in ("password", "signature", "file")]
        bodies += [self.payload(options=["Male", "Female"]), self.payload(protected=True)]
        for body in bodies:
            self.assertEqual(self.service.correction(body)["status"], "skipped")
        learned = self.service.learn({**self.payload(), "dry_run": False, "pairs": [
            {"label": label, "answer": USER, "previous_answer": None} for label in labels]})
        self.assertTrue(all(row["status"] == "skipped" for row in learned["results"]))
        self.assertFalse((self.data / corrections.FILENAME).exists())
        for label in labels:
            if label in ("Criminal history", "Expected salary"):
                continue
            body = self.payload(label=label)
            directory = self.service.company_scope(body)[0]
            answer_memory.update_memory(lambda memory: answer_memory.remember(memory, label, WRONG), directory)
            self.assertEqual(self.service.answer(body)["status"], "none", label)
            with self.assertRaises(ValueError):
                self.service.accept({**body, "answer": USER})
        self.draft.assert_not_called()

    def test_bounds_empty_unchanged_and_atomic_validation(self):
        for change in ({"user_value": USER * 200}, {"wrong_value": None}, {"label": "Q" * 301},
                       {"company_hint": "C" * 151}, {"type": "t" * 41}, {"host": "bad/host"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.service.correction(self.payload(**change))
        for change in ({"wrong_value": ""}, {"user_value": " "}, {"user_value": WRONG}):
            self.assertEqual(self.service.correction(self.payload(**change))["status"], "skipped")
        self.assertFalse((self.data / corrections.FILENAME).exists())

    def test_concurrent_counts_and_report_order_values_never_printed(self):
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(lambda _: self.service.correction(self.payload()), range(12)))
        self.assertTrue(all(item["status"] == "recorded" for item in results))
        self.service.correction(self.payload(label="Another project?"))
        rows = corrections.report(self.data)
        self.assertEqual([row["count"] for row in rows], [12, 1])
        for arguments in ([], ["--json"]):
            result = subprocess.run([sys.executable, "-B", str(HERE / "corrections.py"),
                                     "--data", str(self.data), *arguments], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(LABEL, result.stdout)
            self.assertNotIn(USER, result.stdout)
            self.assertNotIn(WRONG, result.stdout)
            if arguments:
                self.assertEqual(json.loads(result.stdout)[0]["count"], 12)

    def test_malformed_store_fails_without_disclosing_values(self):
        self.service.correction(self.payload())
        (self.data / corrections.FILENAME).write_text("not json")
        result = subprocess.run([sys.executable, "-B", str(HERE / "corrections.py"),
                                 "--data", str(self.data)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr.strip(), "Cannot read correction store.")

    def test_http_correction_uses_existing_auth_origin_host_method_and_size_guards(self):
        server = make_server(None, 0, assist=self.service)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)
        def request(method="POST", headers=None):
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            self.addCleanup(connection.close)
            connection.request(method, "/assist/correction", json.dumps(self.payload()) if method == "POST" else None,
                               {"Origin": ORIGIN, "X-Assist-Token": TOKEN, **(headers or {})})
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        for headers, expected in (({"X-Assist-Token": "wrong"}, 401), ({"Origin": "https://example.invalid"}, 403),
                                  ({"Host": "forged.invalid"}, 403),
                                  ({"Content-Length": str(assist_api.MAX_BODY + 1)}, 413),
                                  ({"Transfer-Encoding": "chunked"}, 413)):
            self.assertEqual(request(headers=headers)[0], expected)
        self.assertEqual(request(method="GET")[0], 405)
        self.assertFalse((self.data / corrections.FILENAME).exists())
        self.assertEqual(request(), (200, {"status": "recorded"}))


if __name__ == "__main__":
    unittest.main()
