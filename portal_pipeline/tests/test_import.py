"""Import tests use a synthetic tracker and the original read-only audit code."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from server import Pipeline
from test_support import INTEGRATION_SKIP_REASON, audited_fixture, workflow_source
from openpyxl import load_workbook

SOURCE = workflow_source()


@unittest.skipIf(SOURCE is None, INTEGRATION_SKIP_REASON)
class ImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build_temp = tempfile.TemporaryDirectory()
        pipeline = Pipeline(SOURCE, Path(cls.build_temp.name))
        session = pipeline.create({"company": "Synthetic Employer", "role": "Treasury Analyst", "jd": "Python and SQL",
                                   "template": "Resume_Draft_ALM_Treasury_Liquidity.json"})
        pipeline.build(session["id"], {"content": session["content"], "resume_terms": ["Python"], "eligibility": [],
                                       "requirements_reviewed": True, "content_reviewed": True})
        cls.built_folder = pipeline.folder(session["id"])

    @classmethod
    def tearDownClass(cls):
        cls.build_temp.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source, self.folder = audited_fixture(self.root, self.built_folder, SOURCE)
        self.pipeline = Pipeline(self.source, self.root / "sandbox")
        self.snapshot = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.source.rglob("*") if p.is_file()}

    def tearDown(self):
        self.temp.cleanup()

    def import_session(self):
        return self.pipeline.import_application({"folder": str(self.folder)})

    def change_tracker(self, cell, value):
        path = self.source / "Applications.xlsx"
        workbook = load_workbook(path)
        workbook.active[cell] = value
        workbook.save(path)
        workbook.close()

    def test_audited_import_copies_exact_resume_without_source_writes(self):
        session = self.import_session()
        self.assertEqual(session["mode"], "audited_import")
        self.assertEqual(session["application_id"], 900001)
        self.assertEqual(session["state"], "built")
        self.assertIn("PASS - no blocking issues", session["audit_report"])
        with self.assertRaises(ValueError):
            self.pipeline.resume(session["id"], for_upload=True)
        self.pipeline.approve_upload(session["id"], {"visual_reviewed": True})
        self.assertEqual(self.pipeline.resume(session["id"], for_upload=True), (self.folder / "Yazad_Madan.docx").read_bytes())
        for path, digest in self.snapshot.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest, path)
        self.assertEqual(set(self.snapshot), {p for p in self.source.rglob("*") if p.is_file()})

    def test_imported_resume_cannot_be_rebuilt_in_prototype(self):
        session = self.import_session()
        with self.assertRaisesRegex(ValueError, "current workflow"):
            self.pipeline.build(session["id"], {"content": session["content"]})

    def test_changed_source_blocks_visual_approval_and_upload(self):
        session = self.import_session()
        self.pipeline.approve_upload(session["id"], {"visual_reviewed": True})
        (self.folder / ".application_id").write_text("900002", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.pipeline.resume(session["id"], for_upload=True)
        with self.assertRaisesRegex(ValueError, "changed"):
            self.pipeline.approve_upload(session["id"], {"visual_reviewed": True})

    def test_changed_tracker_context_blocks_upload(self):
        session = self.import_session()
        self.pipeline.approve_upload(session["id"], {"visual_reviewed": True})
        self.change_tracker("D2", "https://example.myworkdayjobs.com/role/another")
        with self.assertRaisesRegex(ValueError, "tracker context changed"):
            self.pipeline.resume(session["id"], for_upload=True)

    def test_explicit_portal_url_override_keeps_tracker_link_unchanged(self):
        override = "https://another.myworkdayjobs.com/employer/job/900001"
        session = self.pipeline.import_application({"folder": str(self.folder), "portal_url": override})
        self.assertEqual(session["url"], override)
        self.assertEqual(session["tracker_url"], "https://example.myworkdayjobs.com/role/900001")
        self.pipeline.approve_upload(session["id"], {"visual_reviewed": True})
        self.assertTrue(self.pipeline.resume(session["id"], for_upload=True))
        self.assertEqual(hashlib.sha256((self.source / "Applications.xlsx").read_bytes()).hexdigest(), self.snapshot[self.source / "Applications.xlsx"])

    def test_outside_source_folder_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "inside"):
            self.pipeline.import_application({"folder": str(self.root)})

    def test_missing_or_duplicate_tracker_id_is_rejected(self):
        self.change_tracker("A2", 900002)
        with self.assertRaisesRegex(ValueError, "exactly one tracker row"):
            self.import_session()
        self.change_tracker("A2", 900001)
        self.change_tracker("A3", 900001)
        with self.assertRaisesRegex(ValueError, "exactly one tracker row"):
            self.import_session()

    def test_applied_application_is_rejected(self):
        self.change_tracker("E2", "Applied")
        with self.assertRaisesRegex(ValueError, "never changes tracker status"):
            self.import_session()

    def test_failed_existing_audit_is_rejected(self):
        path = next((self.folder / "_inputs").glob("Keywords_*.json"))
        content = json.loads(path.read_text(encoding="utf-8"))
        content["resume_terms"] = ["UnclaimedSyntheticSkill"]
        path.write_text(json.dumps(content), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "current application audit failed"):
            self.import_session()

    def test_unreviewed_or_conflicting_archived_requirements_are_rejected(self):
        path = next((self.folder / "_inputs").glob("Keywords_*.json"))
        content = json.loads(path.read_text(encoding="utf-8"))
        content["role"] = "Another synthetic role"
        path.write_text(json.dumps(content), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "different applications"):
            self.import_session()
        content["role"] = "Treasury Analyst"
        content["requirements_reviewed"] = False
        path.write_text(json.dumps(content), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "completed JD requirements review"):
            self.import_session()


if __name__ == "__main__":
    unittest.main()
