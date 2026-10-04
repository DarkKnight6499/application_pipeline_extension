"""Unknown eligibility stays pending using a wholly fabricated source."""
import shutil
import json
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
ADDITIONAL_UNKNOWN_VALUES = ["Not specified", "Not provided", "Not yet confirmed", "To be determined", "Not sure", "[VERIFY]", "[TAILOR]"]
MASTER_FILENAME = "Resume_Content_Master.json"
BOILER_FILENAME = "Application_Boilerplate.md"
CONTACT_KEYS = {"email", "phone", "location", "city"}
INVALID_CONTACTS = ["candidate@example.invalid | 555-0100", "candidate@example.invalid / 555-0100 / Example City", "555-0100 | candidate@example.invalid | Example City, ZZ", "candidate@example.invalid | 555-0100 | other@example.invalid", "candidate@example.invalid | 555-0100 | Example City | Extra", "candidate@example.invalid | | Example City", " | | "]

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

    def write_master(self, mutate):
        path = self.reference / MASTER_FILENAME
        master = json.loads(path.read_text(encoding="utf-8"))
        mutate(master)
        path.write_text(json.dumps(master), encoding="utf-8")

    def test_blank_answer_does_not_consume_next_label(self):
        (self.reference / BOILER_FILENAME).write_text("- Start date:\n- Source: Company website\n", encoding="utf-8")
        values = resolve_profile(self.root)["values"]
        self.assertNotIn("available_from", values)
        self.assertEqual(values["job_source"]["value"], "Company website")

    def test_conflicting_duplicates_remain_pending(self):
        for answers in [("Yes", "No"), ("No", "Yes"), ("Yes", "Unknown"), ("Yes", "")]:
            with self.subTest(answers=answers):
                boiler = "\n".join(f"- Require sponsorship now: {answer}" for answer in answers)
                (self.reference / BOILER_FILENAME).write_text(boiler, encoding="utf-8")
                self.assertNotIn("sponsorship_now", resolve_profile(self.root)["values"])

    def test_identical_duplicates_preserve_confirmed_answer(self):
        (self.reference / BOILER_FILENAME).write_text("- Require sponsorship now: No\n- Require sponsorship now: **No**\n", encoding="utf-8")
        self.assertEqual(resolve_profile(self.root)["values"]["sponsorship_now"]["value"], "No")

    def test_invalid_contact_is_not_misrouted(self):
        for contact in INVALID_CONTACTS:
            with self.subTest(contact=contact):
                self.write_master(lambda master: master["header"].update(contact=contact))
                values = resolve_profile(self.root)["values"]
                self.assertNotIn("email", values)
                self.assertNotIn("phone", values)
                if "other@example.invalid" in contact:
                    self.assertNotIn("location", values)

    def test_unknown_phrases_remain_pending(self):
        for value in ADDITIONAL_UNKNOWN_VALUES:
            with self.subTest(value=value):
                (self.reference / BOILER_FILENAME).write_text(f"- Start date: {value}\n", encoding="utf-8")
                self.assertNotIn("available_from", resolve_profile(self.root)["values"])

    def test_unknown_master_facts_remain_pending(self):
        self.write_master(lambda master: master["header"].update(name="[CONFIRM]", contact="Unknown | Pending | TBD", linkedin="[VERIFY]", github="[TAILOR]"))
        values = resolve_profile(self.root)["values"]
        for key in CONTACT_KEYS | {"first_name", "last_name", "full_name", "linkedin", "github"}:
            self.assertNotIn(key, values)

    def test_missing_name_stays_pending(self):
        self.write_master(lambda master: master["header"].update(name=""))
        values = resolve_profile(self.root)["values"]
        self.assertNotIn("first_name", values)
        self.assertEqual(values["email"]["value"], "candidate@example.invalid")

    def test_mixed_unknown_name_keeps_all_components_pending(self):
        for name in ("[CONFIRM] Jane", "Unknown Person"):
            with self.subTest(name=name):
                self.write_master(lambda master: master["header"].update(name=name))
                values = resolve_profile(self.root)["values"]
                for key in ("first_name", "last_name", "full_name"):
                    self.assertNotIn(key, values)

    def test_unknown_history_facts_remain_pending(self):
        self.write_master(lambda master: master.update(
            experience=[{"company": "[CONFIRM]", "location": "Not specified", "dateRange": "Unknown", "roles": [{"title": "[TAILOR]"}]}],
            education=[{"school": "Pending", "degree": "[VERIFY]", "location": "TBD", "date": "Unknown"}]))
        values = resolve_profile(self.root)["values"]
        self.assertFalse(any(key.startswith(("employment.", "education.")) for key in values))

    def test_reversed_chronology_remains_pending(self):
        self.write_master(lambda master: master.update(experience=[{"company": "Synthetic Company", "location": "Example City", "dateRange": "January 2026 to December 2025", "roles": [{"title": "Synthetic Role"}]}]))
        values = resolve_profile(self.root)["values"]
        self.assertNotIn("employment.0.start_date", values)
        self.assertNotIn("employment.0.end_date", values)

    def test_confirmed_history_dates_and_contact_preserved(self):
        self.write_master(lambda master: master.update(
            experience=[{"company": "Synthetic Company", "location": "Example City", "dateRange": "January 2020 to February 2021", "roles": [{"title": "Synthetic Role"}]}],
            education=[{"school": "Synthetic School", "degree": "Synthetic Degree", "location": "Example City", "date": "May 2022"}]))
        values = resolve_profile(self.root)["values"]
        self.assertEqual(values["employment.0.start_date"]["value"], "2020-01")
        self.assertEqual(values["employment.0.end_date"]["value"], "2021-02")
        self.assertEqual(values["education.0.end_date"]["value"], "2022-05")
        self.assertNotIn("education.0.start_date", values)
        self.assertEqual(values["phone"]["value"], "555-0100")
        self.assertEqual(values["location"]["value"], "Example City, ZZ")
        self.assertEqual(values["city"]["value"], "Example City")


if __name__ == "__main__":
    unittest.main()
