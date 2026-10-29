"""Author: Yazad Madan. Browser-free replays of delayed Workday forms and rerenders."""
import contextlib
import io
import itertools
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Config
HERE = Path(__file__).resolve().parents[1]
URL = "https://sample.wd5.myworkdayjobs.com/en-US/Careers/job/City/Analyst_JR12345"
APPLY_URL = URL + "/apply/useMyLastApplication"
LABELS = ("Securities industry experience?*", "Government Official?*", "Post-employment restrictions?*",
          "Family or associate?*", "Referred by official?*")
SUCCESS_MESSAGES = ("synthetic.docx successfully uploaded", "File successfully attached", "Upload completed")
sys.path.insert(0, str(HERE))

import answer_memory
import apply as application
import browser_target
import failure_telemetry as telemetry
import learning_queue
import workday_run as driver


def field(label=LABELS[0], **changes):
    return {"id": label, "label": label, "key": None, "type": "combobox", "options": [],
            "current": "", "proposal": "", "required": True, "visible": True, "record": None,
            "blocked": False, "disabled": False, "status": "pending", "structure": {"dom_id": label}, **changes}


class TransitionReplayTests(unittest.TestCase):
    def ready(self, scans, states=None, known=()):
        page = MagicMock(url=APPLY_URL)
        ticks = iter(index / 10 for index in range(200))
        scans = scans if callable(scans) else itertools.chain(scans, itertools.repeat(scans[-1]))
        with patch.object(driver, "scan", side_effect=scans), \
             patch.object(driver, "step_title", return_value="My Experience"), \
             patch.object(driver, "form_title_rendered", side_effect=states or [True] * 100), \
             patch.object(driver, "KNOWN_FIELDLESS_STEPS", frozenset(known)), \
             patch.object(driver.time, "monotonic", side_effect=lambda: next(ticks)), \
             patch.object(driver.time, "sleep"):
            return driver.wait_form_ready(page, {}, "My Experience", {})

    def test_delayed_fields_and_title_must_settle(self):
        populated = [field()]
        result = self.ready([[], [], populated, populated, populated, populated, populated, populated],
                            [False, False, False, True, True, True, True, True])
        self.assertEqual(result, populated)

    def test_changing_field_count_restarts_stability_window(self):
        populated = [field(), field(LABELS[1])]
        self.assertEqual(self.ready([[], [field()], populated, populated, populated, populated, populated]), populated)

    def test_unknown_empty_page_stops_within_bound(self):
        with self.assertRaisesRegex(driver.DriverStopped, "form|fields"):
            self.ready([[]] * 100)

    def test_known_empty_page_requires_full_bounded_rescan(self):
        calls = []
        def empty(*args):
            calls.append(True)
            return []
        self.assertEqual(self.ready(empty, known=("My Experience",)), [])
        self.assertGreater(len(calls), 30)

    def test_title_never_rendered_stops_even_with_fields(self):
        with self.assertRaises(driver.DriverStopped):
            self.ready([[field()]] * 100, [False] * 100)

    def test_transient_observation_error_resets_stability(self):
        result = self.ready([RuntimeError("Execution context replaced"), [field()], [field()], [field()], [field()], [field()], [field()]])
        self.assertEqual(len(result), 1)

    def test_next_transition_waits_before_scanning_new_page_for_fill(self):
        page = MagicMock(url=APPLY_URL)
        state = SimpleNamespace(changed=False, polls=0, clock=0.0)
        first, questions = [field("Existing answer", current="Known")], [field(label) for label in LABELS]
        button = page.locator.return_value
        button.count.return_value = 1
        button.inner_text.return_value = "Next"
        button.click.side_effect = lambda: setattr(state, "changed", True)
        def scan(*args):
            if not state.changed:
                return first
            state.polls += 1
            return [] if state.polls < 3 else questions
        def fill(page, profile, dry, event):
            if state.changed:
                self.assertGreaterEqual(state.polls, 7)
            fields = questions if state.changed else first
            event["fields"] = len(fields)
            return fields
        def sleep(seconds):
            state.clock += seconds
        report = driver.RunReport()
        args = SimpleNamespace(dry=False, batch=True, resume=None, cover=None, no_cover=False)
        with patch.object(driver, "step_title", side_effect=lambda page: "Application Questions" if state.changed else "My Information"), \
             patch.object(driver, "dialog_open", return_value=False), patch.object(driver, "inject"), \
             patch.object(driver, "build_profile", return_value={}), patch.object(driver, "scan", side_effect=scan), \
             patch.object(driver, "run_page", side_effect=fill), patch.object(driver, "bind_rows", return_value={}), \
             patch.object(driver, "form_title_rendered", side_effect=lambda *args: state.polls >= 3), \
             patch.object(driver.time, "monotonic", side_effect=lambda: state.clock), patch.object(driver.time, "sleep", side_effect=sleep), \
             patch.object(driver, "wait_for_person", return_value=True), patch.object(driver, "learn", return_value=0), \
             patch.object(driver, "require_writable_step"), patch.object(driver, "upload_resume", return_value=None), \
             patch.object(driver, "page_state", return_value={"title": "My Information"}), \
             patch.object(driver, "wait_next_outcome", return_value={"reason": "step_changed", "after": {"title": "Application Questions"}}), \
             contextlib.redirect_stdout(io.StringIO()), self.assertRaises(driver.DriverStopped):
            driver.drive(page, args, report)
        button.click.assert_called_once()
        self.assertEqual(report.data["pages"][1]["pending_required"], list(LABELS))

    def test_answered_questions_clear_pending_before_next(self):
        report = driver.RunReport()
        page = MagicMock(url=APPLY_URL)
        page.evaluate.return_value = {"slots": {"resume": {"inputs": [], "items": []}, "cover": {"inputs": [], "items": []}},
                                      "items": [], "unknown_inputs": []}
        page.locator.return_value.count.return_value = 1
        page.locator.return_value.inner_text.return_value = "Next"
        args = SimpleNamespace(dry=False, batch=False, resume=None, cover=None, no_cover=False)
        with patch.object(driver, "step_title", return_value="Application Questions"), \
             patch.object(driver, "dialog_open", return_value=False), patch.object(driver, "inject"), \
             patch.object(driver, "build_profile", return_value={}), patch.object(driver, "run_page", return_value=[field()]), \
             patch.object(driver, "scan", return_value=[field(current="Reviewed answer")]), \
             patch.object(driver, "wait_for_person", return_value=True), patch.object(driver, "learn", return_value=1), \
             patch.object(driver, "upload_resume", return_value=None), patch.object(driver, "require_writable_step"), \
             patch.object(driver, "page_state", return_value={"title": "Application Questions"}), \
             patch.object(driver, "wait_next_outcome", return_value={"reason": "step_changed", "after": {"title": "Review"}}), \
             contextlib.redirect_stdout(io.StringIO()), self.assertRaises(driver.ReviewReached):
            driver.drive(page, args, report)
        self.assertEqual(report.data["pages"][0]["pending_required"], [])
        self.assertEqual(report.data["pages"][0]["learned"], 1)
        self.assertEqual(report.data["unanswered"], [])
        page.locator.return_value.click.assert_called_once()

    def test_final_zero_rescan_blocks_next_after_nonempty_fill(self):
        report = driver.RunReport()
        page = MagicMock(url=APPLY_URL)
        args = SimpleNamespace(dry=False, batch=False, resume=None, cover=None, no_cover=False)
        with patch.object(driver, "step_title", return_value="Application Questions"), \
             patch.object(driver, "dialog_open", return_value=False), patch.object(driver, "inject"), \
             patch.object(driver, "build_profile", return_value={}), \
             patch.object(driver, "run_page", return_value=[field(current="Known")]), \
             patch.object(driver, "scan", return_value=[]), patch.object(driver, "wait_for_person", return_value=True), \
             patch.object(driver, "upload_resume", return_value=None), \
             patch.object(driver, "wait_form_ready", side_effect=driver.DriverStopped("No form fields settled")), \
             contextlib.redirect_stdout(io.StringIO()), self.assertRaises(driver.DriverStopped):
            driver.drive(page, args, report)
        page.locator.return_value.click.assert_not_called()

    def test_zero_fields_cannot_click_next(self):
        page = MagicMock(url=APPLY_URL)
        report = driver.RunReport()
        args = SimpleNamespace(dry=False, batch=True, resume=None, cover=None, no_cover=False)
        with patch.object(driver, "step_title", return_value="My Experience"), \
             patch.object(driver, "dialog_open", return_value=False), patch.object(driver, "inject"), \
             patch.object(driver, "build_profile", return_value={}), \
             patch.object(driver, "wait_form_ready", side_effect=driver.DriverStopped("No form fields settled")), \
             patch.object(driver, "run_page", return_value=[]) as fill, contextlib.redirect_stdout(io.StringIO()), \
             self.assertRaises(driver.DriverStopped):
            driver.drive(page, args, report)
        fill.assert_called_once()
        page.locator.return_value.click.assert_not_called()

    def test_empty_dry_posting_reports_without_advancing(self):
        page = MagicMock(url=URL)
        report = driver.RunReport(dry=True)
        args = SimpleNamespace(dry=True, batch=False, resume=None, cover=None, no_cover=False)
        with patch.object(driver, "step_title", return_value=""), patch.object(driver, "dialog_open", return_value=False), \
             patch.object(driver, "inject"), patch.object(driver, "build_profile", return_value={}), \
             patch.object(driver, "run_page", return_value=[]), patch.object(driver, "wait_form_ready") as ready, \
             contextlib.redirect_stdout(io.StringIO()), self.assertRaises(driver.ReviewReached):
            driver.drive(page, args, report)
        ready.assert_not_called()
        page.locator.return_value.click.assert_not_called()


class InlineSuccessReplayTests(unittest.TestCase):
    def test_upload_success_does_not_become_next_error(self):
        for text in SUCCESS_MESSAGES:
            with self.subTest(text=text):
                before = {"title": "My Experience", "inline_errors": []}
                after = {"title": "Application Questions", "inline_errors": [text]}
                self.assertEqual(telemetry.next_reason(before, after), "step_changed")

    def test_real_error_survives_success_notice(self):
        after = {"inline_errors": [SUCCESS_MESSAGES[0], "Please answer Government Official"]}
        self.assertEqual(telemetry.next_reason({}, after), "inline_validation_error")

    def test_mixed_success_and_failure_is_still_an_error(self):
        self.assertTrue(telemetry.is_inline_error("File successfully uploaded. Another upload failed."))

    def test_python_page_state_filters_success_not_actual_errors(self):
        page = MagicMock(url=URL)
        page.evaluate.return_value = {"inline_errors": [*SUCCESS_MESSAGES, "Required question is missing"]}
        with patch.object(driver, "step_title", return_value="My Experience"):
            self.assertEqual(driver.page_state(page)["inline_errors"], ["Required question is missing"])


class QuestionsReplayTests(unittest.TestCase):
    def test_visible_optional_unknowns_join_required_questions_and_dedupe(self):
        fields = [field(label) for label in LABELS] + [field("Office preference?", required=False)]
        report = driver.RunReport()
        report.new_page("Application Questions")
        report.record_unanswered(fields, URL)
        self.assertEqual(len(report.data["unanswered"]), 6)
        queue = learning_queue.collect([dict(report.data, url=URL)] * 2, {"answers": {}})
        self.assertEqual(len(queue["questions"]), 6)
        self.assertTrue(all(question["job_count"] == 1 for question in queue["questions"]))

    def test_reviewed_menu_answers_are_remembered_and_do_not_queue_again(self):
        report = driver.RunReport()
        report.new_page("Application Questions")
        report.record_unanswered([field(label) for label in LABELS], URL)
        with tempfile.TemporaryDirectory() as directory:
            reports = [dict(report.data, url=URL)] * 2
            queue = learning_queue.write_queue(reports, directory)
            for question in queue["questions"]:
                question["answer"] = "No"
            reviewed = Path(directory) / "reviewed.json"
            reviewed.write_text(json.dumps(queue), encoding="utf-8")
            stored, _ = learning_queue.import_answers(reviewed, directory)
            memory = answer_memory.load_memory(directory)
            self.assertEqual(stored, len(LABELS))
            self.assertEqual([answer_memory.lookup(memory, label) for label in LABELS], ["No"] * len(LABELS))
            self.assertEqual(learning_queue.collect(reports, memory)["questions"], [])

    def test_required_or_visible_only_and_no_existing_answer(self):
        fields = [field(required=False, visible=False), field("Answered", current="No"),
                  field("Optional", required=False), field("Hidden required", visible=False)]
        self.assertEqual([item["label"] for item in driver.unanswered(fields)], ["Optional", "Hidden required"])

    def test_protected_questions_are_manual_and_never_queued(self):
        fields = [field("Visa type"), field("Consent", blocked=True), field("Gender", blocked=True),
                  field("Signature", blocked=True), field("Are you authorized to work here?")]
        report = driver.RunReport()
        event = report.new_page("Voluntary Disclosures")
        driver.record_pending(event, fields)
        report.record_unanswered(fields, URL)
        self.assertEqual(report.data["unanswered"], [])
        self.assertEqual(set(event["manual_required"]), {item["label"] for item in fields})
        report.finish_report("Manual answers required", driver.EXIT_GATE)
        summary = report.summary()
        for item in fields:
            self.assertIn("Voluntary Disclosures: " + item["label"], summary)
        self.assertNotIn('"current"', summary)

    def test_stop_reason_retains_all_manual_labels_beyond_single_text_limit(self):
        report = driver.RunReport()
        event = report.new_page("Application Questions")
        labels = [label + " Please review the full question before continuing." for label in LABELS]
        driver.record_pending(event, [field(label, blocked=True, current="", proposal="Private sentinel") for label in labels])
        report.finish_report(driver.pending_stop(event), driver.EXIT_GATE)
        for label in labels:
            self.assertIn(label, report.data["stop_reason"])
        self.assertNotIn("Private sentinel", json.dumps(report.data))

    def test_batch_stop_names_page_and_all_manual_labels(self):
        fields = [field(label) for label in LABELS] + [field("Signature", blocked=True)]
        report = driver.RunReport()
        args = SimpleNamespace(dry=False, batch=True, resume=None, cover=None, no_cover=False)
        page = MagicMock(url=APPLY_URL)
        with patch.object(driver, "step_title", return_value="Application Questions"), \
             patch.object(driver, "dialog_open", return_value=False), patch.object(driver, "inject"), \
             patch.object(driver, "build_profile", return_value={}), patch.object(driver, "wait_form_ready"), \
             patch.object(driver, "run_page", return_value=fields), patch.object(driver, "upload_resume", return_value=None), \
             patch.object(driver, "scan", return_value=fields), patch.object(driver, "bind_rows", return_value={}), \
             contextlib.redirect_stdout(io.StringIO()), self.assertRaises(driver.DriverStopped) as caught:
            driver.drive(page, args, report)
        self.assertIn("Application Questions", str(caught.exception))
        self.assertIn("Signature", str(caught.exception))
        self.assertEqual(report.data["pages"][0]["pending_required"], list(LABELS))
        page.locator.return_value.click.assert_not_called()


class TransientReplayTests(unittest.TestCase):
    def replay(self, kinds, changes=None):
        candidate = field("How Did You Hear About Us?", proposal="Job Board", status="prepared",
                          structure={"dom_id": "source--source"})
        scans = [[candidate] for _ in kinds] + [[dict(candidate, current="Job Board")]]
        if changes:
            scans[1] = [dict(candidate, **changes)]
        results = [[{"id": candidate["id"], "status": "failed", "failure_kind": kind,
                     "message": "Question or control identity changed. (#2:old=>new)"}] if kind else
                   [{"id": candidate["id"], "status": "filled"}] for kind in kinds]
        page = MagicMock()
        page.evaluate.side_effect = results
        event = {}
        with patch.object(driver, "ensure_rows", return_value=True), patch.object(driver, "bind_rows", return_value={}), \
             patch.object(driver, "scan", side_effect=scans), patch.object(driver, "require_writable_step"), \
             patch.object(driver.time, "sleep"), contextlib.redirect_stdout(io.StringIO()):
            try:
                driver.run_page(page, {}, False, event)
            except driver.DriverStopped as error:
                return event, page, error
        return event, page, None

    def test_identity_and_replaced_node_retry_without_prior_progress(self):
        for kind in ("identity_changed", "node_replaced"):
            with self.subTest(kind=kind):
                event, page, error = self.replay([kind, None])
                self.assertIsNone(error)
                self.assertEqual(page.evaluate.call_count, 2)
                self.assertEqual(event[telemetry.RETRY_KEY], 1)
                self.assertIn("#2:old=>new", event[telemetry.FIELD_RECORDS_KEY][0]["reason"])
                self.assertEqual(event["retry_events"][0]["failure_kind"], kind)

    def test_two_retries_succeed_and_third_failure_stops(self):
        event, page, error = self.replay(["identity_changed", "node_replaced", None])
        self.assertIsNone(error)
        self.assertEqual(event[telemetry.RETRY_KEY], 2)
        self.assertEqual(len(event["retry_events"]), 2)
        event, page, error = self.replay(["identity_changed"] * 3)
        self.assertIsInstance(error, driver.DriverFailed)
        self.assertEqual(page.evaluate.call_count, 3)
        self.assertEqual(event[telemetry.FILL_STOP_KEY], "retry_cap")

    def test_changed_question_or_protected_rescan_cannot_retry(self):
        for changes in ({"label": "Different question"}, {"blocked": True}, {"proposal": "Different answer"},
                        {"record": {"id": "another row", "index": 0}}):
            with self.subTest(changes=changes):
                event, page, error = self.replay(["identity_changed", None], changes)
                self.assertIsInstance(error, driver.DriverFailed)
                self.assertEqual(page.evaluate.call_count, 1)


class ApplyReplayTests(unittest.TestCase):
    def test_dry_launch_orders_edge_open_scan_without_login_or_apply_clicks(self):
        order = []
        report = driver.RunReport(dry=True).finish_report("Dry run finished", 0)
        job = {"url": URL, "portal": "workday", "resume": None, "cover": None}
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(application, "resolve", return_value=job), \
             patch.object(application.edge_launch, "ensure_edge", side_effect=lambda: order.append("edge") or {"started": True}), \
             patch.object(application, "open_job", side_effect=lambda job, **kwargs: order.append(("open", kwargs)) or
                          {"notes": [], "url": APPLY_URL, "target_id": "target"}), \
             patch.object(application, "login_step") as login, \
             patch.object(driver, "execute", side_effect=lambda args: order.append(("scan", args.dry, args.target_id)) or report), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(application.run(URL, launch=True, dry=True, report_path=Path(directory) / "report.json"), 0)
        self.assertEqual(order, ["edge", ("open", {"dry": True}), ("scan", True, "target")])
        login.assert_not_called()

    def test_dry_open_job_only_navigates_new_tab(self):
        page = MagicMock(url=URL)
        browser = MagicMock()
        browser.contexts[0].new_page.return_value = page
        playwright = MagicMock()
        playwright.chromium.connect_over_cdp.return_value = browser
        with patch.object(application, "sync_playwright", return_value=contextlib.nullcontext(playwright)), \
             patch.object(application, "target_id_of", return_value="target"):
            result = application.open_job({"url": URL, "portal": "workday"}, dry=True)
        page.goto.assert_called_once()
        page.locator.assert_not_called()
        self.assertEqual(result["target_id"], "target")

    def test_dry_no_open_launch_uses_existing_tab_without_opening(self):
        report = driver.RunReport(dry=True).finish_report("Dry scan", 0)
        job = {"url": URL, "portal": "workday", "resume": None, "cover": None}
        with tempfile.TemporaryDirectory() as directory, patch.object(application, "resolve", return_value=job), \
             patch.object(application.edge_launch, "ensure_edge", return_value={"started": False}) as edge, \
             patch.object(application, "open_job") as opened, patch.object(application, "login_step") as login, \
             patch.object(driver, "execute", return_value=report), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(application.run(URL, launch=True, open_page=False, dry=True,
                                             report_path=Path(directory) / "report.json"), 0)
        edge.assert_called_once()
        opened.assert_not_called()
        login.assert_not_called()

    def test_reuse_url_matches_job_and_refuses_ambiguity(self):
        page = SimpleNamespace(url=APPLY_URL)
        browser = SimpleNamespace(contexts=[SimpleNamespace(pages=[page])])
        self.assertIs(browser_target.select_tab(browser, URL), page)
        browser.contexts[0].pages.append(SimpleNamespace(url=APPLY_URL + "/next"))
        with self.assertRaises(SystemExit):
            browser_target.select_tab(browser, URL)

    def test_posting_and_apply_tabs_for_same_job_require_target_id(self):
        pages = [SimpleNamespace(url=URL), SimpleNamespace(url=APPLY_URL)]
        browser = SimpleNamespace(contexts=[SimpleNamespace(pages=pages)])
        with self.assertRaises(SystemExit):
            browser_target.select_tab(browser, URL)
        with patch.object(browser_target, "target_id_of", side_effect=["posting", "application"]):
            self.assertIs(browser_target.select_tab(browser, URL, target_id="application"), pages[1])

    def test_requisition_or_slug_match_requires_exact_host_and_token(self):
        urls = [URL.replace("Analyst_JR12345", "Other_JR12345") + "/apply",
                URL.replace("Analyst_JR12345", "Analyst") + "/apply"]
        for url in urls:
            page = SimpleNamespace(url=url)
            browser = SimpleNamespace(contexts=[SimpleNamespace(pages=[page])])
            self.assertIs(browser_target.select_tab(browser, URL), page)
        for url in (APPLY_URL.replace("sample.wd5", "other.wd5"), URL.replace("JR12345", "JR123456"),
                    URL.rsplit("/", 1)[0] + "/Unrelated/apply", "https://sample.wd5.myworkdayjobs.com/login"):
            with self.subTest(url=url), self.assertRaises(SystemExit):
                browser_target.select_tab(SimpleNamespace(contexts=[SimpleNamespace(pages=[SimpleNamespace(url=url)])]), URL)


class EngineReplayTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node unavailable")
    def test_actual_scan_required_flags_and_guarded_rescan_fills(self):
        script = r"""
const fs = require('node:fs'), vm = require('node:vm');
let nodes = [], notices = [];
const document = {body: {}, getElementById: () => null,
  querySelectorAll: selector => selector === '*' || selector === '[id]' ? nodes : selector.startsWith('[role=alert]') ? notices : []};
function menu(label, id, aria = null) {
  const attributes = {'aria-haspopup': 'listbox', 'aria-expanded': 'false', 'aria-required': aria};
  return {tagName: 'BUTTON', type: 'button', name: id, id, isConnected: true, parentElement: null,
    textContent: 'Select One', labels: [{cloneNode: () => ({textContent: label, querySelectorAll: () => []})}],
    getAttribute: key => attributes[key] ?? null, getRootNode: () => document, closest: () => null,
    getClientRects() {return this.isConnected ? [1] : [];},
    matches: selector => selector.includes('button[aria-haspopup=listbox]')};
}
const context = vm.createContext({document, location: {href: 'https://sample.myworkdayjobs.com/apply', hostname: 'sample.myworkdayjobs.com'},
  getComputedStyle: () => ({visibility: 'visible', display: 'block'}), setTimeout: callback => callback()});
for (const filename of ['classifier.js', 'workday-menu.js', 'engine.js'])
  vm.runInContext(fs.readFileSync(process.argv[1] + '/' + filename, 'utf8'), context);
const labels = JSON.parse(process.argv[2]), engine = context.PortalEngine;
nodes = labels.map((label, index) => menu(index === 1 ? label.replace(/\*$/, '') : label, 'question' + index, index === 1 ? 'true' : null));
const empty = engine.scan({values: {}}), answers = {};
for (const field of empty) answers[field.label.toLowerCase().replace(/[^a-z0-9+#\s-]+/g, ' ').trim()] = 'No';
const profile = {values: {}, answers};
const prepared = engine.scan(profile), selected = [{id: prepared[0].id, value: 'No'}];
nodes[0].name = 'rerendered';
context.PortalWorkdayMenu.choose = async (element, answer, guard) => {guard(); element.textContent = answer; return answer;};
(async () => {
  const identity = await engine.fill(selected);
  engine.scan(profile);
  const afterRescan = await engine.fill(selected);
  engine.scan(profile);
  nodes[0].isConnected = false;
  nodes[0] = menu(labels[0], 'question0');
  const replaced = await engine.fill(selected);
  engine.scan(profile);
  const afterReplacement = await engine.fill(selected);
  engine.scan(profile);
  nodes[0].isConnected = false;
  nodes[0] = menu(labels[0], 'question0');
  nodes[0].getClientRects = () => {nodes[1].textContent = 'Unexpected side effect'; return [1];};
  const collateral = await engine.fill(selected);
  notices = Array.from({length: 12}, () => ({textContent: 'file.docx successfully uploaded', getClientRects: () => [1], closest: () => null}));
  notices.push({textContent: 'Required question is missing', getClientRects: () => [1], closest: () => null});
  const pageState = vm.runInContext('(' + process.argv[3] + ')()', context);
  process.stdout.write(JSON.stringify({empty, identity, afterRescan, replaced, afterReplacement, collateral, pageState,
    untouched: nodes.slice(2).map(node => node.textContent)}));
})().catch(error => {console.error(error); process.exit(1);});
"""
        result = subprocess.run(["node", "-e", script, str(HERE / "extension"), json.dumps(LABELS), driver.PAGE_STATE_JS],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertTrue(all(item["required"] and item["current"] == "" and item["status"] == "pending" for item in data["empty"]))
        self.assertEqual(data["identity"][0]["failure_kind"], "identity_changed")
        self.assertIn("#2:", data["identity"][0]["message"])
        self.assertEqual(data["afterRescan"][0]["status"], "filled")
        self.assertEqual(data["replaced"][0]["failure_kind"], "node_replaced")
        self.assertEqual(data["afterReplacement"][0]["status"], "filled")
        self.assertEqual(data["collateral"][0]["failure_kind"], "collateral_change")
        self.assertEqual(data["untouched"], ["Select One"] * 3)
        self.assertEqual(data["pageState"]["inline_errors"], ["Required question is missing"])

    @unittest.skipUnless(shutil.which("node"), "Node unavailable")
    def test_actual_engine_required_and_inline_classifiers(self):
        script = r"""
const fs = require('node:fs'), vm = require('node:vm');
const context = vm.createContext({PortalWorkdayMenu: {matches: node => node.menu},
  document: {}, location: {href: 'https://sample.myworkdayjobs.com/apply'}});
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), context);
const engine = context.PortalEngine;
const node = (menu, aria) => ({menu, getAttribute: key => key === 'aria-required' ? aria : null});
process.stdout.write(JSON.stringify({
  required: [engine.requiredFor(node(true, null), 'Industry?*'), engine.requiredFor(node(true, 'true'), 'Industry?'),
             engine.requiredFor(node(false, null), 'Optional*'), engine.requiredFor(node(true, null), 'Optional')],
  errors: ['sample.docx successfully uploaded', 'File successfully attached', 'Upload completed',
           'Answer is required', 'Successfully uploaded. Another upload failed.'].map(engine.isInlineError)
}));
"""
        result = subprocess.run(["node", "-e", script, str(HERE / "extension/engine.js")],
                                capture_output=True, text=True, check=True, timeout=10)
        data = json.loads(result.stdout)
        self.assertEqual(data["required"], [True, True, False, False])
        self.assertEqual(data["errors"], [False, False, False, True, True])


if __name__ == "__main__":
    unittest.main()
