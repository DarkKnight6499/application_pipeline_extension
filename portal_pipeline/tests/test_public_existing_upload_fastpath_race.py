"""Matching existing uploads must still satisfy live target and validation checks."""
import base64
import hashlib

from browser_test_support import SyntheticBrowserTest


RESUME_BYTES = b"Fabricated reviewed resume bytes"
ATTACHMENT = {"name": "Synthetic_Resume.docx", "mime": "application/octet-stream",
              "base64": base64.b64encode(RESUME_BYTES).decode(),
              "sha256": hashlib.sha256(RESUME_BYTES).hexdigest()}


class ExistingUploadFastpathRaceTests(SyntheticBrowserTest):
    def prepare(self):
        self.open_markup('<label>Resume<input id="upload" type="file"></label>')
        self.page.evaluate("""attachment => {
          const transfer = new DataTransfer();
          const bytes = Uint8Array.from(atob(attachment.base64), char => char.charCodeAt(0));
          transfer.items.add(new File([bytes], attachment.name));
          document.getElementById('upload').files = transfer.files;
        }""", ATTACHMENT)
        return next(field for field in self.scan() if field["type"] == "file")

    def test_multiple_enabled_during_existing_file_read_is_refused(self):
        field = self.prepare()
        self.page.evaluate("""() => {
          const original = File.prototype.arrayBuffer;
          File.prototype.arrayBuffer = function(...args) {
            document.getElementById('upload').multiple = true;
            return original.apply(this, args);
          };
        }""")
        result = self.fill([{"id": field["id"], "value": ""}], {"attachment": ATTACHMENT})[0]
        self.assertEqual(result["status"], "failed")
        self.assertIn("multiple-file", result["message"].lower())
        self.assertEqual(self.page.locator("#upload").input_value().split("\\")[-1], ATTACHMENT["name"])

    def test_matching_file_with_validation_error_is_not_skipped(self):
        field = self.prepare()
        self.page.evaluate("document.getElementById('upload').setCustomValidity('Upload failed')")
        result = self.fill([{"id": field["id"], "value": ""}], {"attachment": ATTACHMENT})[0]
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["failure_kind"], "validation_error")
        self.assertIn("Upload failed", result["validation_error"])
