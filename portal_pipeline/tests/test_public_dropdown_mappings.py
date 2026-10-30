"""Author: Yazad Madan. Synthetic vendor mapping storage, review, and transport checks."""
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
HOST = "example.wd5.myworkdayjobs.com"
LABEL = "Country?"
ANSWER = "USA"
OPTION = "United States of America"
OTHER_OPTION = "United States"
TOKEN = "synthetic-assist-token"
ORIGIN = "chrome-extension://" + "a" * 32
NODE = shutil.which("node")
HARNESS = Path(__file__).with_name("assist_dropdown_harness.js")
sys.path.insert(0, str(HERE))

import answer_memory
import assist_api
import dropdown_mappings as mappings
import dropdown_mappings_cli
from server import make_server


class DropdownTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.service = assist_api.AssistService(self.root / "data", self.root / "reference", token=TOKEN)
        self.draft = patch.object(self.service, "draft", return_value=None).start()
        self.addCleanup(patch.stopall)

    def body(self, **changes):
        return dict(label=LABEL, host=HOST, url="https://" + HOST + "/apply", type="select-one",
                    options=[OPTION, OTHER_OPTION], company_hint="Example Corp", **changes)

    def seed(self, label=LABEL, answer=ANSWER):
        self.service.accept({"label": label, "answer": answer})

    def learning(self, **changes):
        return {**self.body(), "dry_run": True, "pairs": [dict(label=LABEL, answer=OPTION,
                type="select-one", options=[OPTION, OTHER_OPTION], manual=True)], **changes}

    def confirm(self, body):
        row = self.service.learn(body)["results"][0]
        pair = {**body["pairs"][0], "mapping_answer": row["mapping_answer"],
                "previous_option": row["previous_option"]}
        return self.service.learn({**body, "pairs": [pair], "dry_run": False})["results"][0]

    def test_vendor_boundaries_tenants_and_lookalikes(self):
        for vendor, domains in mappings.VENDOR_DOMAINS.items():
            for domain in domains:
                for host in (domain, "tenant." + domain, "tenant.region." + domain, "TENANT." + domain.upper() + "."):
                    with self.subTest(host=host):
                        self.assertEqual(mappings.vendor_from_host(host), vendor)
                for host in ("not" + domain, domain + ".evil.invalid", domain + "evil", domain + ":443",
                             "https://" + domain, "user@" + domain, "bad.." + domain, "bad_." + domain, domain + ".."):
                    self.assertIsNone(mappings.vendor_from_host(host), host)
        for host in (None, "", "example.invalid", " myworkdayjobs.com", "myworkdayjobs.com/path"):
            self.assertIsNone(mappings.vendor_from_host(host))

    def test_store_persistence_isolation_and_explicit_replacement(self):
        self.assertTrue(mappings.update(self.service.data, "workday", LABEL, ANSWER, OPTION))
        store = mappings.load(self.service.data)
        self.assertEqual(store["author"], "Yazad Madan")
        self.assertEqual(mappings.lookup(store, "workday", " COUNTRY * ", ANSWER), OPTION)
        for vendor, label, answer in (("greenhouse", LABEL, ANSWER), ("workday", "Other country", ANSWER),
                                      ("workday", LABEL, "Canada")):
            self.assertIsNone(mappings.lookup(store, vendor, label, answer))
        self.assertFalse(mappings.update(self.service.data, "workday", LABEL, ANSWER, OTHER_OPTION))
        self.assertTrue(mappings.update(self.service.data, "workday", LABEL, ANSWER, OTHER_OPTION, OPTION))
        self.assertFalse(mappings.update(self.service.data, "workday", LABEL, ANSWER, None, OPTION))
        self.assertTrue(mappings.update(self.service.data, "workday", LABEL, ANSWER, None, OTHER_OPTION))
        self.assertEqual(mappings.load(self.service.data)[mappings.ROWS], [])

    def test_concurrent_confirms_do_not_overwrite(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda index: mappings.update(self.service.data, "workday", LABEL,
                           ANSWER, "Example option " + str(index)), range(12)))
        self.assertEqual(sum(results), 1)
        self.assertEqual(len(mappings.load(self.service.data)[mappings.ROWS]), 1)

    def test_learn_preview_confirm_preserves_kb_and_reuses_across_tenants(self):
        self.seed()
        original = answer_memory.memory_path(self.service.data).read_bytes()
        body = self.learning()
        review = self.service.learn(body)["results"][0]
        self.assertEqual((review["status"], review["mapping_answer"], review["answer"]), ("dropdown", ANSWER, OPTION))
        self.assertFalse(review["stored"])
        self.assertFalse((self.service.data / mappings.FILENAME).exists())
        self.assertFalse(self.service.learn({**body, "dry_run": False})["results"][0]["stored"])
        self.assertTrue(self.confirm(body)["stored"])
        self.assertEqual(answer_memory.memory_path(self.service.data).read_bytes(), original)
        for host in (HOST, "other.myworkdaysite.com"):
            result = self.service.answer({**self.body(), "host": host, "url": "https://" + host + "/apply"})
            self.assertEqual(result["mapped_options"], [OPTION])
            self.assertEqual(result["answer"], ANSWER)
        result = self.service.answer({**self.body(), "host": "boards.greenhouse.io", "url": "https://boards.greenhouse.io/example"})
        self.assertEqual(result["mapped_options"], [None])
        self.assertFalse(any(self.service.data.glob("company_kb/*/answer_memory.json")))
        log = (self.service.data / assist_api.LOG_FILENAME).read_text()
        self.assertNotIn(ANSWER, log)
        self.assertNotIn(OPTION, log)
        self.draft.assert_not_called()

    def test_resolution_precedence_and_candidate_alignment(self):
        self.seed(answer="USA|Canada")
        mappings.update(self.service.data, "workday", LABEL, "Canada", "Example Canada")
        result = self.service.answer(self.body())
        self.assertEqual(result["candidates"], ["USA", "Canada"])
        self.assertEqual(result["mapped_options"], [None, "Example Canada"])
        self.service.accept({**self.body(), "answer": "Example company answer", "previous_answer": "USA|Canada"})
        mappings.update(self.service.data, "workday", LABEL, "Example company answer", OPTION)
        result = self.service.answer(self.body())
        self.assertEqual(result["source"], "company_kb")
        self.assertEqual(result["mapped_options"], [OPTION])

    def test_stale_mapping_or_answer_requires_fresh_review(self):
        self.seed()
        body = self.learning()
        row = self.service.learn(body)["results"][0]
        pair = {**body["pairs"][0], "mapping_answer": row["mapping_answer"], "previous_option": None}
        mappings.update(self.service.data, "workday", LABEL, ANSWER, OTHER_OPTION)
        self.assertFalse(self.service.learn({**body, "dry_run": False, "pairs": [pair]})["results"][0]["stored"])
        self.service.accept({"label": LABEL, "answer": "Example changed answer", "previous_answer": ANSWER})
        self.assertFalse(self.service.learn({**body, "dry_run": False, "pairs": [pair]})["results"][0]["stored"])
        self.assertTrue(self.confirm(body)["stored"])

    def test_manual_select_combobox_radio_only_and_unknown_vendor_skips(self):
        self.seed()
        for kind in ("select-one", "select", "radio", "combobox"):
            body = self.learning()
            body["pairs"][0]["type"] = kind
            if kind == "combobox":
                body["pairs"][0]["options"] = []
            self.assertEqual(self.service.learn(body)["results"][0]["status"], "dropdown")
            body["pairs"][0]["manual"] = False
            self.assertEqual(self.service.learn(body)["results"][0]["status"], "skipped")
        body = self.learning(host="example.invalid", url="https://example.invalid/apply")
        self.assertEqual(self.service.learn(body)["results"][0]["status"], "skipped")
        body = self.learning()
        body["pairs"][0]["answer"] = "Not an offered option"
        self.assertEqual(self.service.learn(body)["results"][0]["status"], "skipped")

    def test_blocked_labels_options_and_legacy_answers_never_map_learn_or_fill(self):
        for label in ("Need sponsorship now?", "Need sponsorship in future?", "Authorized to work?",
                      "Work authorization", "Veteran", "Disability", "Gender", "Race or ethnicity",
                      "Religious affiliation", "Marital status", "Active duty", "Uniformed services",
                      "Password", "Signature", "I attest this is true", "SSN", "S.S.N."):
            with self.subTest(label=label):
                with self.assertRaises(ValueError):
                    self.service.accept({"label": label, "answer": ANSWER})
                with self.assertRaises(ValueError):
                    mappings.update(self.service.data, "workday", label, ANSWER, OPTION)
                answer_memory.update_memory(lambda memory: memory["answers"].update({
                    answer_memory.normalize_label(label): {"answer": ANSWER}}) or True, self.service.data)
                result = self.service.answer({**self.body(), "label": label})
                self.assertEqual((result["status"], result["mapped_options"]), ("none", []))
                body = self.learning()
                body["pairs"][0]["label"] = label
                self.assertEqual(self.service.learn(body)["results"][0]["status"], "skipped")
        self.seed()
        body = self.learning()
        body["pairs"][0]["options"].append("Decline to disclose")
        self.assertEqual(self.service.learn(body)["results"][0]["status"], "skipped")
        self.assertFalse((self.service.data / mappings.FILENAME).exists())
        self.draft.assert_not_called()

    def test_store_rejects_empty_oversized_and_protected_options(self):
        for label, answer, option in (("", ANSWER, OPTION), (LABEL, "", OPTION), (LABEL, ANSWER, ""),
                                      (LABEL, ANSWER, False), ("Q" * 301, ANSWER, OPTION),
                                      (LABEL, "x" * 2001, OPTION), (LABEL, ANSWER, "x" * 2001),
                                      (LABEL, ANSWER, "Female"), (LABEL, "Veteran", OPTION)):
            with self.assertRaises(ValueError):
                mappings.update(self.service.data, "workday", label, answer, option)
        with self.assertRaises(ValueError):
            mappings.update(self.service.data, "unknown", LABEL, ANSWER, OPTION)
        self.assertFalse((self.service.data / mappings.FILENAME).exists())

    def test_accept_requires_current_previous_answer_for_replacement(self):
        self.seed()
        for previous in (None, "Stale answer"):
            with self.assertRaises(ValueError):
                self.service.accept({"label": LABEL, "answer": "Changed answer", "previous_answer": previous})
        self.assertEqual(self.service.answer(self.body())["answer"], ANSWER)
        self.service.accept({"label": LABEL, "answer": "Changed answer", "previous_answer": ANSWER})
        self.assertEqual(self.service.answer(self.body())["answer"], "Changed answer")

    def test_invalid_store_is_explicit_and_normal_fill_writes_no_mappings(self):
        self.seed()
        self.assertEqual(self.service.answer(self.body())["mapped_options"], [None])
        path = self.service.data / mappings.FILENAME
        self.assertFalse(path.exists())
        for raw in ("broken", "[]", '{"schema_version": 0, "mappings": []}',
                    json.dumps({"schema_version": 1, "mappings": [{"vendor": "workday"}]}),
                    " " * (mappings.MAX_STORE_BYTES + 1)):
            path.write_text(raw, encoding="utf-8")
            with self.assertRaises(ValueError):
                mappings.load(self.service.data)

    def test_cli_list_remove_and_missing_mapping(self):
        mappings.update(self.service.data, "workday", LABEL, ANSWER, OPTION)
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(dropdown_mappings_cli.main(["--data", str(self.service.data), "list", "workday"]), 0)
        self.assertEqual(json.loads(output.getvalue())[0]["option"], OPTION)
        with contextlib.redirect_stdout(io.StringIO()):
            dropdown_mappings_cli.main(["--data", str(self.service.data), "remove", "workday", LABEL, ANSWER])
        self.assertEqual(mappings.load(self.service.data)[mappings.ROWS], [])
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            dropdown_mappings_cli.main(["--data", str(self.service.data), "remove", "workday", LABEL, ANSWER])

    def test_http_response_shape_and_draft_without_mapping(self):
        self.seed()
        self.confirm(self.learning())
        server = make_server(None, 0, assist=self.service)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        self.addCleanup(connection.close)
        connection.request("POST", "/assist/answer", json.dumps(self.body()),
                           {"Origin": ORIGIN, "X-Assist-Token": TOKEN, "Content-Type": "application/json"})
        response = connection.getresponse()
        self.assertEqual(response.status, 200)
        result = json.loads(response.read())
        self.assertEqual(result["mapped_options"], [OPTION])
        self.assertEqual(len(result["mapped_options"]), len(result["candidates"]))
        self.draft.return_value = "Example draft"
        result = self.service.answer({**self.body(), "label": "Unseen example question"})
        self.assertEqual((result["status"], result["mapped_options"]), ("draft", [None]))

    @unittest.skipUnless(NODE, "Node.js is required for browser-free checks.")
    def test_extension_mapping_harness(self):
        result = subprocess.run([NODE, str(HARNESS)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Assist dropdown checks passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
