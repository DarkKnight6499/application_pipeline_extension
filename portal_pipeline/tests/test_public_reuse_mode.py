"""Author: Yazad Madan. Browser-free Workday prefill regressions."""
import contextlib
import io
import json
import re
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import unittest

import apply as application
import batch_apply
import reuse_mode as reuse
import workday_run as driver

# Config
PROFILE = {"values": {}, "employment": [{"company": "Example Inc", "title": "Analyst"}],
           "education": [{"school": "Example College", "degree": "MS"}]}
URL = "https://sample.myworkdayjobs.com/jobs/one"
UPLOAD_MODULE = Path(__file__).resolve().parents[1] / "extension" / "workday-upload.js"
REPLACEMENT_HARNESS = r"""
const fs = require('node:fs'), vm = require('node:vm');
const {File} = require('node:buffer');
const bytes = Buffer.from('Invented new attachment');
const hash = require('node:crypto').createHash('sha256').update(bytes).digest('hex');
async function run(kind, slot = 'resume') {
  let attached = true, shown = '', clicks = 0, writes = 0, clock = 0;
  const title = slot === 'cover' ? 'Cover letter' : 'Resume';
  const input = {isConnected: true, files: [], labels: [],
    getAttribute: () => null, matches: selector => selector === ':disabled' ? kind === 'disabled' : true,
    dispatchEvent() {writes++; shown = `new.pdf ${bytes.length} bytes`;}};
  const deletion = {type: kind === 'submit' ? 'submit' : 'button', disabled: false,
    textContent: kind === 'unsafe' ? 'Submit and remove' : 'Remove',
    getAttribute: () => null, getClientRects: () => [1], closest: () => null,
    click() {clicks++; if (kind !== 'timeout') {attached = false; input.files = [];}}};
  const container = {id: 'slot', isConnected: true,
    get textContent() {return title + ' ' + (attached ? (kind === 'multiple' ? 'old.pdf other.pdf' : 'old.pdf') : shown);},
    get innerText() {return this.textContent;},
    getAttribute: name => name === 'data-automation-id' ? 'file-upload' : null,
    contains: node => node === input || node === deletion,
    querySelectorAll(selector) {
      if (selector.startsWith('input[type="file"]')) return [input];
      if (selector.startsWith('button')) return attached ? [deletion] : [];
      return [];
    }};
  input.parentElement = {closest: () => container};
  const document = {querySelectorAll(selector) {
    if (selector.startsWith('input[type="file"]')) return [input];
    return kind === 'two_slots' ? [container, {...container}] : [container];
  }};
  const sandbox = {document, File, Uint8Array, atob, crypto: require('node:crypto').webcrypto,
    Event: class {}, performance: {now: () => clock}, setTimeout: callback => {clock += 100; callback();},
    DataTransfer: class {constructor() {this.files = []; this.items = {add: file => this.files.push(file)};}}};
  vm.createContext(sandbox); vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), sandbox);
  const attachment = {name: kind === 'bad_name' ? '' : 'new.pdf', mime: 'application/pdf', base64: bytes.toString('base64'), sha256: kind === 'bad_hash' ? '0'.repeat(64) : hash};
  try {
    const result = await sandbox.PortalWorkdayUpload.replace(attachment, slot, () => {}, {timeout: 1});
    return {result, clicks, writes};
  } catch(error) {return {error: error.message, clicks, writes};}
}
(async () => {
  const results = {};
  for (const kind of ['normal', 'multiple', 'two_slots', 'unsafe', 'submit', 'bad_hash', 'bad_name', 'disabled', 'timeout']) results[kind] = await run(kind);
  results.cover = await run('normal', 'cover');
  process.stdout.write(JSON.stringify(results));
})();
"""


def field(current="", proposal="Example", **changes):
    return {"id": "name", "label": "First name", "key": "first_name", "type": "text", "current": current,
            "proposal": proposal, "status": "prepared", "blocked": False, "disabled": False,
            "required": True, "record": None, "options": [], **changes}


def row(identity, group="employment", **values):
    return [field(value, "", id=f"{identity}.{key}", label=key, key=f"{group}.{key}",
                  record={"id": identity, "group": group}) for key, value in values.items()]


class ReuseTests(unittest.TestCase):
    def test_batch_forwards_fresh_only_to_application_driver(self):
        for scan_only in (False, True):
            job = {"report_path": "unused.json", "url": URL, "folder": "invented", reuse.MODE_KEY: reuse.FRESH,
                   batch_apply.SCAN_ONLY_KEY: scan_only}
            process = MagicMock(returncode=0)
            with patch.object(batch_apply.subprocess, "run", return_value=process) as run, \
                 patch.object(Path, "read_text", return_value='{"exit_code": 0}'):
                batch_apply.run_job(job, dry=scan_only)
            assert ("--fresh" in run.call_args.args[0]) is (not scan_only)

    def test_last_application_refuses_native_submit(self):
        page, control = MagicMock(), MagicMock()
        page.locator.return_value.all.return_value = [control]
        control.inner_text.return_value = "Use my last application"
        control.get_attribute.return_value = "submit"
        used, note = application.choose_last_application(page)
        assert used is False and "unsafe" in note
        control.click.assert_not_called()

    def test_replacement_uses_upload_telemetry_and_exact_payload_hash(self):
        page = MagicMock()
        page.evaluate.side_effect = [{"status": "ready", "attached": True},
                                     {"confirmed": True, "status": "confirmed", "removal": "removed",
                                      "observed_filename": "new.pdf", "observed_size": 42}]
        event = {"uploads": []}
        attachment = {"sha256": "payload_hash"}
        with patch.object(driver, "attachment_for", return_value=attachment), patch.object(driver, "require_writable_step"):
            result = driver.upload_resume(page, "new.pdf", event, replace_mode=True, slot="cover")
        assert result["subtype"] == "cover"
        assert result["reason"] == "upload_confirmed"
        assert result["sha256"] == "payload_hash"
        assert result["removal"] == "removed"
        assert event[reuse.FORCED_KEY] == 1
        assert page.evaluate.call_args.args == (driver.REPLACE_UPLOAD_JS, [attachment, 15000, "cover"])

    def test_dry_scan_prints_no_answer_values(self):
        candidate = field("private@example.test", "new@example.test", label="Email", key="email")
        page, output = MagicMock(), io.StringIO()
        event = {}
        with patch.object(driver, "scan", return_value=[candidate]), patch.object(driver, "bind_rows", return_value={}), \
             patch.object(driver, "ensure_rows") as ensure, contextlib.redirect_stdout(output):
            driver.run_page(page, {}, True, event)
        assert "private@example.test" not in output.getvalue() + json.dumps(event)
        assert "new@example.test" not in output.getvalue() + json.dumps(event)
        page.evaluate.assert_not_called()
        ensure.assert_not_called()

    def test_fresh_history_binding_uses_original_order(self):
        candidates = row("first", company="Other", title="Intern") + row("second", company="Example Inc", title="Analyst")
        token = driver.RUN_MODE.set(reuse.FRESH)
        try:
            with patch.object(driver, "scan", return_value=candidates):
                assert driver.bind_rows(MagicMock(), PROFILE) == {"first": 0}
        finally:
            driver.RUN_MODE.reset(token)

    @unittest.skipUnless(shutil.which("node"), "Node is required for the upload mock.")
    def test_actual_attachment_replacement_without_browser(self):
        result = subprocess.run([shutil.which("node"), "-e", REPLACEMENT_HARNESS, str(UPLOAD_MODULE)],
                                capture_output=True, text=True, timeout=20, check=True)
        cases = json.loads(result.stdout)
        for kind in ("normal", "cover"):
            with self.subTest(kind=kind):
                assert cases[kind]["result"]["confirmed"]
                assert cases[kind]["result"]["removal"] == "removed"
                assert cases[kind]["result"]["observed_filename"] == "new.pdf"
                assert (cases[kind]["clicks"], cases[kind]["writes"]) == (1, 1)
        assert cases["cover"]["result"]["subtype"] == "cover"
        for kind in ("multiple", "two_slots", "unsafe", "submit", "bad_hash", "bad_name", "disabled"):
            with self.subTest(kind=kind):
                assert (cases[kind]["clicks"], cases[kind]["writes"]) == (0, 0)
        assert cases["timeout"]["result"]["removal"] == "timeout"
        assert cases["timeout"]["writes"] == 0

    def test_attachment_ambiguity_names_slot_in_report(self):
        page = MagicMock()
        page.evaluate.return_value = {"status": "ambiguous"}
        event = {"uploads": []}
        with self.assertRaisesRegex(driver.DriverStopped, "slot cover"), \
             patch.object(driver, "sha256_file", return_value="hash"):
            driver.upload_resume(page, "invented.pdf", event, replace_mode=True, slot="cover")
        assert event["uploads"][0]["reason"] == "upload_removal_ambiguous"
        assert event["uploads"][0]["subtype"] == "cover"
        assert page.evaluate.call_count == 1

    def test_fresh_preserves_original_selection_behavior(self):
        candidate = field("Old", "New", id="salary", key="salary")
        page = MagicMock()
        page.evaluate.return_value = [{"id": "salary", "status": "preserved"}]
        with patch.object(driver, "scan", return_value=[candidate]), patch.object(driver, "ensure_rows", return_value=True), \
             patch.object(driver, "bind_rows", return_value={}), patch.object(driver, "require_writable_step"), \
             contextlib.redirect_stdout(io.StringIO()):
            driver.run_page(page, {}, False, {}, mode=reuse.FRESH)
        assert page.evaluate.call_args.args[1] == [{"id": "salary", "value": "New"}]

    def test_classification(self):
        cases = [
            (" EXAMPLE ", "Example", {}, "kept"),
            ("Example, Inc.", "example inc", {}, "kept"),
            ("+1 (202) 555-0123", "2025550123", {"key": "phone"}, "kept"),
            ("10/28/2026", "2026-10-28", {"key": "birth_date"}, "kept"),
            ("October 2026", "2026-10", {"key": "education.0.end_date"}, "kept"),
            ("2026-10-01", "2026-10", {"key": "birth_date"}, "diff"),
            ("Other", "Example", {}, "diff"), ("", "Example", {}, "filled"),
            ("Yes", "No", {"key": "sponsorship_future"}, "forced"),
            ("No", "Yes", {"key": "authorized_us"}, "forced"),
            ("old", "new", {"key": "salary"}, "forced"),
            ("old", "new", {"key": "available_from"}, "forced"),
            ("old.pdf", "new.pdf", {"type": "file", "key": "resume"}, "forced"),
        ]
        for current, proposal, changes, expected in cases:
            with self.subTest(case=(current, proposal, changes, expected)):
                assert reuse.classify(field(current, proposal, **changes)) == expected

    def test_select_uses_visible_option_label(self):
        candidate = field("opaque", "Example", type="select-one", options=[{"value": "opaque", "label": "Example"}])
        assert reuse.classify(candidate) == "kept"

    def test_diff_preview_masks_sensitive_values(self):
        cases = [("Phone", "+1 (202) 555-0123"), ("Email", "private@example.test"),
                                                 ("Employee ID", "ABC123456"), ("Other", "123-45-6789")]
        for label, value in cases:
            with self.subTest(case=(label, value)):
                difference = reuse.difference(field(value, "Different", label=label))
                encoded = json.dumps(difference)
                assert value not in encoded
                assert not any(character.isdigit() for character in difference[reuse.PREVIEW_KEY])
                assert len(difference[reuse.PREVIEW_KEY]) <= 40
                assert difference[reuse.PROFILE_KIND_KEY] == "string"

    def test_difference_list_and_preview_are_bounded(self):
        event = {}
        reuse.record_classifications(event, [field("x" * 500, id=str(index)) for index in range(250)])
        assert event[reuse.DIFF_KEY] == 250
        assert len(event[reuse.DIFFS_KEY]) == reuse.DIFF_LIMIT
        assert all(len(item[reuse.PREVIEW_KEY]) <= 40 for item in event[reuse.DIFFS_KEY])

    def test_history_matching_binds_by_identity_and_leaves_extras(self):
        fields = row("extra", company="Older Co", title="Intern") + row("match", company="EXAMPLE, INC.", title="Analyst")
        fields += row("edu", "education", school="Example College", degree="MS")
        plan = reuse.history_plan(fields, PROFILE)
        assert plan[reuse.BINDINGS_KEY] == {"match": 0, "edu": 0}
        assert plan[reuse.PRESERVED_KEY] == {"match", "edu", "extra"}
        assert plan[reuse.EXTRAS_KEY] == [{"group": "employment", "id": "extra"}]
        assert plan[reuse.MISSING_KEY] == {"employment": [], "education": []}

    def test_matching_rows_do_not_add_or_rewrite(self):
        fields = row("match", company="Example Inc", title="Analyst")
        with patch.object(driver, "scan", return_value=fields), patch.object(driver, "has_heading", return_value=True), \
             patch.object(driver, "click_add") as add:
            assert driver.ensure_rows(MagicMock(), {**PROFILE, "education": []})
            assert driver.bind_rows(MagicMock(), PROFILE) == {"match": 0}
        add.assert_not_called()
        page = MagicMock()
        with patch.object(driver, "scan", return_value=fields), patch.object(driver, "ensure_rows", return_value=True), \
             patch.object(driver, "bind_rows", return_value={"match": 0}), contextlib.redirect_stdout(io.StringIO()):
            driver.run_page(page, PROFILE, False, {})
        page.evaluate.assert_not_called()

    def test_empty_row_is_used_only_for_missing_profile_record(self):
        fields = row("extra", company="Other", title="Intern") + row("blank", company="", title="")
        plan = reuse.history_plan(fields, PROFILE)
        assert plan[reuse.BINDINGS_KEY] == {"blank": 0}
        assert plan[reuse.MISSING_KEY]["employment"] == []
        assert "blank" not in plan[reuse.PRESERVED_KEY]

    def test_missing_row_added_even_with_extra_prefilled_row(self):
        old = row("extra", company="Other", title="Intern")
        new = old + row("blank", company="", title="")
        with patch.object(driver, "scan", side_effect=[old, new]), \
             patch.object(driver, "has_heading", side_effect=lambda page, heading: heading == "Work Experience"), \
             patch.object(driver, "click_add", return_value=True) as add, \
             patch.object(driver, "require_writable_step"), patch.object(driver.time, "sleep"):
            assert driver.ensure_rows(MagicMock(), {**PROFILE, "education": []})
        add.assert_called_once()

    def test_duplicate_history_identity_requires_human(self):
        fields = row("one", company="Example Inc", title="Analyst") + row("two", company="Example Inc", title="Analyst")
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            reuse.history_plan(fields, PROFILE)

    def test_loose_last_application_matcher(self):
        cases = [
            (["Use My Last Application", "Apply Manually"], 0, "matched"),
            (["Reuse previous application data"], 0, "matched"),
            (["Last Application", "Use my last"], None, "ambiguous"),
            (["Apply manually"], None, "none"),
            (["Submit previous application"], None, "unsafe"),
            (["Sign previous application"], None, "unsafe"),
        ]
        for labels, index, reason in cases:
            with self.subTest(case=(labels, index, reason)):
                assert application.last_application_match(labels) == (index, reason)
        assert application.last_application_match(["Reuse saved answers"], re.compile("saved answers", re.I)) == (0, "matched")

    def test_open_job_fallback(self):
        cases = [(["Use my last application"], True, 0), (["Other"], False, 1),
                 (["Last application", "Previous application"], False, 1)]
        for labels, used, manual_clicks in cases:
            with self.subTest(case=(labels, used, manual_clicks)):
                page = MagicMock(url=URL)
                controls = [MagicMock() for _ in labels]
                for control, label in zip(controls, labels):
                    control.inner_text.return_value = label
                    control.get_attribute.return_value = None
                    control.is_visible.return_value = True
                    control.is_enabled.return_value = True
                page.locator.return_value.count.return_value = 1
                page.locator.return_value.first.inner_text.return_value = "Apply"
                page.locator.return_value.first.get_attribute.return_value = None
                page.locator.return_value.first.evaluate.return_value = False
                page.locator.return_value.all.return_value = controls
                browser = MagicMock()
                browser.contexts[0].new_page.return_value = page
                playwright = MagicMock()
                playwright.chromium.connect_over_cdp.return_value = browser
                with patch.object(application, "sync_playwright", return_value=contextlib.nullcontext(playwright)), \
                     patch.object(application, "target_id_of", return_value="target"):
                    result = application.open_job({"portal": "workday", "url": URL})
                assert result[reuse.LAST_USED_KEY] is used
                manual = [call for call in page.locator.call_args_list if call.args[0] == application.APPLY_CLICK["workday"][1]]
                assert len(manual) == manual_clicks
                assert any("fallback" in note for note in result["notes"]) is (not used)

    def test_run_page_preserves_diff_and_forces_existing_answers(self):
        candidates = [field("Other"), field("Yes", "No", id="sponsor", key="sponsorship_future"),
                      field("Old", "New", id="salary", key="salary")]
        page = MagicMock()
        page.evaluate.return_value = [{"id": "sponsor", "status": "filled"}, {"id": "salary", "status": "filled"}]
        event = {}
        with patch.object(driver, "scan", return_value=candidates), patch.object(driver, "ensure_rows", return_value=True), \
             patch.object(driver, "bind_rows", return_value={}), patch.object(driver, "require_writable_step"), \
             patch.object(driver.time, "sleep"), contextlib.redirect_stdout(io.StringIO()):
            driver.run_page(page, {}, False, event)
        selections = page.evaluate.call_args.args[1]
        assert selections == [{"id": "sponsor", "value": "No", "overwrite": True},
                              {"id": "salary", "value": "New", "overwrite": True}]
        assert event[reuse.DIFF_KEY] == 1
        assert event[reuse.FORCED_KEY] == 2

    def test_fresh_flag_and_report_keys(self):
        assert application.parse_args(["--fresh"]).fresh
        assert driver.parse_args(["--fresh"]).fresh
        report = driver.RunReport()
        assert report.data[reuse.MODE_KEY] == reuse.REUSE
        assert report.data[reuse.LAST_USED_KEY] == reuse.UNKNOWN
        assert set(reuse.COUNT_KEYS) <= report.new_page("Information").keys()

    def test_diff_is_not_a_learning_question(self):
        import learning_queue
        report = {reuse.DIFFS_KEY: [reuse.difference(field("Other"))], "unanswered": []}
        assert learning_queue.collect([report], {"answers": {}})["questions"] == []


if __name__ == "__main__":
    unittest.main()
