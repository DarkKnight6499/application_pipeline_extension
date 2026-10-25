"""Inspection reports upload controls (file inputs, drop zones) by structure only, including hidden inputs and open shadow roots."""
from browser_test_support import SyntheticBrowserTest

UPLOAD = '''<label>Name<input></label>
<div data-automation-id="file-upload-drop-zone"><span>Drop files here</span><button type="button" data-automation-id="select-files">Select files</button>
  <input type="file" id="resume-file" data-automation-id="file-upload-input-ref" accept=".pdf,.doc" style="display:none"></div>
<input type="file" id="second" multiple>
<div id="host"></div>
<script>document.getElementById("host").attachShadow({mode: "open"}).innerHTML = '<input type="file" id="inner">';</script>'''


class UploadCoverageTests(SyntheticBrowserTest):
    def coverage(self, markup):
        self.open_markup(markup)
        return self.page.evaluate("PortalEngine.inspect()")["coverage"]

    def test_file_inputs_and_drop_zone_are_sampled(self):
        coverage = self.coverage(UPLOAD)
        self.assertEqual(coverage["upload_controls"], 3)
        by_id = {item["dom_id"]: item for item in coverage["upload_samples"] if item["tag"] == "input"}
        self.assertEqual(set(by_id), {"resume-file", "second", "inner"})
        self.assertFalse(by_id["resume-file"]["visible"])
        self.assertEqual(by_id["resume-file"]["accept"], ".pdf,.doc")
        self.assertEqual(by_id["resume-file"]["automation_id"], "file-upload-input-ref")
        self.assertTrue(by_id["second"]["multiple"])
        self.assertTrue(by_id["inner"]["in_shadow"])

    def test_drop_zone_container_is_reported(self):
        zones = [item for item in self.coverage(UPLOAD)["upload_samples"] if item["tag"] != "input"]
        self.assertEqual([item["automation_id"] for item in zones], ["file-upload-drop-zone"])

    def test_no_upload_reports_zero(self):
        coverage = self.coverage('<label>Name<input></label>')
        self.assertEqual(coverage["upload_controls"], 0)

    def test_filename_is_never_reported(self):
        self.assertNotIn("SECRET", str(self.coverage(UPLOAD.replace('id="second"', 'id="second" value="" data-x="SECRET"'))["upload_samples"]).replace("data-x", ""))
