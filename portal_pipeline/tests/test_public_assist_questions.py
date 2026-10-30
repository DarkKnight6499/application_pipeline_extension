"""Author: Yazad Madan. Synthetic page capture, sorting, privacy, and HTTP contracts."""
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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

# Config
HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parent
TOKEN = "synthetic-assist-token"
ORIGIN = "chrome-extension://" + "a" * 32
HOST = "example.myworkdayjobs.com"
COMPANY = "Example Corp"
LABEL = "Describe your preferred project"
ANSWER = "Synthetic project answer"
OTHER = "Other synthetic answer"
NODE = shutil.which("node")
sys.path.insert(0, str(HERE))

import answer_memory
import assist_api
import assist_jobs
import intent_layer
import page_questions
import questions_sort
from server import make_server


class PageQuestionsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        self.service = assist_api.AssistService(self.data, self.root / "reference", token=TOKEN)
        self.draft = patch.object(self.service, "draft", return_value=None).start()
        patch.object(assist_jobs, "schedule").start()
        self.addCleanup(patch.stopall)

    def pair(self, **changes):
        return {"label": LABEL, "answer": ANSWER, "source": "prefilled", "type": "text", "options": [], **changes}

    def body(self, pairs=None, **changes):
        return {"host": HOST, "url": f"https://{HOST}/apply", "company_hint": COMPANY,
                "pairs": [self.pair()] if pairs is None else pairs, **changes}

    def capture(self, company=COMPANY, **pair):
        return self.service.dump(self.body([self.pair(**pair)], company_hint=company))

    def test_line_format_counts_only_page_group_and_append(self):
        result = self.service.dump(self.body([self.pair(), self.pair(label="Other project")]))
        self.assertEqual(result, {"saved": 2, "duplicate": 0, "excluded_by_type": 0, "flagged_sensitive": 0})
        self.assertTrue(all(type(value) is int for value in result.values()))
        path = self.data / page_questions.FILENAME
        prefix = path.read_bytes()
        rows = page_questions.read(self.data)
        self.assertEqual(rows[0]["page_id"], rows[1]["page_id"])
        self.assertEqual(rows[0]["author"], "Yazad Madan")
        self.assertEqual(rows[0]["vendor"], "workday")
        self.assertEqual(datetime.fromisoformat(rows[0]["ts"]).utcoffset(), timedelta(0))
        self.capture("Other Corp")
        self.assertTrue(path.read_bytes().startswith(prefix))
        self.assertNotEqual(page_questions.read(self.data)[-1]["page_id"], rows[0]["page_id"])
        self.assertFalse((self.data / assist_api.LOG_FILENAME).exists())
        self.assertFalse((self.data / "learning_queue.json").exists())
        self.assertEqual(answer_memory.load_memory(self.data)["answers"], {})

    def test_every_label_captured_sensitive_flagged_and_never_promoted(self):
        labels = ["Password", "SSN", "S.S.N.", "Social Security Number", "Signature", "I attest this is true",
                  "I certify", "I confirm", "Need sponsorship now?", "Need sponsorship in future?",
                  "Authorized to work?", "Right to work?", "Employment eligibility", "Veteran status",
                  "Disability", "Gender", "Race or ethnicity", "Nationality", "Pronouns", "Visa status",
                  "Religious affiliation", "Marital status", "Active duty", "Expected salary", "Criminal history"]
        pairs = [self.pair(label=label) for label in labels]
        pairs += [self.pair(label="Generic choice", options=["Male", "Female"]),
                  self.pair(label="Protected project", protected=True), self.pair(label="Draw here", type="signature")]
        for company in (COMPANY, "Other Corp"):
            result = self.service.dump(self.body(pairs, company_hint=company))
            self.assertEqual((result["saved"], result["flagged_sensitive"]), (len(pairs), len(pairs)))
        groups = questions_sort.report(self.service)
        self.assertEqual(sum(map(len, groups.values())), len(pairs))
        self.assertEqual(len(groups["SENSITIVE"]), len(pairs))
        questions_sort.promote(self.service)
        self.assertFalse(list(self.data.rglob("answer_memory.json")))
        for label in labels:
            with self.subTest(label=label), self.assertRaises(ValueError):
                questions_sort.resolve(self.service, label, ANSWER)
        for label in ("Gender", "SSN", "Signature", "Need sponsorship now?", "Authorized to work?"):
            self.assertEqual(self.service.answer({**self.body(), "label": label})["status"], "none")
        self.draft.assert_not_called()

    def test_profile_answers_saved_and_promoted(self):
        labels = ["First name", "Last name", "Email address", "Phone number", "Address", "LinkedIn URL"]
        for company in (COMPANY, "Other Corp"):
            result = self.service.dump(self.body([self.pair(label=label) for label in labels], company_hint=company))
            self.assertEqual((result["saved"], result["flagged_sensitive"]), (6, 0))
        self.assertEqual(questions_sort.promote(self.service)["shared"], 6)
        for label in labels:
            self.assertEqual(self.service.answer({**self.body(), "label": label})["answer"], ANSWER)

    def test_password_file_excluded_by_type_only(self):
        pairs = [self.pair(type="PASSWORD"), self.pair(type="file"), self.pair(label="Password", type="text")]
        result = self.service.dump(self.body(pairs))
        self.assertEqual((result["saved"], result["excluded_by_type"], result["flagged_sensitive"]), (1, 2, 1))
        rows = page_questions.read(self.data)
        self.assertEqual(rows[0]["type"], "text")

    def test_caps_truncate_flag_and_check_uncapped_sensitive_context(self):
        pair = self.pair(label="Q" * 310 + " signature", answer="A" * 2100,
                         options=["O" * 125] * 40 + ["Gender"])
        self.service.dump(self.body([pair], company_hint="C" * 160))
        row = page_questions.read(self.data)[0]
        self.assertEqual((len(row["label"]), len(row["answer"]), len(row["company"])), (300, 2000, 150))
        self.assertEqual((len(row["options"]), len(row["options"][0])), (40, 120))
        self.assertTrue(row["sensitive"])
        self.assertTrue(row["truncated"])
        self.assertEqual(row["truncated_fields"], ["answer", "company", "label", "options"])
        self.service.dump(self.body([self.pair(label="Generic choice", options=["Example"] * 40 + ["Gender"]),
                                    self.pair(label="Other choice", options=["O" * 130 + " disability"])]))
        self.assertTrue(all(row["sensitive"] for row in page_questions.read(self.data)))
        self.assertEqual(len(questions_sort.report(self.service)["SENSITIVE"]), 3)
        result = self.service.dump(self.body([self.pair(label=f"Project {index}") for index in range(80)]))
        self.assertEqual(result["saved"], 80)

    def test_atomic_validation_and_invalid_requests(self):
        invalid = [[], {}, self.body(pairs=[self.pair()] * 81), self.body(pairs=[self.pair(), self.pair(answer=5)]),
                   self.body(pairs=[self.pair(options=[5])]), self.body(pairs=[self.pair(source="untrusted")]),
                   self.body(pairs=[self.pair(label="")]), self.body(pairs=[self.pair(protected="true")]),
                   self.body(url="http://" + HOST), self.body(host="forged.example")]
        for body in invalid:
            with self.subTest(body=str(body)[:60]), self.assertRaises(ValueError):
                self.service.dump(body)
        self.assertFalse((self.data / page_questions.FILENAME).exists())

    def test_duplicates_exact_seven_days_and_restart(self):
        self.assertEqual(self.capture()["saved"], 1)
        restarted = assist_api.AssistService(self.data, self.root / "reference", token=TOKEN)
        self.assertEqual(restarted.dump(self.body())["duplicate"], 1)
        self.assertEqual(self.capture("Other Corp")["saved"], 1)
        self.assertEqual(self.capture(answer=OTHER)["saved"], 1)
        self.assertEqual(self.capture(label=LABEL.upper())["saved"], 1)
        path = self.data / page_questions.FILENAME
        rows = page_questions.read(self.data)
        rows[0]["ts"] = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        self.assertEqual(restarted.dump(self.body())["saved"], 1)

    def test_truncated_pairs_dedup_by_full_original_values(self):
        self.assertEqual(self.capture(answer="x" * 2000 + "a")["saved"], 1)
        self.assertEqual(self.capture(answer="x" * 2000 + "b")["saved"], 1)
        self.assertEqual(self.capture(answer="x" * 2000 + "a")["duplicate"], 1)
        self.assertEqual(len(page_questions.read(self.data)), 2)

    def test_unnamed_hosts_do_not_prove_distinct_companies(self):
        self.capture(company="")
        self.service.dump(self.body(company_hint="", host="other.myworkdayjobs.com",
                                    url="https://other.myworkdayjobs.com/apply"))
        report = questions_sort.report(self.service)
        self.assertEqual(report["AGREE"], [])
        self.assertEqual(report["SINGLE"][0]["company_count"], 0)
        questions_sort.promote(self.service)
        self.assertEqual(answer_memory.load_memory(self.data)["answers"], {})

    def test_reviewed_intent_normalization_stays_idempotent(self):
        self.capture(label="Are you willing to travel?", answer="Opt In")
        self.capture("Other Corp", label="Are you willing to travel?", answer="Opt In")
        self.assertEqual(questions_sort.promote(self.service)["shared"], 1)
        self.assertEqual(questions_sort.promote(self.service)["unchanged"], 1)

    def test_concurrent_appends_and_dedup(self):
        with ThreadPoolExecutor(max_workers=16) as pool:
            results = list(pool.map(lambda index: self.capture(label=f"Project {index}"), range(24)))
        self.assertEqual(sum(result["saved"] for result in results), 24)
        with ThreadPoolExecutor(max_workers=16) as pool:
            results = list(pool.map(lambda _: self.capture(), range(16)))
        self.assertEqual(sum(result["saved"] for result in results), 1)
        self.assertEqual(sum(result["duplicate"] for result in results), 15)
        self.assertEqual(len(page_questions.read(self.data)), 25)

    def test_agree_promotes_and_prefill_counts_equally(self):
        self.capture(source="prefilled")
        self.capture("Other Corp", source="typed", answer="  SYNTHETIC project answer  ")
        report = questions_sort.report(self.service)
        self.assertEqual((len(report["AGREE"]), report["AGREE"][0]["company_count"]), (1, 2))
        self.assertEqual(questions_sort.promote(self.service)["shared"], 1)
        entry = next(iter(answer_memory.load_memory(self.data)["answers"].values()))
        self.assertEqual(entry["source"], "questions-promoted")
        self.assertEqual(self.service.answer({**self.body(company_hint="Third Corp"), "label": LABEL})["answer"], ANSWER)

    def test_single_company_counts_once_and_stays_scoped(self):
        self.capture(source="filled")
        self.capture(label=LABEL.upper(), source="corrected")
        group = questions_sort.report(self.service)["SINGLE"][0]
        self.assertEqual((group["company_count"], group["sighting_count"], group["capture_count"]), (1, 1, 2))
        self.assertEqual(questions_sort.promote(self.service)["company"], 1)
        self.assertEqual(answer_memory.load_memory(self.data)["answers"], {})
        directory = self.service.company_scope(self.body())[0]
        self.assertEqual(answer_memory.load_memory(directory)["answers"][answer_memory.normalize_label(LABEL)]["source"], "questions-single")
        self.assertEqual(self.service.answer({**self.body(), "label": LABEL})["answer"], ANSWER)
        self.assertEqual(self.service.answer({**self.body(company_hint="Other Corp"), "label": LABEL})["status"], "none")

    def test_company_conflict_and_existing_shared_conflict_never_overwrite(self):
        self.capture()
        self.capture("Other Corp", answer=OTHER)
        self.assertEqual(len(questions_sort.report(self.service)["CONFLICT"]), 1)
        self.assertEqual(questions_sort.promote(self.service)["conflict"], 1)
        self.assertFalse(list(self.data.rglob("answer_memory.json")))
        self.service.accept({"label": LABEL, "answer": "Already stored synthetic answer"})
        before = answer_memory.memory_path(self.data).read_bytes()
        questions_sort.promote(self.service)
        self.assertEqual(answer_memory.memory_path(self.data).read_bytes(), before)

    def test_agreement_conflicts_against_stored_shared_and_company_answers(self):
        self.capture()
        self.capture("Other Corp")
        for scoped in (False, True):
            directory = self.service.company_scope(self.body())[0] if scoped else self.data
            answer_memory.update_memory(lambda memory: answer_memory.remember(memory, LABEL, OTHER), directory)
        self.assertEqual(len(questions_sort.report(self.service)["CONFLICT"]), 1)
        before = {str(path): path.read_bytes() for path in self.data.rglob("answer_memory.json")}
        questions_sort.promote(self.service)
        self.assertEqual({str(path): path.read_bytes() for path in self.data.rglob("answer_memory.json")}, before)

    def test_near_stored_and_read_only_reference_conflicts(self):
        self.capture()
        self.capture("Other Corp")
        self.service.accept({"label": "Please describe your preferred project", "answer": OTHER})
        self.assertEqual(len(questions_sort.report(self.service)["CONFLICT"]), 1)
        directory = self.service.reference / "company_kb"
        directory.mkdir(parents=True)
        path = directory / "example_corp.json"
        original = json.dumps({"company": COMPANY, "questions": [{"text": LABEL, "answer": OTHER}]})
        path.write_text(original, encoding="utf-8")
        self.assertTrue(any(entry["scope"].startswith("reference:")
                            for entry in questions_sort.report(self.service)["CONFLICT"][0]["stored_answers"]))
        questions_sort.promote(self.service)
        self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_near_wording_merge_and_meaning_boundaries(self):
        self.capture()
        alias = "Please describe your preferred project"
        self.capture("Other Corp", label=alias)
        self.assertEqual(len(questions_sort.report(self.service)["AGREE"]), 1)
        questions_sort.promote(self.service)
        for label in (LABEL, alias):
            self.assertEqual(self.service.answer({**self.body(), "label": label})["answer"], ANSWER)
        for label in ("Describe your first project", "Describe your last project", "Do not describe your preferred project",
                      "Need sponsorship now?", "Need sponsorship in future?"):
            self.capture(label=label)
        report = questions_sort.report(self.service)
        self.assertEqual((len(report["AGREE"]), len(report["SINGLE"]), len(report["SENSITIVE"])), (1, 3, 2))

    def test_intent_storage_collision_is_conflict(self):
        self.capture(label="Are you willing to travel?", answer="Yes")
        self.capture("Other Corp", label="Are you willing to travel internationally?", answer="No")
        self.assertEqual(len(questions_sort.report(self.service)["CONFLICT"]), 2)
        questions_sort.promote(self.service)
        self.assertFalse(list(self.data.rglob("answer_memory.json")))

    def test_promote_idempotent_state_has_no_values_and_store_changes_rechecked(self):
        self.capture()
        self.capture("Other Corp")
        path = self.data / page_questions.FILENAME
        before = path.read_bytes()
        questions_sort.promote(self.service)
        state_path = self.data / questions_sort.STATE_FILENAME
        state = state_path.read_bytes()
        memory_path = answer_memory.memory_path(self.data)
        memory = memory_path.read_bytes()
        with patch.object(self.service, "save_reviewed", side_effect=AssertionError("Must not write twice")):
            self.assertEqual(questions_sort.promote(self.service)["unchanged"], 1)
        self.assertEqual(state_path.read_bytes(), state)
        self.assertEqual(memory_path.read_bytes(), memory)
        self.assertEqual(path.read_bytes(), before)
        self.assertNotIn(ANSWER, state.decode())
        answer_memory.update_memory(lambda memory: answer_memory.remember(memory, LABEL, OTHER), self.data)
        self.assertEqual(questions_sort.promote(self.service)["conflict"], 1)

    def test_concurrent_promotes_share_processed_state(self):
        self.capture()
        self.capture("Other Corp")
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: questions_sort.promote(self.service), range(8)))
        self.assertEqual(sum(result["shared"] for result in results), 1)
        restarted = assist_api.AssistService(self.data, self.root / "reference", token=TOKEN)
        self.assertEqual(questions_sort.promote(restarted)["unchanged"], 1)

    def test_raw_capture_never_used_for_fill(self):
        self.capture()
        self.assertEqual(self.service.answer({**self.body(), "label": LABEL})["status"], "none")
        with patch.object(page_questions, "read", side_effect=AssertionError("Raw capture must not be read")):
            self.assertEqual(self.service.answer({**self.body(), "label": LABEL})["status"], "none")

    def test_resolve_shared_keeps_differing_company_scoped_and_marks_group(self):
        self.capture()
        self.capture("Other Corp", answer=OTHER)
        self.assertEqual(questions_sort.resolve(self.service, LABEL, ANSWER), {"resolved": 1})
        group = questions_sort.report(self.service)["CONFLICT"][0]
        self.assertTrue(group["resolved"])
        self.assertEqual(questions_sort.promote(self.service)["unchanged"], 1)
        self.assertEqual(self.service.answer({**self.body(company_hint="Other Corp"), "label": LABEL})["answer"], OTHER)
        self.assertEqual(self.service.answer({**self.body(company_hint="Third Corp"), "label": LABEL})["answer"], ANSWER)
        self.capture("New Corp", answer="New synthetic answer")
        self.assertFalse(questions_sort.report(self.service)["CONFLICT"][0]["resolved"])

    def test_resolve_explicitly_replaces_shared_and_refuses_company_overwrite(self):
        self.capture()
        self.service.accept({"label": LABEL, "answer": OTHER})
        questions_sort.resolve(self.service, LABEL, ANSWER)
        self.assertEqual(answer_memory.lookup(answer_memory.load_memory(self.data), LABEL), ANSWER)
        directory = self.service.company_scope(self.body())[0]
        answer_memory.update_memory(lambda memory: answer_memory.remember(memory, LABEL, OTHER), directory)
        with self.assertRaises(ValueError):
            questions_sort.resolve(self.service, LABEL, "New synthetic answer")
        self.assertEqual(answer_memory.lookup(answer_memory.load_memory(self.data), LABEL), ANSWER)

    def test_resolve_reconciles_legacy_exact_answer_hidden_by_global_intent(self):
        label = "Are you willing to travel?"
        self.capture(label=label, answer="Yes")
        self.capture("Other Corp", label=label, answer="Yes")
        self.service.accept({"label": label, "answer": "Yes"})
        answer_memory.update_memory(lambda memory: answer_memory.remember(memory, label, "No"), self.data)
        self.assertEqual(len(questions_sort.report(self.service)["CONFLICT"]), 1)
        questions_sort.resolve(self.service, label, "Yes")
        self.assertTrue(questions_sort.report(self.service)["AGREE"][0]["resolved"])
        self.assertEqual(answer_memory.lookup(answer_memory.load_memory(self.data), label), "Yes")

    def test_report_cli_json_stable_text_sensitive_and_generic_errors(self):
        self.capture()
        self.capture(label="Gender")
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch.object(questions_sort, "AssistService", return_value=self.service):
            self.assertEqual(questions_sort.main(["--data", str(self.data), "report", "--json"]), 0)
        self.assertEqual(json.loads(output.getvalue()), questions_sort.report(self.service))
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch.object(questions_sort, "AssistService", return_value=self.service):
            questions_sort.main(["--data", str(self.data), "report"])
        self.assertIn("SENSITIVE (captured, never auto-filled)", output.getvalue())
        self.assertIn(ANSWER, output.getvalue())
        (self.data / page_questions.FILENAME).write_text(ANSWER, encoding="utf-8")
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors), patch.object(questions_sort, "AssistService", return_value=self.service):
            self.assertEqual(questions_sort.main(["--data", str(self.data), "promote"]), 1)
        self.assertNotIn(ANSWER, errors.getvalue())

    def test_cli_promote_and_resolve_counts_only(self):
        self.capture()
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch.object(questions_sort, "AssistService", return_value=self.service):
            self.assertEqual(questions_sort.main(["--data", str(self.data), "promote"]), 0)
        self.assertEqual(json.loads(output.getvalue())["company"], 1)
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch.object(questions_sort, "AssistService", return_value=self.service):
            self.assertEqual(questions_sort.main(["--data", str(self.data), "resolve", "--label", LABEL, "--answer", ANSWER]), 0)
        self.assertEqual(json.loads(output.getvalue()), {"resolved": 1})
        self.assertEqual(questions_sort.promote(self.service)["unchanged"], 1)

    def test_git_ignores_default_data_and_capture_files_anywhere(self):
        paths = ["portal_pipeline/data/page_questions.jsonl", "portal_pipeline/data/questions_processed.json",
                 "portal_pipeline/data/company_kb/example/answer_memory.json", "custom/page_questions.jsonl",
                 "custom/questions_processed.json", "custom/conflicts.json", "custom/questions_sort_errors.log"]
        result = subprocess.run(["git", "-c", f"safe.directory={REPO.as_posix()}", "check-ignore", *paths],
                                cwd=REPO, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), paths)

    def test_http_dump_auth_caps_counts_only_and_no_side_effects_on_rejection(self):
        server = make_server(None, 0, assist=self.service)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)
        def request(body=None, headers=None, method="POST"):
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            self.addCleanup(connection.close)
            connection.request(method, "/assist/dump", json.dumps(self.body() if body is None else body) if method == "POST" else None,
                               {"Origin": ORIGIN, "X-Assist-Token": TOKEN, **(headers or {})})
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        for headers, status in (({"X-Assist-Token": "wrong"}, 401), ({"X-Assist-Token": ""}, 401),
                                ({"Origin": "https://example.invalid"}, 403), ({"Origin": "chrome-extension://bad"}, 403),
                                ({"Host": "forged.example"}, 403), ({"Content-Length": str(assist_api.MAX_BODY + 1)}, 413),
                                ({"Transfer-Encoding": "chunked"}, 413)):
            self.assertEqual(request(headers=headers)[0], status)
        self.assertEqual(request(method="GET")[0], 405)
        self.assertEqual(request(headers={"Access-Control-Request-Method": "POST"}, method="OPTIONS")[0], 200)
        self.assertEqual(request(self.body([self.pair()] * 81))[0], 400)
        self.assertFalse((self.data / page_questions.FILENAME).exists())
        status, result = request()
        self.assertEqual(status, 200)
        self.assertTrue(all(type(value) is int for value in result.values()))
        self.assertNotIn(ANSWER, json.dumps(result))
        self.assertEqual(request()[1]["duplicate"], 1)
        status, result = request(self.body([self.pair(label="Q" * 310 + " signature", answer="A" * 2100)]))
        self.assertEqual((status, result["saved"], result["flagged_sensitive"]), (200, 1, 1))
        with ThreadPoolExecutor(max_workers=8) as pool:
            responses = list(pool.map(lambda index: request(self.body([self.pair(label=f"HTTP project {index}")])), range(8)))
        self.assertTrue(all(status == 200 and result["saved"] == 1 for status, result in responses))
        self.assertEqual(len(page_questions.read(self.data)), 10)

    @unittest.skipUnless(NODE, "Node.js is required for browser-free checks.")
    def test_save_page_content_and_worker(self):
        result = subprocess.run([NODE, str(HERE / "tests" / "assist_questions_harness.js")],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
