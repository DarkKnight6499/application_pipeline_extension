"""HTTP boundary tests use a fabricated profile and a minimal read-only stub."""
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
PAIRING_TOKEN = "synthetic-test-token"
FOREIGN_ORIGIN = "https://example.invalid"

sys.path.insert(0, str(HERE))
from server import MAX_BODY, make_server


class PublicBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name)
        shutil.copytree(PROFILE_FIXTURE, root / "_Reference")
        pipeline = SimpleNamespace(source=root, lock=threading.RLock(), current=lambda: None, templates=lambda: [])
        cls.server = make_server(pipeline, 0, PAIRING_TOKEN)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def request(self, path, headers=None, method="GET", body=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        supplied = {"X-Portal-Token": PAIRING_TOKEN}
        supplied.update(headers or {})
        connection.request(method, path, body=body, headers=supplied)
        response = connection.getresponse()
        result = response.status, response.read()
        connection.close()
        return result

    def test_foreign_host_and_origin_are_rejected(self):
        self.assertEqual(self.request("/api/current", {"Host": "example.invalid"})[0], 403)
        self.assertEqual(self.request("/api/current", {"Origin": FOREIGN_ORIGIN})[0], 403)
        self.assertEqual(self.request("/api/current", {"Origin": "null"})[0], 403)

    def test_wrong_token_rejected_and_valid_profile_is_synthetic(self):
        self.assertEqual(self.request("/api/profile", {"X-Portal-Token": "wrong"})[0], 401)
        status, body = self.request("/api/profile")
        self.assertEqual(status, 200)
        values = json.loads(body)["values"]
        self.assertEqual(values["email"]["value"], "candidate@example.invalid")
        self.assertNotIn("relocation", values)

    def test_static_traversal_is_not_served(self):
        for path in ["/../server.py", "/%2e%2e/server.py", "/api/sessions/../attachment"]:
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0], 404)

    def test_oversized_and_nonobject_bodies_are_rejected(self):
        self.assertEqual(self.request("/api/sessions", {"Content-Length": str(MAX_BODY + 1)}, method="POST", body="")[0], 413)
        self.assertEqual(self.request("/api/sessions", method="POST", body="[]")[0], 400)


if __name__ == "__main__":
    unittest.main()
