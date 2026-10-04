"""Sandbox containment with fabricated workflow modules and temporary paths."""
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

# Test configuration
HERE = Path(__file__).resolve().parents[1]
SESSION_ID = "a" * 32
WORKFLOW_MODULES = ("atomic_json", "check_ats", "check_page_fit", "jd_intake", "scan_em_dashes")
CREATE_BODY = {"company": "Synthetic Company", "role": "Synthetic Role", "jd": "Fabricated requirements"}
DOCUMENT_BYTES = b"FABRICATED DOCUMENT STUB"
SESSION_FILES = ("session.json", "resume_content.json", "keywords.json", "Yazad_Madan.docx")
CREATE_FILES = ("session.json", "resume_content.json", "jd.txt", "JD.docx", "keywords.json", "current.json")

sys.path.insert(0, str(HERE))
from server import Pipeline


class PublicPathTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="portal-public-paths-")
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "fabricated-source"
        self.reference = self.source / "_Reference"
        self.reference.mkdir(parents=True)
        (self.reference / "Resume_Content_Master.json").write_text(json.dumps({"experience": []}), encoding="utf-8")
        self.data = self.root / "sandbox"
        self.external = self.root / "external"
        self.external.mkdir()
        self.redirects = []
        self.path_before = list(sys.path)
        modules = {name: types.ModuleType(name) for name in WORKFLOW_MODULES}
        modules["atomic_json"].write = lambda path, value: Path(path).write_text(json.dumps(value), encoding="utf-8")
        modules["jd_intake"].save_jd_docx = lambda jd, company, role, path: Path(path).write_bytes(DOCUMENT_BYTES)
        modules["jd_intake"].extract_keywords = lambda jd: []
        modules["check_page_fit"].count_bullets_and_words = lambda path: (14, 600)
        modules["check_page_fit"].evaluate_fit = lambda bullets, words: ([], [])
        modules["check_ats"].check_resume_terms = lambda document, keywords: (None, [], [], 100)
        modules["scan_em_dashes"].find_em_dashes = lambda document: []
        self.module_patch = patch.dict(sys.modules, modules)
        self.module_patch.start()
        self.pipeline = Pipeline(self.source, self.data)

    def tearDown(self):
        for path, directory in reversed(self.redirects):
            if directory and os.name == "nt":
                result = subprocess.run(["cmd", "/c", "rmdir", str(path)], capture_output=True, text=True)
                if result.returncode:
                    raise RuntimeError("Temporary junction cleanup failed: " + result.stderr)
            else:
                path.unlink()
        self.module_patch.stop()
        sys.path[:] = self.path_before
        self.temp.cleanup()

    def redirect(self, path, target, *, directory):
        self.assertTrue(path.parent.resolve().is_relative_to(self.root))
        self.assertTrue(target.resolve().is_relative_to(self.root))
        if directory and os.name == "nt":
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(path), str(target)], capture_output=True, text=True)
            if result.returncode:
                self.skipTest("Temporary Windows junction unavailable: " + result.stderr.strip())
        else:
            try:
                path.symlink_to(target, target_is_directory=directory)
            except OSError as error:
                self.skipTest("Temporary symlink unavailable: " + str(error))
        self.redirects.append((path, directory))

    def populate(self, folder):
        folder.mkdir(parents=True, exist_ok=True)
        session = {"id": SESSION_ID, "mode": "sandbox", "state": "built", "upload_reviewed": False,
                   "url": "http://127.0.0.1/fixture"}
        for filename, value in {"session.json": session, "resume_content.json": {}, "keywords.json": {}}.items():
            (folder / filename).write_text(json.dumps(value), encoding="utf-8")
        (folder / "Yazad_Madan.docx").write_bytes(DOCUMENT_BYTES)

    def test_source_descendants_rejected_before_creation(self):
        for relative in ("", "Projects/output", "unrelated/output", "_Reference/output", "Applications/output"):
            with self.subTest(relative=relative):
                destination = self.source / relative
                before = destination.exists()
                with self.assertRaises(ValueError):
                    Pipeline(self.source, destination)
                self.assertEqual(destination.exists(), before)

    def test_sandbox_ancestor_of_source_rejected(self):
        with self.assertRaises(ValueError):
            Pipeline(self.source, self.root)

    def test_reference_and_tracker_looking_destinations_rejected(self):
        for component in ("_Reference", "Applications", "Applications.xlsx"):
            with self.subTest(component=component):
                destination = self.root / "other-fabricated-workflow" / component / "output"
                with self.assertRaises(ValueError):
                    Pipeline(self.source, destination)
                self.assertFalse(destination.exists())

    def test_session_directory_junction_cannot_escape(self):
        self.populate(self.external)
        self.redirect(self.data / SESSION_ID, self.external, directory=True)
        before = (self.external / "session.json").read_bytes()
        for operation in (lambda: self.pipeline.read(SESSION_ID), lambda: self.pipeline.resume(SESSION_ID),
                          lambda: self.pipeline.approve_upload(SESSION_ID, {"visual_reviewed": True})):
            with self.subTest(operation=operation):
                with self.assertRaises(ValueError):
                    operation()
        self.assertEqual((self.external / "session.json").read_bytes(), before)

    def test_current_file_redirect_cannot_escape(self):
        target = self.external / "current.json"
        target.write_text(json.dumps({"id": SESSION_ID}), encoding="utf-8")
        self.populate(self.data / SESSION_ID)
        self.redirect(self.data / "current.json", target, directory=False)
        with self.assertRaises(ValueError):
            self.pipeline.current()
        with self.assertRaises(ValueError):
            self.pipeline.create(CREATE_BODY)
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"id": SESSION_ID})

    def test_artifact_file_redirects_cannot_escape(self):
        self.populate(self.external)
        folder = self.data / SESSION_ID
        self.populate(folder)
        capability_probe = self.data / "file-symlink-probe"
        self.redirect(capability_probe, self.external / "session.json", directory=False)
        capability_probe.unlink()
        self.redirects.pop()
        for filename in SESSION_FILES:
            with self.subTest(filename=filename):
                target = self.external / filename
                path = folder / filename
                original = path.read_bytes()
                path.unlink()
                self.redirect(path, target, directory=False)
                before = target.read_bytes()
                with self.assertRaises(ValueError):
                    (self.pipeline.resume(SESSION_ID) if filename.endswith(".docx") else self.pipeline.read(SESSION_ID))
                self.assertEqual(target.read_bytes(), before)
                path.unlink()
                self.redirects.pop()
                path.write_bytes(original)

    def test_normal_create_read_approve_and_download(self):
        session = self.pipeline.create(CREATE_BODY)
        self.assertEqual(self.pipeline.current()["id"], session["id"])
        self.assertEqual(self.pipeline.read(session["id"])["content"], {"experience": []})
        folder = self.pipeline.folder(session["id"])
        stored = json.loads((folder / "session.json").read_text(encoding="utf-8"))
        stored["state"] = "built"
        (folder / "session.json").write_text(json.dumps(stored), encoding="utf-8")
        (folder / "Yazad_Madan.docx").write_bytes(DOCUMENT_BYTES)
        self.assertTrue(self.pipeline.approve_upload(session["id"], {"visual_reviewed": True})["upload_reviewed"])
        self.assertEqual(self.pipeline.resume(session["id"]), DOCUMENT_BYTES)

    def test_portable_artifact_resolve_escape_read_guards(self):
        self.populate(self.data / SESSION_ID)
        original_resolve = Path.resolve
        for filename in SESSION_FILES + ("current.json",):
            with self.subTest(filename=filename):
                target = self.external / filename
                target.write_bytes(DOCUMENT_BYTES)

                def redirected_resolve(path, *args, **kwargs):
                    if path.name == filename and path.is_relative_to(self.data):
                        return target
                    return original_resolve(path, *args, **kwargs)

                with patch.object(Path, "resolve", redirected_resolve):
                    with self.assertRaises(ValueError):
                        if filename == "current.json":
                            self.pipeline.current()
                        elif filename.endswith(".docx"):
                            self.pipeline.resume(SESSION_ID)
                        else:
                            self.pipeline.read(SESSION_ID)
                self.assertEqual(target.read_bytes(), DOCUMENT_BYTES)

    def test_portable_artifact_resolve_escape_write_guards(self):
        original_resolve = Path.resolve
        for filename in CREATE_FILES:
            with self.subTest(filename=filename):
                target = self.external / filename
                target.write_bytes(DOCUMENT_BYTES)

                def redirected_resolve(path, *args, **kwargs):
                    if path.name == filename and path.is_relative_to(self.data):
                        return target
                    return original_resolve(path, *args, **kwargs)

                with patch.object(Path, "resolve", redirected_resolve):
                    with self.assertRaises(ValueError):
                        self.pipeline.create(CREATE_BODY)
                self.assertEqual(target.read_bytes(), DOCUMENT_BYTES)

    def test_normal_build_with_fabricated_builder(self):
        from docx import Document
        session = self.pipeline.create(CREATE_BODY)

        def fabricated_builder(command, **kwargs):
            document = Document()
            document.add_paragraph("Synthetic resume builder output")
            document.core_properties.author = "Yazad Madan"
            document.core_properties.last_modified_by = "Yazad Madan"
            document.save(command[-1])
            return types.SimpleNamespace(returncode=0, stderr="")

        with patch("server.subprocess.run", side_effect=fabricated_builder):
            built = self.pipeline.build(session["id"], {"content": {"experience": []},
                                        "requirements_reviewed": True, "content_reviewed": True})
        self.assertEqual(built["state"], "built")
        self.assertFalse(built["checks"]["blocking"])

    def test_normal_import_with_fabricated_audit(self):
        with patch("server.inspect_application", return_value=({"url": "https://example.invalid/posting"},
                                                               {"experience": []}, DOCUMENT_BYTES, {})):
            imported = self.pipeline.import_application({"folder": "fabricated-audited-application"})
        self.assertEqual(imported["mode"], "audited_import")
        self.assertEqual(self.pipeline.resume(imported["id"]), DOCUMENT_BYTES)


if __name__ == "__main__":
    unittest.main()
