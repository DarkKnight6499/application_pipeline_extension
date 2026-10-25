import tempfile
from pathlib import Path

import single_upload as su
from browser_test_support import SyntheticBrowserTest

PAGE = '''<form><div class="ashby-application-form-autofill-input-root"><input type="file" id="auto"></div>
<div class="ashby-application-form-field-entry"><label for="r">Resume</label><input type="file" id="r"></div>
<div class="ashby-application-form-field-entry"><label for="c">Cover Letter</label><input type="file" id="c"></div></form>'''
DONE = '''<form><div class="ashby-application-form-field-entry"><label for="r">Resume</label><input type="file" id="r"><span>Yazad_Madan.pdf</span></div></form>'''


def test_classify():
    assert su.classify({"autofill": True, "own": "resume", "head": ""}) is None
    assert su.classify({"autofill": False, "own": "", "head": "cover letter upload"}) == "cover"
    assert su.classify({"autofill": False, "own": "resume/cv", "head": ""}) == "resume"
    assert su.classify({"autofill": False, "own": "", "head": "portfolio"}) is None


class SingleUploadTests(SyntheticBrowserTest):
    def test_attaches_empty_slot_not_autofill(self):
        self.open_markup(PAGE)
        with tempfile.TemporaryDirectory() as folder:
            resume = Path(folder) / "Yazad_Madan.pdf"
            resume.write_bytes(b"%PDF")
            self.assertIn("attached", su.upload(self.page, "resume", resume))
            self.assertEqual(self.page.evaluate("[document.getElementById('auto').files.length, document.getElementById('r').files.length, document.getElementById('c').files.length]"), [0, 1, 0])

    def test_already_uploaded_is_left_alone(self):
        self.open_markup(DONE)
        self.assertIn("already uploaded", su.upload(self.page, "resume", Path(__file__)))
