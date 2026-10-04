"""Resolver v2 precedence and per-application overrides, synthetic data only."""
import hashlib
import http.client
import json
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

# Test configuration
HERE = Path(__file__).resolve().parents[1]
PROFILE_FIXTURE = Path(__file__).resolve().parent / "fixtures/synthetic_profile"
MASTER_FILENAME = "Resume_Content_Master.json"
BOILER_FILENAME = "Application_Boilerplate.md"
SESSION_FILENAME = "session.json"
TAILORED_FILENAME = "resume_content.json"
OVERRIDES_FILENAME = "overrides.json"
APPLICATION_ID = 123
SESSION_ID = "a" * 32
PAIRING_TOKEN = "synthetic-test-token"
OVERRIDE_REASON = "Synthetic posting states a range"
EMPLOYERS = [("Synthetic Bank One", "Analyst"), ("Synthetic Bank Two", "Associate")]
BOILER_SECTION_TEXT = ("## Standard Boilerplate Answers\n\n- Work authorized in US: Yes\n"
                       "- Require sponsorship now: No\n- Require sponsorship in future: Yes\n"
                       "- Salary expectation: 100000\n\n## Role Descriptions\n\n")

sys.path.insert(0, str(HERE))
from portal_profile import ELIGIBILITY_KEYS, load_overrides, resolve_for_application, resolve_profile, save_override, source_ref
from server import make_server


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ResolverV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "source"
        self.reference = self.root / "_Reference"
        shutil.copytree(PROFILE_FIXTURE, self.reference)
        self.master_path = self.reference / MASTER_FILENAME
        self.boiler_path = self.reference / BOILER_FILENAME
        master = json.loads(self.master_path.read_text(encoding="utf-8"))
        master["experience"] = [{"company": company, "location": "Example City, ZZ", "dateRange": "January 2020 to March 2021",
                                 "roles": [{"title": title, "bullets": ["Master bullet"]}]} for company, title in EMPLOYERS]
        master["education"] = [{"school": "Synthetic University", "degree": "Synthetic Degree", "location": "Example City, ZZ", "date": "May 2019"}]
        self.master_path.write_text(json.dumps(master), encoding="utf-8")
        descriptions = "".join(f"### {company} \u2014 {title} | x\nSynthetic description for {company}.\n\n---\n\n" for company, title in EMPLOYERS)
        self.boiler_path.write_text(BOILER_SECTION_TEXT + descriptions, encoding="utf-8")
        self.session = Path(self.temp.name) / "session"
        self.session.mkdir()
        (self.session / SESSION_FILENAME).write_text(json.dumps({"id": SESSION_ID, "application_id": APPLICATION_ID}), encoding="utf-8")
        self.write_tailored(EMPLOYERS[:1])

    def tearDown(self):
        self.temp.cleanup()

    def write_tailored(self, employers):
        content = {"experience": [{"company": company, "roles": [{"title": title, "bullets": [f"Tailored bullet for {company}"]}]}
                                  for company, title in employers]}
        (self.session / TAILORED_FILENAME).write_text(json.dumps(content), encoding="utf-8")

    def test_override_wins_for_salary_and_records_reason(self):
        record = save_override(self.session, "salary", "120000", OVERRIDE_REASON)
        self.assertEqual(record["value"], "120000")
        stored = json.loads((self.session / OVERRIDES_FILENAME).read_text(encoding="utf-8"))
        self.assertEqual(stored["schema_version"], 1)
        self.assertEqual(stored["application_id"], APPLICATION_ID)
        entry = stored["overrides"]["salary"]
        self.assertEqual((entry["value"], entry["reason"]), ("120000", OVERRIDE_REASON))
        self.assertTrue(entry["edited_at"])
        self.assertEqual(load_overrides(self.session)["salary"]["value"], "120000")
        resolved = resolve_for_application(self.root, self.session)
        self.assertEqual(resolved["values"]["salary"]["value"], "120000")
        self.assertEqual(resolved["precedence"]["salary"], 1)
        self.assertEqual(resolve_profile(self.root)["values"]["salary"]["value"], "100000")

    def test_override_refused_for_each_eligibility_key(self):
        self.assertEqual(len(ELIGIBILITY_KEYS), 6)
        for key in sorted(ELIGIBILITY_KEYS):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    save_override(self.session, key, "Yes", OVERRIDE_REASON)
                self.assertFalse((self.session / OVERRIDES_FILENAME).exists())

    def test_hand_edited_eligibility_override_is_ignored(self):
        payload = {"schema_version": 1, "application_id": APPLICATION_ID,
                   "overrides": {"sponsorship_now": {"value": "Yes", "reason": "x", "edited_at": "2026-01-01T00:00:00+00:00"}}}
        (self.session / OVERRIDES_FILENAME).write_text(json.dumps(payload), encoding="utf-8")
        resolved = resolve_for_application(self.root, self.session)
        self.assertEqual(resolved["values"]["sponsorship_now"]["value"], "No")

    def test_override_requires_reason_and_value(self):
        for value, reason in (("", OVERRIDE_REASON), ("120000", " ")):
            with self.subTest(value=value, reason=reason):
                with self.assertRaises(ValueError):
                    save_override(self.session, "salary", value, reason)

    def test_override_never_mutates_master_or_boilerplate(self):
        before = (digest(self.master_path), digest(self.boiler_path))
        save_override(self.session, "salary", "120000", OVERRIDE_REASON)
        save_override(self.session, "first_name", "Alias", OVERRIDE_REASON)
        resolve_for_application(self.root, self.session)
        self.assertEqual((digest(self.master_path), digest(self.boiler_path)), before)

    def test_full_history_from_master_even_when_tailored_omits_employer(self):
        values = resolve_for_application(self.root, self.session)["values"]
        for index, (company, title) in enumerate(EMPLOYERS):
            self.assertEqual(values[f"employment.{index}.company"]["value"], company)
            self.assertEqual(values[f"employment.{index}.start_date"]["value"], "2020-01")
        self.assertEqual(values["employment.1.company"]["source"].split("#")[0], MASTER_FILENAME)

    def test_tailored_bullets_only_as_draft_needs_review(self):
        resolved = resolve_for_application(self.root, self.session)
        values = resolved["values"]
        self.assertEqual(values["employment.0.description"]["value"], "Synthetic description for Synthetic Bank One.")
        draft = values["employment.0.description_draft"]
        self.assertIn("Tailored bullet for Synthetic Bank One", draft["value"])
        self.assertEqual(draft["status"], "draft_needs_review")
        self.assertEqual(resolved["precedence"]["employment.0.description_draft"], 5)
        self.assertLess(resolved["precedence"]["employment.0.description"], 5)
        self.assertNotIn("employment.1.description_draft", values)

    def test_draft_is_not_used_as_description_when_boilerplate_lacks_one(self):
        self.boiler_path.write_text(BOILER_SECTION_TEXT, encoding="utf-8")
        values = resolve_for_application(self.root, self.session)["values"]
        self.assertNotIn("employment.0.description", values)
        self.assertEqual(values["employment.0.description_draft"]["status"], "draft_needs_review")

    def test_missing_fact_stays_pending(self):
        resolved = resolve_for_application(self.root, self.session)
        for key in ("street_address", "postal_code", "education.0.start_date"):
            with self.subTest(key=key):
                self.assertNotIn(key, resolved["values"])
                self.assertIn(key, resolved["pending"])

    def test_sponsorship_now_and_future_stay_separate_and_combined_is_derived(self):
        values = resolve_for_application(self.root, self.session)["values"]
        self.assertEqual((values["sponsorship_now"]["value"], values["sponsorship_future"]["value"]), ("No", "Yes"))
        self.assertEqual(values["sponsorship_now_or_future"]["value"], "Yes")
        self.assertTrue(values["sponsorship_now_or_future"]["source"].startswith("Derived"))
        self.assertNotIn("sponsorship", values)

    def test_source_ref_names_file_and_section(self):
        self.assertEqual(source_ref("Application_Boilerplate.md", "Standard Boilerplate Answers", 20),
                         "Application_Boilerplate.md#Standard Boilerplate Answers:L20")
        self.assertEqual(source_ref(MASTER_FILENAME, "header"), MASTER_FILENAME + "#header")
        values = resolve_profile(self.root)["values"]
        file, _, rest = values["sponsorship_now"]["source"].partition("#")
        self.assertEqual(file, BOILER_FILENAME)
        self.assertTrue(rest.startswith("Standard Boilerplate Answers:L"))
        self.assertTrue(values["email"]["source"].startswith(MASTER_FILENAME + "#header"))

    def test_precedence_marks_each_source_tier(self):
        precedence = resolve_for_application(self.root, self.session)["precedence"]
        self.assertEqual(precedence["email"], 2)
        self.assertEqual(precedence["sponsorship_now"], 2)
        self.assertEqual(precedence["employment.0.company"], 3)
        self.assertEqual(precedence["employment.0.description"], 4)


class OverrideRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name) / "source"
        shutil.copytree(PROFILE_FIXTURE, root / "_Reference")
        self.session = Path(self.temp.name) / "session"
        self.session.mkdir()
        (self.session / SESSION_FILENAME).write_text(json.dumps({"id": SESSION_ID, "application_id": APPLICATION_ID}), encoding="utf-8")
        pipeline = SimpleNamespace(source=root, lock=threading.RLock(), current=lambda: None, templates=lambda: [],
                                   folder=lambda session_id: self.session)
        self.server = make_server(pipeline, 0, PAIRING_TOKEN)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, path, method="GET", body=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        data = json.dumps(body) if body is not None else None
        connection.request(method, path, body=data, headers={"X-Portal-Token": PAIRING_TOKEN})
        response = connection.getresponse()
        result = response.status, json.loads(response.read())
        connection.close()
        return result

    def test_override_route_saves_and_profile_route_reflects_it(self):
        status, _ = self.request(f"/api/sessions/{SESSION_ID}/override", "POST", {"key": "salary", "value": "130000", "reason": OVERRIDE_REASON})
        self.assertEqual(status, 200)
        status, profile = self.request(f"/api/sessions/{SESSION_ID}/profile")
        self.assertEqual(status, 200)
        self.assertEqual(profile["values"]["salary"]["value"], "130000")
        self.assertEqual(profile["precedence"]["salary"], 1)

    def test_override_route_refuses_eligibility_key(self):
        status, body = self.request(f"/api/sessions/{SESSION_ID}/override", "POST", {"key": "sponsorship_future", "value": "No", "reason": OVERRIDE_REASON})
        self.assertEqual(status, 400)
        self.assertIn("eligibility", body["error"].lower())
        self.assertFalse((self.session / OVERRIDES_FILENAME).exists())


if __name__ == "__main__":
    unittest.main()
