"""Question reader on a fabricated posting response only. No network code exists or is exercised."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

from browser_test_support import HERE, SyntheticBrowserTest

sys.path.insert(0, str(HERE))
import export_intake
import question_reader

RESPONSE = {
    "id": 1, "title": "Synthetic Role",
    "questions": [
        {"label": "First Name", "required": True, "fields": [{"name": "first_name", "type": "input_text", "values": []}]},
        {"label": "Resume/CV", "required": True, "fields": [{"name": "resume", "type": "input_file", "values": []},
                                                              {"name": "resume_text", "type": "textarea", "values": []}]},
        {"label": "Are you legally authorized to work in the country in which you are applying?", "required": True,
         "fields": [{"name": "question_1", "type": "multi_value_single_select",
                     "values": [{"label": "Yes", "value": 1}, {"label": "No", "value": 0}]}]},
        {"label": "Which tools do you use?", "required": False,
         "fields": [{"name": "question_2", "type": "multi_value_multi_select", "values": [{"label": "A", "value": 1}, {"label": "B", "value": 2}]}]},
        {"label": "<b>Why us?</b> <script>x</script>", "required": False, "fields": [{"name": "question_3", "type": "textarea", "values": []}]},
        {"label": "Weird", "required": False, "fields": [{"name": "question_4", "type": "input_hidden", "values": []},
                                                         {"name": "question_5", "type": "something_new", "values": []}]},
    ],
    "location_questions": [{"label": "Location", "required": False, "fields": [{"name": "location", "type": "input_text", "values": []}]}],
    "compliance": [{"type": "eeoc", "questions": [{"label": "Gender", "fields": []}, {"label": "Race", "fields": []}]}],
    "demographic_questions": {"questions": [{"label": "Veteran status", "fields": []}], "header": "Optional"},
}


class QuestionReaderTests(unittest.TestCase):
    def test_maps_types_required_and_options(self):
        report = question_reader.read_questions(RESPONSE, "greenhouse")
        rows = [(f["label"], f["type"], f["required"], f["option_count"]) for f in report["fields"]]
        self.assertIn(("First Name", "text", True, 0), rows)
        self.assertIn(("Resume/CV", "file", True, 0), rows)
        self.assertIn(("Resume/CV", "textarea", True, 0), rows)
        self.assertIn(("Are you legally authorized to work in the country in which you are applying?", "select-one", True, 2), rows)
        self.assertIn(("Location", "text", False, 0), rows)

    def test_html_is_stripped_and_hidden_fields_skipped(self):
        report = question_reader.read_questions(RESPONSE, "greenhouse")
        labels = [f["label"] for f in report["fields"]]
        self.assertIn("Why us? x", labels)
        self.assertFalse(any("<" in label for label in labels))
        self.assertNotIn("question_4", [f["structure"]["name"] for f in report["fields"]])

    def test_multi_select_and_unknown_types_need_manual_review(self):
        report = question_reader.read_questions(RESPONSE, "greenhouse")
        by_name = {f["structure"]["name"]: f for f in report["fields"]}
        self.assertTrue(by_name["question_2"]["manual_reason"])
        self.assertIn("Unrecognized", by_name["question_5"]["manual_reason"])
        self.assertEqual(by_name["question_5"]["type"], "text")

    def test_demographic_and_compliance_are_counted_never_listed(self):
        report = question_reader.read_questions(RESPONSE, "greenhouse")
        text = json.dumps(report)
        for hidden in ("Gender", "Race", "Veteran"):
            self.assertNotIn(hidden, text)
        self.assertGreaterEqual(report["protected_fields_omitted"], 2)

    def test_report_passes_export_validation_and_marks_non_dom_source(self):
        report = question_reader.read_questions(RESPONSE, "greenhouse")
        self.assertEqual(export_intake.validate(report)["errors"], [])
        self.assertIn("posting_api_not_live_dom", report["coverage"]["reason_codes"])
        self.assertEqual(report["coverage"]["scope"], "posting_api_response")

    def test_bad_input_is_rejected_or_ignored(self):
        with self.assertRaises(ValueError):
            question_reader.read_questions(RESPONSE, "lever")
        with self.assertRaises(ValueError):
            question_reader.read_questions([], "greenhouse")
        report = question_reader.read_questions({"questions": "nope", "location_questions": [1, {"label": "x"}]}, "greenhouse")
        self.assertEqual(report["fields"], [])
        self.assertTrue(report["portal_manual_reason"])

    def test_limits(self):
        many = {"questions": [{"label": f"Q{i}", "required": False, "fields": [{"name": f"q{i}", "type": "input_text"}]} for i in range(400)]}
        report = question_reader.read_questions(many, "greenhouse")
        self.assertEqual(len(report["fields"]), question_reader.MAX_QUESTIONS)
        long_label = question_reader.read_questions({"questions": [{"label": "x" * 500, "fields": [{"name": "a", "type": "input_text"}]}]}, "greenhouse")
        self.assertEqual(len(long_label["fields"][0]["label"]), question_reader.MAX_LABEL)

    def test_cli_and_no_network_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, out = Path(tmp) / "response.json", Path(tmp) / "report.json"
            source.write_text(json.dumps(RESPONSE), encoding="utf-8")
            self.assertEqual(question_reader.main([str(source), "--portal", "greenhouse", "--out", str(out)]), 0)
            self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["schema_version"], 1)
            self.assertEqual(question_reader.main([str(Path(tmp) / "missing.json"), "--portal", "greenhouse"]), 1)
        source_text = (HERE / "question_reader.py").read_text(encoding="utf-8")
        for forbidden in ("import urllib", "import requests", "import http", "import socket", "urlopen", "import aiohttp"):
            self.assertNotIn(forbidden, source_text)


class QuestionReaderRoundTripTests(SyntheticBrowserTest):
    def test_report_drafts_a_fixture_that_scans_back(self):
        report = question_reader.read_questions(RESPONSE, "greenhouse")
        report["fields"] = [f for f in report["fields"] if f["type"] in ("text", "textarea", "select-one", "file")]
        self.open_markup(export_intake.draft_fixture(report))
        fields = [f for f in self.page.evaluate("PortalEngine.inspect().fields") if not f["structure"]["dom_id"].startswith("guard-")]
        self.assertEqual([f["type"] for f in fields], [f["type"] for f in report["fields"]])


if __name__ == "__main__":
    unittest.main()
