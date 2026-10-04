"""Existing upload verification retains target and file identity on fabricated pages."""
import base64
import hashlib

from browser_test_support import SyntheticBrowserTest

BYTES = b"Fabricated resume bytes"
ATTACHMENT = {"name": "Synthetic_Resume.docx", "mime": "application/octet-stream",
              "base64": base64.b64encode(BYTES).decode(), "sha256": hashlib.sha256(BYTES).hexdigest()}


class ExistingUploadBoundaryTests(SyntheticBrowserTest):
    def prepare(self, label="Resume", multiple=False):
        self.open_markup(f'<label>{label}<input id="upload" type="file" {"multiple" if multiple else ""}></label>')
        self.page.evaluate("""attachment => {
          const transfer = new DataTransfer();
          transfer.items.add(new File([Uint8Array.from(atob(attachment.base64), char => char.charCodeAt(0))], attachment.name));
          document.getElementById('upload').files = transfer.files;
        }""", ATTACHMENT)
        return next(field for field in self.scan() if field["type"] == "file")

    def test_matching_existing_file_in_cover_letter_target_is_not_resume_success(self):
        field = self.prepare("Cover letter")
        result = self.fill([{"id": field["id"], "value": ""}], {"attachment": ATTACHMENT})
        self.assertEqual(result[0]["status"], "failed")
        self.assertIn("resume field", result[0]["message"].lower())

    def test_matching_existing_file_does_not_bypass_multiple_upload_refusal(self):
        field = self.prepare(multiple=True)
        result = self.fill([{"id": field["id"], "value": ""}], {"attachment": ATTACHMENT})
        self.assertEqual(result[0]["status"], "failed")
        self.assertIn("multiple-file", result[0]["message"].lower())

    def test_existing_file_replaced_during_hash_is_not_reported_verified(self):
        field = self.prepare()
        self.page.evaluate("""name => {
          const digest = crypto.subtle.digest.bind(crypto.subtle);
          let calls = 0;
          crypto.subtle.digest = async (...args) => {
            const result = await digest(...args);
            if (++calls === 2) {
              const transfer = new DataTransfer();
              transfer.items.add(new File(['Different fabricated bytes'], name));
              document.getElementById('upload').files = transfer.files;
            }
            return result;
          };
        }""", ATTACHMENT["name"])
        result = self.fill([{"id": field["id"], "value": ""}], {"attachment": ATTACHMENT})
        self.assertEqual(result[0]["status"], "failed")
        self.assertIn("changed", result[0]["message"].lower())
