"""Synthetic application mode storage and HTTP boundary regressions."""
import concurrent.futures
import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import application_mode
import portal_record
from server import make_server

TOKEN = "fabricated-mode-token"
FIRST = "a" * 32
SECOND = "b" * 32
THIRD = "c" * 32
SYNTHETIC_SESSIONS = {
    FIRST: {"id": FIRST, "mode": "audited_import", "application_id": 11},
    SECOND: {"id": SECOND, "mode": "audited_import", "application_id": 11},
    THIRD: {"id": THIRD, "mode": "audited_import", "application_id": 12},
}


def write_json(path, value):
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as output:
        json.dump(value, output)
        temporary = output.name
    os.replace(temporary, path)


class ApplicationModeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name) / "data"
        self.data.mkdir()

    def test_two_sessions_restart_and_other_application(self):
        self.assertEqual(application_mode.effective(self.data, SYNTHETIC_SESSIONS[FIRST])["mode"], "fill")
        saved = application_mode.restrict(self.data, SYNTHETIC_SESSIONS[FIRST],
                                          {"mode": "answer_sheet_only", "reason": "captcha"}, write_json)
        self.assertEqual(saved, {"schema_version": 1, "application_id": 11, "mode": "answer_sheet_only", "reason": "captcha"})
        self.assertEqual(application_mode.effective(self.data, SYNTHETIC_SESSIONS[SECOND]), saved)
        self.assertEqual(application_mode.effective(self.data, SYNTHETIC_SESSIONS[THIRD])["mode"], "fill")
        self.assertEqual(application_mode.effective(Path(self.temp.name) / "data", SYNTHETIC_SESSIONS[FIRST]), saved)

    def test_identity_and_write_contract(self):
        for identity in (None, False, True, 0, -1, "11"):
            with self.subTest(identity=identity):
                session = {"mode": "audited_import", "application_id": identity}
                self.assertEqual(application_mode.effective(self.data, session),
                                 {"schema_version": 1, "application_id": None, "mode": "answer_sheet_only",
                                  "reason": "unaudited_application"})
                with self.assertRaises(ValueError):
                    application_mode.restrict(self.data, session, {"mode": "answer_sheet_only", "reason": "captcha"}, write_json)
        session = {"mode": "draft", "application_id": 11}
        self.assertEqual(application_mode.effective(self.data, session)["mode"], "answer_sheet_only")
        with self.assertRaises(ValueError):
            application_mode.restrict(self.data, session, {"mode": "answer_sheet_only", "reason": "captcha"}, write_json)
        for body in ({"mode": "fill", "reason": "captcha"}, {"mode": "answer_sheet_only", "reason": "manual"},
                     {"mode": "answer_sheet_only", "reason": "captcha", "reset": True}, {}):
            with self.subTest(body=body), self.assertRaises(ValueError):
                application_mode.restrict(self.data, SYNTHETIC_SESSIONS[FIRST], body, write_json)

    def test_malformed_state_fails_closed_and_cannot_be_overwritten(self):
        folder = self.data / "application_modes"
        folder.mkdir()
        path = folder / "11.json"
        for value in ('{', json.dumps({"schema_version": 1, "application_id": 11, "mode": "fill", "reason": "unrestricted"}),
                      json.dumps({"schema_version": 1, "application_id": True, "mode": "answer_sheet_only", "reason": "captcha"}),
                      json.dumps({"schema_version": True, "application_id": 11, "mode": "answer_sheet_only", "reason": "captcha"}),
                      json.dumps({"schema_version": 1.0, "application_id": 11, "mode": "answer_sheet_only", "reason": "captcha"})):
            with self.subTest(value=value):
                path.write_text(value, encoding="utf-8")
                self.assertEqual(application_mode.effective(self.data, SYNTHETIC_SESSIONS[FIRST])["mode"], "answer_sheet_only")
                with self.assertRaises(ValueError):
                    application_mode.restrict(self.data, SYNTHETIC_SESSIONS[FIRST],
                                              {"mode": "answer_sheet_only", "reason": "captcha"}, write_json)
                self.assertEqual(path.read_text(encoding="utf-8"), value)

    def test_write_failure_blocks_and_does_not_report_success(self):
        def fail(_path, _value):
            raise OSError("fabricated storage failure")
        with self.assertRaises(OSError):
            application_mode.restrict(self.data, SYNTHETIC_SESSIONS[FIRST],
                                      {"mode": "answer_sheet_only", "reason": "captcha"}, fail)
        self.assertFalse((self.data / "application_modes" / "11.json").exists())

    def test_concurrent_downgrades_and_record_updates_keep_restriction(self):
        body = {"mode": "answer_sheet_only", "reason": "captcha"}
        def action(index):
            if index == 1:
                portal_record.record_page(self.data, 11, {"page_key": str(index), "fields": []}, write_json)
            return application_mode.restrict(self.data, SYNTHETIC_SESSIONS[FIRST], body, write_json)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(action, range(20)))
        self.assertTrue(all(result == results[0] for result in results))
        portal_record.append_event(self.data, 11, "fabricated", "record update", write_json)
        self.assertEqual(application_mode.effective(self.data, SYNTHETIC_SESSIONS[SECOND]), results[0])
        self.assertTrue((self.data / "records" / "11.json").is_file())

    def test_redirected_sidecar_path_is_rejected_without_external_write(self):
        outside = Path(self.temp.name) / "outside.json"
        outside.write_text("SENTINEL", encoding="utf-8")
        folder = self.data / "application_modes"
        folder.mkdir()
        sidecar = folder / "11.json"
        original_resolve = Path.resolve

        def redirected_resolve(path, *args, **kwargs):
            if path == sidecar:
                return outside
            return original_resolve(path, *args, **kwargs)

        writer = mock.Mock()
        with mock.patch.object(Path, "resolve", autospec=True, side_effect=redirected_resolve):
            mode = application_mode.effective(self.data, SYNTHETIC_SESSIONS[FIRST])
            self.assertEqual((mode["mode"], mode["reason"]), ("answer_sheet_only", "storage_error"))
            with self.assertRaises(ValueError):
                application_mode.restrict(self.data, SYNTHETIC_SESSIONS[FIRST],
                                          {"mode": "answer_sheet_only", "reason": "captcha"}, writer)
            writer.assert_not_called()
        self.assertEqual(outside.read_text(encoding="utf-8"), "SENTINEL")


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name) / "data"
        self.data.mkdir()
        self.sessions = dict(SYNTHETIC_SESSIONS)
        self.pipeline = SimpleNamespace(data=self.data, lock=threading.RLock(),
                                        read=lambda sid: self.sessions[sid],
                                        atomic=SimpleNamespace(write=write_json))
        self.start_server()

    def start_server(self):
        self.server = make_server(self.pipeline, 0, TOKEN)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join()
            self.server = None

    def call(self, method, session=FIRST, body=None, token=TOKEN, suffix="fill-mode"):
        client = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        client.request(method, f"/api/sessions/{session}/{suffix}",
                       body=json.dumps(body) if body is not None else None, headers={"X-Portal-Token": token})
        response = client.getresponse()
        result = response.status, json.loads(response.read())
        client.close()
        return result

    def test_authenticated_route_restart_and_no_reset(self):
        self.assertEqual(self.call("GET", token="wrong")[0], 401)
        self.assertEqual(self.call("GET"), (200, {"schema_version": 1, "application_id": 11,
                                                 "mode": "fill", "reason": "unrestricted"}))
        self.assertEqual(self.call("POST", body={"mode": "answer_sheet_only", "reason": "captcha"})[0], 200)
        self.assertEqual(self.call("GET", session=SECOND)[1]["mode"], "answer_sheet_only")
        self.stop_server()
        self.start_server()
        self.assertEqual(self.call("GET", session=SECOND)[1]["reason"], "captcha")
        self.assertEqual(self.call("GET", session=THIRD)[1]["mode"], "fill")
        self.assertEqual(self.call("POST", body={"mode": "fill", "reason": "reset"})[0], 400)
        self.assertEqual(self.call("GET")[1]["mode"], "answer_sheet_only")

    def test_unaudited_bad_body_and_storage_failure(self):
        self.sessions[FIRST] = {"id": FIRST, "mode": "draft", "application_id": 11}
        self.assertEqual(self.call("GET")[1]["reason"], "unaudited_application")
        self.assertEqual(self.call("POST", body={"mode": "answer_sheet_only", "reason": "captcha"})[0], 400)
        self.sessions[FIRST] = SYNTHETIC_SESSIONS[FIRST]
        self.assertEqual(self.call("POST", body={"mode": "answer_sheet_only", "reason": "captcha", "x": 1})[0], 400)
        self.pipeline.atomic.write = lambda path, value: (_ for _ in ()).throw(OSError("failure"))
        self.assertEqual(self.call("POST", body={"mode": "answer_sheet_only", "reason": "captcha"})[0], 500)


if __name__ == "__main__":
    unittest.main()
