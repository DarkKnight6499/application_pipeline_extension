"""Author: Yazad Madan. Synthetic question alias review, safety, storage, and CLI checks."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Config
HERE = Path(__file__).resolve().parents[1]
QUESTION = "Describe your preferred project"
ALIAS = "Please describe your preferred project"
ANSWER = "Example project answer"
HOST = "example.myworkdayjobs.com"
COMPANY = "Example Corp"
NODE = shutil.which("node")
sys.path.insert(0, str(HERE))

import answer_memory
import assist_api
import question_alias


class QuestionAliasTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.service = assist_api.AssistService(root / "data", root / "reference", root / "profile.json", token="synthetic")
        self.draft = patch.object(self.service, "draft", return_value=None).start()
        self.addCleanup(patch.stopall)
        self.body = dict(host=HOST, url=f"https://{HOST}/apply", company_hint=COMPANY)
        self.directory = self.service.company_scope(self.body)[0]

    def seed(self, question=QUESTION, answer=ANSWER, global_store=False):
        directory = self.service.data if global_store else self.directory
        answer_memory.update_memory(lambda memory: answer_memory.remember(memory, question, answer), directory)

    def review(self, label=ALIAS, answer=ANSWER, **pair):
        return self.service.learn({**self.body, "dry_run": True,
                                   "pairs": [dict(label=label, answer=answer, **pair)]})["results"][0]

    def confirm(self, result=None, **pair):
        result = result or self.review()
        payload = {key: result[key] for key in ("label", "answer", "previous_answer")}
        if "similar_to" in result:
            payload.update(similar_to=result["similar_to"], similar_scope=result["similar_scope"])
        return self.service.learn({**self.body, "dry_run": False,
                                   "pairs": [{**payload, **pair}]})["results"][0]

    def lookup(self, label=ALIAS, **context):
        return self.service.answer({**self.body, "label": label, **context})

    def test_similarity_positive_and_one_word_negatives(self):
        positives = [(QUESTION, ALIAS), ("Preferred project?", "What is your preferred project?"),
                     ("Describe your project experience", "Briefly describe your project experience"),
                     ("Preferred project", "PREFERRED PROJECT!")]
        negatives = [("Are you authorized to work here", "Are you required to work here"),
                     ("Describe your current project", "Describe your previous project"),
                     ("Are you willing to travel", "Are you willing to relocate"),
                     ("Describe your preferred project", "Do not describe your preferred project"),
                     ("Your first name", "Your last name"),
                     ("Minimum project duration", "Maximum project duration"),
                     ("Describe project 1", "Describe project 2"),
                     ("Preferred project", "Preferred project location"),
                     ("Describe your project", "Describe your project about you"),
                     ("Describe your project experience", "Describe your experience project"),
                     ("Do you have project experience", "Do you have no project experience")]
        for left, right in positives:
            with self.subTest(left=left, right=right):
                self.assertGreaterEqual(question_alias.similarity(left, right), question_alias.MIN_SIMILARITY)
        for left, right in negatives:
            with self.subTest(left=left, right=right):
                self.assertEqual(question_alias.similarity(left, right), 0)

    def test_review_opt_in_lookup_persistence_and_scope(self):
        self.seed()
        result = self.review()
        self.assertEqual(result["similar_to"], QUESTION)
        self.assertEqual(result["similar_scope"], "company")
        self.assertFalse((self.directory / question_alias.FILENAME).exists())
        self.assertEqual(self.lookup()["status"], "none")
        saved = self.confirm(result, use_alias=True)
        self.assertTrue(saved["stored"])
        self.assertEqual(saved["alias_status"], "stored")
        self.assertIsNone(answer_memory.lookup(answer_memory.load_memory(self.directory), ALIAS))
        self.assertEqual((self.lookup()["answer"], self.lookup()["source"]), (ANSWER, "question_alias"))
        restarted = assist_api.AssistService(self.service.data, self.service.reference, token="synthetic")
        self.assertEqual(restarted.answer({**self.body, "label": ALIAS})["answer"], ANSWER)
        self.assertIsNone(question_alias.lookup(self.service, {**self.body, "label": ALIAS, "company_hint": "Other Corp"}))
        self.assertIsNone(question_alias.lookup(self.service, {**self.body, "label": ALIAS,
                          "host": "other.myworkdayjobs.com", "url": "https://other.myworkdayjobs.com/apply"}))
        store = json.loads((self.directory / question_alias.FILENAME).read_text())
        self.assertEqual(store["author"], "Yazad Madan")
        self.assertNotIn(ANSWER, json.dumps(store))
        self.assertFalse((self.service.data / question_alias.FILENAME).exists())
        self.assertNotIn(ANSWER, (self.service.data / assist_api.LOG_FILENAME).read_text())
        self.assertEqual(list(self.service.reference.glob("**/*")), [])

    def test_unticked_stores_regular_answer_without_alias(self):
        self.seed()
        self.assertTrue(self.confirm(use_alias=False)["stored"])
        self.assertFalse((self.directory / question_alias.FILENAME).exists())
        self.assertEqual(self.lookup()["source"], "company_kb")

    def test_global_alias_requires_existing_global_target_and_never_promotes_company(self):
        self.seed(global_store=True)
        result = self.review()
        self.assertEqual(result["similar_scope"], "global")
        self.assertTrue(self.confirm(result, use_alias=True)["stored"])
        self.assertEqual(self.lookup(company_hint="Other Corp")["answer"], ANSWER)
        self.assertEqual(len(answer_memory.load_memory(self.service.data)["answers"]), 1)
        self.assertTrue((self.service.data / question_alias.FILENAME).exists())
        self.assertFalse((self.directory / question_alias.FILENAME).exists())

    def test_global_intent_target_and_removed_target(self):
        question = "What is your notice period"
        alias = "Please what is your notice period"
        self.service.accept({"label": question, "answer": ANSWER})
        result = self.review(label=alias)
        self.assertEqual(result["similar_to"], question)
        self.assertTrue(self.confirm(result, use_alias=True)["stored"])
        self.assertEqual(self.lookup(alias)["source"], "question_alias")
        path = answer_memory.memory_path(self.service.data)
        memory = json.loads(path.read_text())
        memory["answers"] = {}
        path.write_text(json.dumps(memory))
        self.assertEqual(self.lookup(alias)["status"], "none")

    def test_reference_answer_conflict_refuses_alias_without_writing_reference(self):
        self.seed()
        directory = self.service.reference / "company_kb"
        directory.mkdir(parents=True)
        path = directory / "example_corp.json"
        content = json.dumps({"questions": [{"text": ALIAS, "answer": "Reference answer"}]})
        path.write_text(content)
        result = self.review()
        self.assertEqual(result["status"], "changed")
        self.assertNotIn("similar_to", result)
        self.assertFalse(self.confirm(result, use_alias=True, similar_to=QUESTION, similar_scope="company")["stored"])
        self.assertEqual(path.read_text(), content)

    def test_reference_question_alias_stays_company_scoped_and_reference_read_only(self):
        alias = "What is your preferred project"
        directory = self.service.reference / "company_kb"
        directory.mkdir(parents=True)
        path = directory / "example_corp.json"
        content = json.dumps({"company": COMPANY, "portals": [{"host": HOST}],
                              "questions": [{"text": QUESTION, "answer": ANSWER}]})
        path.write_text(content)
        result = self.review(label=alias)
        self.assertEqual((result["similar_to"], result["similar_scope"]), (QUESTION, "company"))
        self.assertTrue(self.confirm(result, use_alias=True)["stored"])
        self.assertEqual(path.read_text(), content)
        self.assertFalse((self.service.data / question_alias.FILENAME).exists())
        self.assertEqual(self.lookup(alias)["source"], "question_alias")
        self.assertIsNone(question_alias.lookup(self.service, {**self.body, "label": alias, "company_hint": "Other Corp"}))
        path.write_text(content.replace(ANSWER, "Changed reference answer"))
        self.assertIsNone(question_alias.lookup(self.service, {**self.body, "label": alias}))

    def test_existing_alias_is_reviewed_and_repeated_confirmation_is_idempotent(self):
        self.seed()
        result = self.review()
        self.assertTrue(self.confirm(result, use_alias=True)["stored"])
        self.assertFalse(self.confirm(result, use_alias=True)["stored"])
        result = self.review()
        self.assertEqual((result["status"], result["previous_answer"]), ("same", ANSWER))
        self.assertTrue(self.confirm(result, use_alias=True)["stored"])

    def test_conflicting_answers_forged_match_and_ambiguous_matches_refused(self):
        self.seed()
        self.assertNotIn("similar_to", self.review(answer="Different answer"))
        forged = dict(label=ALIAS, answer="Different answer", previous_answer=None,
                      similar_to=QUESTION, similar_scope="company")
        self.assertFalse(self.confirm(forged, use_alias=True)["stored"])
        forged.update(answer=ANSWER, similar_to="Entirely unrelated question")
        self.assertFalse(self.confirm(forged, use_alias=True)["stored"])
        self.seed(question="Briefly describe your preferred project")
        self.assertNotIn("similar_to", self.review())
        self.assertFalse((self.directory / question_alias.FILENAME).exists())
        self.assertEqual(answer_memory.lookup(answer_memory.load_memory(self.directory), QUESTION), ANSWER)

    def test_stale_target_rejected_and_changed_target_disables_alias(self):
        self.seed()
        result = self.review()
        self.seed(answer="Changed answer")
        self.assertFalse(self.confirm(result, use_alias=True)["stored"])
        self.seed()
        self.assertTrue(self.confirm(use_alias=True)["stored"])
        self.seed(answer="Changed answer")
        self.assertEqual(self.lookup()["status"], "none")
        refreshed = self.review(answer="Changed answer")
        self.assertFalse(self.confirm(refreshed, use_alias=True)["stored"])

    def test_existing_alias_never_retargeted_or_overwrites_direct_answer(self):
        self.seed()
        self.assertTrue(self.confirm(use_alias=True)["stored"])
        self.seed(question=ALIAS, answer="Separate answer")
        self.assertIsNone(question_alias.lookup(self.service, {**self.body, "label": ALIAS}))
        self.assertEqual(self.lookup()["answer"], "Separate answer")
        self.assertFalse(self.confirm(dict(label=ALIAS, answer=ANSWER, previous_answer="Separate answer",
                              similar_to=QUESTION, similar_scope="company"), use_alias=True)["stored"])
        self.assertEqual(self.lookup()["answer"], "Separate answer")

    def test_server_blocks_sensitive_stored_answers_options_and_aliases(self):
        labels = ["Authorized to work?", "Need sponsorship?", "Veteran status", "Disability status",
                  "Gender", "Race or ethnicity", "Password", "Signature", "I attest this is true", "SSN"]
        for label in labels:
            with self.subTest(label=label):
                self.seed(question=label)
                self.assertEqual(self.lookup(label)["status"], "none")
                self.assertEqual(self.review(label=label)["status"], "skipped")
                self.assertFalse(question_alias.similarity(label, "Please " + label))
                with self.assertRaises(ValueError):
                    self.service.accept({**self.body, "label": label, "answer": ANSWER})
        self.seed()
        self.assertTrue(self.confirm(use_alias=True)["stored"])
        self.assertEqual(self.lookup(options=["Female", "Male"])["status"], "none")
        self.draft.assert_not_called()

    def test_alias_controls_validated_before_any_write(self):
        self.seed()
        for pair in ({"use_alias": "true"}, {"similar_to": []}, {"similar_scope": "elsewhere"}):
            with self.subTest(pair=pair), self.assertRaises(ValueError):
                self.review(**pair)
        self.assertFalse((self.directory / question_alias.FILENAME).exists())

    def test_accept_requires_previous_value_for_replacements(self):
        self.seed()
        body = {**self.body, "label": QUESTION, "answer": "Reviewed replacement"}
        with self.assertRaises(ValueError):
            self.service.accept(body)
        with self.assertRaises(ValueError):
            self.service.accept({**body, "previous_answer": "Stale answer"})
        self.assertEqual(self.lookup(QUESTION)["answer"], ANSWER)
        self.service.accept({**body, "previous_answer": ANSWER})
        self.assertEqual(self.lookup(QUESTION)["answer"], "Reviewed replacement")

    def test_cli_lists_removes_and_rejects_invalid_scope(self):
        self.seed()
        self.confirm(use_alias=True)
        command = [sys.executable, "-B", str(HERE / "question_alias.py"), "--data", str(self.service.data)]
        listing = subprocess.run([*command, "list"], capture_output=True, text=True, timeout=10)
        self.assertEqual(listing.returncode, 0, listing.stderr)
        rows = json.loads(listing.stdout)
        self.assertEqual(rows[0]["label"], ALIAS)
        self.assertNotIn(ANSWER, listing.stdout)
        removed = subprocess.run([*command, "--scope", self.directory.name, "remove", ALIAS],
                                 capture_output=True, text=True, timeout=10)
        self.assertEqual(removed.returncode, 0, removed.stderr)
        self.assertEqual(self.lookup()["status"], "none")
        invalid = subprocess.run([*command, "--scope", "../reference", "list"],
                                 capture_output=True, text=True, timeout=10)
        self.assertNotEqual(invalid.returncode, 0)

    @unittest.skipUnless(NODE, "Node.js is required for browser-free alias checks.")
    def test_alias_checkbox_and_worker(self):
        result = subprocess.run([NODE, str(HERE / "tests" / "assist_alias_harness.js")],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Assist alias checks passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
