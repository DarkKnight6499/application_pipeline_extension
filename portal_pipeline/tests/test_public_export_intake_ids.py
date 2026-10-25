"""Structural DOM identifiers must not be mistaken for secrets by export intake."""
import sys
import unittest

from browser_test_support import HERE

sys.path.insert(0, str(HERE))
import export_intake
from test_public_export_intake import export, field

STRUCTURAL_IDS = [
    "workExperience-23--startDate-dateSectionMonth-input",
    "workExperience-1--jobTitle-input-field-name",
    "educationSection-12--fieldOfStudy-searchBox-input",
    "formField-countryPhoneCode-selectedItemList-9",
    "input_workExperienceDescriptionText_5_textarea",
]
SECRETS = [
    "aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY",
    "aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY-zT4",
    "sk_" + "live_aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY",
    "workExperience-23-aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1x",
    "0123456789abcdef0123456789abcdef",
    "workExperience-1234567--startDate-dateSection",
]


def with_id(value):
    item = field("Synthetic id")
    item["structure"]["dom_id"] = value
    return export([item])


class StructuralIdTests(unittest.TestCase):
    def test_structural_ids_are_not_errors(self):
        for value in STRUCTURAL_IDS:
            with self.subTest(value=value):
                self.assertEqual(export_intake.validate(with_id(value))["errors"], [])

    def test_secret_like_strings_stay_errors(self):
        for value in SECRETS:
            with self.subTest(value=value):
                self.assertTrue(any("token" in e for e in export_intake.validate(with_id(value))["errors"]))

    def test_exemption_applies_only_to_structural_keys(self):
        item = field(STRUCTURAL_IDS[0])
        self.assertTrue(any("token" in e for e in export_intake.validate(export([item]))["errors"]))

    def test_structural_ids_stay_visible_as_warnings(self):
        result = export_intake.validate(with_id(STRUCTURAL_IDS[0]))
        self.assertTrue(any("long identifier" in w for w in result["warnings"]))


class LocalDraftTests(unittest.TestCase):
    def run_draft(self, out_dir, *extra):
        import json, tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "01.json"
            source.write_text(json.dumps(with_id(SECRETS[0])), encoding="utf-8")
            return export_intake.main(["draft", str(source), "--portal", "synthetic", "--out-dir", str(out_dir), *extra])

    def test_local_flag_is_refused_outside_data_folder(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.run_draft(tmp, "--local"), 1)

    def test_local_flag_allows_flagged_export_under_data_folder(self):
        import shutil
        out = export_intake.IGNORED_DIRS[0] / "intake" / "_local_flag_test"
        try:
            self.assertEqual(self.run_draft(out, "--local"), 0)
        finally:
            shutil.rmtree(out, ignore_errors=True)

    def test_default_still_refuses_flagged_export(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.run_draft(tmp), 1)


if __name__ == "__main__":
    unittest.main()
