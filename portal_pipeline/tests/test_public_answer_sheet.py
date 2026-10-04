"""Answer sheet export uses fabricated pages and values and writes only under a temp data directory."""
import http.client
import json
import re
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from browser_test_support import HERE, SYNTHETIC_URL, SyntheticBrowserTest

# Test configuration
PAIRING_TOKEN = "synthetic-test-token"
SESSION_ID = "a" * 32
SENTINEL = "SENTINEL-VALUE-5521"
RESUME_SHA = "b" * 64
FIXED_NOW = "2026-10-04T12:00:00+00:00"
PORTAL_VALUES = {
    "first_name": {"value": "Synthetic", "source": "Fabricated fixture"},
    "email": {"value": "person@example.invalid", "source": "Fabricated fixture"},
}
MARKUP = f"""
<label>First name<input id="first" name="first_name"></label>
<label>Email address<input id="mail" name="email" type="email"></label>
<label>Cover note<textarea id="note" maxlength="40"></textarea></label>
<label>Favorite synthetic color<input id="color"></label>
<label>Password<input id="pw" type="password" value="{SENTINEL}"></label>
<label>Gender<select id="gender"><option value="">Choose</option><option value="x">{SENTINEL}</option></select></label>
<label>Are you a protected veteran?<input id="vet" value="{SENTINEL}"></label>
<label>I agree to the privacy policy<input id="agree" type="checkbox"></label>
"""
PROTECTED_LABELS = ["Password", "Gender", "protected veteran", "privacy policy", "Boundary signature", "I certify this boundary"]
EXPECTED_LABELS = ["First name", "Email address", "Cover note", "Favorite synthetic color", "Untouched field"]

sys.path.insert(0, str(HERE))
import answer_sheet
from server import make_server


def session(folder="."):
    return {"id": SESSION_ID, "application_id": 7, "company": "Synthetic Co", "role": "Synthetic Role",
            "resume_sha256": RESUME_SHA, "resume_path": str(Path(folder) / "Yazad_Madan.docx")}


def field(label, **extra):
    base = {"label": label, "required": False, "type": "text", "proposal": "", "source": "", "status": "pending",
            "blocked": False, "options": [], "structure": {"maxlength": None}}
    base.update(extra)
    return base


def sheet_for(fields, folder="."):
    return answer_sheet.build_answer_sheet(session(folder), fields, url="https://safety-fixture.myworkdayjobs.com/application",
                                           heading="Step One", now=FIXED_NOW)


class SheetUnitTests(SyntheticBrowserTest):
    def scanned(self):
        self.open_markup(MARKUP)
        return self.scan(PORTAL_VALUES)

    def test_sheet_lists_every_scanned_non_protected_field(self):
        fields = self.scanned()
        sheet = sheet_for(fields)
        self.assertEqual(sorted(row["label"] for row in sheet["rows"]), sorted(EXPECTED_LABELS))
        note = next(row for row in sheet["rows"] if row["label"] == "Cover note")
        self.assertEqual((note["type"], note["char_limit"]), ("textarea", 40))
        first = next(row for row in sheet["rows"] if row["label"] == "First name")
        self.assertEqual((first["proposal"], first["status"], first["source"]), ("Synthetic", "prepared", "Fabricated fixture"))
        self.assertEqual((sheet["schema_version"], sheet["mode"], sheet["portal"], sheet["application_id"]), (1, "answer_sheet_only", "workday", 7))
        self.assertEqual(sheet["page_key"], "safety-fixture.myworkdayjobs.com/application#step one")
        self.assertEqual(sheet["resume"]["sha256"], RESUME_SHA)

    def test_protected_fields_absent(self):
        sheet = sheet_for(self.scanned())
        text = json.dumps(sheet) + answer_sheet.render_html(sheet)
        self.assertNotIn(SENTINEL, text)
        for label in PROTECTED_LABELS:
            self.assertNotIn(label, text)

    def test_scan_changes_no_portal_values(self):
        snapshot = "() => [document.body.innerHTML, [...document.querySelectorAll('input,textarea,select')].map(e => [e.id, e.value, e.checked])]"
        self.open_markup(MARKUP)
        before = self.page.evaluate(snapshot)
        answer_sheet.render_html(sheet_for(self.scan(PORTAL_VALUES)))
        self.assertEqual(self.page.evaluate(snapshot), before)

    def test_char_count_matches_js_length(self):
        self.open_markup("")
        for text in ["plain", "emoji \U0001F600 end", "line one\nline two", "crlf\r\nbreak", "\U0001F600\n\U0001F600"]:
            with self.subTest(text=text):
                js = self.page.evaluate("text => text.replace(/\\r\\n/g, '\\n').length + (text.replace(/\\r\\n/g, '\\n').match(/\\n/g) || []).length", text)
                self.assertEqual(answer_sheet.char_count(text), js)
        self.assertEqual(answer_sheet.char_count("\U0001F600"), 2)
        self.assertEqual(answer_sheet.char_count("a\nb"), 4)


class SheetPlainTests(unittest.TestCase):
    def test_pending_rows_have_no_value(self):
        sheet = sheet_for([field("Open pending", proposal=SENTINEL, source="stray", status="pending"),
                           field("No source", proposal=SENTINEL, source="", status="prepared"),
                           field("Forced manual", proposal=SENTINEL, source="x", status="prepared", forced_manual=True)])
        rows = {row["label"]: row for row in sheet["rows"]}
        self.assertEqual((rows["Open pending"]["proposal"], rows["Open pending"]["status"]), ("", "pending"))
        self.assertEqual((rows["No source"]["proposal"], rows["No source"]["status"]), ("", "pending"))
        self.assertEqual((rows["Forced manual"]["proposal"], rows["Forced manual"]["status"], rows["Forced manual"]["source"]), ("", "manual_only", ""))
        self.assertNotIn(SENTINEL, json.dumps(sheet))

    def test_blocked_flag_and_type_drop_rows(self):
        sheet = sheet_for([field("Ordinary", blocked=True), field("Secret", type="password"), field("Kept", proposal="v", source="s", status="prepared")])
        self.assertEqual([row["label"] for row in sheet["rows"]], ["Kept"])

    def test_html_is_offline_escaped_and_dashless(self):
        sheet = sheet_for([field("<script>alert(1)</script>", proposal="a & b", source="s", status="prepared", required=True)])
        html = answer_sheet.render_html(sheet)
        self.assertIn('<meta name="author" content="Yazad Madan">', html)
        self.assertNotIn("<script", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIsNone(re.search(r"(src|href)\s*=|url\(|@import|https?://", html))
        self.assertFalse(set(html) & {"—", "–"})
        self.assertNotIn("--", re.sub(r"<!--.*?-->", "", html, flags=re.S))

    def test_sheet_written_only_under_data_dir(self):
        with tempfile.TemporaryDirectory() as temp:
            data_dir = Path(temp) / "data"
            folder = data_dir / SESSION_ID
            folder.mkdir(parents=True)
            pipeline = SimpleNamespace(source=Path(temp), data=data_dir, lock=threading.RLock(), current=lambda: None, templates=lambda: [],
                                       folder=lambda sid: folder, read=lambda sid: session(folder),
                                       atomic=SimpleNamespace(write=lambda path, data: Path(path).write_text(json.dumps(data), encoding="utf-8")))
            server = make_server(pipeline, 0, PAIRING_TOKEN)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def post(body, path=f"/api/sessions/{SESSION_ID}/answer-sheet"):
                    connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
                    connection.request("POST", path, body=json.dumps(body), headers={"X-Portal-Token": PAIRING_TOKEN})
                    response = connection.getresponse()
                    result = response.status, json.loads(response.read())
                    connection.close()
                    return result
                body = {"fields": [field("First name", proposal="Synthetic", source="s", status="prepared"), field("Gender")],
                        "url": "https://safety-fixture.myworkdayjobs.com/a/../../escape", "heading": "../../evil"}
                status, result = post(body)
                self.assertEqual(status, 200, result)
                self.assertEqual([row["label"] for row in result["sheet"]["rows"]], ["First name"])
                self.assertIn("<html", result["html"])
                written = sorted(p for p in Path(temp).rglob("*") if p.is_file())
                self.assertEqual(len(written), 2)
                for path in written:
                    self.assertEqual(path.parent, folder)
                    self.assertRegex(path.name, r"^answer_sheet_[a-z0-9_-]+\.(json|html)$")
                self.assertEqual(post({"fields": "bad"})[0], 400)
                self.assertEqual(post(body, "/api/sessions/" + "c" * 32 + "/answer-sheet")[0], 200)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


class PanelWiringTests(SyntheticBrowserTest):
    def test_panel_exports_sheet_logs_corpus_and_saves_override(self):
        self.open_markup(MARKUP)
        self.page.add_script_tag(path=str(HERE / "extension/panel.js"))
        self.page.evaluate("""async () => {
          globalThis.calls = [];
          const session = {id: 'a'.repeat(32), mode: 'audited_import', company: 'Synthetic Co', role: 'Synthetic Role', url: location.href};
          const api = async (path, body) => {
            calls.push({path, body});
            if (path === '/api/profile') return {values: {first_name: {value: 'Synthetic', source: 'Fabricated fixture'}}};
            if (path === '/api/current') return session;
            if (path.endsWith('/preflight')) return {items: [], manual_field_ids: [], ack_required: false};
            if (path.endsWith('/answer-sheet')) return {html: '<p>sheet</p>', sheet: {rows: []}};
            return {};
          };
          await PortalPanel.open(api, {load: async () => null, save: async () => {}}, {targetUrl: location.href});
        }""")
        host = self.page.locator("#portal-panel-host")
        host.get_by_role("textbox", name="Answer First name", exact=True).wait_for()
        corpus = next(call for call in self.page.evaluate("calls") if call["path"] == "/api/corpus")
        labels = [item["label"] for item in corpus["body"]["questions"]]
        self.assertIn("Favorite synthetic color", labels)
        self.assertNotIn("First name", labels)
        self.assertFalse({"Password", "Gender", "I agree to the privacy policy"} & set(labels))
        with self.page.expect_download() as download:
            host.get_by_role("button", name="Export answer sheet", exact=True).click()
        self.assertEqual(Path(download.value.path()).read_text(encoding="utf-8"), "<p>sheet</p>")
        request = next(call for call in self.page.evaluate("calls") if call["path"].endswith("/answer-sheet"))
        raw = json.dumps(request["body"])
        for protected in ("Password", "Gender", "veteran", SENTINEL):
            self.assertNotIn(protected, raw)
        host.get_by_role("textbox", name="Answer First name", exact=True).fill("Edited name")
        host.get_by_role("button", name="Save edit to profile for First name", exact=True).click()
        self.page.wait_for_function("calls.some(call => call.path.endsWith('/override'))")
        override = next(call for call in self.page.evaluate("calls") if call["path"].endswith("/override"))
        self.assertEqual((override["body"]["key"], override["body"]["value"]), ("first_name", "Edited name"))
        self.assertEqual(self.page.locator("#first").input_value(), "")
