"""First resume upload must stop if the target becomes a multiple-file input during hashing."""
import base64
import hashlib

from browser_test_support import SyntheticBrowserTest


RESUME_BYTES = b"Fabricated first upload bytes"
ATTACHMENT = {"name": "Synthetic_Resume.docx", "mime": "application/octet-stream",
              "base64": base64.b64encode(RESUME_BYTES).decode(),
              "sha256": hashlib.sha256(RESUME_BYTES).hexdigest()}


class FirstUploadMultipleRaceTests(SyntheticBrowserTest):
    def test_multiple_enabled_during_digest_blocks_first_upload(self):
        self.open_markup('<label>Resume<input id="upload" type="file"></label>')
        field = next(item for item in self.scan() if item["type"] == "file")
        self.assertEqual(self.page.locator("#upload").evaluate("node => node.files.length"), 0)
        self.page.evaluate("""() => {
          const digest = crypto.subtle.digest.bind(crypto.subtle);
          crypto.subtle.digest = async (...args) => {
            const result = await digest(...args);
            document.getElementById('upload').multiple = true;
            return result;
          };
        }""")
        result = self.fill([{"id": field["id"], "value": ""}], {"attachment": ATTACHMENT})[0]
        self.assertEqual(result["status"], "failed")
        self.assertIn("multiple-file", result["message"].lower())
        self.assertEqual(self.page.locator("#upload").evaluate("node => node.files.length"), 0)
