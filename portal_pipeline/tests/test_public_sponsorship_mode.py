"""Per-application sponsorship answer toggle, synthetic data only."""
import http.client
import json
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

# Test configuration
HERE = Path(__file__).resolve().parents[1]
PROFILE_FIXTURE = Path(__file__).resolve().parent / "fixtures/synthetic_profile"
SESSION_FILENAME = "session.json"
APPLICATION_ID = 123
SESSION_ID = "a" * 32
OTHER_SESSION_ID = "b" * 32
PAIRING_TOKEN = "synthetic-test-token"
MODE_PATH = "/api/sessions/{}/sponsorship-mode"
PROFILE_PATH = "/api/sessions/{}/profile"
TOGGLE_SOURCE = f"candidate toggle (career services practice), session {SESSION_ID}"

sys.path.insert(0, str(HERE))
from portal_profile import resolve_for_application, resolve_profile, save_override
from server import make_server


class SponsorshipModeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name) / "source"
        shutil.copytree(PROFILE_FIXTURE, root / "_Reference")
        self.root = root
        self.folders = {}
        for session_id in (SESSION_ID, OTHER_SESSION_ID):
            folder = Path(self.temp.name) / session_id
            folder.mkdir()
            (folder / SESSION_FILENAME).write_text(json.dumps({"id": session_id, "application_id": APPLICATION_ID}), encoding="utf-8")
            self.folders[session_id] = folder
        pipeline = SimpleNamespace(source=root, lock=threading.RLock(), current=lambda: None, templates=lambda: [],
                                   folder=lambda session_id: self.folders[session_id])
        self.server = make_server(pipeline, 0, PAIRING_TOKEN)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, path, method="GET", body=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        connection.request(method, path, body=json.dumps(body) if body is not None else None, headers={"X-Portal-Token": PAIRING_TOKEN})
        response = connection.getresponse()
        result = response.status, json.loads(response.read())
        connection.close()
        return result

    def profile(self, session_id=SESSION_ID):
        return self.request(PROFILE_PATH.format(session_id))[1]

    def set_mode(self, mode, session_id=SESSION_ID):
        return self.request(MODE_PATH.format(session_id), "POST", {"mode": mode})

    def test_default_mode_is_truthful_and_proposes_boilerplate(self):
        self.assertEqual(self.request(MODE_PATH.format(SESSION_ID)), (200, {"mode": "truthful"}))
        values = self.profile()["values"]
        base = resolve_profile(self.root)["values"]
        for key in ("sponsorship_now", "sponsorship_future", "sponsorship_now_or_future"):
            self.assertEqual(values[key], base[key])
            self.assertNotIn("truth", values[key])
        self.assertEqual(values["sponsorship_future"]["value"], "Yes")

    def test_screening_no_flips_only_future_and_combined(self):
        base = resolve_profile(self.root)["values"]
        self.assertEqual(self.set_mode("screening_no")[0], 200)
        self.assertEqual(self.request(MODE_PATH.format(SESSION_ID))[1], {"mode": "screening_no"})
        values = self.profile()["values"]
        for key in ("sponsorship_future", "sponsorship_now_or_future"):
            self.assertEqual(values[key]["value"], "No")
            self.assertEqual(values[key]["source"], TOGGLE_SOURCE)
            self.assertEqual(values[key]["basis"], "override")
            self.assertEqual(values[key]["status"], "prepared")
        changed = {key for key in base if values[key] != base[key]}
        self.assertEqual(changed, {"sponsorship_future", "sponsorship_now_or_future"})

    def test_truth_field_equals_boilerplate_value_and_source(self):
        base = resolve_profile(self.root)["values"]
        self.set_mode("screening_no")
        values = self.profile()["values"]
        for key in ("sponsorship_future", "sponsorship_now_or_future"):
            self.assertEqual(values[key]["truth"], {"value": base[key]["value"], "source": base[key]["source"]})
        self.assertIn("Application_Boilerplate.md", values["sponsorship_future"]["truth"]["source"])

    def test_sponsorship_now_unchanged_in_both_modes(self):
        before = self.profile()["values"]["sponsorship_now"]
        self.set_mode("screening_no")
        after = self.profile()["values"]["sponsorship_now"]
        self.assertEqual(before, after)
        self.assertEqual(after["value"], "No")

    def test_mode_is_per_session_and_resets_for_new_session(self):
        self.set_mode("screening_no")
        self.assertEqual(self.request(MODE_PATH.format(OTHER_SESSION_ID))[1], {"mode": "truthful"})
        self.assertEqual(self.profile(OTHER_SESSION_ID)["values"]["sponsorship_future"]["value"], "Yes")
        self.set_mode("truthful")
        self.assertEqual(self.profile()["values"]["sponsorship_future"]["value"], "Yes")

    def test_toggle_never_touches_global_profile_or_source_files(self):
        before = resolve_profile(self.root)
        files = {path: path.read_bytes() for path in (self.root / "_Reference").iterdir() if path.is_file()}
        self.set_mode("screening_no")
        self.assertEqual(resolve_profile(self.root), before)
        self.assertEqual(self.request("/api/profile")[1]["values"]["sponsorship_future"]["value"], "Yes")
        self.assertEqual(files, {path: path.read_bytes() for path in files})

    def test_override_route_still_refuses_eligibility_keys(self):
        self.set_mode("screening_no")
        for key in ("sponsorship_future", "sponsorship_now_or_future", "sponsorship_now"):
            status, body = self.request(f"/api/sessions/{SESSION_ID}/override", "POST", {"key": key, "value": "No", "reason": "x"})
            self.assertEqual(status, 400)
            self.assertIn("eligibility", body["error"].lower())
            with self.assertRaises(ValueError):
                save_override(self.folders[SESSION_ID], key, "No", "x")

    def test_toggle_never_marks_a_field_selected(self):
        self.set_mode("screening_no")
        result = resolve_for_application(self.root, self.folders[SESSION_ID])
        for entry in result["values"].values():
            for forbidden in ("selected", "checked", "auto_selected"):
                self.assertNotIn(forbidden, entry)
        self.assertEqual(result["values"]["sponsorship_future"]["status"], "prepared")

    def test_route_validates_mode_values(self):
        for bad in ("yes", "", None, 1, ["screening_no"], "Screening_No"):
            status, body = self.set_mode(bad)
            self.assertEqual(status, 400, bad)
            self.assertIn("mode", body["error"].lower())
        self.assertEqual(self.request(MODE_PATH.format(SESSION_ID))[1], {"mode": "truthful"})


if __name__ == "__main__":
    unittest.main()
