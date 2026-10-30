"""Author: Yazad Madan. Synthetic assist resolution and HTTP boundary checks."""
import http.client
import json
import sys
import tempfile
import subprocess
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Config
HERE = Path(__file__).resolve().parents[1]
ORIGIN = "chrome-extension://" + "a" * 32
TOKEN = "synthetic-assist-token"
LABEL = "Example question"
ANSWER = "Example answer"
COMPANY = "Example Corp"
sys.path.insert(0, str(HERE))

import answer_memory
import assist_api
import intent_layer
from server import make_server


class AssistTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.reference = self.root / "reference"
        self.reference.mkdir()
        self.service = assist_api.AssistService(self.root / "data", self.reference,
                                              self.root / "profile.json", token=TOKEN)
        self.draft = patch.object(assist_api.subprocess, "run", return_value=Mock(
            returncode=0, stdout="Example draft.")).start()
        self.addCleanup(patch.stopall)

    def payload(self, label=LABEL):
        return dict(label=label, options=[], type="text", host="example.myworkdayjobs.com",
                    url="https://example.myworkdayjobs.com/apply", company_hint=COMPANY)

    def test_company_precedes_intent_and_exact_memory(self):
        self.service.accept(dict(label="First name", answer="Example intent"))
        kb = self.reference / "company_kb"
        kb.mkdir()
        (kb / "example_corp.json").write_text(json.dumps({"company": COMPANY, "portals": [],
            "questions": [{"key": "first name", "text": "First name", "answer": ANSWER}]}))
        result = self.service.answer(self.payload("First name"))
        self.assertEqual((result["source"], result["answer"]), ("company_kb", ANSWER))
        self.draft.assert_not_called()

    def test_intent_expands_and_precedes_exact_memory(self):
        self.service.accept(dict(label="Are you willing to travel?", answer="YES"))
        answer_memory.update_memory(lambda data: answer_memory.remember(
            data, "Are you willing to travel?", "Example exact"), self.service.data)
        result = self.service.answer(self.payload("Are you willing to travel?"))
        self.assertEqual(result["source"], "intent")
        self.assertIn("Yes", result["candidates"])
        self.draft.assert_not_called()

    def test_company_module_matcher_is_reused(self):
        (self.reference / "company_kb.py").write_text(
            '"""Author: Yazad Madan. Synthetic read-only matcher."""\n'
            'def find_answer(company, question):\n'
            '    return {"answer": "Example module match"}\n')
        self.assertEqual(self.service.answer(self.payload())["answer"], "Example module match")
        self.draft.assert_not_called()

    def test_fallback_overlap_and_ambiguous_match(self):
        directory = self.reference / "company_kb"
        directory.mkdir()
        path = directory / "example_corp.json"
        row = {"text": "Example question about a preferred project", "answer": ANSWER}
        path.write_text(json.dumps({"questions": [row]}))
        self.assertEqual(self.service.answer(self.payload("Example question about the preferred project"))["source"], "claude")
        self.assertEqual(self.service.answer(self.payload("Example question about a preferred project today"))["source"], "company_kb")
        path.write_text(json.dumps({"questions": [row, {**row, "text": row["text"] + " today extra"}]}))
        self.assertEqual(self.service.answer(self.payload("Example question about a preferred project today"))["source"], "claude")

    def test_token_persists_without_entering_question_log(self):
        first = assist_api.AssistService(self.root / "other-data", self.reference, self.service.profile_path)
        second = assist_api.AssistService(first.data, self.reference, self.service.profile_path)
        self.assertEqual(first.token, second.token)
        self.assertEqual(first.token_path.read_text().strip(), first.token)
        first.accept(dict(label=LABEL, answer=ANSWER))
        first.answer(self.payload())
        log = (first.data / assist_api.LOG_FILENAME).read_text()
        self.assertIn(LABEL, log)
        self.assertNotIn(first.token, log)

    def test_accept_exact_and_next_lookup(self):
        self.service.accept(dict(label=LABEL, answer=ANSWER))
        self.assertEqual(self.service.answer(self.payload())["answer"], ANSWER)
        self.draft.assert_not_called()

    def test_blocked_questions_queue_but_never_draft(self):
        labels = ["Authorized to work?", "Right to work?", "Can you legally work?", "Eligible for employment?",
                  "Visa status?", "Need sponsorship in future?", "Criminal history?",
                  "Legal proceedings?", "Disability?", "Veteran status?", "Gender?",
                  "Race or ethnicity?", "Self identification?", "Expected salary?",
                  "Compensation expectations?", "Relatives employed here?", "Related to an employee?", "Conflict of interest?",
                  "Securities registration?", "FINRA license?", "Sign this agreement",
                  "I certify this is true", "Sexual orientation?", "Military service?"]
        for label in labels:
            with self.subTest(label=label):
                self.assertEqual(self.service.answer(self.payload(label))["status"], "none")
        self.draft.assert_not_called()
        queue = json.loads((self.service.data / "learning_queue.json").read_text())
        self.assertEqual(len(queue["questions"]), len(labels))

    def test_miss_queues_without_erasing_existing_review_and_returns_draft(self):
        self.service.answer(self.payload())
        path = self.service.data / "learning_queue.json"
        queue = json.loads(path.read_text())
        queue["questions"][0]["answer"] = "Example reviewed answer"
        path.write_text(json.dumps(queue))
        result = self.service.answer(self.payload("Another example question"))
        self.assertEqual(result["status"], "draft")
        queue = json.loads(path.read_text())
        self.assertEqual(queue["questions"][0]["answer"], "Example reviewed answer")
        self.assertEqual(len(queue["questions"]), 2)
        self.assertEqual(answer_memory.load_memory(self.service.data)["answers"], {})
        self.assertEqual(self.draft.call_args.kwargs["timeout"], 90)
        self.assertFalse(self.draft.call_args.kwargs.get("shell", False))

    def test_draft_profile_allowlist(self):
        self.service.profile_path.write_text(json.dumps({
            "header": {"name": "Example Name", "contact": "DO_NOT_SEND_CONTACT"},
            "education": [{"school": "Example School", "degree": "Example degree", "secret": "DO_NOT_SEND"}],
            "certifications": [{"cert": "Example credential", "issuer": "Example issuer"}],
            "experience": [{"company": "Example Employer", "roles": ["DO_NOT_SEND_ROLES"]}],
            "skills": ["DO_NOT_SEND_SKILLS"]}))
        self.service.answer(self.payload())
        prompt = self.draft.call_args.args[0][-1]
        self.assertIn("Example Employer", prompt)
        self.assertNotIn("DO_NOT_SEND", prompt)

    def test_no_answer_errors_and_bad_prose_return_none(self):
        for output in ("NO_ANSWER", "", "One. Two. Three. Four.", "One. Two. Three. Four",
                       "Example\u2014draft", "Example--draft", '{"answer": "Example"}'):
            self.draft.return_value = Mock(returncode=0, stdout=output)
            self.assertEqual(self.service.answer(self.payload())["status"], "none", output)
        self.draft.side_effect = FileNotFoundError("synthetic missing CLI")
        self.assertEqual(self.service.answer(self.payload())["status"], "none")
        self.draft.side_effect = subprocess.TimeoutExpired("claude", 90)
        self.assertEqual(self.service.answer(self.payload())["status"], "none")

    def test_invalid_profile_returns_none_without_calling_cli(self):
        self.service.profile_path.write_text("invalid json")
        self.assertEqual(self.service.answer(self.payload())["status"], "none")
        self.draft.assert_not_called()

    def test_windows_npm_launcher_bypasses_shell(self):
        shim = self.root / "claude.cmd"
        entry = shim.parent / assist_api.CLAUDE_NODE_ENTRY
        entry.parent.mkdir(parents=True)
        entry.write_text("/* Author: Yazad Madan. Synthetic CLI stub. */")
        with patch.object(assist_api.shutil, "which", side_effect=lambda name:
                          str(self.root / "node.exe") if name == "node" else str(shim)):
            self.assertEqual(self.service.answer(self.payload())["status"], "draft")
        arguments = self.draft.call_args.args[0]
        self.assertEqual(arguments[:2], [str(self.root / "node.exe"), str(entry)])
        self.assertFalse(self.draft.call_args.kwargs["shell"])

    def test_stored_sensitive_answer_and_signature_remain_manual(self):
        answer_memory.update_memory(lambda memory: answer_memory.remember(
            memory, "Gender?", "Example reviewed choice"), self.service.data)
        self.assertEqual(self.service.answer(self.payload("Gender?"))["status"], "none")
        for label in ("Gender?", "Signature"):
            with self.assertRaises(ValueError):
                self.service.accept(dict(label=label, answer=ANSWER))
        self.draft.assert_not_called()

    def test_repeated_miss_has_one_queue_entry(self):
        self.service.answer(self.payload())
        self.service.answer(self.payload())
        queue = json.loads((self.service.data / "learning_queue.json").read_text())
        self.assertEqual(len(queue["questions"]), 1)
        self.assertEqual(queue["questions"][0]["job_count"], 1)

    def test_sensitive_choices_with_generic_label_never_draft(self):
        body = self.payload("Please select one")
        body["options"] = ["Male", "Female", "Decline to disclose"]
        self.assertEqual(self.service.answer(body)["status"], "none")
        self.assertEqual(self.service.answer(self.payload("Are you permitted to work here?"))["status"], "none")
        self.draft.assert_not_called()

    def learning(self, pairs=None, dry_run=True, **context):
        return {**self.payload(), "pairs": pairs if pairs is not None else [{"label": LABEL, "answer": ANSWER}],
                "dry_run": dry_run, **context}

    def confirm(self, body):
        reviewed = self.service.learn(body)
        pairs = [{**pair, "previous_answer": result["previous_answer"]}
                 for pair, result in zip(body["pairs"], reviewed["results"]) if result["status"] != "skipped"]
        return self.service.learn({**body, "dry_run": False, "pairs": pairs})

    def test_learn_dry_run_then_confirm_uses_accept_store_and_lookup(self):
        body = self.learning()
        result = self.service.learn(body)
        self.assertEqual(result["results"][0]["status"], "new")
        self.assertFalse(result["results"][0]["stored"])
        directory, scope = self.service.company_scope(body)
        self.assertEqual(scope, COMPANY)
        self.assertFalse(answer_memory.memory_path(directory).exists())
        self.assertTrue(self.confirm(body)["results"][0]["stored"])
        stored = json.loads(answer_memory.memory_path(directory).read_text())
        self.assertEqual(stored["author"], "Yazad Madan")
        self.assertEqual(self.service.answer(self.payload())["answer"], ANSWER)
        self.assertEqual(self.service.answer(self.payload())["source"], "company_kb")
        self.service.accept({**self.payload(), "answer": "Reviewed replacement", "previous_answer": ANSWER})
        self.assertEqual(self.service.learn(body)["results"][0]["previous_answer"], "Reviewed replacement")
        self.assertEqual(answer_memory.load_memory(self.service.data)["answers"], {})
        self.draft.assert_not_called()

    def test_learn_same_changed_selected_only_and_stale_review(self):
        body = self.learning()
        self.confirm(body)
        self.assertEqual(self.service.learn(body)["results"][0]["status"], "same")
        changed = self.learning([{"label": LABEL, "answer": "New reviewed project"}])
        review = self.service.learn(changed)["results"][0]
        self.assertEqual(review["status"], "changed")
        self.assertEqual(self.service.learn({**changed, "dry_run": False})["results"][0]["stored"], False)
        self.service.learn(self.learning([], dry_run=False))
        self.assertEqual(self.service.company_answer(self.payload()), ANSWER)
        self.service.accept({**self.payload(), "answer": "Concurrent review", "previous_answer": ANSWER})
        stale = self.service.learn({**changed, "dry_run": False, "pairs": [
            {**changed["pairs"][0], "previous_answer": review["previous_answer"]}]})
        self.assertFalse(stale["results"][0]["stored"])
        self.assertEqual(self.service.company_answer(self.payload()), "Concurrent review")
        self.assertTrue(self.confirm(changed)["results"][0]["stored"])
        self.assertEqual(self.service.company_answer(self.payload()), "New reviewed project")

    def test_learn_reference_conflict_stays_read_only(self):
        directory = self.reference / "company_kb"
        directory.mkdir()
        path = directory / "example_corp.json"
        original = json.dumps({"company": COMPANY, "questions": [{"text": LABEL, "answer": "Reference project"}]})
        path.write_text(original)
        body = self.learning()
        self.assertEqual(self.service.learn(body)["results"][0]["status"], "changed")
        self.confirm(body)
        self.assertEqual(path.read_text(), original)
        self.assertEqual(self.service.company_answer(self.payload()), ANSWER)

    def test_learn_company_host_isolation_and_no_global_promotion(self):
        body = self.learning([{"label": "Are you willing to travel?", "answer": "Example travel choice"}])
        self.confirm(body)
        for context in ({"company_hint": "Other Corp"},
                        {"host": "other.myworkdayjobs.com", "url": "https://other.myworkdayjobs.com/apply"}):
            self.assertIsNone(self.service.company_answer({**self.payload("Are you willing to travel?"), **context}))
        self.assertEqual(answer_memory.load_memory(self.service.data)["answers"], {})
        self.assertEqual(list(self.reference.iterdir()), [])

    def test_learn_host_fallback_and_reject_mismatched_page(self):
        body = self.learning(company_hint="")
        self.assertEqual(self.service.learn(body)["scope"], body["host"])
        self.confirm(body)
        self.assertEqual(self.service.company_answer({**self.payload(), "company_hint": ""}), ANSWER)
        for context in ({"host": ""}, {"url": "http://example.myworkdayjobs.com/apply"},
                        {"url": "https://other.example/apply"}):
            with self.assertRaises(ValueError):
                self.service.learn({**body, **context})

    def test_learn_blocks_sensitive_forbidden_empty_and_unsafe_types_on_server(self):
        labels = ["Password", "Passcode", "Verification code", "SSN", "Social security", "Signature", "Signed",
                  "I attest this is true", "I certify", "I confirm", "Authorized to work?", "Right to work?",
                  "Work authorization", "Employment eligibility", "Need sponsorship now?", "Need sponsorship in future?",
                  "Visa status", "Veteran status", "Disability", "Gender", "Race or ethnicity", "Self identification",
                  "Nationality", "Pronouns", "Religious affiliation", "Criminal history", "Expected salary"]
        pairs = [{"label": label, "answer": ANSWER, "previous_answer": None} for label in labels]
        pairs.extend([{"label": "Empty project", "answer": "  "},
                      {"label": "Project file", "answer": ANSWER, "type": "file"},
                      {"label": "Secret project", "answer": ANSWER, "type": "password"},
                      {"label": "Protected project", "answer": ANSWER, "protected": True},
                      {"label": "Please select one", "answer": ANSWER, "options": ["Female", "Male"]}])
        for dry_run in (True, False):
            result = self.service.learn(self.learning(pairs, dry_run=dry_run))
            self.assertTrue(all(row["status"] == "skipped" and not row["stored"] for row in result["results"]))
        directory, _ = self.service.company_scope(self.learning())
        self.assertFalse(answer_memory.memory_path(directory).exists())
        self.draft.assert_not_called()

    def test_learn_bounds_and_atomic_validation(self):
        pair = {"label": LABEL, "answer": ANSWER}
        invalid = [None, [], {"pairs": "bad"}, {"dry_run": "true"},
                   {"pairs": [pair] * 81}, {"pairs": [{**pair, "label": "x" * 301}]},
                   {"pairs": [{**pair, "answer": "x" * 2001}]}, {"pairs": [pair, pair]},
                   {"pairs": [pair, {**pair, "answer": 1}]}, {"pairs": [pair, []]},
                   {"pairs": [{**pair, "previous_answer": False}]}]
        for value in invalid:
            with self.subTest(value=str(value)[:80]), self.assertRaises(ValueError):
                self.service.learn({**self.learning(dry_run=False), **value} if isinstance(value, dict) else value)
        directory, _ = self.service.company_scope(self.learning())
        self.assertFalse(answer_memory.memory_path(directory).exists())
        pairs = [{"label": "x" * 300, "answer": "a" * 2000}]
        self.assertEqual(self.service.learn(self.learning(pairs))["results"][0]["status"], "new")
        pairs = [{"label": f"Project {index}", "answer": ANSWER} for index in range(80)]
        self.assertEqual(len(self.service.learn(self.learning(pairs))["results"]), 80)

    def test_http_learn_auth_origin_host_size_and_methods(self):
        port = self.start()
        body = self.learning()
        preflight = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        self.addCleanup(preflight.close)
        preflight.request("OPTIONS", "/assist/learn", headers={"Origin": ORIGIN,
                          "Access-Control-Request-Method": "POST"})
        response = preflight.getresponse()
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Access-Control-Allow-Origin"), ORIGIN)
        response.read()
        directory, _ = self.service.company_scope(body)
        self.assertFalse(answer_memory.memory_path(directory).exists())
        for token in (None, "incorrect"):
            self.assertEqual(self.request(port, "/assist/learn", body, token=token)[0], 401)
        for origin in (None, "https://example.com", "chrome-extension://bad"):
            self.assertEqual(self.request(port, "/assist/learn", body, origin=origin)[0], 403)
        for headers, status, method in [({"Host": "forged.example"}, 403, "POST"),
                                       ({"Content-Length": str(assist_api.MAX_BODY + 1)}, 413, "POST"),
                                       ({"Transfer-Encoding": "chunked"}, 413, "POST"), ({}, 405, "GET")]:
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            self.addCleanup(connection.close)
            connection.request(method, "/assist/learn", json.dumps(body), headers={
                "Origin": ORIGIN, "X-Assist-Token": TOKEN, **headers})
            response = connection.getresponse()
            self.assertEqual(response.status, status)
            response.read()
        status, result = self.request(port, "/assist/learn", body)
        self.assertEqual((status, result["results"][0]["status"]), (200, "new"))
        body["dry_run"] = False
        body["pairs"][0]["previous_answer"] = None
        self.assertEqual(self.request(port, "/assist/learn", body)[1]["results"][0]["stored"], True)
        self.assertEqual(self.request(port, "/assist/learn", self.learning([{"label": "x" * 301, "answer": ANSWER}]))[0], 400)
        self.draft.assert_not_called()

    def start(self):
        server = make_server(None, 0, assist=self.service)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)
        return server.server_port

    def request(self, port, path="/assist/answer", body=None, token=TOKEN, origin=ORIGIN):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        self.addCleanup(connection.close)
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["X-Assist-Token"] = token
        if origin is not None:
            headers["Origin"] = origin
        connection.request("POST", path, json.dumps(body or self.payload()), headers)
        response = connection.getresponse()
        return response.status, json.loads(response.read())

    def test_http_token_origin_and_size(self):
        port = self.start()
        for token in (None, "incorrect", "\u00e9"):
            self.assertEqual(self.request(port, token=token)[0], 401)
        for origin in (None, "https://example.com", "http://127.0.0.1", "chrome-extension://bad"):
            self.assertEqual(self.request(port, origin=origin)[0], 403)
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        self.addCleanup(connection.close)
        connection.putrequest("POST", "/assist/answer")
        connection.putheader("Origin", ORIGIN)
        connection.putheader("X-Assist-Token", TOKEN)
        connection.putheader("Content-Length", str(assist_api.MAX_BODY + 1))
        connection.endheaders()
        response = connection.getresponse()
        self.assertEqual(response.status, 413)
        response.read()
        self.draft.assert_not_called()

    def test_http_preflight_is_extension_only_and_has_no_side_effects(self):
        port = self.start()
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        self.addCleanup(connection.close)
        connection.request("OPTIONS", "/assist/answer", headers={"Origin": ORIGIN,
                           "Access-Control-Request-Method": "POST"})
        response = connection.getresponse()
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Access-Control-Allow-Origin"), ORIGIN)
        response.read()
        self.assertFalse((self.service.data / "learning_queue.json").exists())
        self.draft.assert_not_called()

    def test_http_accept_then_lookup_and_malformed_input(self):
        port = self.start()
        self.assertEqual(self.request(port, "/assist/accept", dict(label=LABEL, answer=ANSWER))[0], 200)
        status, result = self.request(port)
        self.assertEqual((status, result["status"], result["answer"]), (200, "stored", ANSWER))
        for body in (["bad"], {"label": LABEL, "options": [123]}, {"label": ""}):
            self.assertEqual(self.request(port, body=body)[0], 400)
        self.draft.assert_not_called()


if __name__ == "__main__":
    unittest.main()
