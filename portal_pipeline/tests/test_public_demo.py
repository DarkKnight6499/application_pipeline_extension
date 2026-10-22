"""Validate the standalone synthetic demo and its local-only attachment boundary."""
import base64
import io
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from docx import Document

from browser_test_support import HERE, SyntheticBrowserTest

# Demo test configuration
REMOTE_URL = "https://example.invalid/application"

sys.path.insert(0, str(HERE))
from demo import DEMO_NOTICE, create_demo_server


class DemoTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.server, self.pipeline = create_demo_server(Path(self.temporary.name), 0)
        self.addCleanup(self.server.server_close)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.thread.join, 5)
        self.addCleanup(self.server.shutdown)
        self.origin = f"http://127.0.0.1:{self.server.server_port}"

    def request(self, path, body=None, *, authenticated=True):
        headers = {"X-Portal-Token": self.server.token} if authenticated else {}
        data = json.dumps(body).encode() if body is not None else None
        with urlopen(Request(self.origin + path, data=data, headers=headers), timeout=5) as response:
            return json.load(response)

    def test_profile_has_dummy_history_and_unknowns_stay_pending(self):
        profile = self.request(f"/api/sessions/{self.pipeline.session_id}/profile")
        self.assertEqual(profile["values"]["email"]["value"], "candidate@example.invalid")
        self.assertEqual(len(profile["employment"]), 2)
        self.assertEqual(len(profile["education"]), 2)
        self.assertNotIn("salary", profile["values"])
        self.assertNotIn("street_address", profile["values"])
        self.assertEqual(profile["values"]["sponsorship_now"]["value"], "No")
        self.assertEqual(profile["values"]["sponsorship_future"]["value"], "Yes")

    def test_attachment_is_labeled_docx_and_refuses_changed_origin(self):
        path = f"/api/sessions/{self.pipeline.session_id}/attachment"
        attachment = self.request(path)
        document = Document(io.BytesIO(base64.b64decode(attachment["base64"])))
        self.assertEqual(document.core_properties.author, "Yazad Madan")
        self.assertIn(DEMO_NOTICE, "\n".join(paragraph.text for paragraph in document.paragraphs))
        self.pipeline.session["url"] = REMOTE_URL
        with self.assertRaises(HTTPError) as error:
            self.request(path)
        self.assertEqual(error.exception.code, 400)
        self.assertIn("local fixture", error.exception.read().decode())

    def test_real_import_and_unauthenticated_access_are_refused(self):
        with self.assertRaises(HTTPError) as error:
            self.request("/api/current", authenticated=False)
        self.assertEqual(error.exception.code, 401)
        with self.assertRaises(HTTPError) as error:
            self.request("/api/import", {"folder": "not-a-real-application"})
        self.assertEqual(error.exception.code, 400)
        self.assertIn("cannot import", error.exception.read().decode())


class DemoBrowserTests(SyntheticBrowserTest):
    def test_demo_fills_selected_field_and_attaches_dummy_without_private_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            server, pipeline = create_demo_server(Path(temporary), 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                self.context.route(pipeline.fixture_url.removesuffix("fixture") + "**", lambda route: route.continue_())
                self.page.goto(pipeline.fixture_url)
                self.page.locator("#scan").click()
                panel = self.page.locator("#portal-panel-host")
                panel.get_by_role("checkbox", name="Select Last name", exact=True).check()
                panel.get_by_role("checkbox", name="This page belongs to the selected posting", exact=True).check()
                panel.get_by_role("button", name="Fill selected fields", exact=True).click()
                self.page.wait_for_function("document.querySelector('#last').value === 'Candidate'")
                panel.get_by_text("1 filled, 0 preserved, 0 need attention.", exact=False).wait_for()
                self.assertEqual(self.page.locator("#first").input_value(), "")
                self.page.locator("#next-one").click()
                self.page.locator("#scan").click()
                panel.get_by_role("checkbox", name="Select Resume", exact=True).check()
                panel.get_by_role("checkbox", name="This page belongs to the selected posting", exact=True).check()
                panel.get_by_role("button", name="Fill selected fields", exact=True).click()
                self.page.wait_for_function("document.querySelector('#resume').files.length === 1")
                self.assertEqual(self.page.locator("#cover").evaluate("node => node.files.length"), 0)
                self.assertEqual(self.page.locator("#submit-count").text_content(), "Submit clicks: 0")
            finally:
                server.shutdown()
                thread.join(5)
                server.server_close()
