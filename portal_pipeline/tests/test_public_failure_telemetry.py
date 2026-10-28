"""Author: Yazad Madan. Browser-free failure diagnostics and bounded recovery."""
import contextlib
import io
import json
import subprocess
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import failure_telemetry as telemetry
import workday_run as driver

# Config
HERE = Path(__file__).resolve().parents[1]
URL = "https://sample.myworkdayjobs.com/jobs/one"
SECRET = "Synthetic private answer"
OLD_REPORT_KEYS = {"started", "portal", "dry", "pages", "stop_reason", "exit_code", "review_attachments", "unanswered"}
OLD_PAGE_KEYS = {"title", "fields", "filled", "pending_required", "blocked_gates", "uploads", "learned"}
UPLOAD_CASES = (
    ({}, "upload_timeout"), ({"stale_filename": True}, "upload_stale_filename"),
    ({"size_mismatch": True}, "upload_size_mismatch"), ({"rejected": True}, "upload_rejected"),
    ({"container_replaced": True}, "upload_container_replaced"),
    ({"confirmed": True, "container_replaced": True}, "upload_confirmed"),
    ({"rejected": True, "confirmed": True}, "upload_rejected"),
)
UPLOAD_HARNESS = r"""
const fs = require('node:fs'), vm = require('node:vm');
const {File} = require('node:buffer');
const source = fs.readFileSync(process.argv[1], 'utf8');
const bytes = Buffer.from('Synthetic attachment bytes'), name = 'synthetic.pdf';
const hash = require('node:crypto').createHash('sha256').update(bytes).digest('hex');
async function run(kind) {
  let clock = 0, current, currentInput, changes = 0;
  const container = () => ({isConnected: true, id: 'upload', innerText: '', textContent: 'Resume',
    contains(node) {return node === currentInput && node.isConnected;},
    getAttribute() {return 'attachments-FileUpload';},
    querySelectorAll() {return kind === 'rejected' && changes ? [{textContent: 'Rejected', getClientRects: () => [1], closest: () => null}] : [];}});
  const input = target => ({isConnected: true, files: [], parentElement: {closest: () => target},
    matches(selector) {return selector !== ':disabled';}, getAttribute: () => null,
    dispatchEvent() {
      changes++;
      if (kind.startsWith('replacement')) {
        target.isConnected = false; this.isConnected = false; current = container();
        if (kind === 'replacement_cover') current.textContent = 'Cover letter';
        currentInput = kind === 'replacement_no_input' ? null : input(current);
      }
      current.innerText = kind === 'timeout' || kind === 'replacement_timeout' ? '' :
        kind === 'missing_size' || kind === 'stale' ? name : kind === 'size_mismatch' ? name + ' 99 MB' : name + ' ' + bytes.length + ' bytes';
    }});
  current = container(); currentInput = input(current);
  if (kind === 'stale') current.innerText = name;
  if (kind.startsWith('already')) {
    currentInput.files = [new File([kind === 'already_bad_hash' ? Buffer.from('other bytes') : bytes], name)];
    current.innerText = name + (kind === 'already_late_size' ? '' : ' ' + bytes.length + ' bytes');
  }
  const context = vm.createContext({console, Uint8Array, File, Event, crypto: require('node:crypto').webcrypto,
    atob, performance: {now: () => clock}, setTimeout: (callback, delay) => {
      clock += delay; if (kind === 'already_late_size') current.innerText = name + ' ' + bytes.length + ' bytes'; callback();},
    DataTransfer: class {constructor() {this.files = []; this.items = {add: file => this.files.push(file)};}},
    document: {querySelectorAll: selector => selector.startsWith('input') ? (currentInput ? [currentInput] : []) : [current]}});
  vm.runInContext(source, context);
  const attachment = {name, mime: 'application/pdf', base64: bytes.toString('base64'), sha256: kind === 'bad_hash' ? 'bad' : hash};
  try {const outcome = await context.PortalWorkdayUpload.upload(currentInput, attachment, () => {}, {timeout: 30, detailed: true}); return {kind, changes, outcome};}
  catch (error) {return {kind, changes, error: error.message};}
}
(async () => {
  const results = [];
  for (const kind of ['confirmed', 'timeout', 'stale', 'size_mismatch', 'rejected', 'replacement', 'replacement_no_input', 'replacement_timeout', 'replacement_cover', 'missing_size', 'already', 'already_late_size', 'already_bad_hash', 'bad_hash']) results.push(await run(kind));
  process.stdout.write(JSON.stringify(results));
})().catch(error => {console.error(error); process.exit(1);});
"""


def field(label="City", current="", row=None):
    return {"id": label, "label": label, "key": label.lower(), "type": "text", "status": "prepared",
            "proposal": SECRET, "current": current, "blocked": False, "disabled": False,
            "required": True, "record": row, "structure": {"dom_id": label.lower()}}


class TelemetryTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node is unavailable")
    def test_actual_upload_adapter_without_browser(self):
        result = subprocess.run(["node", "-e", UPLOAD_HARNESS, str(HERE / "extension" / "workday-upload.js")],
                                capture_output=True, text=True, timeout=10, check=True)
        cases = {case["kind"]: case for case in json.loads(result.stdout)}
        expected = {"confirmed": "upload_confirmed", "timeout": "upload_timeout", "stale": "upload_stale_filename",
                    "size_mismatch": "upload_size_mismatch", "rejected": "upload_rejected", "replacement": "upload_confirmed",
                    "replacement_no_input": "upload_confirmed", "replacement_timeout": "upload_container_replaced",
                    "replacement_cover": "upload_container_replaced",
                    "missing_size": "upload_timeout", "already": "upload_confirmed", "already_late_size": "upload_confirmed"}
        for name, reason in expected.items():
            with self.subTest(name=name):
                self.assertEqual(telemetry.upload_reason(cases[name]["outcome"]), reason)
        self.assertTrue(cases["replacement"]["outcome"]["container_replaced"])
        self.assertEqual(cases["already"]["outcome"]["status"], "already attached")
        self.assertEqual(cases["already_late_size"]["changes"], 0)
        self.assertIn("different file", cases["already_bad_hash"]["error"])
        self.assertEqual(cases["already_bad_hash"]["changes"], 0)
        self.assertIn("checksum", cases["bad_hash"]["error"])
        self.assertEqual(cases["bad_hash"]["changes"], 0)

    def test_classification_uses_codes_only(self):
        for kind, expected in telemetry.FAILURE_ACTIONS.items():
            self.assertEqual(telemetry.failure_action({"failure_kind": kind}), expected)
            self.assertEqual(telemetry.failure_action({"reason_code": kind}), expected)
        self.assertEqual(telemetry.failure_action({"message": "identity changed visible form structure changed"}), "hard")
        self.assertEqual(telemetry.failure_action({"status": "refused"}), "human")
        self.assertEqual(telemetry.failure_action({"failure_kind": "unknown"}), "hard")

    def test_sanitization_and_bounds(self):
        candidate = field()
        candidate.update(label="City " + SECRET, adapter="native")
        selection = {"value": SECRET, "overwrite": True}
        result = {"id": "City", "status": "failed", "reason": SECRET + " password=hidden token=hidden " + "x" * 5000,
                  "validation_error": "Rejected " + SECRET, "failure_kind": "validation_error", "actual": SECRET,
                  "dom_state": {"visible": True, "option_count": 10**12, "selected_token_count": 2,
                                "validity": {"valid": False, "value": SECRET}, "value": SECRET}}
        event = {}
        for _ in range(telemetry.FIELD_LIMIT + 10):
            telemetry.append_results(event, [candidate], [selection], [result], {SECRET})
        encoded = json.dumps(event)
        self.assertNotIn(SECRET, encoded)
        self.assertNotIn("hidden", encoded)
        self.assertNotIn('"actual"', encoded)
        self.assertEqual(len(event[telemetry.FIELD_RECORDS_KEY]), telemetry.FIELD_LIMIT)
        record = event[telemetry.FIELD_RECORDS_KEY][0]
        self.assertLessEqual(len(record["reason"]), telemetry.TEXT_LIMIT)
        self.assertEqual(record["attempted_value_kind"], "string")
        self.assertEqual(record["attempted_value_length"], len(SECRET))
        self.assertTrue(record["overwrite"])
        self.assertEqual(record["dom_state"]["option_count"], telemetry.NUMBER_LIMIT)
        self.assertEqual(record["dom_state"]["validity"], {"valid": False})
        self.assertLess(len(encoded), telemetry.FIELD_LIMIT * 2000)

    def test_report_adds_keys_and_revision_fallback(self):
        with patch.object(telemetry, "run_git", side_effect=OSError):
            report = driver.RunReport()
        event = report.new_page("Information")
        report.finish_report("Stopped", 2)
        self.assertTrue(OLD_REPORT_KEYS <= report.data.keys())
        self.assertTrue(OLD_PAGE_KEYS <= event.keys())
        self.assertEqual(set(report.data["source_revision"]["files"]), {"workday_run.py", "apply.py"})

    def test_written_report_sanitizes_late_routing_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            report = driver.RunReport().finish_report("Stopped", 2)
            report.data.update(url="https://user:password@sample.test/path?token=hidden", notes=["password=hidden " + "x" * 1000])
            path = report.write(directory)
            saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(saved["url"], "https://sample.test/path")
        self.assertNotIn("hidden", json.dumps(saved))
        self.assertLessEqual(len(saved["notes"][0]), telemetry.TEXT_LIMIT)

    def test_missing_engine_result_is_recorded(self):
        event = {}
        telemetry.append_results(event, [field()], [{"value": SECRET}], [])
        self.assertEqual(event[telemetry.FIELD_RECORDS_KEY][0]["failure_kind"], "missing_result")

    def test_long_answer_is_redacted_before_truncation(self):
        secret = "Sensitive answer " * 500
        self.assertEqual(telemetry.clean_text(secret, {secret}), "[redacted]")
        record = telemetry.field_record(field(row={"id": "row", "index": 0}), {"value": SECRET}, {}, {SECRET})
        self.assertEqual(record[telemetry.ROW_BINDING_KEY]["index"], 0)

    def test_cap_retains_latest_failure(self):
        event = {telemetry.FIELD_RECORDS_KEY: [{"status": "filled"}] * telemetry.FIELD_LIMIT}
        telemetry.append_results(event, [field()], [{"value": SECRET}],
                                 [{"id": "City", "status": "failed", "failure_kind": "validation_error"}], {SECRET})
        self.assertEqual(len(event[telemetry.FIELD_RECORDS_KEY]), telemetry.FIELD_LIMIT)
        self.assertEqual(event[telemetry.FIELD_RECORDS_KEY][-1]["label"], "City")

    def test_unchanged_inline_error_is_not_a_new_outcome(self):
        state = {"title": "Information", "inline_errors": ["Existing error"]}
        self.assertIsNone(telemetry.next_reason(state, state))
        self.assertEqual(telemetry.next_reason(state, state, True), "timeout")

    def test_url_removes_credentials_query_and_fragment(self):
        self.assertEqual(telemetry.safe_url("https://user:password@sample.test/path?token=hidden#secret"), "https://sample.test/path")
        self.assertEqual(telemetry.safe_url("https://user:password@sample.test:9443/path?token=hidden"), "https://sample.test:9443/path")
        self.assertEqual(telemetry.safe_url("http://[::1]:8766/fixture"), "http://[::1]:8766/fixture")
        self.assertNotIn("hidden phrase", telemetry.clean_text('"password": "hidden phrase"'))
        self.assertNotIn("short-secret", telemetry.clean_text("Authorization: Bearer short-secret"))

    def test_upload_outcome_reasons(self):
        for state, reason in UPLOAD_CASES:
            with self.subTest(reason=reason):
                self.assertEqual(telemetry.upload_reason(state), reason)

    def test_upload_record_exists_before_failure(self):
        event = {"uploads": []}
        page = MagicMock()
        page.evaluate.side_effect = [True, RuntimeError("sensitive details")]
        with patch.object(driver, "sha256_file", return_value="hash"), patch.object(driver, "attachment_for", return_value={}), \
             patch.object(driver, "require_writable_step"), self.assertRaises(driver.DriverFailed):
            driver.upload_resume(page, "synthetic.pdf", event)
        self.assertEqual(event["uploads"][0]["reason"], "upload_error")
        self.assertNotIn("sensitive", json.dumps(event))

    def test_driver_uses_detailed_upload_state_and_bound(self):
        page = MagicMock()
        page.evaluate.side_effect = [True, {"confirmed": True, "status": "confirmed", "container_replaced": True,
                                           "observed_filename": "synthetic.pdf", "observed_size": 42}]
        with patch.object(driver, "sha256_file", return_value="hash"), patch.object(driver, "attachment_for", return_value={}), \
             patch.object(driver, "require_writable_step"):
            record = driver.upload_resume(page, "synthetic.pdf")
        self.assertEqual(record["reason"], "upload_confirmed")
        self.assertTrue(record["container_replaced"])
        self.assertEqual(page.evaluate.call_args.args[1][1], 15000)

    def test_next_outcome_selection_with_mock_page(self):
        cases = [({"dialog": {"title": "Address", "text": "Review address"}}, "dialog_opened"),
                 ({"inline_errors": ["Required"]}, "inline_validation_error"), ({"title": "Experience"}, "step_changed"),
                 ({}, "timeout")]
        for update, reason in cases:
            with self.subTest(reason=reason):
                page = MagicMock(url=URL + "?token=hidden")
                page.evaluate.return_value = {"dialog": update.get("dialog"), "inline_errors": update.get("inline_errors", [])}
                before = {"title": "Information"}
                with patch.object(driver, "step_title", return_value=update.get("title", "Information")), \
                     patch.object(driver, "NEXT_TIMEOUT_SECONDS", 0):
                    outcome = driver.wait_next_outcome(page, before)
                self.assertEqual(outcome["reason"], reason)
                self.assertNotIn("hidden", json.dumps(outcome))
                page.locator.assert_not_called()

    def test_next_returns_on_first_observed_change(self):
        page = MagicMock(url=URL)
        page.evaluate.side_effect = [{"dialog": None, "inline_errors": []}, {"dialog": None, "inline_errors": ["Required"]}]
        with patch.object(driver, "step_title", return_value="Information"), patch.object(driver.time, "sleep") as sleep:
            outcome = driver.wait_next_outcome(page, {"title": "Information"})
        self.assertEqual(outcome["reason"], "inline_validation_error")
        self.assertEqual(page.evaluate.call_count, 2)
        sleep.assert_called_once()

    def test_next_observation_error_retries_within_bound(self):
        page = MagicMock(url=URL)
        page.evaluate.side_effect = [RuntimeError("context replaced"), {"dialog": None, "inline_errors": ["Required"]}]
        with patch.object(driver, "step_title", return_value="Information"), patch.object(driver.time, "sleep"):
            outcome = driver.wait_next_outcome(page, {"title": "Information"})
        self.assertEqual(outcome["reason"], "inline_validation_error")
        self.assertEqual(outcome["observation_errors"], 1)
        self.assertEqual(outcome["last_observation_error_type"], "RuntimeError")

    def test_next_observation_error_still_times_out(self):
        page = MagicMock(url=URL)
        page.evaluate.side_effect = RuntimeError("private context details")
        with patch.object(driver, "NEXT_TIMEOUT_SECONDS", 0):
            outcome = driver.wait_next_outcome(page, {"title": "Information"})
        self.assertEqual(outcome["reason"], "timeout")
        self.assertEqual(outcome["observation_errors"], 1)
        self.assertNotIn("private", json.dumps(outcome))

    def test_dialog_text_is_bounded_and_redacted(self):
        page = MagicMock(url=URL)
        page.evaluate.return_value = {"dialog": {"title": SECRET, "text": SECRET + "x" * 1000}, "inline_errors": ["z" * 1000] * 100}
        token = driver.REPORT_SECRETS.set({SECRET})
        try:
            with patch.object(driver, "step_title", return_value="Information"):
                state = driver.page_state(page)
        finally:
            driver.REPORT_SECRETS.reset(token)
        self.assertNotIn(SECRET, json.dumps(state))
        self.assertLessEqual(len(state["dialog"]["text"]), telemetry.DIALOG_LIMIT)
        self.assertEqual(len(state["inline_errors"]), telemetry.ERROR_LIMIT)


class RecoveryTests(unittest.TestCase):
    def run_fake(self, scans, results, event, cap=1):
        page = MagicMock()
        page.evaluate.side_effect = results
        with patch.object(driver, "ensure_rows", return_value=True), patch.object(driver, "bind_rows", return_value={}), \
             patch.object(driver, "scan", side_effect=scans), patch.object(driver, "require_writable_step"), \
             patch.object(driver, "ROW_SETTLE_SECONDS", 0), patch.object(driver, "RERENDER_RETRY_CAP", cap), \
             contextlib.redirect_stdout(io.StringIO()):
            driver.run_page(page, {}, False, event)
        return page

    def test_progress_with_stable_identity_retries_once(self):
        first, second = field("First"), field("Second")
        scans = [[first, second], [field("First", SECRET), second], [field("First", SECRET), field("Second", SECRET)]]
        results = [[{"id": "First", "status": "failed", "failure_kind": "structure_changed"},
                    {"id": "Second", "status": "failed", "failure_kind": "structure_changed"}],
                   [{"id": "Second", "status": "filled"}]]
        event = {}
        self.assertEqual(self.run_fake(scans, results, event).evaluate.call_count, 2)
        self.assertEqual(event["rerender_retries"], 1)
        self.assertEqual(len(event[telemetry.FIELD_RECORDS_KEY]), 3)

    def test_retry_cap_stops_second_rerender(self):
        scans = [[field("First"), field("Second")], [field("First", SECRET), field("Second")]]
        results = [[{"id": "First", "status": "filled"}, {"id": "Second", "status": "failed", "failure_kind": "node_replaced"}],
                   [{"id": "Second", "status": "failed", "failure_kind": "node_replaced"}]]
        event = {}
        with self.assertRaisesRegex(driver.DriverFailed, "retry cap"):
            self.run_fake(scans, results, event)
        self.assertEqual(event["fill_stop_reason"], "retry_cap")
        self.assertEqual(len(event[telemetry.FIELD_RECORDS_KEY]), 3)

    def test_zero_retry_cap_stops_first_rerender(self):
        event = {}
        with self.assertRaisesRegex(driver.DriverFailed, "retry cap"):
            self.run_fake([[field()]], [[{"id": "City", "status": "failed", "failure_kind": "structure_changed"}]], event, cap=0)
        self.assertEqual(event[telemetry.FILL_STOP_KEY], "retry_cap")

    def test_round_cap_never_returns_unfinished_fields(self):
        event = {}
        with patch.object(driver, "FILL_ROUNDS", 1), self.assertRaisesRegex(driver.DriverFailed, "round cap"):
            self.run_fake([[field()], [field()]], [[{"id": "City", "status": "filled"}]], event)
        self.assertEqual(event[telemetry.FILL_STOP_KEY], "fill_round_cap")

    def test_no_progress_and_changed_row_refuse_retry(self):
        for changed in (False, True):
            before = [field("First"), field("Second", row={"id": "row1", "index": 0})]
            after = [field("First", SECRET if changed else ""), field("Second", row={"id": "row2" if changed else "row1", "index": 0})]
            results = [[{"id": "First", "status": "filled"}, {"id": "Second", "status": "failed", "failure_kind": "structure_changed"}]]
            with self.subTest(changed=changed), self.assertRaisesRegex(driver.DriverFailed, "stable row identity"):
                self.run_fake([before, after], results, {})

    def test_unsupported_control_names_field_and_pauses(self):
        event = {}
        with self.assertRaisesRegex(driver.DriverStopped, "City.*unsupported_control") as caught:
            self.run_fake([[field()]], [[{"id": "City", "status": "failed", "failure_kind": "unsupported_control"}]], event)
        self.assertEqual(caught.exception.code, driver.EXIT_GATE)
        self.assertEqual(event[telemetry.FIELD_RECORDS_KEY][0]["failure_kind"], "unsupported_control")

    def test_exception_and_result_mismatch_keep_telemetry(self):
        for results, kind in ([RuntimeError("private")], "error"), ([[]], "missing_result"):
            event = {}
            with self.subTest(kind=kind), self.assertRaises(driver.DriverFailed):
                self.run_fake([[field()]], results, event)
            self.assertEqual(event[telemetry.FIELD_RECORDS_KEY][0]["failure_kind"], kind)


if __name__ == "__main__":
    unittest.main()
