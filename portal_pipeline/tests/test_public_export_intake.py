"""Export intake tool on fabricated exports only."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

from browser_test_support import HERE, SyntheticBrowserTest

sys.path.insert(0, str(HERE))
import export_intake


def field(label, kind="text", **extra):
    base = {"label": label, "type": kind, "required": False, "disabled": False, "section": "unknown", "adapter": None,
            "record": None, "manual_reason": "", "option_count": 0, "dropdown_state": None,
            "structure": {"tag": "input", "name": "", "automation_id": "", "dom_id": "", "role": "", "controls": "", "popup": "", "maxlength": None}}
    base.update(extra)
    return base


def export(fields, **extra):
    report = {"schema_version": 1, "host": "portal.example.invalid", "inspected_at": "2026-10-11T04:57:00.000Z", "portal": "generic",
              "portal_manual_reason": "", "protected_fields_omitted": 1,
              "coverage": {"scope": "visible_light_dom_current_page", "visible_iframes": 0, "visible_open_shadow_hosts": 0,
                           "unsupported_spinbuttons": 0, "reason_codes": []}, "fields": fields}
    report.update(extra)
    return report


FIELDS = [field("Synthetic name", required=True), field("Synthetic notes", "textarea"),
          field("Synthetic choice", "select-one", option_count=3), field("Synthetic group", "radio", option_count=2),
          field("Synthetic agree", "checkbox"), field("Synthetic resume", "file"),
          field("Synthetic relocate", "combobox", adapter="aria-listbox", option_count=2)]


class ExportIntakeTests(unittest.TestCase):
    def test_clean_export_passes(self):
        self.assertEqual(export_intake.validate(export(FIELDS)), {"errors": [], "warnings": []})

    def test_forbidden_keys_and_values_are_errors(self):
        bad = export(FIELDS)
        bad["fields"][0]["value"] = "Entered"
        bad["fields"][1]["proposal"] = "x"
        errors = " ".join(export_intake.validate(bad)["errors"])
        self.assertIn("forbidden key 'value'", errors)
        self.assertIn("forbidden key 'proposal'", errors)

    def test_personal_data_and_secrets_are_errors(self):
        cases = {"email": "someone@example.invalid", "phone": "+1 (555) 010-0199", "token": "aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY",
                 "hex": "0123456789abcdef0123456789abcdef", "url": "https://portal.example.invalid/x?id=1"}
        for name, text in cases.items():
            with self.subTest(name=name):
                bad = export([field(text)])
                self.assertTrue(export_intake.validate(bad)["errors"], name)

    def test_ordinary_labels_and_ids_are_not_errors(self):
        good = export([field("Are you legally authorized to work in the United States?"),
                       field("Employment history job title", structure={"tag": "input", "name": "workExperience-1--jobTitle", "automation_id": "formField-jobTitle",
                                                                       "dom_id": "workExperience-1--jobTitle", "role": "", "controls": "", "popup": "", "maxlength": 80})])
        self.assertEqual(export_intake.validate(good)["errors"], [])

    def test_schema_problems(self):
        self.assertTrue(export_intake.validate([])["errors"])
        self.assertTrue(export_intake.validate({"schema_version": 2, "host": "h", "fields": []})["errors"])
        self.assertTrue(export_intake.validate({"schema_version": 1, "fields": []})["errors"])
        warn = export_intake.validate(export(FIELDS, surprise=1))["warnings"]
        self.assertTrue(any("surprise" in w for w in warn))

    def test_frame_reports_are_validated_too(self):
        frame = export([field("Frame email someone@example.invalid")], frame_id=3)
        result = export_intake.validate(export(FIELDS, frame_reports=[frame]))
        self.assertTrue(result["errors"])

    def test_contract_draft_marks_unknowns(self):
        text = export_intake.draft_contract([export(FIELDS, frame_reports=[export([field("In frame")], frame_id=2)])], "Example ATS")
        self.assertIn("(DRAFT)", text)
        self.assertIn("UNVERIFIED", text)
        self.assertIn("| page 1 top | UNVERIFIED | 7 | 1 | 1 |", text)
        self.assertIn("frame 2", text)
        self.assertIn("answer_sheet_only", text)
        self.assertNotIn("someone@", text)

    def test_cli_validate_and_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            good, bad = tmp / "01.json", tmp / "02.json"
            good.write_text(json.dumps(export(FIELDS)), encoding="utf-8")
            leaked = copy.deepcopy(export(FIELDS)); leaked["fields"][0]["value"] = "x"
            bad.write_text(json.dumps(leaked), encoding="utf-8")
            self.assertEqual(export_intake.main(["validate", str(good)]), 0)
            self.assertEqual(export_intake.main(["validate", str(bad)]), 1)
            out = tmp / "out"
            self.assertEqual(export_intake.main(["draft", str(good), str(bad), "--portal", "Example", "--out-dir", str(out)]), 1)
            self.assertFalse(out.exists())
            self.assertEqual(export_intake.main(["draft", str(good), "--portal", "Example ATS", "--out-dir", str(out)]), 0)
            self.assertTrue((out / "EXAMPLE_ATS_CONTRACT_DRAFT.md").exists())
            self.assertTrue((out / "example_ats_page_1.html").exists())

    def test_fixture_uses_neutral_labels_by_default(self):
        page = export_intake.draft_fixture(export([field("Employer Specific Label")]))
        self.assertNotIn("Employer Specific", page)
        self.assertIn("Employer Specific", export_intake.draft_fixture(export([field("Employer Specific Label")]), keep_labels=True))
        self.assertNotIn("password", export_intake.draft_fixture(export([field("Pw", "password")])).replace('type="text"', ""))


class ExportIntakeRoundTripTests(SyntheticBrowserTest):
    def test_generated_fixture_scans_back_to_the_same_shape(self):
        self.open_markup(export_intake.draft_fixture(export(FIELDS)))
        fields = [f for f in self.page.evaluate("PortalEngine.inspect().fields") if not f["structure"]["dom_id"].startswith("guard-")]
        self.assertEqual([f["type"] for f in fields], ["text", "textarea", "select-one", "radio", "checkbox", "file", "combobox"])
        self.assertEqual(fields[0]["required"], True)
        self.assertEqual(fields[2]["option_count"], 4)


if __name__ == "__main__":
    unittest.main()
