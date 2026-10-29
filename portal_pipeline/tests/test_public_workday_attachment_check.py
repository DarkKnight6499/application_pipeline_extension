"""Author: Yazad Madan. Browser-free attachment fixtures and manual-presence regressions."""
import contextlib
import hashlib
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import apply as application
import workday_attachments as attachments
import workday_run as driver

# Config
HERE = Path(__file__).resolve().parents[1]
NAME = "Synthetic_Resume.docx"
COVER_NAME = "Synthetic_Cover.docx"
RESUME_BYTES = b"r" * 11749
COVER_BYTES = b"c" * 2048
MATCHING_TEXT = NAME + " 11.47 KB"
STALE_TEXT = NAME + " 11.41 KB"
URL = "https://sample.myworkdayjobs.com/jobs/one/apply"
DOM_HARNESS = r"""
const vm = require('node:vm');
const fixture = JSON.parse(process.argv[1]);
const nodes = [], inputs = [], items = [];
const body = {};
function container(title, identity) {
  const root = {parentElement: body, children: [], textContent: title,
    getAttribute: key => key === 'data-automation-id' ? identity : null,
    cloneNode: () => ({textContent: title, querySelectorAll: () => []}),
    querySelectorAll: selector => selector === 'input[type="file"]' ? root.children.filter(n => n.input) : []};
  return root;
}
for (const slot of ['resume', 'cover']) {
  const root = container(slot === 'resume' ? 'Upload a file' : 'Attachments (optional)', 'formField-' + (slot === 'resume' ? 'file' : 'attachments'));
  if (!fixture.review) {
    const input = {input: true, parentElement: root}; root.children.push(input); inputs.push(input);
  }
  for (const text of fixture[slot] || []) {
    const item = {parentElement: root, textContent: text, closest: () => null, getClientRects: () => [1],
      cloneNode: () => ({textContent: text, querySelectorAll: () => []}), querySelector: () => null};
    root.children.push(item); items.push(item);
  }
}
const document = {body, querySelectorAll: selector => selector === 'input[type="file"]' ? inputs : items};
const context = vm.createContext({document});
process.stdout.write(JSON.stringify(vm.runInContext('(' + process.argv[2] + ')()', context)));
"""
ENGINE_HARNESS = r"""
const fs = require('node:fs'), vm = require('node:vm');
let nodes = [];
const document = {body: {}, getElementById: () => null, querySelectorAll: selector => selector === '*' || selector === '[id]' ? nodes : []};
function node(label, type, value) {
  const menu = type === 'combobox';
  return {tagName: menu ? 'BUTTON' : 'INPUT', type: menu ? 'button' : type, name: label, id: label,
    isConnected: true, parentElement: null, required: true, textContent: value, value: '', checked: value === true,
    labels: [{cloneNode: () => ({textContent: label, querySelectorAll: () => []})}],
    getAttribute: key => key === 'aria-haspopup' && menu ? 'listbox' : null,
    getRootNode: () => document, closest: () => null, getClientRects: () => [1],
    matches: selector => selector !== ':disabled' && selector.includes(menu ? 'button[aria-haspopup=listbox]' : 'input')};
}
nodes = [node('Gender', 'combobox', 'Private choice'), node('Consent', 'checkbox', true), node('Gender empty', 'combobox', 'Select One')];
const context = vm.createContext({document, location: {href: 'https://sample.myworkdayjobs.com/apply', hostname: 'sample.myworkdayjobs.com'},
  getComputedStyle: () => ({visibility: 'visible', display: 'block'})});
for (const filename of ['classifier.js', 'workday-menu.js', 'engine.js'])
  vm.runInContext(fs.readFileSync(process.argv[1] + '/' + filename, 'utf8'), context);
process.stdout.write(JSON.stringify(context.PortalEngine.scan({values: {}}, {register: false})));
"""
DELETE_HARNESS = r"""
const vm = require('node:vm');
const source = process.argv[1];
const outcomes = {};
for (const kind of ['normal', 'changed', 'ambiguous', 'submit', 'boundary']) {
  let clicks = 0;
  const button = {type: kind === 'submit' ? 'submit' : 'button', isConnected: true,
    getAttribute: () => null, closest: () => null, getClientRects: () => [1], matches: () => true,
    click: () => {clicks++;}};
  const item = {isConnected: true, textContent: kind === 'changed' ? 'changed' : 'old.docx 11.41 KB',
    querySelectorAll: () => kind === 'ambiguous' ? [button, button] : [button]};
  const context = vm.createContext({document: {querySelectorAll: () => [item]}, item,
    boundary: () => {if (kind === 'boundary') throw new Error('Review reached');}});
  try {vm.runInContext('(' + source.replaceAll('BOUNDARY()', 'boundary()') + ')([item, 0, "old.docx 11.41 KB"])', context);}
  catch (error) {}
  outcomes[kind] = clicks;
}
process.stdout.write(JSON.stringify(outcomes));
"""


def snapshot(resume=None, cover=None, review=False):
    def item(text, index):
        return {"index": index, "name": text.rsplit(" ", 2)[0], "text": text}
    resume_items = [item(resume, 0)] if resume else []
    cover_items = [item(cover, len(resume_items))] if cover else []
    return {"slots": {"resume": {"inputs": [] if review else [0], "items": resume_items},
                      "cover": {"inputs": [] if review else [1], "items": cover_items}},
            "items": resume_items + cover_items, "unknown_inputs": []}


class AttachmentTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.resume = self.folder / NAME
        self.resume.write_bytes(RESUME_BYTES)
        self.cover = self.folder / COVER_NAME
        self.cover.write_bytes(COVER_BYTES)
        self.args = SimpleNamespace(resume=self.resume, cover=None, dry=False, batch=True, no_cover=False)
        self.report = driver.RunReport()
        self.event = self.report.new_page("My Experience")

    def verify(self, states, review=False):
        page = MagicMock(url=URL)
        iterator = iter(states)
        current = states[0]
        def evaluate(script, *args):
            nonlocal current
            if script == attachments.READ_JS:
                current = next(iterator, current)
                return current
            return None
        page.evaluate.side_effect = evaluate
        page.locator.return_value.nth.return_value.evaluate.return_value = STALE_TEXT
        target = page.locator.return_value.nth.return_value.element_handle.return_value
        target.evaluate.return_value = False
        with patch.object(driver, "require_writable_step"), patch.object(attachments, "CONFIRM_SECONDS", 0):
            driver.verify_workday_attachments(page, self.args, self.report, self.event, review=review)
        return page

    def test_matching_file_kept_and_reported(self):
        page = self.verify([snapshot(MATCHING_TEXT)])
        check = self.report.data["attachment_check"]["resume"]
        self.assertEqual(check, {"expected_bytes": 11749, "seen_kb": "11.47", "status": "matched"})
        page.locator.assert_not_called()
        self.assertEqual(self.event["uploads"][0]["status"], "verified")
        self.assertIn("11749 bytes", self.report.summary())
        self.assertIn("11.47 KB", self.report.summary())

    def test_failure_keeps_requested_filename_in_one_line_summary(self):
        token = driver.REPORT_SECRETS.set({"Synthetic", NAME})
        try:
            with self.assertRaises(driver.DriverStopped) as caught:
                self.verify([snapshot(STALE_TEXT, review=True)], review=True)
            self.report.finish_report(str(caught.exception), 2)
        finally:
            driver.REPORT_SECRETS.reset(token)
        self.assertIn(NAME, self.report.data["stop_reason"])
        self.assertNotIn("\n", self.report.data["stop_reason"])

    def test_two_decimal_kb_rounding_boundary(self):
        self.resume.write_bytes(b"r" * 11740)
        self.assertEqual(attachments.compare(self.resume, snapshot(MATCHING_TEXT)["items"])["status"], "size_mismatch")
        self.resume.write_bytes(b"r" * 11741)
        self.assertEqual(attachments.compare(self.resume, snapshot(MATCHING_TEXT)["items"])["status"], "matched")
        self.resume.write_bytes(b"r" * 11750)
        self.assertEqual(attachments.compare(self.resume, snapshot(MATCHING_TEXT)["items"])["status"], "matched")
        self.resume.write_bytes(b"r" * 11751)
        self.assertEqual(attachments.compare(self.resume, snapshot(MATCHING_TEXT)["items"])["status"], "size_mismatch")

    def test_stale_same_name_deleted_then_uploaded_then_verified(self):
        page = self.verify([snapshot(STALE_TEXT), snapshot(), snapshot(), snapshot(MATCHING_TEXT)])
        writes = page.locator.return_value.nth.return_value.element_handle.return_value.set_input_files
        writes.assert_called_once()
        self.assertTrue(any("button.click()" in call.args[0] for call in page.evaluate.call_args_list))
        self.assertEqual(self.report.data["attachment_check"]["resume"]["status"], "matched")

    def test_missing_file_uploaded_and_verified(self):
        page = self.verify([snapshot(), snapshot(), snapshot(MATCHING_TEXT)])
        page.locator.return_value.nth.return_value.element_handle.return_value.set_input_files.assert_called_once()
        self.assertEqual(self.report.data["attachment_check"]["resume"]["status"], "matched")

    def test_unrelated_empty_input_does_not_block_stale_resume_replacement(self):
        states = [snapshot(STALE_TEXT), snapshot(), snapshot(), snapshot(MATCHING_TEXT)]
        for state in states:
            state["unknown_inputs"] = [2]
        page = self.verify(states)
        page.locator.return_value.nth.return_value.element_handle.return_value.set_input_files.assert_called_once()
        self.assertEqual(self.event["uploads"][0]["status"], "verified")

    def test_two_items_in_resume_slot_stop_before_deletion(self):
        state = snapshot(STALE_TEXT)
        duplicate = dict(state["slots"]["resume"]["items"][0], index=1)
        state["slots"]["resume"]["items"].append(duplicate)
        state["items"].append(duplicate)
        with self.assertRaisesRegex(driver.DriverStopped, "ambiguous"):
            self.verify([state])

    def test_missing_file_after_upload_hard_stops(self):
        with self.assertRaisesRegex(driver.DriverStopped, "Synthetic_Resume.docx.*11749 bytes.*missing") as caught:
            self.verify([snapshot()])
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(self.report.data["failure_telemetry"][0]["kind"], "attachment_mismatch")

    def test_stale_after_replacement_hard_stops(self):
        with self.assertRaisesRegex(driver.DriverStopped, "11749 bytes.*11.41 KB") as caught:
            self.verify([snapshot(STALE_TEXT), snapshot(), snapshot(), snapshot(STALE_TEXT)])
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(self.event["uploads"][0]["status"], "unconfirmed")

    def test_cover_missing_hard_stops(self):
        self.args.cover = self.cover
        states = snapshot(MATCHING_TEXT)
        states["slots"]["cover"]["inputs"] = []
        with self.assertRaisesRegex(driver.DriverStopped, "Synthetic_Cover.docx.*2048 bytes"):
            self.verify([states])
        self.assertEqual(self.report.data["attachment_check"]["cover"]["status"], "missing")

    def test_cover_attachments_slot_uploads_own_file(self):
        self.args.cover = self.cover
        page = self.verify([snapshot(MATCHING_TEXT), snapshot(MATCHING_TEXT),
                            snapshot(MATCHING_TEXT, COVER_NAME + " 2.00 KB")])
        target = page.locator.return_value.nth.return_value.element_handle.return_value
        target.set_input_files.assert_called_once()
        self.assertEqual(self.report.data["attachment_check"]["cover"]["status"], "matched")

    def test_review_mismatch_is_read_only_exit_two(self):
        with self.assertRaisesRegex(driver.DriverStopped, "11749 bytes.*11.41 KB") as caught:
            self.verify([snapshot(STALE_TEXT, review=True)], review=True)
        self.assertEqual(caught.exception.code, 2)
        self.assertFalse(self.report.data["review_attachments"]["ok"])
        self.assertEqual(self.report.data["failure_telemetry"][0]["phase"], "review")

    def test_review_match_and_cover_match(self):
        self.args.cover = self.cover
        page = self.verify([snapshot(MATCHING_TEXT, COVER_NAME + " 2.00 KB", review=True)], review=True)
        self.assertTrue(self.report.data["review_attachments"]["ok"])
        page.locator.assert_not_called()

    def test_unexpected_previous_cover_stops(self):
        with self.assertRaisesRegex(driver.DriverStopped, "unexpected"):
            self.verify([snapshot(MATCHING_TEXT, COVER_NAME + " 2.00 KB")])

    def test_resume_hash_rechecked_before_any_replacement(self):
        self.args.attachment_manifest = {"resume": str(self.resume), "resume_sha256": "0" * 64, "cover": None}
        with self.assertRaisesRegex(driver.DriverStopped, "sha256_mismatch"):
            self.verify([snapshot(STALE_TEXT)])

    def test_rounding_tolerance_only(self):
        self.assertEqual(attachments.compare(self.resume, snapshot(MATCHING_TEXT)["items"])["status"], "matched")
        for text in (STALE_TEXT, NAME + " 11.46 KB", NAME + " 11.48 KB", NAME + " 11 KB"):
            with self.subTest(text=text):
                self.assertNotEqual(attachments.compare(self.resume, snapshot(text)["items"])["status"], "matched")

    def test_review_missing_size_does_not_pass(self):
        state = snapshot(MATCHING_TEXT, review=True)
        state["items"][0]["text"] = NAME
        with self.assertRaisesRegex(driver.DriverStopped, "size_missing"):
            self.verify([state], review=True)

    def test_review_rejects_carried_file_without_expected_source(self):
        self.args.resume = None
        with self.assertRaises(driver.DriverStopped):
            self.verify([snapshot(STALE_TEXT, review=True)], review=True)

    def test_review_rechecks_manifest_hash_even_if_size_matches(self):
        self.args.attachment_manifest = {"resume": str(self.resume), "resume_sha256": "0" * 64, "cover": None}
        with self.assertRaisesRegex(driver.DriverStopped, "sha256_mismatch"):
            self.verify([snapshot(MATCHING_TEXT, review=True)], review=True)

    def test_no_upload_slot_on_contact_page_stays_unchecked(self):
        self.event["title"] = "My Information"
        state = snapshot(review=True)
        self.verify([state])
        self.assertEqual(self.report.data["attachment_check"]["resume"]["status"], "not_checked")
        self.assertEqual(self.event["uploads"], [])

    def test_step_failure_precedes_field_fill_and_next(self):
        page = MagicMock(url=URL)
        page.evaluate.return_value = snapshot(STALE_TEXT)
        with patch.object(driver, "step_title", return_value="My Experience"), patch.object(driver, "dialog_open", return_value=False), \
             patch.object(driver, "inject"), patch.object(driver, "build_profile", return_value={}), \
             patch.object(driver, "require_writable_step"), patch.object(attachments, "CONFIRM_SECONDS", 0), \
             patch.object(driver, "run_page") as fill, contextlib.redirect_stdout(io.StringIO()), \
             self.assertRaises(driver.DriverStopped) as caught:
            driver.drive(page, self.args, self.report)
        self.assertEqual(caught.exception.code, 2)
        fill.assert_not_called()
        page.locator.return_value.click.assert_not_called()

    def test_execute_returns_exit_two_for_review_mismatch(self):
        page = MagicMock(url=URL)
        page.evaluate.return_value = snapshot(STALE_TEXT, review=True)
        playwright = MagicMock()
        with patch.object(driver, "sync_playwright", return_value=contextlib.nullcontext(playwright)), \
             patch.object(driver, "page_of", return_value=page), patch.object(driver, "step_title", return_value="Review"), \
             patch.object(driver, "dialog_open", return_value=False), contextlib.redirect_stdout(io.StringIO()):
            self.args.portal = "workday"
            result = driver.execute(self.args)
        self.assertEqual(result.data["exit_code"], 2)
        self.assertEqual(result.data["failure_telemetry"][0]["kind"], "attachment_mismatch")
        self.assertFalse(result.data["review_attachments"]["ok"])

    def test_input_absent_on_attachment_step_stops_early(self):
        state = snapshot()
        state["slots"]["resume"]["inputs"] = []
        state["slots"]["cover"]["inputs"] = []
        with self.assertRaises(driver.DriverStopped):
            self.verify([state])

    def test_apply_manifest_paths_override_fallback(self):
        inputs = self.folder / "_inputs"
        inputs.mkdir()
        manifest = {"session": True, "url": URL, "resume": str(self.resume), "cover": str(self.cover),
                    "resume_sha256": hashlib.sha256(RESUME_BYTES).hexdigest()}
        (inputs / "apply.json").write_text(json.dumps(manifest), encoding="utf-8")
        job = application.resolve(None, self.folder)
        self.assertEqual(job["attachment_manifest"], manifest)
        args = driver.parse_args(application.driver_args(job))
        self.assertEqual((args.resume, args.cover), (self.resume, self.cover))

    def test_review_path_cannot_report_success_for_stale_file(self):
        page = MagicMock(url=URL)
        page.evaluate.return_value = snapshot(STALE_TEXT, review=True)
        with patch.object(driver, "step_title", return_value="Review"), patch.object(driver, "dialog_open", return_value=False), \
             contextlib.redirect_stdout(io.StringIO()), self.assertRaises(driver.DriverStopped) as caught:
            driver.drive(page, self.args, self.report)
        self.assertEqual(caught.exception.code, 2)
        page.locator.assert_not_called()

    @unittest.skipUnless(shutil.which("node"), "Node unavailable")
    def test_actual_dom_reader_uses_workday_items_and_optional_attachments(self):
        fixture = {"resume": [STALE_TEXT], "cover": [COVER_NAME + " 2.00 KB"]}
        result = subprocess.run(["node", "-e", DOM_HARNESS, json.dumps(fixture), attachments.READ_JS],
                                capture_output=True, text=True, check=True, timeout=10)
        data = json.loads(result.stdout)
        self.assertEqual(data["slots"]["resume"]["items"][0]["name"], NAME)
        self.assertEqual(data["slots"]["resume"]["items"][0]["text"], STALE_TEXT)
        self.assertEqual(data["slots"]["cover"]["inputs"], [1])
        self.assertEqual(data["slots"]["cover"]["items"][0]["name"], COVER_NAME)

    @unittest.skipUnless(shutil.which("node"), "Node unavailable")
    def test_actual_delete_checks_identity_ambiguity_and_boundary(self):
        result = subprocess.run(["node", "-e", DELETE_HARNESS, attachments.DELETE_JS],
                                capture_output=True, text=True, check=True, timeout=10)
        self.assertEqual(json.loads(result.stdout), {"normal": 1, "changed": 0, "ambiguous": 0, "submit": 0, "boundary": 0})


class ManualPresenceTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node unavailable")
    def test_actual_engine_reports_presence_without_protected_answers(self):
        result = subprocess.run(["node", "-e", ENGINE_HARNESS, str(HERE / "extension")],
                                capture_output=True, text=True, check=True, timeout=10)
        fields = json.loads(result.stdout)
        self.assertEqual([field["has_value"] for field in fields], [True, True, False])
        self.assertTrue(all(field["blocked"] and field["current"] == "" for field in fields))
        self.assertNotIn("Private choice", result.stdout)
        event = {}
        driver.record_pending(event, fields)
        self.assertEqual(event["manual_required"], ["Gender empty"])

    def test_nonempty_manual_fields_never_reported_pending(self):
        fields = [{"label": "Manual question", "type": "combobox", "required": True, "blocked": True,
                   "current": "", "has_value": True},
                  {"label": "Checked by person", "type": "checkbox", "required": True,
                   "blocked": True, "current": "", "has_value": True}]
        event = {}
        driver.record_pending(event, fields)
        self.assertEqual(event["manual_required"], [])

    def test_only_empty_required_manual_fields_stop(self):
        fields = [{"label": "Optional manual", "type": "text", "required": False, "blocked": True, "current": ""},
                  {"label": "Required manual", "type": "checkbox", "required": True, "blocked": True, "current": False},
                  {"label": "Already answered", "type": "text", "required": True, "blocked": True, "current": "Existing"}]
        event = {}
        driver.record_pending(event, fields)
        self.assertEqual(event["manual_required"], ["Required manual"])


if __name__ == "__main__":
    unittest.main()
