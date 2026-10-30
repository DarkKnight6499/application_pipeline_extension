"""Author: Yazad Madan. Synthetic track, template, CLI, and assist boundary checks."""
import contextlib
import http.client
import io
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

# Config
HERE = Path(__file__).resolve().parents[1]
TITLES = {
    "alm": "Asset Liability Management Analyst",
    "capital": "Capital Risk and Basel III Analyst",
    "fpa": "FP&A Analyst",
    "model_risk": "Model Validation Analyst",
    "quant": "Quantitative Research Analyst",
    "treasury_ops": "Treasury Operations Analyst",
}
LABELS = {
    "motivation": "Why are you interested in this role/company?",
    "about_yourself": "Tell us about yourself",
    "good_fit": "What makes you a good fit?",
}
COMPANY = "Example Company"
TEMPLATE = "Example approved text for {role} at {company}."
TOKEN = "synthetic-token"
ORIGIN = "chrome-extension://" + "a" * 32
sys.path.insert(0, str(HERE))

import answer_memory
import assist_api
import essay_templates_cli
import essay_tracks
from server import make_server


class EssayTrackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        self.service = assist_api.AssistService(self.data, self.root / "reference", token=TOKEN)
        self.draft = patch.object(self.service, "draft", return_value="Example fallback.").start()
        self.addCleanup(patch.stopall)

    def payload(self, family="alm", kind="motivation", **extra):
        return {"label": LABELS[kind], "type": "textarea", "options": [], "company_hint": COMPANY,
                "job_title": TITLES[family], "url": "https://example.myworkdayjobs.com/apply", **extra}

    def save(self, family="alm", kind="motivation", text=TEMPLATE):
        essay_tracks.update_template(self.data, family, kind, text, approved=True)

    def test_each_family_and_question_kind(self):
        for family, title in TITLES.items():
            with self.subTest(family=family):
                self.assertEqual(essay_tracks.classify_job(title), family)
                self.assertEqual(essay_tracks.classify_job("Analyst", title), family)
                for kind, label in LABELS.items():
                    self.assertEqual(essay_tracks.question_kind(label), kind)
                    self.save(family, kind)
                    result = self.service.answer(self.payload(family, kind))
                    self.assertEqual((result["status"], result["source"], result["family"], result["kind"]),
                                     ("draft", "essay_templates", family, kind))
                    self.assertEqual(result["answer"], TEMPLATE.format(company=COMPANY, role=title))
                    self.assertEqual(result["candidates"], [result["answer"]])
        self.draft.assert_not_called()
        self.assertEqual(answer_memory.load_memory(self.data)["answers"], {})

    def test_ambiguous_and_generic_titles_have_no_family(self):
        for title in ("Analyst", "Treasury Analyst", "Risk Analyst", "Capital Markets Analyst",
                      "ALM and Capital Risk Analyst", "Quantitative Research and Model Risk Analyst"):
            with self.subTest(title=title):
                self.assertIsNone(essay_tracks.classify_job(title))
        self.assertIsNone(essay_tracks.classify_job("ALM Analyst", "Model Risk Analyst"))
        self.assertIsNone(essay_tracks.classify_job(url="https://capital.example/apply?role=ALM"))
        self.assertEqual(essay_tracks.classify_job(url="https://example.test/jobs/treasury-operations-analyst"),
                         "treasury_ops")
        self.assertIsNone(essay_tracks.question_kind("Tell us about yourself and why you want to join"))

    def test_only_company_and_role_fill_once(self):
        self.assertEqual(essay_tracks.render_template("{role} at {company}", "Example {role}", "ALM Analyst"),
                         "ALM Analyst at Example {role}")
        self.assertIsNone(essay_tracks.render_template(TEMPLATE, "", "ALM Analyst"))
        self.assertIsNone(essay_tracks.render_template(TEMPLATE, COMPANY, ""))
        for text in ("{experience}", "{company.name}", "{role[0]}", "{company!r}", "{role:>10}", "{", "{}"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                essay_tracks.validate_template(text)

    def test_context_template_and_render_caps(self):
        self.save()
        self.service.answer(self.payload(job_title="x" * essay_tracks.MAX_JOB_TITLE,
                                         page_snippet="x" * essay_tracks.MAX_PAGE_SNIPPET))
        for key, limit in ((essay_tracks.TITLE_KEY, essay_tracks.MAX_JOB_TITLE),
                           (essay_tracks.SNIPPET_KEY, essay_tracks.MAX_PAGE_SNIPPET)):
            for value in ("x" * (limit + 1), None, [], 5):
                with self.subTest(key=key, value=type(value)), self.assertRaises(ValueError):
                    self.service.answer(self.payload(**{key: value}))
        essay_tracks.validate_template("x" * answer_memory.MAX_ANSWER)
        with self.assertRaises(ValueError):
            self.save(text="x" * (answer_memory.MAX_ANSWER + 1))
        self.assertIsNone(essay_tracks.render_template("x" * (answer_memory.MAX_ANSWER - 10) + "{company}",
                                                     "x" * 20))

    def test_missing_template_uses_existing_kb_memory_and_draft(self):
        directory = self.service.reference / "company_kb"
        directory.mkdir(parents=True)
        kb = directory / "example_company.json"
        kb.write_text(json.dumps({"questions": [{"text": LABELS["motivation"], "answer": "Example KB."}]}))
        self.assertEqual(self.service.answer(self.payload())["source"], "company_kb")
        kb.unlink()
        self.service.accept({"label": LABELS["motivation"], "answer": "Example memory."})
        self.assertEqual(self.service.answer(self.payload())["answer"], "Example memory.")
        self.assertEqual(self.service.answer(self.payload(kind="about_yourself"))["source"], "claude")
        self.save()
        self.assertEqual(self.service.answer(self.payload())["source"], "essay_templates")

    def test_other_family_kind_and_non_text_fall_back(self):
        self.save()
        for body in (self.payload("quant"), self.payload(kind="good_fit"), self.payload(job_title="Analyst"),
                     self.payload(type="select-one"), self.payload(options=["Example option"]),
                     self.payload(label="Example unrelated question")):
            with self.subTest(body=body):
                self.assertEqual(self.service.answer(body)["answer"], "Example fallback.")

    def test_no_approval_or_invalid_store_never_supplies_template(self):
        with self.assertRaises(ValueError):
            essay_tracks.update_template(self.data, "alm", "motivation", TEMPLATE)
        self.assertFalse((self.data / essay_tracks.TEMPLATE_FILENAME).exists())
        for content in ("bad json", "[]", json.dumps({"schema_version": 99, "templates": {}}),
                        "x" * (essay_tracks.MAX_STORE_BYTES + 1)):
            (self.data / essay_tracks.TEMPLATE_FILENAME).write_text(content)
            self.assertEqual(self.service.answer(self.payload())["answer"], "Example fallback.")
        (self.data / essay_tracks.TEMPLATE_FILENAME).unlink()
        self.save()
        store = essay_tracks.load_templates(self.data)
        row = store[essay_tracks.TEMPLATES_KEY]["alm"]["motivation"]
        for updates in ({"approved": False}, {"approved": "true"}, {"text": "{experience}"}, {"text": None}):
            original = dict(row)
            row.update(updates)
            (self.data / essay_tracks.TEMPLATE_FILENAME).write_text(json.dumps(store))
            self.assertEqual(self.service.answer(self.payload())["answer"], "Example fallback.")
            row.clear()
            row.update(original)

    def test_blocked_labels_options_and_protected_types_never_use_templates(self):
        self.save()
        labels = ["Why are you interested in this role? Explain work eligibility.",
                  "Tell us about yourself and sponsorship now or in the future",
                  "Tell us about yourself: gender, race, veteran status and disability",
                  "What makes you a good fit? Include salary expectations",
                  "Why are you interested? I certify this is true", "Why are you interested? Criminal history"]
        for body in ([self.payload(label=label) for label in labels] +
                     [self.payload(options=["Male", "Female"]), self.payload(type="password"),
                      self.payload(protected=True)]):
            with self.subTest(body=body):
                self.assertEqual(self.service.answer(body)["status"], "none")
        self.draft.assert_not_called()

    def test_cli_add_list_replace_remove_and_persistence(self):
        prefix = ["--data", str(self.data)]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                essay_templates_cli.main(prefix + ["add", "alm", "motivation", "--text", TEMPLATE])
            essay_templates_cli.main(prefix + ["add", "alm", "motivation", "--text", TEMPLATE, "--approved"])
            essay_templates_cli.main(prefix + ["add", "quant", "good_fit", "--text", "Example quant.", "--approved"])
        with contextlib.redirect_stdout(io.StringIO()) as output:
            essay_templates_cli.main(prefix + ["list", "alm"])
        self.assertEqual(json.loads(output.getvalue())["alm"]["motivation"]["text"], TEMPLATE)
        text_file = self.root / "template.txt"
        text_file.write_text("Example replacement.", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            essay_templates_cli.main(prefix + ["add", "alm", "motivation", "--text-file", str(text_file), "--approved"])
        other = assist_api.AssistService(self.data, self.service.reference, token=TOKEN)
        self.assertEqual(other.answer(self.payload())["answer"], "Example replacement.")
        with contextlib.redirect_stdout(io.StringIO()):
            essay_templates_cli.main(prefix + ["remove", "alm", "motivation"])
        store = essay_tracks.load_templates(self.data)
        self.assertEqual(store[essay_tracks.AUTHOR_KEY], "Yazad Madan")
        self.assertNotIn("alm", store[essay_tracks.TEMPLATES_KEY])
        self.assertIn("quant", store[essay_tracks.TEMPLATES_KEY])

    def test_http_essay_and_context_rejection(self):
        self.save()
        server = make_server(None, 0, assist=self.service)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)
        for snippet, status in (("ALM Analyst", 200), ("x" * (essay_tracks.MAX_PAGE_SNIPPET + 1), 400)):
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            self.addCleanup(connection.close)
            connection.request("POST", "/assist/answer", json.dumps(self.payload(page_snippet=snippet)),
                               {"Origin": ORIGIN, "X-Assist-Token": TOKEN, "Content-Type": "application/json"})
            response = connection.getresponse()
            self.assertEqual(response.status, status)
            result = json.loads(response.read())
            if status == 200:
                self.assertEqual((result["status"], result["source"]), ("draft", "essay_templates"))
        self.draft.assert_not_called()


if __name__ == "__main__":
    unittest.main()
