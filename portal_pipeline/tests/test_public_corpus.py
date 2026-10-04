"""Question corpus logging uses fabricated labels only and writes under a temp data directory."""
import http.client
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

# Test configuration
HERE = Path(__file__).resolve().parents[1]
PAIRING_TOKEN = "synthetic-test-token"
CORPUS_FILENAME = "question_corpus.json"
LABEL = "Do you hold a Synthetic License?"
LABEL_VARIANT = "  do you hold a synthetic license "
PROTECTED_LABELS = ["Gender", "Are you a protected veteran?", "Disability status", "Enter your password", "I agree to the privacy policy", "Signature"]
SENTINEL = "SENTINEL-ANSWER-9431"

sys.path.insert(0, str(HERE))
import question_corpus
from server import make_server


def entry(label=LABEL, **extra):
    base = {"label": label, "portal": "synthetic", "type": "radio", "options": ["Yes", "No"]}
    base.update(extra)
    return base


def atomic_write(path, data):
    Path(path).write_text(json.dumps(data), encoding="utf-8")


class PublicCorpusTests(unittest.TestCase):
    def test_append_dedupes_and_counts(self):
        data = question_corpus.empty_corpus()
        question_corpus.append_question(data, entry(), now="2026-10-04")
        question_corpus.append_question(data, entry(LABEL_VARIANT), now="2026-10-05")
        self.assertEqual(len(data["questions"]), 1)
        record = next(iter(data["questions"].values()))
        self.assertEqual((record["count"], record["first_seen"], record["last_seen"]), (2, "2026-10-04", "2026-10-05"))
        self.assertEqual((record["reviewed"], record["classified_as"]), (False, None))

    def test_protected_never_logged(self):
        data = question_corpus.empty_corpus()
        for label in PROTECTED_LABELS:
            with self.subTest(label=label):
                self.assertFalse(question_corpus.append_question(data, entry(label)))
        self.assertFalse(question_corpus.append_question(data, entry(protected=True)))
        self.assertFalse(question_corpus.append_question(data, entry(type="password")))
        self.assertEqual(data["questions"], {})

    def test_no_values_stored(self):
        data = question_corpus.empty_corpus()
        question_corpus.append_question(data, entry(current=SENTINEL, value=SENTINEL, answer=SENTINEL, proposal=SENTINEL,
                                                    options=[{"value": SENTINEL, "label": "Yes"}, "No"]))
        text = json.dumps(data)
        self.assertNotIn(SENTINEL, text)
        record = next(iter(data["questions"].values()))
        self.assertEqual(record["options"], ["Yes", "No"])
        self.assertEqual(set(record), {"label", "portal", "type", "options", "first_seen", "last_seen", "count", "classified_as", "reviewed"})

    def test_written_under_data_only(self):
        with tempfile.TemporaryDirectory() as temp:
            data_dir = Path(temp) / "data"
            data_dir.mkdir()
            question_corpus.log_question(data_dir, entry(), atomic_write)
            self.assertEqual([p.name for p in Path(temp).rglob("*") if p.is_file()], [CORPUS_FILENAME])
            self.assertTrue((data_dir / CORPUS_FILENAME).is_file())
            self.assertEqual(question_corpus.corpus_path(data_dir), data_dir.resolve() / CORPUS_FILENAME)
            self.assertEqual(question_corpus.load_corpus(data_dir)["schema_version"], 1)

    def test_promote_prints_case_without_mutating(self):
        data = question_corpus.empty_corpus()
        question_corpus.append_question(data, entry(classified_as="work_authorized"), now="2026-10-04")
        before = json.dumps(data)
        line = question_corpus.promote(data, LABEL)
        self.assertIn(LABEL, line)
        self.assertIn("work_authorized", line)
        self.assertEqual(json.dumps(data), before)
        self.assertIsNone(question_corpus.promote(data, "never seen"))

    def test_route_logs_and_rejects_protected(self):
        with tempfile.TemporaryDirectory() as temp:
            pipeline = SimpleNamespace(source=Path(temp), data=Path(temp) / "data", lock=threading.RLock(), current=lambda: None,
                                       templates=lambda: [], atomic=SimpleNamespace(write=atomic_write))
            pipeline.data.mkdir()
            server = make_server(pipeline, 0, PAIRING_TOKEN)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def post(body):
                    connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
                    connection.request("POST", "/api/corpus", body=json.dumps(body), headers={"X-Portal-Token": PAIRING_TOKEN})
                    response = connection.getresponse()
                    result = response.status, json.loads(response.read())
                    connection.close()
                    return result
                self.assertEqual(post({"questions": [entry(), entry("Gender")]}), (200, {"logged": 1, "skipped": 1}))
                self.assertEqual(post({"questions": "bad"})[0], 400)
                stored = json.loads((pipeline.data / CORPUS_FILENAME).read_text(encoding="utf-8"))
                self.assertEqual(len(stored["questions"]), 1)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == "__main__":
    unittest.main()
