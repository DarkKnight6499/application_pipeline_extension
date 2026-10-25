"""Row-count honesty, exact-filename upload confirmation and the read-only Review attachment check; synthetic pages only."""
import base64
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Config
SOURCE_DIR = Path(__file__).resolve().parents[1]
TEST_DIR = SOURCE_DIR / "tests"
RESUME_BYTES = b"Invented reviewed bytes " * 100
NAME = "Synthetic_Resume.pdf"
ATTACHMENT = {"name": NAME, "mime": "application/pdf", "base64": base64.b64encode(RESUME_BYTES).decode("ascii"),
              "sha256": hashlib.sha256(RESUME_BYTES).hexdigest()}
UPLOAD_PAGE = '''<div data-automation-id="attachments-FileUpload-container">
<input id="resume" type="file" data-automation-id="file-upload-input-ref"><div id="confirmation">{stale}</div></div>
<script>window.shown = %s; window.changes = 0;
document.getElementById('resume').addEventListener('change', event => {{
  window.changes++; document.getElementById('confirmation').textContent = window.shown(event.target.files[0].name); }});</script>'''
sys.path.insert(0, str(SOURCE_DIR))
sys.path.insert(0, str(TEST_DIR))
import workday_run as driver
from browser_test_support import SyntheticBrowserTest


class RowTests(unittest.TestCase):
    def test_ensure_rows_false_when_add_creates_no_row(self):
        with patch.object(driver, "has_heading", return_value=True), patch.object(driver, "click_add", return_value=True), \
             patch.object(driver, "scan", return_value=[]), patch.object(driver, "require_writable_step"), patch.object(driver.time, "sleep"):
            self.assertFalse(driver.ensure_rows(MagicMock(), {"employment": [{}], "education": []}))

    def test_add_without_row_writes_zero_fields(self):
        page = MagicMock()
        with patch.object(driver, "has_heading", return_value=True), patch.object(driver, "click_add", return_value=True), \
             patch.object(driver, "scan", return_value=[]), patch.object(driver, "require_writable_step"), \
             patch.object(driver, "bind_rows") as bind, patch.object(driver.time, "sleep"):
            with self.assertRaises(driver.DriverStopped):
                driver.run_page(page, {"employment": [{}], "education": []}, False)
        bind.assert_not_called()
        page.evaluate.assert_not_called()


class UploadStatusTests(unittest.TestCase):
    def run_upload(self, evaluate_result=None, error=None):
        page = MagicMock()
        page.evaluate.side_effect = lambda script, *args: True if "find()" in script and "upload" not in script else (_ for _ in ()).throw(error) if error else evaluate_result
        with tempfile.TemporaryDirectory() as folder:
            resume = Path(folder) / "resume.bin"
            resume.write_bytes(RESUME_BYTES)
            with patch.object(driver, "require_writable_step"):
                return driver.upload_resume(page, resume)

    def test_confirmed_status_carries_sha256(self):
        record = self.run_upload(evaluate_result=NAME)
        self.assertEqual((record["status"], record["sha256"]), ("confirmed", hashlib.sha256(RESUME_BYTES).hexdigest()))

    def test_unconfirmed_error_becomes_unconfirmed_status(self):
        self.assertEqual(self.run_upload(error=Exception("Upload was not confirmed on the page. Check it manually."))["status"], "unconfirmed")

    def test_other_error_is_a_failure_stop(self):
        with self.assertRaises(driver.DriverFailed):
            self.run_upload(error=Exception("The upload input is unavailable."))

    def test_compare_attachments(self):
        self.assertTrue(driver.compare_attachments(["A.docx"], ["A.docx"])["ok"])
        result = driver.compare_attachments(["Old.docx"], ["A.docx"])
        self.assertEqual((result["ok"], result["missing"], result["unexpected"]), (False, ["A.docx"], ["Old.docx"]))


class UploadConfirmBrowserTests(SyntheticBrowserTest):
    def upload(self, shown, stale=""):
        self.open_markup(UPLOAD_PAGE.format(stale=stale) % shown)
        self.page.add_script_tag(path=str(SOURCE_DIR / "extension" / "workday-upload.js"))
        return self.page.evaluate('''async attachment => {
          try { return {result: await PortalWorkdayUpload.upload(document.getElementById('resume'), attachment)}; }
          catch (e) { return {error: e.message}; }
        }''', ATTACHMENT)

    def test_exact_filename_with_matching_size_confirms(self):
        self.assertEqual(self.upload("name => name + ' 2.3 KB'").get("result"), NAME)

    def test_longer_filename_does_not_confirm(self):
        result = self.upload("name => 'Old_' + name + '.bak'")
        self.assertIn("not confirmed", result.get("error", ""), result)

    def test_wrong_size_does_not_confirm(self):
        result = self.upload("name => name + ' 90 MB'")
        self.assertIn("not confirmed", result.get("error", ""), result)

    def test_stale_filename_text_gives_unconfirmed(self):
        result = self.upload("name => name", stale=NAME)
        self.assertIn("not confirmed", result.get("error", ""), result)

    def test_review_page_attachment_names_are_listed_read_only(self):
        self.open_markup(f'<div data-automation-id="attachmentsSection"><span data-automation-id="fileName">{NAME}</span></div>'
                         '<div data-automation-id="other">Old_Draft.docx</div>')
        found = self.page.evaluate(driver.REVIEW_ATTACHMENTS_JS)
        self.assertEqual(found, sorted([NAME, "Old_Draft.docx"]))
        self.assertEqual(self.page.evaluate("syntheticSubmitClicks"), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
