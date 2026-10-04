"""Portal record tests use fabricated values and write only under a temp data directory."""
import http.client
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import portal_record
from server import Pipeline, make_server

# Test configuration
APPLICATION_ID = 7
SESSION_ID = "a" * 32
PAIRING_TOKEN = "synthetic-test-token"
SENTINEL = "SENTINEL-VALUE-5521"
RESUME_SHA = "b" * 64
FIXED_NOW = "2026-10-04T12:00:00+00:00"
TODAY = "2026-10-05"
SESSION = {"id": SESSION_ID, "application_id": APPLICATION_ID, "company": "Synthetic Co", "role": "Synthetic Role",
           "url": "https://example.invalid/jobs/1", "resume_sha256": RESUME_SHA}


def entry(label, **extra):
    base = {"field_id": "f-" + label, "label": label, "key": "", "type": "text", "proposal": "p", "final_value": "v", "source": "Fabricated fixture",
            "selected": True, "overwrite": False, "result": "filled", "readback": "v"}
    base.update(extra)
    return base


def seeded(data, **session):
    return portal_record.load_record(data, APPLICATION_ID, {**SESSION, **session})


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data = Path(self.temp.name) / "data"
        self.data.mkdir()
        self.addCleanup(self.temp.cleanup)

    def test_record_stores_selected_and_unselected_with_results(self):
        seeded(self.data)
        page = {"page_key": "example.invalid/apply#step one", "portal_state": "partially_filled",
                "fields": [entry("First name"), entry("Cover note", selected=False, result="", readback=""), entry("Phone", overwrite=True, result="preserved")]}
        record = portal_record.record_page(self.data, APPLICATION_ID, page, now=FIXED_NOW)
        fields = {item["label"]: item for item in record["pages"][0]["fields"]}
        self.assertEqual(set(fields), {"First name", "Cover note", "Phone"})
        self.assertTrue(fields["First name"]["selected"])
        self.assertFalse(fields["Cover note"]["selected"])
        self.assertEqual((fields["Phone"]["overwrite"], fields["Phone"]["result"]), (True, "preserved"))
        self.assertEqual(record["portal_state"], "partially_filled")
        self.assertEqual(record["resume"], {"filename": "Yazad_Madan.docx", "sha256": RESUME_SHA})
        self.assertEqual(portal_record.load_record(self.data, APPLICATION_ID), record)
        again = portal_record.record_page(self.data, APPLICATION_ID, {**page, "fields": [entry("Only")]})
        self.assertEqual(len(again["pages"]), 1)
        self.assertEqual([item["label"] for item in again["pages"][0]["fields"]], ["Only"])

    def test_protected_values_never_stored(self):
        seeded(self.data)
        fields = [entry("Password", type="password", final_value=SENTINEL), entry("Gender", final_value=SENTINEL),
                  entry("Are you a protected veteran?", final_value=SENTINEL), entry("I agree to the privacy policy", final_value=SENTINEL),
                  entry("Flagged", protected=True, final_value=SENTINEL), entry("Kept")]
        record = portal_record.record_page(self.data, APPLICATION_ID, {"page_key": "k", "fields": fields})
        self.assertEqual([item["label"] for item in record["pages"][0]["fields"]], ["Kept"])
        self.assertNotIn(SENTINEL, (self.data / "records" / f"{APPLICATION_ID}.json").read_text(encoding="utf-8"))

    def test_state_never_submitted_without_user_report(self):
        seeded(self.data)
        with self.assertRaises(ValueError):
            portal_record.record_page(self.data, APPLICATION_ID, {"page_key": "k", "portal_state": portal_record.SUBMITTED_STATE, "fields": []})
        record = portal_record.record_page(self.data, APPLICATION_ID, {"page_key": "k", "portal_state": "complete_for_review", "fields": []})
        self.assertEqual(record["portal_state"], "complete_for_review")
        portal_record.append_event(self.data, APPLICATION_ID, "note", "x")
        self.assertNotEqual(portal_record.load_record(self.data, APPLICATION_ID)["portal_state"], portal_record.SUBMITTED_STATE)
        done = portal_record.mark_reported_submitted(self.data, APPLICATION_ID, None, now=FIXED_NOW)
        self.assertEqual(done["portal_state"], portal_record.SUBMITTED_STATE)
        later = portal_record.record_page(self.data, APPLICATION_ID, {"page_key": "k2", "portal_state": "scanned", "fields": []})
        self.assertEqual(later["portal_state"], portal_record.SUBMITTED_STATE)

    def test_employer_ref_distinct_from_application_id(self):
        seeded(self.data)
        with self.assertRaises(ValueError):
            portal_record.mark_reported_submitted(self.data, APPLICATION_ID, str(APPLICATION_ID))
        for bad in ['REQ"1', "REQ 1; rm", "A--B", "x" * 80, "$(whoami)"]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                portal_record.mark_reported_submitted(self.data, APPLICATION_ID, bad)
        self.assertNotEqual(portal_record.load_record(self.data, APPLICATION_ID)["portal_state"], portal_record.SUBMITTED_STATE)
        done = portal_record.mark_reported_submitted(self.data, APPLICATION_ID, "REQ-4421")
        self.assertEqual((done["employer_reference_id"], done["application_id"]), ("REQ-4421", APPLICATION_ID))

    def test_tracker_command_exact_text(self):
        record = seeded(self.data)
        base = 'py -3 D:\\Code\\Resume\\_Reference\\mark_application_status.py "Synthetic Co" "Synthetic Role" Applied 2026-10-05 --id 7'
        self.assertEqual(portal_record.tracker_command(record, TODAY), base)
        record["employer_reference_id"] = "REQ-4421"
        self.assertEqual(portal_record.tracker_command(record, TODAY), base + ' --employer-ref "REQ-4421"')
        record["role"] = 'Quant "Lead" $5'
        self.assertIn('"Quant `"Lead`" `$5"', portal_record.tracker_command(record, TODAY))
        with self.assertRaises(ValueError):
            portal_record.tracker_command(record, "10/05/2026")

    def test_record_written_under_data_only(self):
        seeded(self.data)
        portal_record.record_page(self.data, APPLICATION_ID, {"page_key": "../../evil", "fields": [entry("A")]})
        portal_record.append_event(self.data, APPLICATION_ID, "k", "d")
        written = [p for p in Path(self.temp.name).rglob("*") if p.is_file()]
        self.assertEqual([p.relative_to(self.data).as_posix() for p in written], [f"records/{APPLICATION_ID}.json"])
        for bad in ["../7", True, -1, "7"]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                portal_record.load_record(self.data, bad)

    def test_sponsorship_mode_defaults_to_truthful_and_is_kept(self):
        self.assertEqual(seeded(self.data)["sponsorship_answer_mode"], "truthful")
        (self.data / "records" / f"{APPLICATION_ID}.json").unlink()
        self.assertEqual(seeded(self.data, sponsorship_answer_mode="screening_no")["sponsorship_answer_mode"], "screening_no")
        stored = json.loads((self.data / "records" / f"{APPLICATION_ID}.json").read_text(encoding="utf-8"))
        del stored["sponsorship_answer_mode"]
        (self.data / "records" / f"{APPLICATION_ID}.json").write_text(json.dumps(stored), encoding="utf-8")
        self.assertEqual(portal_record.load_record(self.data, APPLICATION_ID)["sponsorship_answer_mode"], "truthful")
        (self.data / "records" / f"{APPLICATION_ID}.json").unlink()
        self.assertEqual(seeded(self.data, sponsorship_answer_mode="bogus")["sponsorship_answer_mode"], "truthful")


class RouteTests(unittest.TestCase):
    def test_routes_and_helper_never_spawns_mark_script(self):
        with tempfile.TemporaryDirectory() as temp:
            data = Path(temp) / "data"
            data.mkdir()
            pipeline = SimpleNamespace(source=Path(temp), data=data, lock=threading.RLock(), current=lambda: None, templates=lambda: [],
                                       read=lambda sid: dict(SESSION),
                                       atomic=SimpleNamespace(write=lambda path, value: Path(path).write_text(json.dumps(value), encoding="utf-8")))
            pipeline.record_for = lambda sid: Pipeline.record_for(pipeline, sid)
            server = make_server(pipeline, 0, PAIRING_TOKEN)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def call(method, path, body=None):
                    connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
                    connection.request(method, path, body=json.dumps(body) if body is not None else None, headers={"X-Portal-Token": PAIRING_TOKEN})
                    response = connection.getresponse()
                    result = response.status, json.loads(response.read())
                    connection.close()
                    return result
                url = f"/api/sessions/{SESSION_ID}"
                with mock.patch("subprocess.run") as run, mock.patch("subprocess.Popen") as popen, mock.patch("os.system") as system:
                    status, result = call("GET", url + "/record")
                    self.assertEqual((status, result["record"]["application_id"]), (200, APPLICATION_ID))
                    status, result = call("POST", url + "/record", {"page": {"page_key": "k", "portal_state": "awaiting_review", "fields": [entry("A")]}})
                    self.assertEqual((status, result["record"]["portal_state"]), (200, "awaiting_review"))
                    self.assertEqual(call("POST", url + "/record", {"event": {"kind": "note", "detail": "d"}})[0], 200)
                    self.assertEqual(call("POST", url + "/record", {})[0], 400)
                    self.assertEqual(call("POST", url + "/reported-submitted", {"employer_reference_id": str(APPLICATION_ID)})[0], 400)
                    status, result = call("POST", url + "/reported-submitted", {"employer_reference_id": "REQ-9"})
                    self.assertEqual(status, 200, result)
                    self.assertTrue(result["command"].startswith("py -3 D:\\Code\\Resume\\_Reference\\mark_application_status.py "))
                    self.assertTrue(result["command"].endswith(' --id 7 --employer-ref "REQ-9"'))
                    self.assertEqual(result["record"]["portal_state"], "candidate_reported_submitted")
                    for mocked in (run, popen, system):
                        mocked.assert_not_called()
                self.assertEqual([p.name for p in data.rglob("*") if p.is_file()], [f"{APPLICATION_ID}.json"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_sandbox_session_without_application_id_has_no_record(self):
        pipeline = SimpleNamespace(data=Path("."), read=lambda sid: {"id": sid}, atomic=SimpleNamespace(write=None))
        with self.assertRaises(ValueError):
            Pipeline.record_for(pipeline, SESSION_ID)


class SourceRuleTests(unittest.TestCase):
    def test_mark_script_named_only_in_command_builder(self):
        users = [p.name for p in HERE.rglob("*.py") if "mark_application_status" in p.read_text(encoding="utf-8") and "tests" not in p.parts]
        self.assertEqual(users, ["portal_record.py"])


if __name__ == "__main__":
    unittest.main()
