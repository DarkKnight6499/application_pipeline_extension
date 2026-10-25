from pathlib import Path

import oracle_attach as o

ROWS = [{"remove": "remove resume", "name": "Yazad_Madan.docx"}, {"remove": "remove cover letter", "name": "Old.docx"}]


def test_existing_slots_read_names():
    assert o.existing_slots(ROWS) == {"resume": "Yazad_Madan.docx", "cover": "Old.docx"}


def test_same_resume_kept_and_wrong_cover_removed_when_dropped():
    have = o.existing_slots(ROWS)
    assert o.plan(have, resume=Path("x/Yazad_Madan.docx"), drop_cover=True) == [("remove", "cover", None)]


def test_wrong_cover_replaced_by_wanted():
    have = o.existing_slots(ROWS)
    assert o.plan(have, cover=Path("a/New.docx")) == [("remove", "cover", None), ("attach", "cover", Path("a/New.docx"))]


def test_nothing_requested_changes_nothing():
    assert o.plan(o.existing_slots(ROWS)) == []


def test_empty_slot_attaches():
    assert o.plan({}, resume=Path("r.docx")) == [("attach", "resume", Path("r.docx"))]


from browser_test_support import SyntheticBrowserTest

SLOTS = '''<div class="attachment-upload-button" id="a"><div class="attachment-upload-button__filled">
<button class="attachment-upload-button__download">Yazad_Madan.docx</button><button class="attachment-upload-button__bottom-button">Remove Resume</button></div></div>
<div class="attachment-upload-button" id="b"><div class="attachment-upload-button__filled">
<button class="attachment-upload-button__download">Old.docx</button><button class="attachment-upload-button__bottom-button">Remove Cover Letter</button></div></div>
<script>
const drop = id => { const n = document.getElementById(id); n.innerHTML = '<span>Drop Cover Letter Here or Upload Cover Letter</span><input type="file">';
  n.querySelector("input").addEventListener("change", e => { n.innerHTML = '<div><button class="attachment-upload-button__download">' + e.target.files[0].name + '</button><button class="attachment-upload-button__bottom-button">Remove Cover Letter</button></div>'; }); };
document.querySelector("#b .attachment-upload-button__bottom-button").addEventListener("click", () => drop("b"));
</script>'''


class OracleAttachBrowserTests(SyntheticBrowserTest):
    def test_wrong_cover_removed_and_new_one_attached(self):
        import tempfile
        self.open_markup(SLOTS)
        with tempfile.TemporaryDirectory() as folder:
            new = Path(folder) / "New.docx"
            new.write_bytes(b"x")
            notes = o.apply(self.page, resume=Path("Yazad_Madan.docx"), cover=new)
            self.assertEqual(notes, ["remove cover: ok", "attach cover: ok"])
            self.assertEqual(o.existing_slots(self.page.evaluate(o.SLOT_JS)), {"resume": "Yazad_Madan.docx", "cover": "New.docx"})
