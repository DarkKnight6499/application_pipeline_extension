"""Workday uploads: require reviewed bytes and confirmation in the upload container."""
import base64
import hashlib
from pathlib import Path

from browser_test_support import SyntheticBrowserTest

SCRIPT = Path(__file__).resolve().parents[1] / "extension" / "workday-upload.js"
RESUME_BYTES = b"Synthetic resume attachment."
ATTACHMENT = {"name": "Resume.pdf", "mime": "application/pdf",
              "base64": base64.b64encode(RESUME_BYTES).decode("ascii"),
              "sha256": hashlib.sha256(RESUME_BYTES).hexdigest()}
PAGE = '''<div id="upload" data-automation-id="attachments-FileUpload-container">
<input id="resume" type="file" multiple hidden data-automation-id="file-upload-input-ref">
<span id="confirmation"></span></div>
<script>
window.changeCount = 0;
window.confirmUpload = true;
document.getElementById("upload").addEventListener("change", event => {
  window.changeCount += 1;
  if (window.confirmUpload) { const file = event.target.files[0]; document.getElementById("confirmation").textContent = file.name + " " + file.size + " bytes"; }
});
</script>'''


class WorkdayUploadTests(SyntheticBrowserTest):
    def open_upload_page(self, confirm=True):
        self.open_markup(PAGE)
        self.page.evaluate("confirm => { window.confirmUpload = confirm; }", confirm)
        self.page.add_script_tag(path=str(SCRIPT))

    def upload(self, attachment=None):
        return self.page.evaluate("attachment => PortalWorkdayUpload.upload(document.getElementById('resume'), attachment)",
                                  ATTACHMENT if attachment is None else attachment)

    def test_find_returns_single_hidden_input(self):
        self.open_upload_page()
        self.assertTrue(self.page.evaluate("PortalWorkdayUpload.find() === document.getElementById('resume')"))
        self.assertTrue(self.page.evaluate("PortalWorkdayUpload.find(document.getElementById('upload')) === document.getElementById('resume')"))

    def test_find_returns_null_for_no_match(self):
        self.open_upload_page()
        self.page.evaluate("document.getElementById('resume').remove()")
        self.assertIsNone(self.page.evaluate("PortalWorkdayUpload.find()"))

    def test_find_returns_null_for_two_matches(self):
        self.open_upload_page()
        self.page.evaluate("document.getElementById('upload').append(document.getElementById('resume').cloneNode())")
        self.assertIsNone(self.page.evaluate("PortalWorkdayUpload.find()"))

    def test_upload_resolves_after_bubbling_change_confirms_name(self):
        self.open_upload_page()
        self.assertEqual(self.upload(), ATTACHMENT["name"])
        self.assertEqual(self.page.evaluate("changeCount"), 1)
        file = self.page.evaluate("async () => { const file = document.getElementById('resume').files[0]; return {name: file.name, mime: file.type, text: await file.text()}; }")
        self.assertEqual(file, {"name": ATTACHMENT["name"], "mime": ATTACHMENT["mime"], "text": RESUME_BYTES.decode("ascii")})

    def test_missing_confirmation_throws(self):
        self.open_upload_page(confirm=False)
        with self.assertRaisesRegex(Exception, "Upload was not confirmed on the page. Check it manually."):
            self.upload()

    def test_wrong_checksum_writes_nothing(self):
        self.open_upload_page()
        with self.assertRaisesRegex(Exception, "Resume checksum does not match."):
            self.upload({**ATTACHMENT, "sha256": "0" * 64})
        self.assertEqual(self.page.evaluate("document.getElementById('resume').files.length"), 0)
        self.assertEqual(self.page.evaluate("changeCount"), 0)

    def test_existing_different_file_throws(self):
        self.open_upload_page()
        self.page.evaluate("() => { const transfer = new DataTransfer(); transfer.items.add(new File(['existing'], 'Other.pdf')); document.getElementById('resume').files = transfer.files; }")
        with self.assertRaisesRegex(Exception, "A different file is already attached. Replace it manually."):
            self.upload()
        self.assertEqual(self.page.evaluate("document.getElementById('resume').files[0].name"), "Other.pdf")
        self.assertEqual(self.page.evaluate("changeCount"), 0)

    def test_same_file_already_attached_does_not_dispatch_again(self):
        self.open_upload_page()
        self.assertEqual(self.upload(), ATTACHMENT["name"])
        self.assertEqual(self.upload(), "already attached")
        self.assertEqual(self.page.evaluate("changeCount"), 1)

    def test_guard_aborts_before_writing(self):
        self.open_upload_page()
        with self.assertRaisesRegex(Exception, "Guard stopped upload"):
            self.page.evaluate("attachment => PortalWorkdayUpload.upload(document.getElementById('resume'), attachment, () => { throw new Error('Guard stopped upload'); })", ATTACHMENT)
        self.assertEqual(self.page.evaluate("document.getElementById('resume').files.length"), 0)
        self.assertEqual(self.page.evaluate("changeCount"), 0)

    def test_missing_fields_write_nothing(self):
        self.open_upload_page()
        for field in ATTACHMENT:
            with self.subTest(field=field):
                attachment = dict(ATTACHMENT)
                del attachment[field]
                with self.assertRaisesRegex(Exception, "Provide all resume attachment fields."):
                    self.upload(attachment)
        self.assertEqual(self.page.evaluate("document.getElementById('resume').files.length"), 0)

    def test_detached_input_is_refused(self):
        self.open_upload_page()
        with self.assertRaisesRegex(Exception, "The upload input is unavailable"):
            self.page.evaluate("attachment => { const input = document.getElementById('resume'); input.remove(); return PortalWorkdayUpload.upload(input, attachment); }", ATTACHMENT)
        self.assertEqual(self.page.evaluate("changeCount"), 0)

    def test_delayed_confirmation_is_polled(self):
        self.open_upload_page(confirm=False)
        self.page.evaluate("document.getElementById('resume').addEventListener('change', event => { const file = event.target.files[0]; setTimeout(() => { document.getElementById('confirmation').textContent = file.name + ' ' + file.size + ' bytes'; }, 200); })")
        self.assertEqual(self.upload(), ATTACHMENT["name"])

    def test_confirmation_outside_container_does_not_count(self):
        self.open_upload_page(confirm=False)
        self.page.evaluate("name => { const text = document.createElement('p'); text.textContent = name; document.body.append(text); }", ATTACHMENT["name"])
        with self.assertRaisesRegex(Exception, "Upload was not confirmed on the page"):
            self.upload()

    def test_guard_runs_after_change(self):
        self.open_upload_page()
        result = self.page.evaluate("attachment => { const calls = []; return PortalWorkdayUpload.upload(document.getElementById('resume'), attachment, () => { calls.push(window.changeCount); }).then(name => ({name, calls})); }", ATTACHMENT)
        self.assertEqual(result["name"], ATTACHMENT["name"])
        self.assertEqual((result["calls"][0], result["calls"][-1]), (0, 1))


class UploadReviewFixTests(WorkdayUploadTests):
    def test_existing_file_with_same_name_but_other_bytes_is_refused(self):
        self.open_upload_page()
        self.page.evaluate("""() => { const t = new DataTransfer(); t.items.add(new File(['wrong bytes'], 'Resume.pdf'));
          const i = document.getElementById('resume'); i.files = t.files; document.getElementById('confirmation').textContent = 'Resume.pdf'; }""")
        with self.assertRaisesRegex(Exception, "do(es)? not match|different"):
            self.upload()

    def test_guard_revoked_during_hashing_blocks_the_write(self):
        self.open_upload_page()
        with self.assertRaisesRegex(Exception, "revoked"):
            self.page.evaluate("""attachment => { let calls = 0;
          return PortalWorkdayUpload.upload(document.getElementById('resume'), attachment, () => { if (++calls >= 3) throw new Error('revoked'); }); }""", ATTACHMENT)
        self.assertEqual(self.page.evaluate("[changeCount, document.getElementById('resume').files.length]"), [0, 0])

    def test_cover_letter_upload_is_not_given_the_resume(self):
        self.open_markup(PAGE.replace('<input id="resume"', '<h3>Cover Letter</h3><input id="resume"'))
        self.page.add_script_tag(path=str(SCRIPT))
        with self.assertRaisesRegex(Exception, "[Cc]over"):
            self.upload()

    def test_disabled_input_is_refused(self):
        self.open_upload_page()
        self.page.evaluate("document.getElementById('resume').disabled = true")
        with self.assertRaisesRegex(Exception, "unavailable"):
            self.upload()
        self.assertEqual(self.page.evaluate("changeCount"), 0)
