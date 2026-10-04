"""Integration tests use temporary output folders and never write real trackers."""
import copy
import hashlib
import http.client
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from portal_profile import hard_fact_errors, resolve_profile
from server import Pipeline, make_server

from test_support import INTEGRATION_SKIP_REASON, workflow_source
SOURCE = workflow_source()


@unittest.skipIf(SOURCE is None, INTEGRATION_SKIP_REASON)
class BackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protected = [SOURCE / file for file in ["Applications.xlsx", "_Reference/Status_History.json",
                         "_Reference/Resume_Content_Master.json", "_Reference/Application_Boilerplate.md",
                         "_Reference/build_resume.js", "_Reference/Project_Backlog.json"]]
        cls.hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in cls.protected}
        cls.master = json.loads((SOURCE / "_Reference/Resume_Content_Master.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        for path, expected in cls.hashes.items():
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise AssertionError(f"A protected source file changed: {path.name}")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.pipeline = Pipeline(SOURCE, Path(self.temp.name))
        self.server = make_server(self.pipeline, 0, "test-pairing-token")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, method, path, body=None, headers=None):
        client = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        raw = json.dumps(body) if body is not None else None
        supplied = {"X-Portal-Token": "test-pairing-token", "Content-Type": "application/json"}
        supplied.update(headers or {})
        client.request(method, path, body=raw, headers=supplied)
        response = client.getresponse()
        data = response.read()
        content_type = response.getheader("Content-Type")
        status = response.status
        client.close()
        return status, json.loads(data) if "application/json" in content_type else data

    def session(self):
        return self.pipeline.create({"company": "Synthetic Employer", "role": "Treasury Analyst",
            "jd": "Treasury analyst: Python, SQL and ALM. Finance education preferred.",
            "template": "Resume_Draft_ALM_Treasury_Liquidity.json", "url": "http://127.0.0.1/fixture"})

    def build_body(self, session):
        return {"content": session["content"], "resume_terms": ["Python", "SQL"], "eligibility": [],
                "requirements_reviewed": True, "content_reviewed": True}

    def test_api_requires_pairing_token(self):
        status, value = self.request("GET", "/api/profile", headers={"X-Portal-Token": "wrong"})
        self.assertEqual(status, 401)
        self.assertNotIn("values", value)

    def test_foreign_origin_and_host_are_rejected(self):
        self.assertEqual(self.request("GET", "/api/profile", headers={"Origin": "https://evil.example"})[0], 403)
        self.assertEqual(self.request("GET", "/", headers={"Host": "evil.example"})[0], 403)

    def test_extension_origin_can_pair(self):
        self.assertEqual(self.request("GET", "/api/profile", headers={"Origin": "chrome-extension://" + "a" * 32})[0], 200)

    def test_profile_has_separate_sponsorship_and_nonoverlapping_dates(self):
        profile = resolve_profile(SOURCE)["values"]
        self.assertEqual(profile["sponsorship_now"]["value"], "No")
        self.assertEqual(profile["sponsorship_future"]["value"], "Yes")
        self.assertEqual(profile["employment.2.start_date"]["value"], "2023-08")
        self.assertEqual(profile["employment.3.end_date"]["value"], "2023-08")
        self.assertEqual(profile["employment.4.end_date"]["value"], "2022-05")
        self.assertNotIn("gender", profile)
        self.assertNotIn("street", profile)

    def test_hard_fact_drift_is_rejected(self):
        changed = copy.deepcopy(self.master)
        changed["education"][0]["date"] = "December 2025"
        changed["experience"][0]["dateRange"] = "May 2025 to August 2026"
        self.assertEqual(len(hard_fact_errors(changed, self.master)), 2)

    def test_template_traversal_and_empty_jd_are_rejected(self):
        for body in [{"company": "Test", "role": "Test", "jd": "JD", "template": "../secret.json"},
                     {"company": "Test", "role": "Test", "jd": ""}]:
            self.assertEqual(self.request("POST", "/api/sessions", body)[0], 400)

    def test_sessions_do_not_allocate_real_application_ids(self):
        session = self.session()
        self.assertIsNone(session["application_id"])
        self.assertEqual(session["state"], "draft")
        self.assertFalse((self.pipeline.data / session["id"] / ".application_id").exists())
        self.assertEqual(self.pipeline.current()["id"], session["id"])

    def test_unbuilt_resume_cannot_be_attached(self):
        session = self.session()
        self.assertEqual(self.request("GET", f"/api/sessions/{session['id']}/attachment")[0], 400)

    def test_sandbox_resume_cannot_attach_to_employer_portal(self):
        session = self.pipeline.create({"company": "Synthetic Employer", "role": "Treasury Analyst", "jd": "Python and SQL",
            "template": "Resume_Draft_ALM_Treasury_Liquidity.json", "url": "https://example.myworkdayjobs.com/job"})
        self.pipeline.build(session["id"], self.build_body(session))
        self.pipeline.approve_upload(session["id"], {"visual_reviewed": True})
        with self.assertRaisesRegex(ValueError, "only to the local fixture"):
            self.pipeline.resume(session["id"], for_upload=True)

    def test_build_download_review_and_checksum(self):
        session = self.session()
        built = self.pipeline.build(session["id"], self.build_body(session))
        self.assertEqual(built["state"], "built", built["checks"])
        from docx import Document
        properties = Document(self.pipeline.folder(session["id"]) / "Yazad_Madan.docx").core_properties
        self.assertEqual(properties.author, "Yazad Madan")
        self.assertEqual(properties.last_modified_by, "Yazad Madan")
        self.assertEqual(self.request("GET", f"/api/sessions/{session['id']}/download")[0], 200)
        self.assertEqual(self.request("GET", f"/api/sessions/{session['id']}/attachment")[0], 400)
        self.pipeline.approve_upload(session["id"], {"visual_reviewed": True})
        self.assertEqual(self.request("GET", f"/api/sessions/{session['id']}/attachment")[0], 200)
        path = self.pipeline.folder(session["id"]) / "Yazad_Madan.docx"
        path.write_bytes(path.read_bytes() + b"changed")
        self.assertEqual(self.request("GET", f"/api/sessions/{session['id']}/attachment")[0], 400)

    def test_rebuild_invalidates_upload_review(self):
        session = self.session()
        self.pipeline.build(session["id"], self.build_body(session))
        self.pipeline.approve_upload(session["id"], {"visual_reviewed": True})
        rebuilt = self.pipeline.build(session["id"], self.build_body(session))
        self.assertFalse(rebuilt["upload_reviewed"])

    def test_skipped_requirement_review_blocks_upload(self):
        session = self.session()
        body = self.build_body(session)
        body["requirements_reviewed"] = False
        built = self.pipeline.build(session["id"], body)
        self.assertEqual(built["state"], "needs_review")
        with self.assertRaises(ValueError):
            self.pipeline.approve_upload(session["id"], {"visual_reviewed": True})

    def test_missing_terms_block_but_honest_eligibility_gap_is_advisory(self):
        session = self.session()
        body = self.build_body(session)
        body["eligibility"] = [{"requirement": "Synthetic experience requirement", "meets": "partial", "severity": "required"}]
        built = self.pipeline.build(session["id"], body)
        self.assertEqual(built["state"], "built")
        self.assertTrue(any("Eligibility partial" in warning for warning in built["checks"]["advisory"]))
        body["resume_terms"] = ["UnclaimedSyntheticSkill"]
        self.assertEqual(self.pipeline.build(session["id"], body)["state"], "needs_review")


if __name__ == "__main__":
    unittest.main()
