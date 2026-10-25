"""Driver helpers that act on the page: add buttons are found by their section heading, never by position."""
import sys

from browser_test_support import HERE, SyntheticBrowserTest

sys.path.insert(0, str(HERE))
import workday_run

PAGE = '''<div><div><div><h3>Work Experience</h3><div><button data-automation-id="add-button" onclick="window.work=(window.work||0)+1">Add Another</button></div></div></div>
<div><div><h3>Education</h3><div><button data-automation-id="add-button" onclick="window.edu=(window.edu||0)+1">Add Another</button></div></div></div></div>'''


class AddButtonTests(SyntheticBrowserTest):
    def test_click_add_uses_the_named_section_only(self):
        self.open_markup(PAGE)
        self.assertTrue(workday_run.click_add(self.page, "Education"))
        self.assertEqual(self.page.evaluate("[window.work || 0, window.edu || 0]"), [0, 1])

    def test_unknown_heading_clicks_nothing(self):
        self.open_markup(PAGE)
        self.assertFalse(workday_run.click_add(self.page, "Languages"))
        self.assertEqual(self.page.evaluate("[window.work || 0, window.edu || 0]"), [0, 0])

    def test_two_matching_buttons_are_ambiguous(self):
        self.open_markup(PAGE + PAGE)
        self.assertFalse(workday_run.click_add(self.page, "Education"))


class AttachmentTests(SyntheticBrowserTest):
    def test_attachment_carries_name_mime_and_matching_checksum(self):
        import base64, hashlib, tempfile
        from pathlib import Path
        path = Path(tempfile.mkdtemp()) / "Resume.pdf"
        path.write_bytes(b"%PDF-1.4 test")
        record = workday_run.attachment_for(path)
        self.assertEqual((record["name"], record["mime"]), ("Resume.pdf", "application/pdf"))
        self.assertEqual(hashlib.sha256(base64.b64decode(record["base64"])).hexdigest(), record["sha256"])


class DialogTests(SyntheticBrowserTest):
    def test_only_visible_dialogs_count(self):
        self.open_markup('<div role="dialog" style="display:none">hidden</div><div role="alertdialog" hidden>hidden</div>')
        self.assertFalse(workday_run.dialog_open(self.page))
        self.page.evaluate("document.body.insertAdjacentHTML('beforeend', '<div role=dialog>shown</div>')")
        self.assertTrue(workday_run.dialog_open(self.page))


class HistorySectionTests(SyntheticBrowserTest):
    def test_page_without_history_headings_is_reported_as_having_none(self):
        self.open_markup("<h2>Contact</h2><button>Next</button>")
        self.assertFalse(workday_run.has_heading(self.page, "Work Experience"))

    def test_heading_text_must_match_exactly(self):
        self.open_markup("<h3>Work Experience</h3><h3>Work Experience Summary</h3>")
        self.assertTrue(workday_run.has_heading(self.page, "Work Experience"))
        self.assertFalse(workday_run.has_heading(self.page, "Education"))
