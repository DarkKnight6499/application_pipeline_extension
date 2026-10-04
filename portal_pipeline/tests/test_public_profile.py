"""Unknown eligibility stays pending using a wholly fabricated source."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Test configuration
HERE = Path(__file__).resolve().parents[1]
PROFILE_FIXTURE = Path(__file__).resolve().parent / "fixtures/synthetic_profile"
BOOLEAN_LABEL = "Work authorized in US"
UNKNOWN_VALUES = ["[CONFIRM]", "Unknown", "Yes [CONFIRM]", "No (unconfirmed)", "Yes if approved", "TBD", "Yes?", "pending", " "]
UNKNOWN_TEXT_VALUES = ["[CONFIRM]", "Unknown", "Pending confirmation", "TBC"]

sys.path.insert(0, str(HERE))
from portal_profile import resolve_profile


class PublicProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.reference = self.root / "_Reference"
        shutil.copytree(PROFILE_FIXTURE, self.reference)

    def tearDown(self):
        self.temp.cleanup()

    def test_unknown_boolean_answers_are_not_promoted(self):
        for value in UNKNOWN_VALUES:
            with self.subTest(value=value):
                (self.reference / "Application_Boilerplate.md").write_text(f"- {BOOLEAN_LABEL}: {value}\n", encoding="utf-8")
                profile = resolve_profile(self.root)
                self.assertNotIn("authorized_us", profile["values"])

    def test_unknown_text_answers_are_not_promoted(self):
        for value in UNKNOWN_TEXT_VALUES:
            with self.subTest(value=value):
                (self.reference / "Application_Boilerplate.md").write_text(f"- Start date: {value}\n", encoding="utf-8")
                self.assertNotIn("available_from", resolve_profile(self.root)["values"])

    def test_confirmed_answers_and_separate_sponsorship_are_preserved(self):
        values = resolve_profile(self.root)["values"]
        self.assertEqual(values["authorized_us"]["value"], "Yes")
        self.assertEqual(values["sponsorship_now"]["value"], "No")
        self.assertEqual(values["sponsorship_future"]["value"], "Yes")
        self.assertNotIn("relocation", values)
        self.assertNotIn("salary", values)
        self.assertNotIn("available_from", values)
        self.assertEqual(values["email"]["value"], "candidate@example.invalid")


if __name__ == "__main__":
    unittest.main()
